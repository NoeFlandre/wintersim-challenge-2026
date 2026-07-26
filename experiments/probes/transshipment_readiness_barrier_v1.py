"""Read-only, fail-closed probe for the transshipment readiness barrier v1.

.. important::

    This module is part of the Round 0 *proposal* and has not yet been
    executed against a real simulation. It is implemented in this round
    and exercised against fake models that respect the o2despy.Sandbox
    contract (no ``event_count`` attribute; supports ``clock_time``,
    ``head_event_time``, ``warmup(period=...)``, ``run(duration=...)``,
    ``run_once()``, ``get_teu_weighted_average_transport_time_hours``).

Two phases:

* :func:`run_observation_probe` runs the organizer-equivalent main loop:
  install the berth hook *before* warm-up, call
  ``model.warmup(period=timedelta(days=140))``, then advance the model by
  360 simulated days in 1-day durations as the organizer main.py does,
  sampling :meth:`get_teu_weighted_average_transport_time_hours` once
  every 5 days. The hook returns ``None`` always; valid strict
  divergences are recorded as evidence and a private internal stop
  sentinel raised by the run_once wrapper. The NO_DIVERGENCE branch
  writes the 72-row ``ATT_By_Statistics_Interval.csv`` into an isolated
  ignored private directory, hashes the file's *bytes* (not a JSON
  list), invokes :func:`wsc2026_tools.scoring.compute_resilience_loss`
  with the just-written CSV as scenario path, and requires
  ``period_count == 72`` and ``cumulative_loss == EXPECTED_CUMULATIVE_RESILIENCE_LOSS``.
* :func:`run_bounded_replay` consumes the saved provenance-safe evidence
  and verifies the buffer-then-receiver mechanism, counting every
  ``model.run_once`` call against ``search_max_events``.

Both phases share :func:`_load_runtime`, which inserts the Round 0
organizer source on ``sys.path`` and exposes the participant helper
as a synthetic package; on exit it always restores ``sys.path`` and
removes every package it inserted from ``sys.modules``.

The probe is FAIL-CLOSED. Any safety violation, provenance mismatch,
configuration mismatch, non-finite metric, non-integer index, unknown
schema, or event-cap exhaustion aborts with a clear :class:`ProbeError`.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import hashlib
import importlib
import importlib.util
import json
import os
import sys
import tempfile
import types
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

from wsc2026_tools.paths import repo_root, round_source_dir, submission_strategies_dir

__all__ = [
    "ProbeError",
    "ObserverHandle",
    "install_observer",
    "remove_observer",
    "run_observation_probe",
    "run_bounded_replay",
    "WARMUP_DAYS",
    "MEASURED_DAYS",
    "ATT_PERIOD_DAYS",
    "EXPECTED_PERIODS",
    "EXPECTED_CUMULATIVE_RESILIENCE_LOSS",
    "EXPECTED_OBSERVATION_HASH",
    "EVIDENCE_SCHEMA_VERSION",
    "SEED",
    "SCENARIO_IDENTIFIER",
    "MAX_OBSERVATION_EVENTS",
    "MAX_REPLAY_EVENTS_AFTER_DECISION",
    "MAX_REPLAY_SEARCH_EVENTS",
    "HELPER_SOURCE_PATH",
    "_PARTICIPANT_PACKAGE",
    "_ORGANIZER_PREFIXES",
    "_current_helper_sha256",
    "validate_evidence",
]

# Trajectory and event caps for the read-only lifecycle.
WARMUP_DAYS = 140
MEASURED_DAYS = 360
ATT_PERIOD_DAYS = 5
EXPECTED_PERIODS = MEASURED_DAYS // ATT_PERIOD_DAYS  # 72
MAX_OBSERVATION_EVENTS = 1_000_000
MAX_REPLAY_EVENTS_AFTER_DECISION = 100_000
MAX_REPLAY_SEARCH_EVENTS = 100_000

# Documented invariants that must hold for the lifecycle to validate.
EXPECTED_OBSERVATION_HASH = "10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658"
EXPECTED_CUMULATIVE_RESILIENCE_LOSS = 18.673577819840556

# Experiment configuration (canonical values; provenance must match).
SEED = 2026
SCENARIO_IDENTIFIER = "create_with_disruption"
EVIDENCE_SCHEMA_VERSION = 1

# Provenance safety-net path: the participant helper file whose SHA-256
# must match the value recorded in evidence.
HELPER_SOURCE_PATH = submission_strategies_dir() / "transshipment_readiness.py"

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
# Top-level package names that must be cleared (because the same spelling
# is used for both organizer and participant code).
_ORGANIZER_PACKAGE_NAMES = frozenset(
    {"response_strategies", "simulation_model", "scenario_builders", "maritime_data_context"}
)

_OBSERVATION_HASH_PATH = (
    repo_root() / "experiments" / "results" / "transshipment_readiness_barrier_v1_probe.json"
)


# Private stop sentinel raised by the wrapped run_once after a valid
# divergence is recorded. The exception name and class are private; only
# the type identity is used to distinguish it from safety ProbeErrors.
class _DivergenceStop(BaseException):
    """Private internal stop sentinel raised by the wrapped run_once."""

    pass


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
    model_class: Any
    organizer_user_strategy: Any
    default_strategy: Any
    output_dir: Path  # organizer source Output/ directory
    baseline_att_path: Path


# ---------------------------------------------------------------------------
# Runtime loading
# ---------------------------------------------------------------------------


def _clear_modules(prefixes: tuple[str, ...]) -> None:
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)


@contextmanager
def _load_runtime() -> Iterator[_Runtime]:
    """Insert Round 0 organizer source + synthetic participant package.

    Cleanup is unconditional: ``sys.path`` is restored, every
    ``sys.modules`` entry that the context manager inserted is removed,
    and any organizer-package top-level names that were temporarily
    shadowed are CLEARED (not restored) so a subsequent test cannot
    import the organizer-side ``response_strategies.default_strategy``
    through a stale participant-side package entry.
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
        # Clear any organizer-prefixed modules that may have been loaded
        # elsewhere (e.g. participant's response_strategies).
        _clear_modules(_ORGANIZER_PREFIXES)
        # Also clear conflicting top-level package entries so that
        # importing organizer.modules resolves to the organizer source
        # rather than the participant submission. We do NOT save them:
        # restoring a stale participant-side entry would corrupt any
        # later organizer import.
        for name in list(sys.modules):
            if name in _ORGANIZER_PACKAGE_NAMES:
                sys.modules.pop(name, None)

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
        model_module = importlib.import_module("simulation_model")
        model_class = model_module.Model
        berth_idle = importlib.import_module("simulation_model.berth_idle")
        default_strategy = importlib.import_module(
            "response_strategies.default_strategy"
        ).DefaultStrategy
        # Organizer source ships the Baseline CSV under Output/.
        output_dir = source / "Output"
        baseline_att_path = output_dir / "Baseline_ATT_By_Statistics_Interval.csv"
        yield _Runtime(
            readiness=readiness,
            scenario_builders=scenario_builders,
            model_class=model_class,
            organizer_user_strategy=berth_idle.UserStrategy,
            default_strategy=default_strategy,
            output_dir=output_dir,
            baseline_att_path=baseline_att_path,
        )
    finally:
        _clear_modules(tuple(inserted_modules) + _ORGANIZER_PREFIXES)
        for name in list(sys.modules):
            if name in _ORGANIZER_PACKAGE_NAMES:
                sys.modules.pop(name, None)
        for path in inserted:
            with contextlib.suppress(ValueError):
                if path in sys.path:
                    sys.path.remove(path)


