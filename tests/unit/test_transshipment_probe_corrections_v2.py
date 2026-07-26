"""Phase 1 RED tests for second-round probe operational-wiring corrections.

Independent reviewer findings (against ``0ff71c8``) that must be
addressed by the GREEN refactor:

A. Search termination -- the current replay loop's ``while target is
   None`` exits only by exception (queue / horizon / cap), so the
   later ``if target is None`` recorded-event-mismatch branch is
   unreachable. Tests must drive the search to its four distinct
   terminal reasons behaviorally through ``_execute_replay`` /
   ``run_bounded_replay``.

B. Post-decision phase -- the existing test
   ``test_replay_post_decision_aborts_on_empty_queue`` never enters
   the post-decision loop because the search never locates a target.
   We need tests that genuinely locate a recorded target first and
   then independently prove empty-queue / deadline / cap aborts.

C. Hook restoration -- the cleanup currently asserts only
   ``current is not observer`` (any unrelated callable passes) and
   uses Python ``assert`` (vanishes under -O). We need tests that
   require exact identity restoration to ``handle.original`` and a
   fail-closed cleanup error if a third callable is observed.

D. CLI JSON -- ``_serializable()`` runs every primitive through
   ``str()``. Tests must pass an outcome containing strings, ints,
   floats, bools, ``None``, ``Path``, list, dict, and verify only
   ``Path`` and unsupported objects become strings.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "experiments" / "probes" / "transshipment_readiness_barrier_v1.py"


def _load_probe_module() -> types.ModuleType:
    name = "_test_probe_corrections_v2"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, PROBE_PATH)
    if spec is None or spec.loader is None:
        pytest.skip("cannot load the probe module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def probe() -> types.ModuleType:
    return _load_probe_module()


class _Obj:
    def __init__(self, **attrs: Any) -> None:
        for name, value in attrs.items():
            setattr(self, name, value)

    # Some pipeline objects (like the organizer UserStrategy class)
    # expose ``select_vessel_for_berth`` as a static method on the
    # class itself rather than per-instance. The probe's call sites
    # attribute-access the class.
    select_vessel_for_berth: Any = None


def _simple_helper() -> Any:
    helper = _Obj()

    def evaluator(**_kwargs: Any) -> Any:
        return None

    helper.evaluate_transshipment_readiness_barrier = evaluator
    helper._fallback_ranking = lambda *_a, **_k: (_Obj(), True)
    helper._validate_route_fleet = lambda *_a, **_k: (_Obj(),)
    helper._next_segment = lambda *_a, **_k: _Obj()
    helper._classify_receiver_cargo = lambda *_a, **_k: _Obj(
        transitional_teu=5.0, transitional_shipments=()
    )
    helper._booking_chain = lambda *_a, **_k: _Obj(
        current=_Obj(service_route=_Obj(), departure_segment_index=0)
    )
    helper._segment_by_index = lambda *_a, **_k: _Obj()
    return helper


def _evidence(probe: types.ModuleType) -> dict[str, Any]:
    return {
        "schema_version": probe.EVIDENCE_SCHEMA_VERSION,
        "seed": probe.SEED,
        "warmup_days": probe.WARMUP_DAYS,
        "measured_days": probe.MEASURED_DAYS,
        "interval_days": probe.ATT_PERIOD_DAYS,
        "scenario": probe.SCENARIO_IDENTIFIER,
        "helper_sha256": probe._current_helper_sha256(),
        "simulation_timestamp": datetime(2026, 1, 2).isoformat(),
        "receiver_waiting_index": 0,
        "buffer_waiting_index": 1,
        "guaranteed_transitional_teu": 5.0,
        "affected_receiver_teu": 0.0,
        "next_opportunity_hours": 19.0,
        "buffer_service_hours": 3.5,
        "net_teu_hours": 78.0,
        "fallback_parity": True,
        "no_mutation": True,
    }


def _env_with_fake_model(model: Any, helper: Any, probe_obj: types.ModuleType) -> dict[str, Any]:
    return {
        "model": model,
        "readiness": helper,
        "default_strategy": _Obj(),
        "user_strategy_class": _Obj(),
        "scenario_builders": _Obj(create_with_disruption=lambda: None),
        "model_class": type(model),
        "output_dir": probe_obj.repo_root(),
        "baseline_att_path": probe_obj.repo_root() / "README.md",
        "results_dir": probe_obj.repo_root() / "experiments" / "results" / "round0_att",
        "max_events": probe_obj.MAX_OBSERVATION_EVENTS,
        "writer": None,
        "scorer": None,
        "csv_hash": None,
    }


# ===========================================================================
# A. Search termination -- four reachable failure modes
# ===========================================================================


class _SearchEmptyQueueModel:
    """Model whose queue is empty before search begins."""

    head_event_time: datetime | None = None
    clock_time: datetime = datetime(2026, 1, 1)

    def run_once(self) -> bool:
        return False


def test_search_terminates_with_empty_queue_reason_when_queue_empty_before_search(
    probe: types.ModuleType,
) -> None:
    """Empty event queue BEFORE search runs -> empty-queue reason.

    The search must not run even one ``model.run_once()`` and must not
    attribute the abort to cap exhaustion.
    """
    env = _env_with_fake_model(_SearchEmptyQueueModel(), _simple_helper(), probe)
    env["search_max_events"] = 1_000_000
    env["post_decision_max_events"] = 1_000_000

    with pytest.raises(probe.ProbeError) as info:
        probe.run_bounded_replay(evidence=_evidence(probe), env=env)
    msg = str(info.value).lower()
    assert "queue" in msg and "empty" in msg
    assert "cap" not in msg
    assert "horizon" not in msg


class _SearchPastHorizonModel:
    """Model whose next-event time is past the measured horizon."""

    head_event_time: datetime | None = datetime(2099, 1, 1)
    clock_time: datetime = datetime(2026, 1, 1)

    def run_once(self) -> bool:
        return True


def test_search_terminates_with_horizon_reason_when_no_event_within_window(
    probe: types.ModuleType,
) -> None:
    """Next-event time exceeds horizon -> horizon reason, no cap noise."""
    env = _env_with_fake_model(_SearchPastHorizonModel(), _simple_helper(), probe)
    env["search_max_events"] = 1_000_000
    env["post_decision_max_events"] = 1_000_000

    with pytest.raises(probe.ProbeError) as info:
        probe.run_bounded_replay(evidence=_evidence(probe), env=env)
    msg = str(info.value).lower()
    assert "horizon" in msg
    assert "cap" not in msg


class _SearchCapExhaustModel:
    """Model whose queue is nonempty, no horizon miss, but cap runs out.

    Tracks ``run_once`` invocations so the cap must not be exceeded.
    """

    def __init__(self) -> None:
        self.head_event_time: datetime | None = datetime(2026, 1, 2)
        self.clock_time: datetime = datetime(2026, 1, 1)
        self.calls: int = 0

    def run_once(self) -> bool:
        self.calls += 1
        return True


def test_search_terminates_with_cap_reason_when_no_event_matches_within_cap(
    probe: types.ModuleType,
) -> None:
    """``run_once`` runs at most ``search_cap`` times and the abort
    reason must be cap exhaustion -- not mismatch (no candidate was
    observed) and not horizon (next event is in window).
    """
    model = _SearchCapExhaustModel()
    env = _env_with_fake_model(model, _simple_helper(), probe)

    with pytest.raises(probe.ProbeError) as info:
        probe.run_bounded_replay(
            evidence=_evidence(probe),
            env=env,
            search_max_events=7,
            post_decision_max_events=1_000_000,
        )
    msg = str(info.value).lower()
    assert "cap" in msg
    assert "horizon" not in msg
    assert "mismatch" not in msg
    assert model.calls == 7


# A custom evaluator returning a non-None decision for the FIRST call
# only -- so exactly one candidate IS observed, but it does not match
# the recorded evidence.


def test_search_terminates_with_mismatch_reason_after_one_nonmatching_candidate(
    probe: types.ModuleType,
) -> None:
    """One non-``None`` candidate is observed; it does not match the
    recorded evidence; subsequent queue exhaustion (empty queue after
    more ``run_once`` calls) must be reported as recorded-event
    MISMATCH -- not as queue-empty or cap.

    We use ``_PDModel`` so the model invokes the bound hook on the
    first step. The helper's evaluator returns a non-None decision
    whose ``guaranteed_transitional_teu`` mismatches the recorded
    evidence, so the observer's candidate_seen flag is set but
    ``_matches_recorded_event`` returns False. After that one
    candidate is observed, the queue becomes empty on a subsequent
    ``run_once`` and the search exits with ``target is None`` and
    ``candidate_seen is True`` -- which the probe must report as
    recorded-event MISMATCH (not as queue-empty or cap).
    """
    # Step 0: search tick with head_event_time set; model fires the
    # hook on this step. After: queue becomes empty.
    model = _PDModel(
        steps=[
            (datetime(2026, 1, 2), datetime(2026, 1, 2)),
            (None, datetime(2026, 1, 2)),
        ]
    )
    env = _post_decision_env(probe, model)

    # Patch the matching helper's evaluator so it returns a non-None
    # decision that does NOT match the recorded evidence (we
    # deliberately set ``guaranteed_transitional_teu`` to a value
    # different from 5.0 so ``_matches_recorded_event`` returns
    # False).
    helper = env["readiness"]

    def mismatch_evaluator(**kwargs: Any) -> Any:
        waiting = kwargs["waiting_vessels"]
        return _Obj(
            receiver=waiting[0],
            buffer=waiting[1],
            guaranteed_transitional_teu=999.0,  # mismatch
            affected_receiver_teu=0.0,
            next_opportunity_hours=19.0,
            buffer_service_hours=3.5,
            net_teu_hours=78.0,
        )

    helper.evaluate_transshipment_readiness_barrier = mismatch_evaluator

    with pytest.raises(probe.ProbeError) as info:
        probe.run_bounded_replay(
            evidence=_evidence(probe),
            env=env,
            search_max_events=1_000_000,
            post_decision_max_events=1_000_000,
        )
    msg = str(info.value).lower()
    assert "mismatch" in msg, f"expected recorded-event mismatch reason, got: {msg!r}"
    # The mismatch reason is reported instead of the cap or queue reasons.
    assert "event cap" not in msg
    assert "queue" not in msg or "mismatch" in msg


def test_search_with_matching_candidate_enters_post_decision_phase(
    probe: types.ModuleType,
) -> None:
    """When the search LOCATES a target, control must reach the
    post-decision phase -- not stop at a search-phase abort. The
    three follow-up post-decision tests prove the phase's three
    distinct abort reasons; this smoke test proves the search-phase
    abort reasons (queue/horizon/cap) do NOT fire when a match
    occurs.
    """
    # Step 0: search tick with head_event_time set; the model fires
    # the bound hook here, which matches -> target set.
    # Step 1: post-decision tick, queue becomes empty.
    model = _PDModel(
        steps=[
            (datetime(2026, 1, 2), datetime(2026, 1, 2)),
            (None, datetime(2026, 1, 2)),
        ]
    )
    env = _post_decision_env(probe, model)

    with pytest.raises(probe.ProbeError) as info:
        probe.run_bounded_replay(
            evidence=_evidence(probe),
            env=env,
            search_max_events=1_000_000,
            post_decision_max_events=1_000_000,
        )
    msg = str(info.value).lower()
    # Must reference the POST-decision phase, NOT a search-phase abort.
    assert "post-decision" in msg or "post decision" in msg, msg
    # Search-phase reasons must not appear.
    assert "search" not in msg or "post-decision" in msg or "post decision" in msg


# ===========================================================================
# B. Post-decision failure modes -- genuinely entered phase
# ===========================================================================


class _PDModel:
    """Model controllable per ``run_once`` step.

    The replay's hook matches the first time it fires, so the search
    phase succeeds and control enters the post-decision loop. After
    that, the model advances step-by-step so the test can drive each
    post-decision abort independently.

    The model's ``run_once`` invokes
    ``self.user_strategy_class.select_vessel_for_berth(...)`` on the
    first step -- which is the hook the probe has just bound -- with
    the same argument shape as the real ``BerthIdle.on_idle`` event.
    """

    def __init__(
        self,
        steps: list[tuple[datetime | None, datetime]],
        *,
        user_strategy_class: Any = None,
        waiting_vessels: tuple[Any, ...] = (),
        berths: tuple[Any, ...] = (),
    ) -> None:
        self._steps = list(steps)
        self.head_event_time: datetime | None = self._steps[0][0] if self._steps else None
        self.clock_time: datetime = datetime(2026, 1, 1)
        self.calls: int = 0
        self._step_index: int = 0
        self._fired: bool = False
        self.user_strategy_class = user_strategy_class
        self._waiting_vessels = waiting_vessels
        self._berths = berths

    def run_once(self) -> bool:
        self.calls += 1
        if self._step_index >= len(self._steps):
            self.head_event_time = None
            return True
        _, new_clock = self._steps[self._step_index]
        self.clock_time = new_clock
        self._step_index += 1
        if self._step_index < len(self._steps):
            self.head_event_time = self._steps[self._step_index][0]
        else:
            self.head_event_time = None
        # Fire the bound hook exactly once on the first step.
        if (
            not self._fired
            and self.user_strategy_class is not None
            and hasattr(self.user_strategy_class, "select_vessel_for_berth")
        ):
            self._fired = True
            self.user_strategy_class.select_vessel_for_berth(
                maritime_data_context=_Obj(),
                port=_Obj(),
                waiting_vessels=self._waiting_vessels,
                available_berths=self._berths,
                current_time=datetime(2026, 1, 2),
                waiting_since_by_vessel={},
            )
        return True


def _build_matching_helper(probe_obj: types.ModuleType) -> Any:
    """Build a helper whose evaluator returns a decision matching the
    recorded evidence. The helper's evaluator swaps in the actual
    ``waiting_vessels[0]`` / ``waiting_vessels[1]`` objects as
    decision.receiver / decision.buffer so identity comparisons in
    ``_matches_recorded_event`` succeed.
    """
    helper = _Obj()

    def evaluator(**kwargs: Any) -> Any:
        waiting = kwargs["waiting_vessels"]
        actual_receiver = waiting[0]
        actual_buffer = waiting[1]
        return _Obj(
            receiver=actual_receiver,
            buffer=actual_buffer,
            guaranteed_transitional_teu=5.0,
            affected_receiver_teu=0.0,
            next_opportunity_hours=19.0,
            buffer_service_hours=3.5,
            net_teu_hours=78.0,
        )

    helper.evaluate_transshipment_readiness_barrier = evaluator
    helper._fallback_ranking = lambda waiting, *_a, **_k: (waiting[0], True)
    helper._validate_route_fleet = lambda *_a, **_k: (_Obj(),)
    helper._next_segment = lambda *_a, **_k: _Obj()
    helper._classify_receiver_cargo = lambda *_a, **_k: _Obj(
        transitional_teu=5.0, transitional_shipments=()
    )
    helper._booking_chain = lambda *_a, **_k: _Obj(
        current=_Obj(service_route=_Obj(), departure_segment_index=0)
    )
    helper._segment_by_index = lambda *_a, **_k: _Obj()
    return helper


def _post_decision_env(
    probe: types.ModuleType,
    model: Any,
) -> dict[str, Any]:
    """Build an env with a user_strategy_class that the model can
    invoke through ``model.user_strategy_class.select_vessel_for_berth``.
    """
    helper = _build_matching_helper(probe)
    env = _env_with_fake_model(model, helper, probe)

    # Use a real waiting-list shape: receiver at index 0, buffer at
    # index 1, so _matches_recorded_event succeeds.
    receiver = _Obj(name="rec", assigned_service_route=_Obj(name="route"))
    buffer = _Obj(name="buf")
    berth = _Obj(occupying_vessel=None)
    model._waiting_vessels = (receiver, buffer)
    model._berths = (berth,)

    class _StrategyClass:
        pass

    _StrategyClass.select_vessel_for_berth = lambda **_k: None
    env["user_strategy_class"] = _StrategyClass
    model.user_strategy_class = _StrategyClass

    # DefaultStrategy must also be callable; it returns the receiver
    # so the strict-identity check succeeds.
    default_strategy = _Obj()
    default_strategy.select_vessel_for_berth = lambda **kwargs: kwargs["waiting_vessels"][0]
    env["default_strategy"] = default_strategy
    return env


def test_post_decision_aborts_on_empty_queue_after_match(
    probe: types.ModuleType,
) -> None:
    """Search phase matches; queue becomes empty DURING the
    post-decision loop. The terminal reason must reference
    ``post-decision`` and ``empty`` (queue).
    """
    # Step 0: search tick with head_event_time set; the model fires
    # the bound hook here, which matches -> target set.
    # Step 1: post-decision tick, but queue is now empty.
    model = _PDModel(
        steps=[
            (datetime(2026, 1, 2), datetime(2026, 1, 2)),
            (None, datetime(2026, 1, 2)),
        ]
    )
    env = _post_decision_env(probe, model)

    with pytest.raises(probe.ProbeError) as info:
        probe.run_bounded_replay(
            evidence=_evidence(probe),
            env=env,
            search_max_events=1_000_000,
            post_decision_max_events=1_000_000,
        )
    msg = str(info.value).lower()
    assert "post-decision" in msg or "post decision" in msg, msg
    assert "empty" in msg, msg


def test_post_decision_aborts_on_deadline_overrun(
    probe: types.ModuleType,
) -> None:
    """Search matches; queue stays nonempty; next event time exceeds
    deadline. Terminal reason: post-decision deadline overrun.
    """
    # deadline = 2026-01-02 03:30:00 + 24h = 2026-01-03 03:30:00
    deadline = datetime(2026, 1, 2) + timedelta(hours=3.5 + 24.0)
    model = _PDModel(
        steps=[
            (datetime(2026, 1, 2), datetime(2026, 1, 2)),  # search tick
            (deadline + timedelta(days=2), deadline + timedelta(days=2)),
        ]
    )
    env = _post_decision_env(probe, model)

    with pytest.raises(probe.ProbeError) as info:
        probe.run_bounded_replay(
            evidence=_evidence(probe),
            env=env,
            search_max_events=1_000_000,
            post_decision_max_events=1_000_000,
        )
    msg = str(info.value).lower()
    assert "post-decision" in msg or "post decision" in msg, msg
    assert "deadline" in msg or "exceed" in msg, msg


def test_post_decision_aborts_on_cap_exhaustion(
    probe: types.ModuleType,
) -> None:
    """Search matches; queue stays nonempty; events within deadline;
    post-decision cap runs out before mechanism completes.
    """
    model = _PDModel(
        steps=[
            (datetime(2026, 1, 2), datetime(2026, 1, 2)),  # search tick
            (datetime(2026, 1, 2, 1), datetime(2026, 1, 2, 1)),  # post
            (datetime(2026, 1, 2, 2), datetime(2026, 1, 2, 2)),  # post
            (datetime(2026, 1, 2, 3), datetime(2026, 1, 2, 3)),  # post
        ]
    )
    env = _post_decision_env(probe, model)

    with pytest.raises(probe.ProbeError) as info:
        probe.run_bounded_replay(
            evidence=_evidence(probe),
            env=env,
            search_max_events=1_000_000,
            post_decision_max_events=3,
        )
    msg = str(info.value).lower()
    assert "post-decision" in msg or "post decision" in msg, msg
    assert "cap" in msg, msg


# ===========================================================================
# C. Cleanup identity -- exact original restoration
# ===========================================================================


def test_observation_cleanup_restores_exact_original_callable_by_identity(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """After a successful observation, the hook must point at the
    EXACT ORIGINAL callable (``handle.original``), NOT at the observer
    and NOT at any unrelated third callable. We compare by identity.
    """

    original = lambda **_k: _Obj(name="original")  # noqa: E731

    class _StrategyClass:
        select_vessel_for_berth = original

    class _Model:
        clock_time: datetime = datetime(2026, 1, 1)
        head_event_time: datetime | None = None

        def warmup(self, *, period: timedelta) -> bool:
            return True

        def run(self, *, duration: timedelta) -> bool:
            return False

        def run_once(self) -> bool:
            return False

        def get_teu_weighted_average_transport_time_hours(
            self, _s: datetime, _e: datetime
        ) -> float:
            return 24.0

    helper = _Obj()
    helper.evaluate_transshipment_readiness_barrier = lambda **_k: None
    helper._fallback_ranking = lambda *_a, **_k: (_Obj(), True)

    env = _env_with_fake_model(_Model(), helper, probe)
    env["user_strategy_class"] = _StrategyClass
    env["scenario_builders"] = _Obj(
        create_with_disruption=lambda: _Obj(),
    )
    env["output_dir"] = tmp_path
    env["baseline_att_path"] = tmp_path / "baseline.csv"
    env["results_dir"] = tmp_path / "results"

    out = tmp_path / "evidence.json"
    # Run a successful (no-divergence) observation. The probe raises
    # ``ProbeError`` because the writer/scorer/csv_hash are None, but
    # we want to assert that EVEN IN FAILURE the hook is restored
    # exactly. So we expect a ProbeError.
    with pytest.raises(probe.ProbeError):
        probe.run_observation_probe(output_path=out, env=env)

    # The hook must now be the exact original callable (not None, not
    # observer, not anything else).
    assert _StrategyClass.select_vessel_for_berth is original
    assert _StrategyClass.select_vessel_for_berth is not None


def test_replay_cleanup_restores_exact_original_callable_by_identity(
    probe: types.ModuleType,
) -> None:
    """After a replay that aborts, the hook must be the EXACT ORIGINAL
    callable, NOT the observer, NOT any unrelated third callable.
    """
    original = lambda **_k: _Obj(name="original")  # noqa: E731

    class _StrategyClass:
        select_vessel_for_berth = original

    class _Model:
        head_event_time: datetime | None = None
        clock_time: datetime = datetime(2026, 1, 1)

        def run_once(self) -> bool:
            return False

    helper = _simple_helper()
    env = _env_with_fake_model(_Model(), helper, probe)
    env["user_strategy_class"] = _StrategyClass
    env["search_max_events"] = 1_000_000
    env["post_decision_max_events"] = 1_000_000

    with pytest.raises(probe.ProbeError):
        probe.run_bounded_replay(evidence=_evidence(probe), env=env)

    assert _StrategyClass.select_vessel_for_berth is original
    assert _StrategyClass.select_vessel_for_berth is not None


def test_observation_cleanup_recovers_when_hook_is_third_callable(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """While the probe's observer is installed, an unrelated third
    callable replaces the hook. After cleanup, the hook MUST point
    back at the ORIGINAL callable -- not at the third callable.

    ``handle.restore()`` is idempotent only when the current hook
    matches ``handle.current`` (the observer). Because a third
    callable now sits between, restore is a no-op and the
    ``_enforce_hook_identity`` post-check detects the corruption and
    fails closed with a ``ProbeError`` naming both the expected
    original and the actual third callable.
    """
    original = lambda **_k: _Obj(name="original")  # noqa: E731
    third = lambda **_k: _Obj(name="third")  # noqa: E731

    class _StrategyClass:
        select_vessel_for_berth = original

    class _Model:
        clock_time: datetime = datetime(2026, 1, 1)
        head_event_time: datetime | None = None

        def warmup(self, *, period: timedelta) -> bool:
            return True

        def run(self, *, duration: timedelta) -> bool:
            return False

        def run_once(self) -> bool:
            return False

        def get_teu_weighted_average_transport_time_hours(
            self, _s: datetime, _e: datetime
        ) -> float:
            return 24.0

    helper = _Obj()
    helper.evaluate_transshipment_readiness_barrier = lambda **_k: None
    helper._fallback_ranking = lambda *_a, **_k: (_Obj(), True)

    env = _env_with_fake_model(_Model(), helper, probe)
    env["user_strategy_class"] = _StrategyClass
    env["output_dir"] = tmp_path
    env["baseline_att_path"] = tmp_path / "baseline.csv"
    env["results_dir"] = tmp_path / "results"

    out = tmp_path / "evidence.json"

    real_install_observer = probe.install_observer

    def patched_install_observer(runtime: Any, observer: Any) -> Any:
        handle = real_install_observer(runtime, observer)
        runtime.organizer_user_strategy.select_vessel_for_berth = third
        return handle

    with (
        mock.patch.object(probe, "install_observer", side_effect=patched_install_observer),
        pytest.raises(probe.ProbeError) as info,
    ):
        probe.run_observation_probe(output_path=out, env=env)

    msg = str(info.value)
    assert "hook restoration failed" in msg, msg
    # The error names the original and the third callable.
    assert "expected the original callable" in msg, msg
    # The hook remains the third callable (because restore was a
    # no-op); the failure is detected, not papered over.
    assert _StrategyClass.select_vessel_for_berth is third


def test_observation_primary_error_plus_cleanup_error_surfaces_both(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """When the primary execution fails AND cleanup raises, both
    errors must be visible in the raised exception.
    """
    original = lambda **_k: _Obj(name="original")  # noqa: E731

    class _StrategyClass:
        select_vessel_for_berth = original

    class _Model:
        clock_time: datetime = datetime(2026, 1, 1)
        head_event_time: datetime | None = None

        def warmup(self, *, period: timedelta) -> bool:
            raise RuntimeError("primary boom during warmup")

        def run(self, *, duration: timedelta) -> bool:
            return False

        def run_once(self) -> bool:
            return False

        def get_teu_weighted_average_transport_time_hours(
            self, _s: datetime, _e: datetime
        ) -> float:
            return 24.0

    helper = _Obj()
    helper.evaluate_transshipment_readiness_barrier = lambda **_k: None
    helper._fallback_ranking = lambda *_a, **_k: (_Obj(), True)

    env = _env_with_fake_model(_Model(), helper, probe)
    env["user_strategy_class"] = _StrategyClass
    env["output_dir"] = tmp_path
    env["baseline_att_path"] = tmp_path / "baseline.csv"
    env["results_dir"] = tmp_path / "results"

    out = tmp_path / "evidence.json"

    def boom_remove_observer(handle: Any) -> None:
        raise RuntimeError("cleanup boom during restore")

    with (
        mock.patch.object(probe, "remove_observer", side_effect=boom_remove_observer),
        pytest.raises(probe.ProbeError) as info,
    ):
        probe.run_observation_probe(output_path=out, env=env)

    msg = str(info.value)
    assert "primary boom" in msg, (
        f"primary error message must be visible in the chained ProbeError, got: {msg!r}"
    )
    assert "cleanup boom" in msg, (
        f"cleanup error message must be visible in the chained ProbeError, got: {msg!r}"
    )


# ===========================================================================
# D. JSON serialization preserves native types
# ===========================================================================


def test_serializable_preserves_native_json_types(
    probe: types.ModuleType,
) -> None:
    """``_serializable`` must preserve ``None``, ``str``, ``bool``,
    ``int``, and finite ``float`` as their native JSON types. Only
    ``Path`` and unsupported objects may become strings. Lists and
    dicts must be recursed.
    """
    sample = {
        "s": "hello",
        "i": 42,
        "f": 3.14,
        "b_true": True,
        "b_false": False,
        "none": None,
        "path": Path("/tmp/foo"),
        "list": [1, 2.5, "three", None, True],
        "nested": {"k": "v", "n": 0},
    }
    out = probe._serializable(sample)
    encoded = json.dumps(out)
    parsed = json.loads(encoded)

    assert parsed["s"] == "hello"
    assert parsed["i"] == 42
    assert isinstance(parsed["i"], int)
    assert parsed["f"] == 3.14
    assert isinstance(parsed["f"], float)
    assert parsed["b_true"] is True
    assert parsed["b_false"] is False
    assert parsed["none"] is None
    assert parsed["path"] == "/tmp/foo"  # Path becomes string
    assert parsed["list"] == [1, 2.5, "three", None, True]
    assert parsed["nested"] == {"k": "v", "n": 0}


def test_serializable_cli_output_preserves_native_types_via_json(
    probe: types.ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """End-to-end: the CLI prints one JSON document and native types
    are preserved through ``json.dumps`` / ``json.loads``.
    """
    outcome = {
        "status": "OK",
        "int_field": 72,
        "float_field": 18.673577819840556,
        "bool_field": True,
        "none_field": None,
        "path_field": tmp_path / "x.csv",
        "list_field": [1, 2.0, "three"],
    }

    def fake_observe(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return outcome

    evidence = tmp_path / "evidence.json"
    with mock.patch.object(probe, "run_observation_probe", side_effect=fake_observe):
        rc = probe.main(["observe", "--evidence", str(evidence)])
    assert rc == 0
    parsed = json.loads(capsys.readouterr().out.strip())
    assert parsed["int_field"] == 72
    assert isinstance(parsed["int_field"], int)
    assert parsed["float_field"] == 18.673577819840556
    assert isinstance(parsed["float_field"], float)
    assert parsed["bool_field"] is True
    assert parsed["none_field"] is None
    assert parsed["path_field"] == str(tmp_path / "x.csv")
    assert parsed["list_field"] == [1, 2.0, "three"]
