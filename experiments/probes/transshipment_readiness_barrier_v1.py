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
  with the just-written CSV as scenario path, enforces
  ``att_csv_sha256 == EXPECTED_OBSERVATION_HASH`` (raising
  :class:`ProbeError` on mismatch), and requires
  ``period_count == 72`` and ``cumulative_loss == EXPECTED_CUMULATIVE_RESILIENCE_LOSS``.
* :func:`run_bounded_replay` consumes the saved provenance-safe evidence
  and verifies the buffer-then-receiver mechanism, counting every
  ``model.run_once`` call against ``search_max_events``.

Both phases share :func:`_load_runtime`, which inserts the Round 0
organizer source on ``sys.path`` and exposes the participant helper
as a synthetic package; on exit it always restores ``sys.path`` and
removes every package it inserted from ``sys.modules``.

Public function signatures (corrected in this round):

* :func:`run_observation_probe` -- ``output_path`` is the FIRST
  POSITIONAL parameter; ``env`` is keyword-only.
* :func:`run_bounded_replay` -- ``evidence_path`` is the FIRST
  POSITIONAL parameter; ``env`` is keyword-only.

Both phases keep the real organizer runtime ALIVE across the entire
operation (model construction + execution + cleanup happen inside a
single ``_load_runtime`` enter/exit). This is required because
``simulation_output_csv_writer.write_att_by_period`` is only available
while the organizer source is on ``sys.path``.

The probe is FAIL-CLOSED. Any safety violation, provenance mismatch,
configuration mismatch, non-finite metric, non-integer index, unknown
schema, hash mismatch, or event-cap exhaustion aborts with a clear
:class:`ProbeError`.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import hashlib
import importlib
import importlib.util
import json
import math
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
MAX_OBSERVATION_EVENTS = 20_000_000
MAX_REPLAY_EVENTS_AFTER_DECISION = 100_000
MAX_REPLAY_SEARCH_EVENTS = MAX_OBSERVATION_EVENTS

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
DEFAULT_OBSERVATION_PATH = _OBSERVATION_HASH_PATH
DEFAULT_REPLAY_PATH = _OBSERVATION_HASH_PATH


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


def _enforce_hook_identity(handle: ObserverHandle) -> None:
    """Fail-closed verification that the hook attribute matches the original.

    Compares the post-cleanup hook value to ``handle.original`` by
    identity (not ``is not observer``). If they do not match, raises
    a ``ProbeError`` naming both the expected and actual callable so
    the caller can diagnose the corruption. Does NOT use Python
    ``assert`` so the check survives ``python -O``.
    """
    current = getattr(handle.owner, handle.attribute, None)
    if current is not handle.original:
        raise ProbeError(
            f"hook restoration failed: expected the original callable "
            f"{handle.original!r}, found {current!r}"
        )


def _cleanup_observer(
    handle: ObserverHandle,
    *,
    primary_error: BaseException | None,
) -> None:
    """Restore an observer and surface every cleanup failure."""
    cleanup_errors: list[BaseException] = []
    try:
        remove_observer(handle)
    except BaseException as exc:  # noqa: BLE001
        cleanup_errors.append(exc)
    try:
        _enforce_hook_identity(handle)
    except BaseException as exc:  # noqa: BLE001
        cleanup_errors.append(exc)

    if not cleanup_errors:
        return
    details = "; ".join(f"{type(exc).__name__}: {exc}" for exc in cleanup_errors)
    if primary_error is not None:
        raise ProbeError(f"{primary_error}: cleanup failed: {details}") from primary_error
    raise ProbeError(f"cleanup failed: {details}") from cleanup_errors[0]


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
        if isinstance(value, float) and math.isnan(value):
            raise ProbeError(f"replay aborted: metric {key!r} is non-finite")
        if isinstance(value, float) and math.isinf(value):
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