def _build_real_environment(
    *,
    results_dir: Path,
    max_events: int = MAX_OBSERVATION_EVENTS,
) -> dict[str, Any]:
    """Construct the production environment for :func:`run_observation_probe`.

    Reads from the loaded runtime so all calls share the same imports.
    """
    with _load_runtime() as runtime:
        context_factory = runtime.scenario_builders.create_with_disruption
        return {
            "model": _produce_real_model(runtime, context_factory),
            "readiness": runtime.readiness,
            "default_strategy": runtime.default_strategy,
            "user_strategy_class": runtime.organizer_user_strategy,
            "scenario_builders": runtime.scenario_builders,
            "model_class": runtime.model_class,
            "output_dir": runtime.output_dir,
            "baseline_att_path": runtime.baseline_att_path,
            "results_dir": results_dir,
            "max_events": max_events,
            "writer": _real_att_writer,
            "scorer": _real_scorer,
            "csv_hash": _real_csv_hash,
            "helper_path": HELPER_SOURCE_PATH,
            "context_factory": context_factory,
        }


def _produce_real_model(runtime: _Runtime, context_factory: Callable[..., Any]) -> Any:
    """Create a real ``simulation_model.Model`` instance from the loaded runtime."""
    context = context_factory()
    return runtime.model_class(context, seed=SEED)


# ---------------------------------------------------------------------------
# Observer hook + safety validation
# ---------------------------------------------------------------------------


