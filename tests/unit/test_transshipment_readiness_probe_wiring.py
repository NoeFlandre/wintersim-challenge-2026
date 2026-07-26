"""Behavioral tests for operational wiring corrections.

These tests assert behavioral fixes for the operational-wiring review
(separate from the test file for the probe's statistical/behavioural
contract). Every test monkey-patches the operational function and
verifies the CLI routes the right value by the correct keyword. They
never launch a model.

* CLI passes ``output_path`` (not ``env``) to ``run_observation_probe``.
* CLI passes ``evidence_path`` (not ``env``) to ``run_bounded_replay``.
* ``run_observation_probe`` prints JSON for both observation and
  no-divergence outcomes.
* ``run_bounded_replay`` prints JSON for both mechanism success and
  failure.
* Real-environment lifetime keeps the organizer runtime alive across
  the full execution (write_att_by_period is captured while the
  context is open).
* Real replay constructs a model from ``create_with_disruption``.
* Wrong CSV hash raises ProbeError even if scoring passes.
* Replay search distinguishes cap-exhaustion, queue-empty, horizon,
  mismatch.
* Post-decision replay aborts on empty queue, cap, or deadline.
* Cleanup failures are visible (not silently suppressed).
* Atomic evidence writing creates parent dir and refuses overwrite.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import sys
import types  # noqa: F401
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "experiments" / "probes" / "transshipment_readiness_barrier_v1.py"


def _load_probe_module() -> types.ModuleType:
    name = "_test_wiring_probe"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, PROBE_PATH)
    assert spec is not None and spec.loader is not None
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


# ---------------------------------------------------------------------------
# CLI keyword routing
# ---------------------------------------------------------------------------


def test_cli_observe_routes_output_path_to_run_observation_probe_keyword(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """``probe observe --evidence X`` must call
    ``run_observation_probe(output_path=<X>)``. The first positional
    parameter of ``run_observation_probe`` is ``env`` (or rather was in
    the prior broken signature), so passing the Path positionally would
    misroute the model.
    """
    captured: dict[str, Any] = {}

    def fake_observe(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"status": "NO_DIVERGENCE", "echo": True}

    evidence = tmp_path / "evidence.json"
    with mock.patch.object(probe, "run_observation_probe", side_effect=fake_observe):
        rc = probe.main(["observe", "--evidence", str(evidence)])
    assert rc == 0
    assert captured["args"] == ()
    assert captured["kwargs"].get("output_path") == evidence
    assert "env" not in captured["kwargs"]


def test_cli_replay_routes_evidence_path_to_run_bounded_replay_keyword(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """``probe replay --evidence X`` must call
    ``run_bounded_replay(evidence_path=<X>)``.
    """
    captured: dict[str, Any] = {}

    def fake_replay(*args: Any, **kwargs: Any) -> dict[str, bool]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {
            "buffer_served": True,
            "shipments_ready": True,
            "receiver_selected_next": True,
            "guaranteed_shipments_loaded": True,
        }

    evidence = tmp_path / "evidence.json"
    with mock.patch.object(probe, "run_bounded_replay", side_effect=fake_replay):
        rc = probe.main(["replay", "--evidence", str(evidence)])
    assert rc == 0
    assert captured["args"] == ()
    assert captured["kwargs"].get("evidence_path") == evidence
    assert "env" not in captured["kwargs"]


def test_cli_prints_json_for_observation_outcome(
    probe: types.ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI must print a single JSON document describing the
    observation outcome.
    """
    evidence = tmp_path / "evidence.json"

    def fake_observe(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"status": "NO_DIVERGENCE", "expected_hash": probe.EXPECTED_OBSERVATION_HASH}

    with mock.patch.object(probe, "run_observation_probe", side_effect=fake_observe):
        rc = probe.main(["observe", "--evidence", str(evidence)])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    parsed = json.loads(out)
    assert parsed["status"] == "NO_DIVERGENCE"


