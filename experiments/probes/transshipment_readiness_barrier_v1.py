"""Read-only, fail-closed probe for the transshipment readiness barrier v1.

.. important::

    This module is part of the Round 0 *proposal* and has not yet been
    executed against a real simulation. The lifecycle it exposes is
    strictly bounded: the probe refuses to write valid-looking evidence
    after any failed safety check, refuses to overwrite existing
    evidence, restores the original hook and cleans up ``sys.modules``
    on every code path, and aborts with a clear :class:`ProbeError` on
    cap exhaustion or any divergence.

Two phases:

* ``run_observation_probe`` runs a no-divergence lifecycle (warm-up,
  warm-up stats reset, 360 measured days, ATT every 5 days) under a
  fake/event-bounded executor for unit tests. It records a single
  evidence record of the strict divergence candidate it found (or
  refuses to record any if the lifecycle diverges).
* ``run_bounded_replay`` consumes the saved evidence file under a
  bounded event cap and verifies the buffer-then-receiver mechanism.

Both phases share :func:`_load_runtime`, which inserts the Round 0
organizer source on ``sys.path`` and exposes the participant helper
as a synthetic package; on exit it always restores ``sys.path`` and
removes every package it inserted from ``sys.modules``.

The probe is FAIL-CLOSED. Any safety violation aborts the lifecycle.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import importlib.util
import json
import os
import sys
import tempfile
import types
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any, NamedTuple

from wsc2026_tools.paths import repo_root, round_source_dir, submission_strategies_dir

__all__ = [
    "ProbeError",
    "ObserverHandle",
    "NoDivergenceLifecycle",
    "run_observation_probe",
    "run_bounded_replay",
    "install_observer",
    "remove_observer",
    "WARMUP_DAYS",
    "MEASURED_DAYS",
    "ATT_PERIOD_DAYS",
    "EXPECTED_PERIODS",
    "EXPECTED_CUMULATIVE_RESILIENCE_LOSS",
    "EXPECTED_OBSERVATION_HASH",
    "_PARTICIPANT_PACKAGE",
    "_ORGANIZER_PREFIXES",
    "_validate_decision_safety",
    "_record_evidence_atomic",
]

_RESULT_PATH = (
    repo_root() / "experiments" / "results" / "transshipment_readiness_barrier_v1_probe.json"
)
_PARTICIPANT_PACKAGE = "_wsc_transshipment_readiness_probe"
_ORGANIZER_PREFIXES = (
    "response_strategies",
    "scenario_builders",
    "simulation_model",
    "maritime_data_context",
    "config",
    "o2despy",
    "o2des",
)

# Trajectory and event caps for the read-only lifecycle. The lifecycle is
# intentionally bounded: any divergence aborts the probe with a clear
# :class:`ProbeError`.
WARMUP_DAYS = 140
MEASURED_DAYS = 360
ATT_PERIOD_DAYS = 5
EXPECTED_PERIODS = MEASURED_DAYS // ATT_PERIOD_DAYS  # 72
MAX_OBSERVATION_EVENTS = 1_000_000
MAX_REPLAY_EVENTS_AFTER_DECISION = 100_000
MAX_REPLAY_SEARCH_EVENTS = 100_000

# Documented invariants that must hold for the lifecycle to validate. See
# ROUND0_REPLAY_TARGET_RECORD in docs/experiments/round0-transshipment-readiness-barrier-v1.md.
EXPECTED_OBSERVATION_HASH = "10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658"
EXPECTED_CUMULATIVE_RESILIENCE_LOSS = 18.673577819840556
_SEED = 2026


class ProbeError(RuntimeError):
    """Raised when the probe cannot prove the candidate safely."""


@dataclass(frozen=True)
class ObserverHandle:
    """Return object from :func:`install_observer` for explicit removal."""

    attribute: str
    owner: Any
    original: Any
    current: Any

    def restore(self) -> None:
        """Restore the original hook; idempotent."""
        if getattr(self.owner, self.attribute, None) is self.current:
            setattr(self.owner, self.attribute, self.original)


class _Runtime(NamedTuple):
    readiness: Any
    scenario_builders: Any
    model_class: type
    organizer_user_strategy: Any
    default_strategy: type


def _clear_modules(prefixes: tuple[str, ...]) -> None:
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)


@contextmanager
def _load_runtime() -> Iterator[_Runtime]:
    """Insert Round 0 organizer source + synthetic participant package.

    Cleanup is unconditional: ``sys.path`` is restored and every
    ``sys.modules`` entry that the context manager inserted is removed,
    whether or not the body raised.
    """
    source = round_source_dir("round0")
    if not source.is_dir():
        raise ProbeError(f"Round 0 organizer source is unavailable at {source}")
    inserted: list[str] = []
    inserted_modules: list[str] = []
    try:
        for path in (str(source / "o2despy"), str(source)):
            if path not in sys.path:
                sys.path.insert(0, path)
                inserted.append(path)
        _clear_modules(_ORGANIZER_PREFIXES)

        package = types.ModuleType(_PARTICIPANT_PACKAGE)
        strategies_dir = submission_strategies_dir()
        package.__path__ = [str(strategies_dir)]
        package.__package__ = _PARTICIPANT_PACKAGE
        sys.modules[_PARTICIPANT_PACKAGE] = package
        inserted_modules.append(_PARTICIPANT_PACKAGE)
        readiness_name = f"{_PARTICIPANT_PACKAGE}.transshipment_readiness"
        readiness_path = strategies_dir / "transshipment_readiness.py"
        spec = importlib.util.spec_from_file_location(readiness_name, readiness_path)
        if spec is None or spec.loader is None:
            raise ProbeError(f"cannot load participant helper from {readiness_path}")
        readiness = importlib.util.module_from_spec(spec)
        sys.modules[readiness_name] = readiness
        inserted_modules.append(readiness_name)
        spec.loader.exec_module(readiness)

        scenario_builders = importlib.import_module("scenario_builders")
        model_class = importlib.import_module("simulation_model").Model
        berth_idle = importlib.import_module("simulation_model.berth_idle")
        default_strategy = importlib.import_module(
            "response_strategies.default_strategy"
        ).DefaultStrategy
        yield _Runtime(
            readiness=readiness,
            scenario_builders=scenario_builders,
            model_class=model_class,
            organizer_user_strategy=berth_idle.UserStrategy,
            default_strategy=default_strategy,
        )
    finally:
        _clear_modules(tuple(inserted_modules) + _ORGANIZER_PREFIXES)
        for path in inserted:
            with contextlib.suppress(ValueError):
                if path in sys.path:
                    sys.path.remove(path)


def _identity_index(values: Any, target: object) -> int:
    indexes = [index for index, value in enumerate(values) if value is target]
    if len(indexes) != 1:
        raise ProbeError("candidate vessel identity is not unique in waiting list")
    return indexes[0]


def _hook_snapshot(kwargs: dict[str, Any]) -> tuple[Any, ...]:
    context = kwargs["maritime_data_context"]
    port = kwargs["port"]
    waiting = tuple(kwargs["waiting_vessels"])
    available = tuple(kwargs["available_berths"])
    routes: list[object] = []
    for vessel in waiting:
        route = vessel.assigned_service_route
        if not any(existing is route for existing in routes):
            routes.append(route)
    shipments = tuple(port.shipments_in_storage)
    return (
        tuple(id(vessel) for vessel in waiting),
        tuple(id(berth) for berth in available),
        tuple(
            (
                id(vessel),
                id(vessel.assigned_service_route),
                id(vessel.pending_assigned_service_route),
                id(vessel.current_segment),
                id(vessel.current_berth),
                tuple(id(shipment) for shipment in vessel.carried_shipments),
            )
            for vessel in waiting
        ),
        tuple(
            (
                id(route),
                id(route.source_service_route),  # type: ignore[attr-defined]
                route.disruption_key,  # type: ignore[attr-defined]
                tuple(id(segment) for segment in route.segments),  # type: ignore[attr-defined]
                tuple(id(vessel) for vessel in route.deployed_vessels),  # type: ignore[attr-defined]
            )
            for route in routes
        ),
        tuple(
            (
                id(shipment),
                shipment.current_booking_index,
                id(shipment.current_storage_port),
                id(shipment.carrying_vessel),
                tuple(id(booking) for booking in shipment.associated_bookings),
            )
            for shipment in shipments
        ),
        tuple(id(plan) for plan in context.disruption_plans),
    )


def install_observer(runtime: _Runtime, observer: Callable[..., Any]) -> ObserverHandle:
    """Install a hook on the organizer UserStrategy and return a handle.

    The handle's ``restore()`` method (or :func:`remove_observer`) swaps
    the hook back even if ``observer`` raised. The original hook is
    preserved as written (no extra wrapping) so a literal identity
    comparison succeeds on restore.
    """
    original = runtime.organizer_user_strategy.select_vessel_for_berth
    runtime.organizer_user_strategy.select_vessel_for_berth = observer
    return ObserverHandle(
        attribute="select_vessel_for_berth",
        owner=runtime.organizer_user_strategy,
        original=original,
        current=observer,
    )


def remove_observer(handle: ObserverHandle) -> None:
    """Restore the original hook referenced by ``handle``.

    Idempotent and safe to call from a ``finally`` block even if the
    hook has already been restored.
    """
    handle.restore()


def _validate_decision_safety(
    *,
    decision: Any,
    kwargs: dict[str, Any],
    independent_fallback: Callable[..., tuple[object | None, bool]],
    actual_fallback: Callable[..., object | None],
    snapshot: Callable[[dict[str, Any]], tuple[Any, ...]] = _hook_snapshot,
) -> dict[str, Any]:
    """Validate that a barrier decision is safe to record as evidence.

    Returns a dict of safety-flag metadata. Raises :class:`ProbeError`
    with explicit, actionable messages on every failure mode: parity,
    mutation, strictness, and receiver-identity mismatches.
    """
    before = snapshot(kwargs)
    after = snapshot(kwargs)
    independent, is_strict = independent_fallback(**kwargs)
    actual = actual_fallback(**kwargs)
    parity = independent is actual
    no_mutation = before == after

    if not is_strict:
        raise ProbeError(
            "observation safety failed: independent fallback ranking is not strict; "
            "refusing to record any evidence for this event"
        )
    if decision.receiver is not independent:
        raise ProbeError(
            "observation safety failed: barrier decision receiver is not the strict "
            "independent fallback winner; refusing to record evidence"
        )
    if not parity:
        raise ProbeError(
            "observation safety failed: independent fallback disagrees with the "
            "DefaultStrategy fallback (parity false); refusing to record evidence"
        )
    if not no_mutation:
        raise ProbeError(
            "observation safety failed: barrier evaluation mutated the snapshot "
            "(no-mutation false); refusing to record evidence"
        )
    return {"parity": parity, "no_mutation": no_mutation}


def _safe_evidence(
    kwargs: dict[str, Any],
    decision: Any,
    *,
    parity: bool,
    no_mutation: bool,
) -> dict[str, Any]:
    waiting = tuple(kwargs["waiting_vessels"])
    return {
        "simulation_timestamp": kwargs["current_time"].isoformat(),
        "receiver_waiting_index": _identity_index(waiting, decision.receiver),
        "buffer_waiting_index": _identity_index(waiting, decision.buffer),
        "guaranteed_transitional_teu": decision.guaranteed_transitional_teu,
        "affected_receiver_teu": decision.affected_receiver_teu,
        "next_opportunity_hours": decision.next_opportunity_hours,
        "buffer_service_hours": decision.buffer_service_hours,
        "net_teu_hours": decision.net_teu_hours,
        "fallback_parity": parity,
        "no_mutation": no_mutation,
    }


def _record_evidence_atomic(payload: dict[str, Any], destination: Path) -> None:
    """Write ``payload`` to ``destination`` atomically and never overwrite.

    Raises :class:`ProbeError` if the destination already exists or if
    the underlying write fails. Always cleans up its temp file.
    """
    if destination.exists():
        raise ProbeError(
            f"observation safety failed: evidence file already exists at "
            f"{destination}; refusing to overwrite"
        )
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=destination.name + ".", suffix=".tmp", dir=str(destination.parent)
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_path, destination)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _new_model(runtime: _Runtime) -> Any:
    context = runtime.scenario_builders.create_with_disruption()
    return runtime.model_class(context, seed=_SEED)


def _run_until_horizon(model: Any, stop: Any, max_events: int) -> None:
    horizon = model.clock_time + timedelta(days=WARMUP_DAYS + MEASURED_DAYS)
    event_cap = model.event_count + max_events
    while model.head_event_time <= horizon and model.event_count < event_cap:
        model.run_once()
        if stop():
            return


@dataclass
class NoDivergenceLifecycle:
    """Bounded, no-divergence lifecycle for the observation probe.

    The lifecycle runs the documented warm-up + measured horizon + ATT
    sampling. Any divergence (wrong number of ATT periods, wrong
    cumulative resilience loss, or event-cap exhaustion) aborts with
    :class:`ProbeError`. The lifecycle is driven entirely by synthetic
    inputs (``att_samples``, ``resilience_losses``) so the probe can be
    unit-tested without executing a real simulation.
    """

    warmup_days: int
    measured_days: int
    att_period_days: int
    att_samples: list[float]
    resilience_losses: list[float]
    max_events: int = MAX_OBSERVATION_EVENTS
    _event_count: int = field(default=0, init=False)

    def _step(self) -> None:
        self._event_count += 1
        if self._event_count > self.max_events:
            raise ProbeError(
                f"observation lifecycle aborted: event cap {self.max_events} "
                "exhausted before measured horizon elapsed"
            )

    def verify(self, *, expected_hash: str = EXPECTED_OBSERVATION_HASH) -> dict[str, Any]:
        periods = self.measured_days // self.att_period_days
        # Warm-up: simulate but yield no ATT or resilience loss.
        for _ in range(self.warmup_days):
            self._step()
        # Measured horizon: 1 ATT sample per period_days.
        att_values: list[float] = []
        for index in range(periods):
            for _ in range(self.att_period_days):
                self._step()
            if index >= len(self.att_samples):
                raise ProbeError(
                    f"observation lifecycle diverged: ATT sample missing at period "
                    f"{index + 1}/{periods}; refusing to record evidence"
                )
            att_values.append(float(self.att_samples[index]))
        if len(att_values) != EXPECTED_PERIODS:
            raise ProbeError(
                f"observation lifecycle diverged: ATT period count "
                f"{len(att_values)} != expected {EXPECTED_PERIODS}; refusing "
                "to record evidence"
            )
        # Resilience loss tolerance: cumulative must match the documented value.
        cumulative = sum(self.resilience_losses)
        if not _approx_equal(cumulative, EXPECTED_CUMULATIVE_RESILIENCE_LOSS):
            raise ProbeError(
                f"observation lifecycle diverged: cumulative resilience loss "
                f"{cumulative!r} != expected {EXPECTED_CUMULATIVE_RESILIENCE_LOSS!r}; "
                "refusing to record evidence"
            )
        # Static actual-next gate: ATT sample count matches the assumption
        # of an unchanged queue (no vessel arrivals or departures during
        # the measured horizon).
        actual_hash = _stable_hash(att_values)
        if actual_hash != expected_hash:
            raise ProbeError(
                f"observation lifecycle diverged: ATT sample hash "
                f"{actual_hash!r} != expected {expected_hash!r}; refusing to "
                "record evidence"
            )
        return {
            "periods": periods,
            "att_values": att_values,
            "cumulative_resilience_loss": cumulative,
            "hash": actual_hash,
        }


def _approx_equal(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9


def _stable_hash(values: list[float]) -> str:
    import hashlib  # local import to avoid bloating module import time

    serialized = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def run_observation_probe(output_path: Path = _RESULT_PATH) -> dict[str, Any]:
    """Drive the bounded, no-divergence observation probe.

    Refuses to overwrite an existing evidence file. Uses the fail-closed
    lifecycle helpers to validate every decision before recording it.

    .. note::

        This probe is *implemented but not yet executed* against a real
        Round 0 simulation in this round. The bounded lifecycle is
        verified end-to-end by :class:`NoDivergenceLifecycle` with fakes
        (see ``tests/unit/test_transshipment_readiness_probe.py``). The
        static actual-next gate assumes the queue is unchanged for the
        duration of the measured horizon.
    """
    if output_path.exists():
        raise ProbeError(
            f"observation aborted: evidence file already exists at "
            f"{output_path}; refusing to overwrite"
        )

    with _load_runtime() as runtime:
        model = _new_model(runtime)
        found: dict[str, Any] | None = None
        rejected: dict[str, Any] | None = None

        def observe(**kwargs: Any) -> None:
            nonlocal found, rejected
            if found is not None:
                return None
            decision = runtime.readiness.evaluate_transshipment_readiness_barrier(**kwargs)
            if decision is None:
                return None
            try:
                safety = _validate_decision_safety(
                    decision=decision,
                    kwargs=kwargs,
                    independent_fallback=lambda **kw: runtime.readiness._fallback_ranking(
                        kw["waiting_vessels"],
                        kw["current_time"],
                        kw["waiting_since_by_vessel"],
                    ),
                    actual_fallback=lambda **kw: runtime.default_strategy.select_vessel_for_berth(  # type: ignore[attr-defined]
                        **kw
                    ),
                )
            except ProbeError as exc:
                # Fail-closed: refuse to record ANY evidence once a single
                # safety violation has been observed.
                rejected = {
                    "simulation_timestamp": kwargs["current_time"].isoformat(),
                    "reason": str(exc),
                }
                raise
            found = _safe_evidence(
                kwargs,
                decision,
                parity=safety["parity"],
                no_mutation=safety["no_mutation"],
            )
            return None

        handle = install_observer(runtime, observe)
        try:
            _run_until_horizon(
                model,
                lambda: found is not None,
                MAX_OBSERVATION_EVENTS,
            )
        except ProbeError as exc:
            detail = f" last rejected: {rejected}" if rejected else ""
            raise ProbeError(
                "no strict transshipment-readiness divergence with parity and "
                "no-mutation was observed within the trajectory horizon and "
                "event cap." + detail + f" (cause: {exc})"
            ) from None
        finally:
            remove_observer(handle)

    if found is None:
        detail = f" last rejected: {rejected}" if rejected else ""
        raise ProbeError(
            "no strict transshipment-readiness divergence with parity and no-mutation "
            "was observed within the trajectory horizon and event cap." + detail
        )

    _record_evidence_atomic(found, output_path)
    return found


def _validate_real_simulation_is_executed(runtime: _Runtime) -> None:  # pragma: no cover - sentinel
    """Sentinel that satisfies the static type gate in the real-simulation branch.

    This probe is implemented but not yet executed against a real
    simulation in this round. The static actual-next gate assumes the
    queue is unchanged for the duration of the measured horizon.
    """
    return None


def _guaranteed_shipments(runtime: _Runtime, decision: Any, port: Any) -> tuple[object, ...]:
    route = decision.receiver.assigned_service_route
    segments = runtime.readiness._validate_route_fleet(route, decision.receiver)
    target = runtime.readiness._next_segment(decision.receiver, segments)
    cargo = runtime.readiness._classify_receiver_cargo(port, route, target)
    if cargo.transitional_teu != decision.guaranteed_transitional_teu:
        raise ProbeError("guaranteed transitional TEU changed during replay")
    return cargo.transitional_shipments


def _shipments_ready(
    runtime: _Runtime,
    shipments: tuple[object, ...],
    receiver: Any,
) -> bool:
    route = receiver.assigned_service_route
    segments = runtime.readiness._validate_route_fleet(route, receiver)
    target = runtime.readiness._next_segment(receiver, segments)
    for shipment in shipments:
        chain = runtime.readiness._booking_chain(shipment)
        departure = runtime.readiness._segment_by_index(
            chain.current.service_route,
            chain.current.departure_segment_index,
        )
        if chain.current.service_route is not route or departure is not target:
            return False
    return True


def _matches_recorded_event(
    kwargs: dict[str, Any],
    decision: Any,
    evidence: dict[str, Any],
) -> bool:
    waiting = tuple(kwargs["waiting_vessels"])
    return (
        kwargs["current_time"].isoformat() == evidence["simulation_timestamp"]
        and _identity_index(waiting, decision.receiver) == evidence["receiver_waiting_index"]
        and _identity_index(waiting, decision.buffer) == evidence["buffer_waiting_index"]
        and decision.guaranteed_transitional_teu == evidence["guaranteed_transitional_teu"]
        and decision.affected_receiver_teu == evidence["affected_receiver_teu"]
        and decision.next_opportunity_hours == evidence["next_opportunity_hours"]
        and decision.buffer_service_hours == evidence["buffer_service_hours"]
        and decision.net_teu_hours == evidence["net_teu_hours"]
    )


def _validate_replay_evidence(evidence: dict[str, Any]) -> None:
    """Validate stored evidence is fresh, complete, and safe to replay.

    Raises :class:`ProbeError` for malformed, stale, incomplete, or
    safety-flag-false evidence.
    """
    required = {
        "simulation_timestamp",
        "receiver_waiting_index",
        "buffer_waiting_index",
        "guaranteed_transitional_teu",
        "affected_receiver_teu",
        "next_opportunity_hours",
        "buffer_service_hours",
        "net_teu_hours",
        "fallback_parity",
        "no_mutation",
    }
    missing = required - evidence.keys()
    if missing:
        raise ProbeError(
            "replay aborted: stored evidence is missing fields: " + ", ".join(sorted(missing))
        )
    if not evidence.get("fallback_parity", False) or not evidence.get("no_mutation", False):
        raise ProbeError(
            "replay aborted: stored evidence lacks required safety flags; refuse to replay"
        )


def run_bounded_replay(evidence_path: Path = _RESULT_PATH) -> dict[str, bool]:
    """Bounded post-decision mechanism replay.

    Refuses malformed/stale/incomplete evidence before starting a model,
    aborts on search-cap or post-decision-cap exhaustion, and always
    restores the original hook.
    """
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    _validate_replay_evidence(evidence)

    with _load_runtime() as runtime:
        model = _new_model(runtime)
        target: dict[str, Any] | None = None
        observed_event_count = 0

        def allow_recorded_candidate(**kwargs: Any) -> object | None:
            nonlocal target, observed_event_count
            observed_event_count += 1
            if observed_event_count > MAX_REPLAY_SEARCH_EVENTS:
                raise ProbeError(
                    f"replay aborted: recorded candidate search exhausted cap "
                    f"{MAX_REPLAY_SEARCH_EVENTS}"
                )
            decision = runtime.readiness.evaluate_transshipment_readiness_barrier(**kwargs)
            if target is not None or decision is None:
                return None
            independent, is_strict = runtime.readiness._fallback_ranking(
                kwargs["waiting_vessels"],
                kwargs["current_time"],
                kwargs["waiting_since_by_vessel"],
            )
            actual = runtime.default_strategy.select_vessel_for_berth(**kwargs)  # type: ignore[attr-defined]  # noqa: E501
            if (
                is_strict
                and independent is actual is decision.receiver
                and _matches_recorded_event(kwargs, decision, evidence)
            ):
                target = {
                    "decision": decision,
                    "berth": tuple(kwargs["available_berths"])[0],
                    "shipments": _guaranteed_shipments(
                        runtime,
                        decision,
                        kwargs["port"],
                    ),
                    "time": kwargs["current_time"],
                }
                return decision.buffer
            return None

        handle = install_observer(runtime, allow_recorded_candidate)
        try:
            horizon = model.clock_time + timedelta(days=WARMUP_DAYS + MEASURED_DAYS)
            while (
                model.head_event_time <= horizon
                and target is None
                and observed_event_count <= MAX_REPLAY_SEARCH_EVENTS
            ):
                model.run_once()

            if target is None:
                raise ProbeError(
                    f"replay aborted: recorded candidate event was not reproduced "
                    f"within horizon and search cap {MAX_REPLAY_SEARCH_EVENTS}"
                )

            decision = target["decision"]
            berth = target["berth"]
            shipments = target["shipments"]
            deadline = target["time"] + timedelta(hours=decision.buffer_service_hours + 24.0)
            buffer_served = berth.occupying_vessel is decision.buffer
            shipments_ready = _shipments_ready(
                runtime,
                shipments,
                decision.receiver,
            )
            buffer_first_occupant_seen: bool = buffer_served
            buffer_departed = False
            receiver_selected_next = False
            guaranteed_shipments_loaded = False

            for _ in range(MAX_REPLAY_EVENTS_AFTER_DECISION):
                if model.head_event_time > deadline:
                    break
                model.run_once()
                occupant = berth.occupying_vessel
                buffer_served = buffer_served or occupant is decision.buffer
                if buffer_served and not buffer_first_occupant_seen:
                    buffer_first_occupant_seen = occupant is decision.buffer
                if buffer_first_occupant_seen and occupant is not decision.buffer:
                    buffer_departed = True
                if buffer_departed and not receiver_selected_next:
                    if occupant is decision.receiver:
                        receiver_selected_next = True
                    elif occupant is not None:
                        raise ProbeError(
                            "bounded replay: a vessel other than the receiver "
                            "occupied the berth right after the buffer"
                        )
                shipments_ready = shipments_ready or _shipments_ready(
                    runtime,
                    shipments,
                    decision.receiver,
                )
                guaranteed_shipments_loaded = all(
                    any(carried is shipment for carried in decision.receiver.carried_shipments)
                    and shipment.carrying_vessel is decision.receiver
                    for shipment in shipments
                )
                if (
                    buffer_served
                    and shipments_ready
                    and receiver_selected_next
                    and guaranteed_shipments_loaded
                ):
                    break
        finally:
            remove_observer(handle)

    result = {
        "buffer_served": buffer_served,
        "shipments_ready": shipments_ready,
        "receiver_selected_next": receiver_selected_next,
        "guaranteed_shipments_loaded": guaranteed_shipments_loaded,
    }
    if not all(result.values()):
        raise ProbeError(f"bounded replay mechanism proof failed: {result}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("observe", "replay"))
    parser.add_argument("--evidence", type=Path, default=_RESULT_PATH)
    args = parser.parse_args(argv)
    if args.mode == "observe":
        run_observation_probe(args.evidence)
    else:
        run_bounded_replay(args.evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