def _current_helper_sha256() -> str:
    """Return the SHA-256 of the active submission helper file."""
    return hashlib.sha256(HELPER_SOURCE_PATH.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Real production defaults (captured while the organizer runtime is alive)
# ---------------------------------------------------------------------------


def _capture_real_callables(runtime: _Runtime) -> dict[str, Any]:
    """Pull organizer-side callables while the runtime context is open.

    Called from inside ``_load_runtime``; the result is bound into the
    environment dict so ``_run_observation_with_env`` and
    ``_run_replay_with_env`` can call them without re-importing the
    organizer-side modules (which would fail once the runtime context
    has exited and removed the organizer source from ``sys.path``).
    """
    from simulation_output_csv_writer import write_att_by_period

    from wsc2026_tools.scoring import compute_resilience_loss

    return {
        "writer": lambda output_dir, periods: _real_att_writer(
            write_att_by_period, output_dir, periods
        ),
        "scorer": compute_resilience_loss,
        "csv_hash": _real_csv_hash,
    }


def _real_att_writer(
    write_att_by_period: Callable[..., Any],
    output_dir: Path,
    periods: list[tuple[int, int, float]],
) -> Path:
    """Write a fresh ``ATT_By_Statistics_Interval.csv`` using the captured writer."""
    write_att_by_period(output_dir, periods)
    return output_dir / "ATT_By_Statistics_Interval.csv"


def _real_csv_hash(csv_path: Path) -> str:
    return hashlib.sha256(csv_path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Wrapped run_once with bound counting + private stop sentinel
# ---------------------------------------------------------------------------


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
        model.run_once = original


# ---------------------------------------------------------------------------
# Observation orchestration
# ---------------------------------------------------------------------------


# Environment shape consumed by the probe's internal execution functions.
_OBSERVATION_ENV_KEYS = (
    "model",
    "readiness",
    "default_strategy",
    "user_strategy_class",
    "scenario_builders",
    "model_class",
    "output_dir",
    "baseline_att_path",
    "results_dir",
    "max_events",
    "writer",
    "scorer",
    "csv_hash",
)


def _build_environment_dict(
    runtime: _Runtime,
    *,
    real_callables: dict[str, Any],
    results_dir: Path,
    max_events: int,
) -> dict[str, Any]:
    """Build an observation env while the organizer runtime is alive."""
    context_factory = runtime.scenario_builders.create_with_disruption
    context = context_factory()
    model = runtime.model_class(context, seed=SEED)
    return {
        "model": model,
        "readiness": runtime.readiness,
        "default_strategy": runtime.default_strategy,
        "user_strategy_class": runtime.organizer_user_strategy,
        "scenario_builders": runtime.scenario_builders,
        "model_class": runtime.model_class,
        "output_dir": runtime.output_dir,
        "baseline_att_path": runtime.baseline_att_path,
        "results_dir": results_dir,
        "max_events": max_events,
        "writer": real_callables["writer"],
        "scorer": real_callables["scorer"],
        "csv_hash": real_callables["csv_hash"],
    }


def run_observation_probe(
    output_path: Path | str | None = DEFAULT_OBSERVATION_PATH,
    *,
    env: dict[str, Any] | None = None,
    on_tick: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Run the real warmup/run observation orchestration.

    ``output_path`` is the first positional parameter (not ``env``); the
    CLI keyword-routing requirement is that ``args.evidence`` reaches
    this parameter by name. If ``env`` is None, the probe enters
    ``_load_runtime`` for the entire duration of model construction,
    hook installation, orchestration, scoring, and cleanup, so the
    organizer source remains on ``sys.path`` while
    ``simulation_output_csv_writer.write_att_by_period`` is invoked.

    The orchestration:

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
         - compares the digest against ``EXPECTED_OBSERVATION_HASH``
           (mismatch raises ProbeError);
         - calls ``wsc2026_tools.scoring.compute_resilience_loss`` with
           the just-written CSV as scenario path;
         - requires ``period_count == 72`` and
           ``cumulative_loss == EXPECTED_CUMULATIVE_RESILIENCE_LOSS``;
         - returns the NO_DIVERGENCE result.
    8. The hook itself always returns ``None`` so the real model
       performs its normal fall-through to ``DefaultStrategy``.
    9. A safety ``ProbeError`` raised inside the observer propagates as
       its original safety failure (mutation / parity / strictness /
       receiver identity / hash mismatch), NOT as a no-divergence
       ProbeError.

    A safety ProbeError raised during cleanup is preserved alongside
    the primary error via ``raise ... from ...`` so neither is silently
    dropped.
    """
    if output_path is None:
        output_path = DEFAULT_OBSERVATION_PATH
    output_path = Path(output_path)
    if output_path.exists():
        raise ProbeError(
            f"observation aborted: evidence file already exists at "
            f"{output_path}; refusing to overwrite"
        )

    if env is None:
        return _run_observation_with_real_runtime(
            output_path=output_path,
            on_tick=on_tick,
        )
    return _run_observation_with_env(
        env=env,
        output_path=output_path,
        on_tick=on_tick,
    )


def _run_observation_with_env(
    *,
    env: dict[str, Any],
    output_path: Path,
    on_tick: Callable[[int], None] | None,
) -> dict[str, Any]:
    """Run observation against an externally-provided env (no runtime).

    The caller is responsible for the lifetime of any model used here.
    Used by unit tests that drive the probe with fake models.
    """
    model = env["model"]
    max_events = int(env["max_events"])
    return _execute_observation(
        env=env,
        model=model,
        max_events=max_events,
        output_path=output_path,
        on_tick=on_tick,
    )


def _run_observation_with_real_runtime(
    *,
    output_path: Path,
    on_tick: Callable[[int], None] | None,
) -> dict[str, Any]:
    """Run observation with the real organizer runtime kept alive.

    The model, the bound scoring / hashing / writing callables, and the
    hook are all in scope while ``_load_runtime()`` is open. The
    runtime context is only exited after hook and run_once restoration
    are complete.
    """
    results_dir = repo_root() / "experiments" / "results" / "round0_att"
    results_dir.mkdir(parents=True, exist_ok=True)
    with _load_runtime() as runtime:
        real_callables = _capture_real_callables(runtime)
        env = _build_environment_dict(
            runtime,
            real_callables=real_callables,
            results_dir=results_dir,
            max_events=MAX_OBSERVATION_EVENTS,
        )
        return _execute_observation(
            env=env,
            model=env["model"],
            max_events=MAX_OBSERVATION_EVENTS,
            output_path=output_path,
            on_tick=on_tick,
        )


def _execute_observation(
    *,
    env: dict[str, Any],
    model: Any,
    max_events: int,
    output_path: Path,
    on_tick: Callable[[int], None] | None,
) -> dict[str, Any]:
    """Run the observation body with hook + run_once restoration guaranteed."""
    user_strategy_class = env["user_strategy_class"]
    readiness = env["readiness"]
    default_strategy = env["default_strategy"]
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

    period_start_day = 0
    period_start_time = model.clock_time
    att_rows: list[tuple[int, int, float]] = []

    def stop_check() -> bool:
        return observer_state["found"] is not None

    primary_error: BaseException | None = None
    try:
        with _with_wrapped_run_once(
            model, max_events=max_events, stop_check=stop_check, on_tick=on_tick
        ):
            model.warmup(period=_dt.timedelta(days=WARMUP_DAYS))
            post_warm_time = model.clock_time
            period_start_day = 1
            period_start_time = post_warm_time

            for day in range(1, MEASURED_DAYS + 1):
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
        pass
    except ProbeError as exc:
        primary_error = exc
        raise
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        _cleanup_observer(handle, primary_error=primary_error)

    if observer_state["found"] is not None:
        evidence = observer_state["found"]
        _record_evidence_atomic(evidence, output_path)
        return evidence

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
    if digest != EXPECTED_OBSERVATION_HASH:
        raise ProbeError(
            f"observation aborted: att_csv_sha256 {digest} != pinned "
            f"EXPECTED_OBSERVATION_HASH {EXPECTED_OBSERVATION_HASH}; "
            "refusing to record a NO_DIVERGENCE result"
        )
    score = scorer(csv_path, env["baseline_att_path"])
    if score.period_count != EXPECTED_PERIODS:
        raise ProbeError(
            f"observation aborted: period_count {score.period_count} != expected {EXPECTED_PERIODS}"
        )
    if not _approx_equal(score.cumulative_loss, EXPECTED_CUMULATIVE_RESILIENCE_LOSS):
        raise ProbeError(
            f"observation aborted: cumulative resilience loss "
            f"{score.cumulative_loss} != expected {EXPECTED_CUMULATIVE_RESILIENCE_LOSS}"
        )
    return {
        "status": "NO_DIVERGENCE",
        "period_count": score.period_count,
        "cumulative_loss": score.cumulative_loss,
        "att_csv_sha256": digest,
        "att_csv_path": str(csv_path),
        "expected_hash": EXPECTED_OBSERVATION_HASH,
    }


def _record_evidence_atomic(payload: dict[str, Any], destination: Path) -> None:
    """Atomic temp-write + rename with no overwrite.

    Creates the parent directory on demand (fresh-clone friendly),
    refuses to overwrite an existing destination, and cleans up the
    temp file on failure.
    """
    if destination.exists():
        raise ProbeError(
            f"observation safety failed: evidence file already exists at "
            f"{destination}; refusing to overwrite"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
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
    evidence_path: Path | str | None = DEFAULT_REPLAY_PATH,
    *,
    env: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    search_max_events: int | None = None,
    post_decision_max_events: int | None = None,
) -> dict[str, Any]:
    """Bounded post-decision mechanism replay.

    Validates provenance-aware evidence BEFORE constructing any model.
    The replay search counts ``model.run_once`` calls (not berth-hook
    invocations). Distinguishes four failure modes: event-queue empty,
    event-cap exhaustion, horizon reached, and recorded-event mismatch.

    ``evidence_path`` is the first positional parameter (not ``env``);
    the CLI keyword-routing requirement is that ``args.evidence``
    reaches this parameter by name. If ``env`` is None, the probe
    enters ``_load_runtime`` for the entire duration of model
    construction, hook installation, search phase, post-decision
    mechanism, and cleanup.

    Returns a dict carrying either the four ``True`` mechanism proofs
    on success or a ``{"status": "FAILED", "reason": ..., ...}`` on
    failure (the CLI prints the JSON for either outcome).
    """
    if evidence is not None:
        payload = dict(evidence)
    elif evidence_path is not None:
        evidence_path = Path(evidence_path)
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    else:
        evidence_path = DEFAULT_REPLAY_PATH
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))

    validate_evidence(payload)

    search_cap = MAX_REPLAY_SEARCH_EVENTS if search_max_events is None else int(search_max_events)
    post_cap = (
        MAX_REPLAY_EVENTS_AFTER_DECISION
        if post_decision_max_events is None
        else int(post_decision_max_events)
    )

    if env is None:
        return _run_replay_with_real_runtime(
            evidence_payload=payload,
            search_cap=search_cap,
            post_cap=post_cap,
        )
    return _run_replay_with_env(
        env=env,
        evidence_payload=payload,
        search_cap=search_cap,
        post_cap=post_cap,
    )


def _resolve_readiness(env: dict[str, Any]) -> Any:
    chosen = env.get("readiness")
    if chosen is None:
        raise ProbeError("replay aborted: readiness helper was not provided in env")
    return chosen


def _run_replay_with_env(
    *,
    env: dict[str, Any],
    evidence_payload: dict[str, Any],
    search_cap: int,
    post_cap: int,
) -> dict[str, Any]:
    """Run replay against an externally-provided env (no runtime)."""
    return _execute_replay(
        env=env,
        evidence_payload=evidence_payload,
        search_cap=search_cap,
        post_cap=post_cap,
    )


def _run_replay_with_real_runtime(
    *,
    evidence_payload: dict[str, Any],
    search_cap: int,
    post_cap: int,
) -> dict[str, Any]:
    """Run replay keeping the organizer runtime open for the full operation."""
    results_dir = repo_root() / "experiments" / "results" / "round0_att"
    results_dir.mkdir(parents=True, exist_ok=True)
    with _load_runtime() as runtime:
        real_callables = _capture_real_callables(runtime)
        env = _build_environment_dict(
            runtime,
            real_callables=real_callables,
            results_dir=results_dir,
            max_events=search_cap,
        )
        return _execute_replay(
            env=env,
            evidence_payload=evidence_payload,
            search_cap=search_cap,
            post_cap=post_cap,
        )


def _execute_replay(
    *,
    env: dict[str, Any],
    evidence_payload: dict[str, Any],
    search_cap: int,
    post_cap: int,
) -> dict[str, Any]:
    """Run the search + post-decision mechanism with hook restoration guaranteed.

    Search-phase termination precedence (must be deterministic):

    1. A matching candidate is observed -> leave the search loop and
       enter the post-decision phase.
    2. Otherwise, the search loop runs up to ``search_cap`` real
       ``model.run_once()`` calls. The loop body checks
       ``head_event_time`` (queue empty) and ``head_event_time >
       horizon`` (horizon reached) BEFORE incrementing the counter,
       so the cap is not exceeded for empty/horizon reasons.
    3. After the loop exits without a match, the terminal reason is:

       * recorded-event mismatch -- if at least one non-``None``
         candidate was observed during the search but none matched
         the recorded evidence;
       * otherwise queue-empty -- if the model event queue is empty
         at loop exit;
       * otherwise horizon -- if the next event time exceeds the
         measured horizon;
       * otherwise cap -- if the loop completed all
         ``search_cap`` iterations without finding a match.

    Cleanup guarantees (no ``assert``):

    * The post-cleanup hook attribute on
      ``user_strategy_class.select_vessel_for_berth`` is compared by
      identity to ``handle.original``. If they do not match, the
      probe raises a fail-closed ProbeError that names both the
      expected and the actual hook.
    * Cleanup runs on every exit path (success and failure).
    * If both the primary action and the cleanup fail, both messages
      are surfaced (cleanup as context); a failure solely in cleanup
      is also surfaced.
    """
    model = env["model"]
    user_strategy_class = env["user_strategy_class"]
    default_strategy = env["default_strategy"]
    readiness = _resolve_readiness(env)

    target: dict[str, Any] | None = None
    candidate_seen = False
    executed_search_count = 0
    horizon = model.clock_time + _dt.timedelta(days=WARMUP_DAYS + MEASURED_DAYS)

    def allow_recorded_candidate(**kwargs: Any) -> Any:
        nonlocal target, candidate_seen
        if target is not None:
            return None
        decision = readiness.evaluate_transshipment_readiness_barrier(**kwargs)
        if decision is None:
            return None
        candidate_seen = True
        if not _matches_recorded_event(kwargs, decision, evidence_payload):
            return None
        independent, is_strict = readiness._fallback_ranking(
            kwargs["waiting_vessels"],
            kwargs["current_time"],
            kwargs["waiting_since_by_vessel"],
        )
        actual = default_strategy.select_vessel_for_berth(**kwargs)
        if is_strict and independent is actual is decision.receiver:
            target = {
                "decision": decision,
                "berth": tuple(kwargs["available_berths"])[0],
                "shipments": _guaranteed_shipments(env, decision, kwargs["port"]),
                "time": kwargs["current_time"],
            }
            return decision.buffer
        return None

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
        allow_recorded_candidate,
    )

    def stop_search() -> bool:
        return target is not None

    post_phase_error: BaseException | None = None
    try:
        try:
            with _with_wrapped_run_once(model, max_events=search_cap, stop_check=stop_search):
                for _executed_search_count in range(search_cap):
                    if target is not None:
                        break
                    if model.head_event_time is None:
                        # If we have already observed a non-None
                        # candidate that did not match the recorded
                        # evidence, exit cleanly so the post-loop
                        # analysis can report the MISMATCH reason
                        # rather than masking it with a queue-empty
                        # error.
                        if candidate_seen:
                            break
                        raise ProbeError(
                            "replay aborted: search terminated because "
                            "the model event queue is empty"
                        )
                    if model.head_event_time > horizon:
                        if candidate_seen:
                            break
                        raise ProbeError(
                            "replay aborted: search terminated because "
                            "the next event is past the measured horizon"
                        )
                    executed_search_count = _executed_search_count + 1
                    try:
                        model.run_once()
                    except _DivergenceStop:
                        break
        except _DivergenceStop:
            pass

        if target is None:
            # Determine the search-phase terminal reason.
            if candidate_seen:
                # At least one non-None candidate was observed, but
                # none matched the recorded evidence -> MISMATCH.
                raise ProbeError(
                    "replay aborted: search exhausted because one or "
                    "more non-None candidate decisions were observed "
                    "but none matched the recorded evidence "
                    "(recorded-event mismatch)"
                )
            if model.head_event_time is None:
                raise ProbeError(
                    "replay aborted: search terminated because the model event queue is empty"
                )
            if model.head_event_time > horizon:
                raise ProbeError(
                    "replay aborted: search terminated because the next "
                    "event is past the measured horizon"
                )
            raise ProbeError(
                "replay aborted: search exhausted the configured event "
                f"cap of {search_cap} run_once calls without locating "
                "a matching candidate"
            )

        decision = target["decision"]
        berth = target["berth"]
        shipments = target["shipments"]
        deadline = target["time"] + _dt.timedelta(hours=decision.buffer_service_hours + 24.0)
        buffer_served = berth.occupying_vessel is decision.buffer
        shipments_ready = _shipments_ready(env, shipments, decision.receiver)
        buffer_departed = False
        receiver_selected_next = False
        guaranteed_shipments_loaded = False

        try:
            for _executed_post_count in range(post_cap):
                if model.head_event_time is None:
                    raise ProbeError(
                        "replay aborted: post-decision phase aborted "
                        "because the model event queue is empty"
                    )
                if model.head_event_time > deadline:
                    raise ProbeError(
                        "replay aborted: post-decision phase aborted "
                        "because the next event exceeds the buffer-deadline"
                    )
                try:
                    model.run_once()
                except _DivergenceStop:
                    break
                occupant = berth.occupying_vessel
                buffer_served = buffer_served or occupant is decision.buffer
                if buffer_served and not buffer_departed and occupant is not decision.buffer:
                    buffer_departed = True
                if buffer_departed and not receiver_selected_next:
                    if occupant is decision.receiver:
                        receiver_selected_next = True
                    elif occupant is not None:
                        raise ProbeError(
                            "bounded replay: a vessel other than the "
                            "receiver occupied the berth right after the buffer"
                        )
                shipments_ready = shipments_ready or _shipments_ready(
                    env, shipments, decision.receiver
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
            else:
                raise ProbeError(
                    "replay aborted: post-decision phase exhausted its "
                    f"event cap ({post_cap}) without completing the "
                    "mechanism"
                )
        except _DivergenceStop:
            pass
    except ProbeError as exc:
        post_phase_error = exc
        raise
    except BaseException as exc:
        post_phase_error = exc
        raise
    finally:
        _cleanup_observer(handle, primary_error=post_phase_error)

    result = {
        "buffer_served": bool(buffer_served),
        "shipments_ready": bool(shipments_ready),
        "receiver_selected_next": bool(receiver_selected_next),
        "guaranteed_shipments_loaded": bool(guaranteed_shipments_loaded),
        "executed_search_events": executed_search_count,
    }
    if not all(
        result[k]
        for k in (
            "buffer_served",
            "shipments_ready",
            "receiver_selected_next",
            "guaranteed_shipments_loaded",
        )
    ):
        raise ProbeError(f"bounded replay mechanism proof failed: {result}")
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI for the operational observation and replay phases.

    Routes ``--evidence`` to the correct keyword parameter of each
    public function:

    * observe -> ``run_observation_probe(output_path=args.evidence)``
    * replay  -> ``run_bounded_replay(evidence_path=args.evidence)``

    Always prints a concise JSON document to stdout describing the
    outcome (success or failure) and exits non-zero on failure.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("observe", "replay"))
    parser.add_argument("--evidence", type=Path, default=DEFAULT_OBSERVATION_PATH)
    args = parser.parse_args(argv)
    try:
        if args.mode == "observe":
            result = run_observation_probe(output_path=args.evidence)
        else:
            result = run_bounded_replay(evidence_path=args.evidence)
        print(json.dumps(_serializable(result), indent=2, sort_keys=True))
        # Replay returns mechanism proofs as booleans; if the result
        # explicitly carries a FAILED status, surface a nonzero exit
        # code so CI can detect the failure.
        if isinstance(result, dict) and result.get("status") == "FAILED":
            return 1
        return 0
    except ProbeError as exc:
        print(
            json.dumps(
                {"status": "FAILED", "reason": str(exc)},
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    except BaseException as exc:
        print(
            json.dumps(
                {"status": "ERROR", "error": repr(exc)},
                indent=2,
                sort_keys=True,
            )
        )
        return 3


def _serializable(value: Any) -> Any:
    """Recursively convert a value into a JSON-native representation.

    Native JSON types (``None``, ``bool``, ``int``, ``float`` -- finite
    only -- and ``str``) are returned unchanged. ``Path`` is converted
    to its string form. Mappings and sequences are recursed. Anything
    else is rendered as its ``repr()`` string so unsupported objects do
    not crash the CLI's JSON encoder.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    return repr(value)


if __name__ == "__main__":
    raise SystemExit(main())