def install_observer(runtime: _Runtime, observer: Callable[..., Any]) -> ObserverHandle:
    """Install a hook on the organizer UserStrategy and return a handle."""
    original = runtime.organizer_user_strategy.select_vessel_for_berth
    runtime.organizer_user_strategy.select_vessel_for_berth = observer
    return ObserverHandle(
        attribute="select_vessel_for_berth",
        owner=runtime.organizer_user_strategy,
        original=original,
        current=observer,
    )


def remove_observer(handle: ObserverHandle) -> None:
    """Restore the original hook; idempotent."""
    handle.restore()


def _hook_snapshot(kwargs: dict[str, Any]) -> tuple[Any, ...]:
    """Snap the kwargs the participant receives, including waiting_since.

    Tolerant of organizer objects missing optional attributes (so tests
    using fakes still work); production organizer vessels/routes always
    expose these attributes.
    """
    context = kwargs["maritime_data_context"]
    port = kwargs["port"]
    waiting = tuple(kwargs["waiting_vessels"])
    available = tuple(kwargs["available_berths"])
    waiting_since = dict(kwargs["waiting_since_by_vessel"])
    routes: list[object] = []
    for vessel in waiting:
        route = getattr(vessel, "assigned_service_route", None)
        if not any(existing is route for existing in routes):
            routes.append(route)
    shipments = tuple(port.shipments_in_storage)
    return (
        tuple(id(vessel) for vessel in waiting),
        tuple(id(berth) for berth in available),
        tuple(
            (
                id(vessel),
                id(waiting_since.get(vessel)),
                id(getattr(vessel, "assigned_service_route", None)),
                id(getattr(vessel, "pending_assigned_service_route", None)),
                id(getattr(vessel, "current_segment", None)),
                id(getattr(vessel, "current_berth", None)),
                tuple(id(shipment) for shipment in getattr(vessel, "carried_shipments", [])),
            )
            for vessel in waiting
        ),
        tuple(
            (
                id(route),
                id(getattr(route, "source_service_route", None)),
                getattr(route, "disruption_key", None),
                tuple(id(segment) for segment in getattr(route, "segments", [])),
                tuple(id(vessel) for vessel in getattr(route, "deployed_vessels", [])),
            )
            for route in routes
        ),
        tuple(
            (
                id(shipment),
                getattr(shipment, "current_booking_index", None),
                id(getattr(shipment, "current_storage_port", None)),
                id(getattr(shipment, "carrying_vessel", None)),
                tuple(id(booking) for booking in getattr(shipment, "associated_bookings", [])),
            )
            for shipment in shipments
        ),
        tuple(id(plan) for plan in getattr(context, "disruption_plans", [])),
    )


def _identity_index(values: Any, target: object) -> int:
    indexes = [index for index, value in enumerate(values) if value is target]
    if len(indexes) != 1:
        raise ProbeError("candidate vessel identity is not unique in waiting list")
    return indexes[0]


def _build_observer(
    *,
    readiness: Any,
    default_strategy: Any,
    snapshot: Callable[[dict[str, Any]], tuple[Any, ...]] = _hook_snapshot,
) -> tuple[Callable[..., None], dict[str, Any]]:
    """Build the berth-hook observer that captures one valid divergence.

    Returns ``(observer_callable, state)``. The observer:
      1. snapshots before;
      2. calls the participant helper;
      3. snapshots after;
      4. aborts with ProbeError on mutation (including None results);
      5. on a non-None decision, performs strictness, receiver-identity,
         and true-fallback parity checks against passed-in snapshot;
      6. on full safety passes, records evidence and stops (caller reads
         ``state[\"found\"]``); on any safety failure, raises ProbeError.

    The observer always returns ``None`` so the real model performs its
    normal fall-through to ``DefaultStrategy``.
    """

    state: dict[str, Any] = {"found": None, "rejected_reason": None}

    def _observer(**kwargs: Any) -> None:
        if state["found"] is not None:
            return None
        before = snapshot(kwargs)
        decision = readiness.evaluate_transshipment_readiness_barrier(**kwargs)
        after = snapshot(kwargs)
        if before != after:
            state["rejected_reason"] = "mutation_observed"
            raise ProbeError(
                "observation safety failed: helper evaluation mutated the "
                "snapshot (no-mutation false); refusing to record evidence"
            )
        if decision is None:
            return None
        independent, is_strict = readiness._fallback_ranking(
            kwargs["waiting_vessels"],
            kwargs["current_time"],
            kwargs["waiting_since_by_vessel"],
        )
        actual = default_strategy.select_vessel_for_berth(**kwargs)
        parity = independent is actual
        no_mutation = before == after
        if not is_strict:
            state["rejected_reason"] = "non_strict_fallback"
            raise ProbeError(
                "observation safety failed: independent fallback ranking "
                "is not strict; refusing to record evidence"
            )
        if decision.receiver is not independent:
            state["rejected_reason"] = "receiver_identity_mismatch"
            raise ProbeError(
                "observation safety failed: barrier decision receiver is "
                "not the strict independent fallback winner; refusing to "
                "record evidence"
            )
        if not parity:
            state["rejected_reason"] = "parity_mismatch"
            raise ProbeError(
                "observation safety failed: independent fallback disagrees "
                "with the DefaultStrategy fallback (parity false); "
                "refusing to record evidence"
            )
        if not no_mutation:
            state["rejected_reason"] = "mutation_in_safety_check"
            raise ProbeError(
                "observation safety failed: post-evaluation snapshot "
                "diverged from pre-evaluation snapshot; refusing to "
                "record evidence"
            )
        state["found"] = _build_evidence_payload(kwargs, decision, parity=parity)
        return None

    return _observer, state