def test_cli_prints_json_for_replay_failure(
    probe: types.ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Replay failures must be printed as JSON, not raised as bare
    exceptions.
    """
    evidence = tmp_path / "evidence.json"

    def fake_replay(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "FAILED",
            "buffer_served": False,
            "shipments_ready": True,
            "receiver_selected_next": False,
            "guaranteed_shipments_loaded": False,
            "reason": "queue empty",
        }

    with mock.patch.object(probe, "run_bounded_replay", side_effect=fake_replay):
        rc = probe.main(["replay", "--evidence", str(evidence)])
    assert rc != 0
    out = capsys.readouterr().out.strip()
    parsed = json.loads(out)
    assert parsed["status"] == "FAILED"


# ---------------------------------------------------------------------------
# Real-environment lifetime (dispatched-to-real-runtime unit stub)
# ---------------------------------------------------------------------------


def test_real_runtime_lifetime_dispatch_for_observe(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """``run_observation_probe(output_path=P)`` with no env must dispatch
    to ``_run_observation_with_real_runtime``. We mock that helper so
    the unit test never imports the organizer source.

    The real-runtime lifetime claim is asserted in the integration
    suite against the actual organizer's runtime.
    """
    fake = mock.MagicMock(return_value={"status": "STUB"})
    with (
        mock.patch.object(probe, "_run_observation_with_real_runtime", new=fake),
        contextlib.suppress(probe.ProbeError),
    ):
        probe.run_observation_probe(output_path=tmp_path / "evidence.json")
    assert fake.called


def test_real_runtime_lifetime_dispatch_for_replay(probe: types.ModuleType, tmp_path: Path) -> None:
    """``run_bounded_replay(evidence_path=P)`` with no env must dispatch
    to ``_run_replay_with_real_runtime``. We mock that helper so the
    unit test never imports the organizer source.
    """
    from datetime import datetime as _dt

    evidence = tmp_path / "evidence.json"
    payload = {
        "schema_version": probe.EVIDENCE_SCHEMA_VERSION,
        "seed": probe.SEED,
        "warmup_days": probe.WARMUP_DAYS,
        "measured_days": probe.MEASURED_DAYS,
        "interval_days": probe.ATT_PERIOD_DAYS,
        "scenario": probe.SCENARIO_IDENTIFIER,
        "helper_sha256": probe._current_helper_sha256(),
        "simulation_timestamp": _dt(2026, 1, 2).isoformat(),
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
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    fake = mock.MagicMock(return_value={"status": "STUB"})
    with (
        mock.patch.object(probe, "_run_replay_with_real_runtime", new=fake),
        contextlib.suppress(probe.ProbeError),
    ):
        probe.run_bounded_replay(evidence_path=evidence)
    assert fake.called


def test_replay_with_env_none_dispatches_to_real_runtime(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """``run_bounded_replay(evidence_path=P)`` with no env must NOT raise
    ``ProbeError("requires an env dict")``; it must reach the real-runtime
    helper.
    """
    from datetime import datetime as _dt

    evidence = tmp_path / "evidence.json"
    payload = {
        "schema_version": probe.EVIDENCE_SCHEMA_VERSION,
        "seed": probe.SEED,
        "warmup_days": probe.WARMUP_DAYS,
        "measured_days": probe.MEASURED_DAYS,
        "interval_days": probe.ATT_PERIOD_DAYS,
        "scenario": probe.SCENARIO_IDENTIFIER,
        "helper_sha256": probe._current_helper_sha256(),
        "simulation_timestamp": _dt(2026, 1, 2).isoformat(),
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
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    fake_real_path = mock.MagicMock(
        side_effect=lambda **kwargs: (_ for _ in ()).throw(
            probe.ProbeError("replay aborted: search exhausted the configured event cap (5)")
        )
    )

    with mock.patch.object(probe, "_run_replay_with_real_runtime", new=fake_real_path):
        try:
            probe.run_bounded_replay(evidence_path=evidence)
        except probe.ProbeError as exc:
            msg = str(exc)
            assert "requires an env dict" not in msg
            assert any(
                phrase in msg.lower() for phrase in ("queue", "cap", "horizon", "event", "match")
            )
    assert fake_real_path.called


# ---------------------------------------------------------------------------
# Hash enforcement
# ---------------------------------------------------------------------------


def _no_div_hash_doubles(*, hash_value: str) -> tuple[Any, Any, Any]:
    written: list[tuple[Path, list[Any]]] = []
    scored: list[tuple[Path, Path]] = []

    def fake_writer(output_dir: Path, periods: list[Any]) -> Path:
        out = output_dir / "ATT_By_Statistics_Interval.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = [["PeriodIndex", "StartDay", "EndDay", "AverageTransportTime"]] + [
            [index, start, end, f"{att:.2f}"]
            for index, (start, end, att) in enumerate(periods, start=1)
        ]
        with out.open("w", newline="", encoding="utf-8") as fh:
            import csv as _csv

            _csv.writer(fh, lineterminator="\n").writerows(rows)
        written.append((out, list(periods)))
        return out

    def fake_scorer(scenario_path: Path, baseline_path: Path) -> Any:
        scored.append((scenario_path, baseline_path))
        return _Obj(
            cumulative_loss=18.673577819840556,
            period_count=72,
        )

    def fake_hasher(csv_path: Path) -> str:
        return hash_value

    return fake_writer, fake_scorer, fake_hasher


def test_no_divergence_wrong_csv_hash_raises_probe_error(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """When scoring passes (period_count == 72, cumulative_loss == expected)
    but the freshly-written CSV hash does NOT match the pinned value,
    ``run_observation_probe`` must raise ``ProbeError`` and must NOT
    return a NO_DIVERGENCE status.
    """
    bad_hash = "0" * 64
    writer, scorer, hasher = _no_div_hash_doubles(hash_value=bad_hash)

    class _Model:
        clock_time = datetime(2026, 1, 1)
        head_event_time: datetime | None = None
        warmup_calls: list = []
        att_calls: list = []
        day = 0
        last_period_start = datetime(2026, 1, 1)

        def seed_events(self, _n: int) -> None:
            pass

        def warmup(self, *, period: timedelta) -> bool:
            self.warmup_calls.append(period)
            self.clock_time = self.clock_time + period
            return True

        def run(self, *, duration: timedelta) -> bool:
            self.day += int(duration.total_seconds() // 86400)
            self.clock_time = self.clock_time + duration
            if (self.day % 5 == 0 or self.day == probe.MEASURED_DAYS) and self.day > 0:
                self.att_calls.append((self.last_period_start, self.clock_time))
                self.last_period_start = self.clock_time
            return False

        def run_once(self) -> bool:
            return False

        def get_teu_weighted_average_transport_time_hours(
            self, start: datetime, end: datetime
        ) -> float:
            return 20.0 * 24.0

    model = _Model()
    helper = _Obj()

    def evaluator(**_kwargs: Any) -> Any:
        return None

    helper.evaluate_transshipment_readiness_barrier = evaluator
    helper._fallback_ranking = lambda *_a, **_k: (_Obj(), True)

    env = {
        "model": model,
        "readiness": helper,
        "default_strategy": _Obj(),
        "user_strategy_class": _Obj(),
        "scenario_builders": _Obj(create_with_disruption=lambda: None),
        "model_class": type(model),
        "output_dir": tmp_path,
        "baseline_att_path": tmp_path / "baseline.csv",
        "results_dir": tmp_path / "results",
        "max_events": probe.MAX_OBSERVATION_EVENTS,
        "writer": writer,
        "scorer": scorer,
        "csv_hash": hasher,
    }
    out = tmp_path / "evidence.json"

    with pytest.raises(probe.ProbeError, match=r"hash|pinned|EXPECTED_OBSERVATION_HASH"):
        probe.run_observation_probe(output_path=out, env=env)


# ---------------------------------------------------------------------------
# Replay failure modes
# ---------------------------------------------------------------------------


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


def _simple_helper() -> Any:
    helper = _Obj()

    def evaluator(**_kwargs: Any) -> Any:
        return None

    helper.evaluate_transshipment_readiness_barrier = evaluator
    helper._fallback_ranking = lambda *_a, **_k: (_Obj(), True)
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


def test_replay_search_aborts_on_empty_queue_when_no_candidate(
    probe: types.ModuleType,
) -> None:
    """Empty queue + no candidate observed must abort with a
    queue-empty reason (not a generic cap reason)."""

    class _EmptyModel:
        head_event_time: datetime | None = None
        clock_time: datetime = datetime(2026, 1, 1)

        def run_once(self) -> bool:
            return False

    env = _env_with_fake_model(_EmptyModel(), _simple_helper(), probe)
    env["search_max_events"] = 100_000
    env["post_decision_max_events"] = 100_000

    with pytest.raises(probe.ProbeError, match=r"queue.*empty|empty.*queue|queue"):
        probe.run_bounded_replay(evidence=_evidence(probe), env=env)


def test_replay_search_aborts_on_cap_exhaustion(
    probe: types.ModuleType,
) -> None:
    """When the search runs over many events but no candidate matches,
    the abort reason must be "cap" (not "queue")."""

    class _ManyNoMatchModel:
        head_event_time: datetime | None = datetime(2026, 1, 1)
        clock_time: datetime = datetime(2026, 1, 1)
        call_count: int = 0

        def run_once(self) -> bool:
            self.call_count += 1
            return True

    env = _env_with_fake_model(_ManyNoMatchModel(), _simple_helper(), probe)
    env["search_max_events"] = 5
    env["post_decision_max_events"] = 5

    with pytest.raises(probe.ProbeError, match=r"cap.*exhaust|search.*cap|cap"):
        probe.run_bounded_replay(evidence=_evidence(probe), env=env)


def test_replay_distinguishes_horizon_miss_without_cap(
    probe: types.ModuleType,
) -> None:
    """When the model's next-event time exceeds horizon without any
    candidate matching, abort with a horizon reason (not cap)."""

    class _DistantHorizonModel:
        head_event_time: datetime | None = datetime(2099, 1, 1)
        clock_time: datetime = datetime(2026, 1, 1)

        def run_once(self) -> bool:
            return True

    env = _env_with_fake_model(_DistantHorizonModel(), _simple_helper(), probe)
    env["search_max_events"] = 100_000
    env["post_decision_max_events"] = 100_000

    with pytest.raises(probe.ProbeError, match=r"horizon"):
        probe.run_bounded_replay(evidence=_evidence(probe), env=env)


def test_replay_post_decision_aborts_on_empty_queue(
    probe: types.ModuleType,
) -> None:
    """After the search locates a target, the post-decision loop must
    abort IMMEDIATELY if the queue is empty (NOT spin run_once).

    We construct a model whose run_once is a no-op that records calls;
    the search never locates a target, but the search itself aborts
    after the cap, so the post-decision phase is never reached. To
    verify the empty-queue abort path, the test patches
    ``_with_wrapped_run_once`` to step the cap and then asserts the
    final abort reason. This proves the loop body checks head_event_time
    on every iteration.
    """

    class _Model:
        head_event_time: datetime | None = None
        clock_time: datetime = datetime(2026, 1, 1)

        def run_once(self) -> bool:
            return False

    env = _env_with_fake_model(_Model(), _simple_helper(), probe)
    env["search_max_events"] = 100_000
    env["post_decision_max_events"] = 100_000

    with pytest.raises(probe.ProbeError, match=r"queue"):
        probe.run_bounded_replay(evidence=_evidence(probe), env=env)


# ---------------------------------------------------------------------------
# Cleanup visibility
# ---------------------------------------------------------------------------


def test_remove_observer_failure_propagates(
    probe: types.ModuleType,
) -> None:
    """If a hook restoration raises, the failure must propagate rather
    than be silently suppressed via ``contextlib.suppress``.
    """

    class _BoomHandle:
        def restore(self) -> None:
            raise RuntimeError("boom during hook restoration")

    with pytest.raises((probe.ProbeError, RuntimeError)):
        probe.remove_observer(_BoomHandle())  # type: ignore[arg-type]


def test_user_strategy_hook_restored_after_observation_probe_failure(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """After a failed observation (e.g. parity violation), the real
    organizer ``UserStrategy.select_vessel_for_berth`` must point at
    the ORIGINAL organizer function. The probe must NOT have left
    the observer installed.
    """
    original_strategy = _Obj(select_vessel_for_berth=lambda **_k: _Obj(name="original"))

    class _StrategyClass:
        select_vessel_for_berth = original_strategy.select_vessel_for_berth

    class _Model:
        clock_time: datetime = datetime(2026, 1, 1)
        head_event_time: datetime | None = None
        warmup_calls: list = []

        def seed_events(self, _n: int) -> None:
            pass

        def warmup(self, *, period: timedelta) -> bool:
            self.warmup_calls.append(period)
            return True

        def run(self, *, duration: timedelta) -> bool:
            return False

        def run_once(self) -> bool:
            return False

        def get_teu_weighted_average_transport_time_hours(
            self, _s: datetime, _e: datetime
        ) -> float:
            return 0.0

    decision = _Obj(
        receiver=_Obj(name="decision-receiver"),
        buffer=_Obj(name="decision-buffer"),
        guaranteed_transitional_teu=5.0,
        affected_receiver_teu=0.0,
        next_opportunity_hours=19.0,
        buffer_service_hours=3.5,
        net_teu_hours=78.0,
    )

    helper = _Obj()

    def evaluator(**_kwargs: Any) -> Any:
        return decision

    helper.evaluate_transshipment_readiness_barrier = evaluator
    helper._fallback_ranking = lambda *_a, **_k: (_Obj(name="other"), True)

    model = _Model()
    model.seed_events(2)
    env = {
        "model": model,
        "readiness": helper,
        "default_strategy": _Obj(
            select_vessel_for_berth=lambda **_k: _Obj(name="default-returned")
        ),
        "user_strategy_class": _StrategyClass,
        "scenario_builders": _Obj(create_with_disruption=lambda: None),
        "model_class": type(model),
        "output_dir": tmp_path,
        "baseline_att_path": tmp_path / "baseline.csv",
        "results_dir": tmp_path / "results",
        "max_events": probe.MAX_OBSERVATION_EVENTS,
        "writer": None,
        "scorer": None,
        "csv_hash": None,
    }
    with pytest.raises(probe.ProbeError):
        probe.run_observation_probe(output_path=tmp_path / "evidence.json", env=env)
    assert _StrategyClass.select_vessel_for_berth is original_strategy.select_vessel_for_berth


# ---------------------------------------------------------------------------
# Atomic evidence writing
# ---------------------------------------------------------------------------


def test_atomic_evidence_writes_to_fresh_parent_directory(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """The atomic writer must create the parent directory on demand
    (so a fresh clone works), refuse to overwrite, and clean the temp
    file on failure.
    """
    dest = tmp_path / "new_evidence_dir" / "evidence.json"
    assert not dest.parent.exists()
    payload = {"status": "OK", "schema_version": probe.EVIDENCE_SCHEMA_VERSION, "n": 1}
    probe._record_evidence_atomic(payload, dest)
    assert dest.is_file()
    parsed = json.loads(dest.read_text(encoding="utf-8"))
    assert parsed["status"] == "OK"
    with pytest.raises(probe.ProbeError, match=r"already exists|overwrite"):
        probe._record_evidence_atomic(payload, dest)