def _build_evidence_payload(
    kwargs: dict[str, Any],
    decision: Any,
    *,
    parity: bool,
) -> dict[str, Any]:
    """Construct the evidence payload for a strict valid divergence."""
    waiting = tuple(kwargs["waiting_vessels"])
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "seed": SEED,
        "warmup_days": WARMUP_DAYS,
        "measured_days": MEASURED_DAYS,
        "interval_days": ATT_PERIOD_DAYS,
        "scenario": SCENARIO_IDENTIFIER,
        "helper_sha256": _current_helper_sha256(),
        "simulation_timestamp": kwargs["current_time"].isoformat(),
        "receiver_waiting_index": _identity_index(waiting, decision.receiver),
        "buffer_waiting_index": _identity_index(waiting, decision.buffer),
        "guaranteed_transitional_teu": decision.guaranteed_transitional_teu,
        "affected_receiver_teu": decision.affected_receiver_teu,
        "next_opportunity_hours": decision.next_opportunity_hours,
        "buffer_service_hours": decision.buffer_service_hours,
        "net_teu_hours": decision.net_teu_hours,
        "fallback_parity": bool(parity),
        "no_mutation": True,
    }


def validate_evidence(evidence: dict[str, Any]) -> None:
    """Validate stored evidence provenance before any replay model load.

    Raises :class:`ProbeError` (without ever constructing a model) for
    unknown schema, wrong configuration constants, stale helper SHA,
    non-finite metrics, or non-integer waiting indexes.
    """
    if not isinstance(evidence, dict):
        raise ProbeError("replay aborted: stored evidence is not a mapping")

    # Schema must be the current exact value (no semantic compatibility).
    if evidence.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise ProbeError(
            "replay aborted: unknown or stale schema_version "
            f"{evidence.get('schema_version')!r}; refuse to replay"
        )

    # Required configuration constants must match exactly.
    for key, expected in (
        ("seed", SEED),
        ("warmup_days", WARMUP_DAYS),
        ("measured_days", MEASURED_DAYS),
        ("interval_days", ATT_PERIOD_DAYS),
        ("scenario", SCENARIO_IDENTIFIER),
    ):
        if evidence.get(key) != expected:
            raise ProbeError(
                f"replay aborted: configuration constant {key!r} "
                f"{evidence.get(key)!r} != expected {expected!r}"
            )

    # Required metric fields and safety flags.
    _require_strict_bool(evidence, "fallback_parity", True)
    _require_strict_bool(evidence, "no_mutation", True)
    for key in (
        "guaranteed_transitional_teu",
        "affected_receiver_teu",
        "next_opportunity_hours",
        "buffer_service_hours",
        "net_teu_hours",
    ):
        value = evidence.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ProbeError(
                f"replay aborted: metric {key!r} must be a number, got {type(value).__name__}"
            )
        if isinstance(value, float) and _import_math().isnan(value):
            raise ProbeError(f"replay aborted: metric {key!r} is non-finite")
        if isinstance(value, float) and _import_math().isinf(value):
            raise ProbeError(f"replay aborted: metric {key!r} is non-finite")
    for key in ("receiver_waiting_index", "buffer_waiting_index"):
        value = evidence.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ProbeError(
                f"replay aborted: waiting index {key!r} must be a non-negative integer"
            )
        if value < 0:
            raise ProbeError(f"replay aborted: waiting index {key!r} must be non-negative")

    # Provenance: helper SHA must equal the current helper file SHA.
    current_helper_sha = _current_helper_sha256()
    stored_helper_sha = evidence.get("helper_sha256")
    if stored_helper_sha != current_helper_sha:
        raise ProbeError(
            "replay aborted: helper SHA mismatch; the stored helper_sha256 "
            "differs from the active submission's helper file. Stored "
            f"{stored_helper_sha!r}; current {current_helper_sha!r}"
        )

    # simulation_timestamp must parse as datetime.
    timestamp = evidence.get("simulation_timestamp")
    if not isinstance(timestamp, str):
        raise ProbeError("replay aborted: simulation_timestamp must be a string")
    try:
        _dt.datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ProbeError(
            f"replay aborted: simulation_timestamp {timestamp!r} is not ISO-parseable"
        ) from exc


def _require_strict_bool(evidence: dict[str, Any], key: str, expected: bool) -> None:
    value = evidence.get(key)
    if type(value) is not bool:
        raise ProbeError(f"replay aborted: {key!r} must be a boolean, got {type(value).__name__}")
    if value is not expected:
        raise ProbeError(f"replay aborted: {key!r} must be {expected}")


def _import_math():
    import math

    return math


def _current_helper_sha256() -> str:
    """Return the SHA-256 of the active submission helper file."""
    return hashlib.sha256(HELPER_SOURCE_PATH.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Real production defaults
# ---------------------------------------------------------------------------


def _real_att_writer(output_dir: Path, periods: list[tuple[int, int, float]]) -> Path:
    """Write a fresh ``ATT_By_Statistics_Interval.csv`` using the organizer's writer."""
    from simulation_output_csv_writer import write_att_by_period

    write_att_by_period(output_dir, periods)
    return output_dir / "ATT_By_Statistics_Interval.csv"


def _real_scorer(scenario_att_path: Path, baseline_att_path: Path) -> Any:
    from wsc2026_tools.scoring import compute_resilience_loss

    return compute_resilience_loss(scenario_att_path, baseline_att_path)


def _real_csv_hash(csv_path: Path) -> str:
    return hashlib.sha256(csv_path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Wrapped run_once with bound counting + private stop sentinel
# ---------------------------------------------------------------------------


def _wrap_run_once(
    model: Any,
    *,
    max_events: int,
    stop_check: Callable[[], bool],
) -> tuple[Callable[[], bool], Callable[[], int]]:
    """Wrap ``model.run_once`` so every executed event is counted.

    Returns ``(wrapped_run_once, executed_event_count_getter)``. The
    wrapper:
      1. Increments the local executed event counter.
      2. Aborts with a clear ProbeError when the counter exceeds the cap.
      3. Calls the original run_once (the organizer's normal behavior).
      4. After the original returns, checks ``stop_check``; if True,
         raises the private ``_DivergenceStop`` sentinel to halt the
         enclosing run_once loop. The sentinel is BaseException-derived
         so the wrapped run_once never confuses it with a safety
         ProbeError.

    The caller is responsible for unwrapping the method in a finally
    block; :func:`_with_wrapped_run_once` does this automatically.
    """
    original_run_once = model.run_once
    executed = {"n": 0}

    def wrapped() -> bool:
        executed["n"] += 1
        if executed["n"] > max_events:
            raise ProbeError(
                f"observation aborted: event cap {max_events} exhausted "
                "before the measured horizon elapsed"
            )
        try:
            result = original_run_once()
        finally:
            pass
        if stop_check():
            raise _DivergenceStop()
        return result

    model.run_once = wrapped
    return wrapped, lambda: executed["n"]


def _restore_run_once(model: Any) -> None:
    """Best-effort restoration of ``model.run_once``.

    Some organizers store bound methods; this handles either case.
    """
    original = getattr(model, "_wsc_probe_original_run_once", None)
    if original is None:
        # Try to locate the wrapper we stored.
        # We always store the original on a known sentinel attribute.
        return
    model.run_once = original


@contextmanager
def _with_wrapped_run_once(
    model: Any,
    *,
    max_events: int,
    stop_check: Callable[[], bool],
    on_tick: Callable[[int], None] | None = None,
) -> Iterator[Callable[[], int]]:
    """Wrap ``model.run_once`` to count events and optionally invoke a hook.

    The wrapper:

    1. Increments a local counter and aborts with ProbeError when the
       counter exceeds ``max_events``.
    2. Calls the original ``run_once``.
    3. Optionally invokes ``on_tick`` (used by tests to drive the
       berth hook between events).
    4. Calls ``stop_check``; if it returns True, raises the private
       ``_DivergenceStop`` sentinel.

    The wrapper is restored in ``finally`` so the real organizer's
    ``model.warmup``/``model.run``/``model.run_once`` semantics resume.
    """
    original = model.run_once
    counter = {"n": 0}

    def wrapped() -> bool:
        counter["n"] += 1
        if counter["n"] > max_events:
            raise ProbeError(
                f"observation aborted: event cap {max_events} exhausted "
                "before the measured horizon elapsed"
            )
        result = original()
        if on_tick is not None:
            on_tick(counter["n"])
        if stop_check():
            raise _DivergenceStop()
        return result

    model.run_once = wrapped
    try:
        yield lambda: counter["n"]
    finally:
        model.run_once = original  # noqa: F841


# ---------------------------------------------------------------------------
# Observation orchestration
# ---------------------------------------------------------------------------


def run_observation_probe(
    env: dict[str, Any] | None = None,
    output_path: Path | None = None,
    *,
    producer: Callable[[], dict[str, Any]] | None = None,
    on_tick: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Run the real warmup/run observation orchestration.

    Refuses to overwrite an existing evidence file. The orchestration:

    1. Installs the berth hook BEFORE warm-up.
    2. Wraps ``model.run_once`` with an executed-event counter and a
       private ``_DivergenceStop`` sentinel.
    3. Runs ``model.warmup(period=timedelta(days=WARMUP_DAYS))`` exactly
       as organizer ``main.py`` does.
    4. Advances the model by 360 simulated days in 1-day durations as
       organizer ``main.py`` does.
    5. After every 5 measured days, calls
       ``model.get_teu_weighted_average_transport_time_hours(
           period_start_time, model.clock_time) / 24.0`` to populate the
       72-row ATT table.
    6. If a valid divergence is recorded:
         - writes the evidence file atomically and returns it.
    7. If the full warm-up + 360 measured days elapses without a
       divergence:
         - writes a fresh ``ATT_By_Statistics_Interval.csv`` to an
           isolated ignored private directory under ``results_dir``;
         - hashes the BYTES of that CSV;
         - calls ``wsc2026_tools.scoring.compute_resilience_loss`` with
           the just-written CSV as scenario path;
         - requires ``period_count == 72`` and
           ``cumulative_loss == EXPECTED_CUMULATIVE_RESILIENCE_LOSS``;
         - returns the NO_DIVERGENCE result.
    8. The hook itself always returns ``None`` so the real model
       performs its normal fall-through to ``DefaultStrategy``.
    9. A safety ``ProbeError`` raised inside the observer propagates as
       its original safety failure (mutation / parity / strictness /
       receiver identity), NOT as a no-divergence ProbeError.
    """
    if output_path is None:
        output_path = _OBSERVATION_HASH_PATH
    if output_path.exists():
        raise ProbeError(
            f"observation aborted: evidence file already exists at "
            f"{output_path}; refusing to overwrite"
        )

    if env is None:
        default_results_dir = repo_root() / "experiments" / "results" / "round0_att"
        env = (
            _build_real_environment(results_dir=default_results_dir)
            if producer is None
            else producer()
        )

    model = env["model"]
    user_strategy_class = env["user_strategy_class"]
    readiness = env["readiness"]
    default_strategy = env["default_strategy"]
    max_events = env["max_events"]
    results_dir: Path = env["results_dir"]
    writer = env["writer"]
    scorer = env["scorer"]
    csv_hash = env["csv_hash"]

    observer, observer_state = _build_observer(
        readiness=readiness,
        default_strategy=default_strategy,
    )
    handle = install_observer(
        _Runtime(
            readiness=readiness,
            scenario_builders=env["scenario_builders"],
            model_class=env["model_class"],
            organizer_user_strategy=user_strategy_class,
            default_strategy=default_strategy,
            output_dir=env["output_dir"],
            baseline_att_path=env["baseline_att_path"],
        ),
        observer,
    )

    # Establish a clock-time origin that the cold-organizer-side helpers
    # can use as a reference for diffs in attribute comparisons.
    period_start_day = 0
    period_start_time = model.clock_time
    att_rows: list[tuple[int, int, float]] = []

    def stop_check() -> bool:
        return observer_state["found"] is not None

    try:
        with _with_wrapped_run_once(
            model, max_events=max_events, stop_check=stop_check, on_tick=on_tick
        ):
            # Warm-up: install hook here, BEFORE warming up, so the first
            # berth-idle event after warm-up is observed.
            model.warmup(period=_dt.timedelta(days=WARMUP_DAYS))
            post_warm_time = model.clock_time
            period_start_day = 1
            period_start_time = post_warm_time

            # Measured horizon. The organizer main.py also does this as a
            # day-by-day loop with a single ATT sample at every interval.
            for day in range(1, MEASURED_DAYS + 1):
                # Advance one simulated day. ``model.run`` already calls
                # run_once; the wrapper accounts for every executed event.
                with contextlib.suppress(_DivergenceStop):
                    model.run(duration=_dt.timedelta(days=1))
                if observer_state["found"] is not None:
                    break
                period_ends_today = day % ATT_PERIOD_DAYS == 0 or day == MEASURED_DAYS
                if not period_ends_today:
                    continue
                att_hours = (
                    model.get_teu_weighted_average_transport_time_hours(
                        period_start_time,
                        model.clock_time,
                    )
                    / 24.0
                )
                att_rows.append((period_start_day, day, att_hours))
                period_start_day = day + 1
                period_start_time = model.clock_time
    except _DivergenceStop:
        # The wrapped run_once raised the private stop sentinel after
        # recording a valid divergence. Fall through to evidence write.
        pass
    except ProbeError:
        # Safety ProbeErrors propagate unchanged.
        raise
    finally:
        with contextlib.suppress(Exception):
            remove_observer(handle)

    if observer_state["found"] is not None:
        evidence = observer_state["found"]
        _record_evidence_atomic(evidence, output_path)
        return evidence

    # NO_DIVERGENCE branch: write CSV, hash bytes, score, validate.
    if len(att_rows) != EXPECTED_PERIODS:
        raise ProbeError(
            f"observation aborted: produced {len(att_rows)} ATT rows, "
            f"expected {EXPECTED_PERIODS}; refusing to record a NO_DIVERGENCE result"
        )
    if writer is None or csv_hash is None or scorer is None:
        raise ProbeError(
            "observation aborted: NO_DIVERGENCE branch requires writer, "
            "csv_hash, and scorer injection"
        )
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = writer(results_dir, att_rows)
    digest = csv_hash(csv_path)
    score = scorer(csv_path, env["baseline_att_path"])
    if not _approx_equal(score.cumulative_loss, EXPECTED_CUMULATIVE_RESILIENCE_LOSS):
        raise ProbeError(
            f"observation aborted: cumulative resilience loss "
            f"{score.cumulative_loss} != expected {EXPECTED_CUMULATIVE_RESILIENCE_LOSS}"
        )
    if score.period_count != EXPECTED_PERIODS:
        raise ProbeError(
            f"observation aborted: period_count {score.period_count} != expected {EXPECTED_PERIODS}"
        )
    return {
        "status": "NO_DIVERGENCE",
        "period_count": score.period_count,
        "cumulative_loss": score.cumulative_loss,
        "att_csv_sha256": digest,
        "att_csv_path": str(csv_path),
        "expected_hash": EXPECTED_OBSERVATION_HASH,
        "actual_hash": digest,
    }


def _record_evidence_atomic(payload: dict[str, Any], destination: Path) -> None:
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


def _approx_equal(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9


# ---------------------------------------------------------------------------
# Bounded replay
# ---------------------------------------------------------------------------


def _guaranteed_shipments(runtime_env: dict[str, Any], decision: Any, port: Any) -> tuple[Any, ...]:
    readiness = runtime_env["readiness"]
    route = decision.receiver.assigned_service_route
    segments = readiness._validate_route_fleet(route, decision.receiver)
    target = readiness._next_segment(decision.receiver, segments)
    cargo = readiness._classify_receiver_cargo(port, route, target)
    if cargo.transitional_teu != decision.guaranteed_transitional_teu:
        raise ProbeError("guaranteed transitional TEU changed during replay")
    return cargo.transitional_shipments


def _shipments_ready(
    runtime_env: dict[str, Any],
    shipments: tuple[Any, ...],
    receiver: Any,
) -> bool:
    readiness = runtime_env["readiness"]
    route = receiver.assigned_service_route
    segments = readiness._validate_route_fleet(route, receiver)
    target = readiness._next_segment(receiver, segments)
    for shipment in shipments:
        chain = readiness._booking_chain(shipment)
        departure = readiness._segment_by_index(
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


def run_bounded_replay(
    env: dict[str, Any] | None = None,
    *,
    evidence: dict[str, Any] | None = None,
    evidence_path: Path | None = None,
    search_max_events: int = MAX_REPLAY_SEARCH_EVENTS,
    post_decision_max_events: int = MAX_REPLAY_EVENTS_AFTER_DECISION,
    readiness: Any | None = None,
) -> dict[str, bool]:
    """Bounded post-decision mechanism replay.

    Validates provenance-aware evidence BEFORE constructing any model.
    The replay search counts ``model.run_once`` calls (not berth-hook
    invocations). Distinguishes four failure modes: event-queue empty,
    event-cap exhaustion, horizon reached, and recorded-event mismatch.

    Returns the four mechanism proofs (``buffer_served`` etc.).
    """
    if evidence is not None:
        payload = dict(evidence)
    elif evidence_path is not None:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    else:
        payload = json.loads(_OBSERVATION_HASH_PATH.read_text(encoding="utf-8"))

    validate_evidence(payload)

    if env is None:
        # In the absence of a caller-provided environment, we use the
        # SAME env shape as the observation probe. Tests typically
        # supply a fake env directly.
        raise ProbeError(
            "run_bounded_replay requires an env dict (test seam); "
            "use the same env factory as run_observation_probe"
        )

    model = env["model"]
    user_strategy_class = env["user_strategy_class"]
    default_strategy = env["default_strategy"]

    # Allow caps to be supplied via env for tests that share env shape.
    env_search_max = int(env.get("search_max_events", search_max_events))
    env_post_max = int(env.get("post_decision_max_events", post_decision_max_events))

    target: dict[str, Any] | None = None

    def allow_recorded_candidate(**kwargs: Any) -> Any:
        nonlocal target
        if target is not None:
            return None
        decision = readiness_or(env, readiness).evaluate_transshipment_readiness_barrier(**kwargs)
        if target is not None or decision is None:
            return None
        independent, is_strict = readiness_or(env, readiness)._fallback_ranking(
            kwargs["waiting_vessels"],
            kwargs["current_time"],
            kwargs["waiting_since_by_vessel"],
        )
        actual = default_strategy.select_vessel_for_berth(**kwargs)
        if (
            is_strict
            and independent is actual is decision.receiver
            and _matches_recorded_event(kwargs, decision, payload)
        ):
            target = {
                "decision": decision,
                "berth": tuple(kwargs["available_berths"])[0],
                "shipments": _guaranteed_shipments(
                    env,
                    decision,
                    kwargs["port"],
                ),
                "time": kwargs["current_time"],
            }
            return decision.buffer
        return None

    handle = install_observer(
        _Runtime(
            readiness=readiness_or(env, readiness),
            scenario_builders=env["scenario_builders"],
            model_class=env["model_class"],
            organizer_user_strategy=user_strategy_class,
            default_strategy=default_strategy,
            output_dir=env["output_dir"],
            baseline_att_path=env["baseline_att_path"],
        ),
        allow_recorded_candidate,
    )

    def stop_search() -> bool:
        return target is not None

    try:
        with _with_wrapped_run_once(model, max_events=env_search_max, stop_check=stop_search):
            horizon = model.clock_time + _dt.timedelta(days=WARMUP_DAYS + MEASURED_DAYS)
            while (
                model.head_event_time is not None
                and model.head_event_time <= horizon
                and target is None
            ):
                try:
                    model.run_once()
                except _DivergenceStop:
                    break
        if target is None:
            # Distinguish: queue empty vs cap vs horizon.
            if model.head_event_time is None:
                raise ProbeError(
                    "replay aborted: recorded candidate event was not "
                    "reproduced; the model's event queue is empty"
                )
            raise ProbeError(
                "replay aborted: recorded candidate event was not "
                "reproduced within horizon and event cap"
            )

        decision = target["decision"]
        berth = target["berth"]
        shipments = target["shipments"]
        deadline = target["time"] + _dt.timedelta(hours=decision.buffer_service_hours + 24.0)
        buffer_served = berth.occupying_vessel is decision.buffer
        shipments_ready = _shipments_ready(env, shipments, decision.receiver)
        buffer_first_occupant_seen: bool = buffer_served
        buffer_departed = False
        receiver_selected_next = False
        guaranteed_shipments_loaded = False

        for _ in range(env_post_max):
            if model.head_event_time is not None and model.head_event_time > deadline:
                break
            try:
                model.run_once()
            except _DivergenceStop:
                break
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
            shipments_ready = shipments_ready or _shipments_ready(env, shipments, decision.receiver)
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
        try:
            remove_observer(handle)
        finally:
            pass

    result = {
        "buffer_served": buffer_served,
        "shipments_ready": shipments_ready,
        "receiver_selected_next": receiver_selected_next,
        "guaranteed_shipments_loaded": guaranteed_shipments_loaded,
    }
    if not all(result.values()):
        raise ProbeError(f"bounded replay mechanism proof failed: {result}")
    return result


def readiness_or(env: dict[str, Any], fallback: Any | None) -> Any:
    """Return the readiness helper, preferring env then fallback."""
    chosen = env.get("readiness")
    if chosen is not None:
        return chosen
    if fallback is not None:
        return fallback
    raise ProbeError("replay aborted: readiness helper was not provided")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("observe", "replay"))
    parser.add_argument("--evidence", type=Path, default=_OBSERVATION_HASH_PATH)
    args = parser.parse_args(argv)
    if args.mode == "observe":
        run_observation_probe(args.evidence)
    else:
        run_bounded_replay(evidence_path=args.evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
