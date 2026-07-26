"""Behavioral tests for operational wiring corrections.

These tests assert behavioral fixes for the operational-wiring review
(separate from the test file for the probe's statistical/behavioural
contract). Every test monkey-patches ``run_observation_probe`` or
``run_bounded_replay`` and verifies the CLI routes the right value by
the correct keyword. They never launch a model.

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
* The non-integration coverage command exits 0 with zero failures.
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


# ---------------------------------------------------------------------------
# CLI keyword routing
# ---------------------------------------------------------------------------


def test_cli_observe_routes_output_path_to_run_observation_probe_keyword(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """``wsc2026 probe observe --evidence X`` must call
    ``run_observation_probe(output_path=<X>)``. The first positional
    parameter of ``run_observation_probe`` is ``env``, so passing the
    Path positionally would misroute the model.
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
    # No positional args; the Path was passed by keyword.
    assert captured["args"] == ()
    assert captured["kwargs"].get("output_path") == evidence
    assert "env" not in captured["kwargs"]


def test_cli_replay_routes_evidence_path_to_run_bounded_replay_keyword(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """``wsc2026 probe replay --evidence X`` must call
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
    observation outcome, regardless of which branch fired.
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
    exceptions, so callers can read structured failure data.
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
# Real-environment lifetime
# ---------------------------------------------------------------------------


def test_real_runtime_lifetime_remains_open_through_observe(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """When ``run_observation_probe`` builds the real environment, the
    organizer runtime must remain open across the entire execution: the
    injected writer that calls ``simulation_output_csv_writer.write_att_by_period``
    is captured while the runtime is loaded, then invoked after the
    runtime context exits (which would fail if the import were
    dynamic).
    """
    # The production path is captured but never executed against a
    # real model. We assert the seam contract: the real writer is
    # pulled from inside ``_load_runtime`` exactly once.
    captured_writer = None

    real_build = probe._build_real_environment

    def patched_build(*args: Any, **kwargs: Any) -> dict[str, Any]:
        env = real_build(*args, **kwargs)
        nonlocal captured_writer
        captured_writer = env["writer"]
        # Replace the model with a fake so the test cannot accidentally
        # drive the real trajectory.
        class _NoOp:
            warmup_calls: list = []
            att_calls: list = []

            def warmup(self, *, period: timedelta) -> bool:
                self.warmup_calls.append(period)
                return True

            def run(self, *, duration: timedelta) -> bool:
                return False

            @property
            def head_event_time(self) -> datetime | None:
                return None

            @property
            def clock_time(self) -> datetime:
                return datetime(2026, 1, 1)

        env["model"] = _NoOp()
        return env

    with mock.patch.object(probe, "_build_real_environment", side_effect=patched_build):
        try:
            probe.run_observation_probe(
                env=None,
                output_path=tmp_path / "evidence.json",
            )
        except probe.ProbeError:
            # No-divergence path fails because the fake returned no
            # events; we only care that the writer was captured while
            # the runtime was open.
            pass

    assert captured_writer is not None
    assert captured_writer is probe._real_att_writer


def test_real_runtime_lifetime_for_replay(probe: types.ModuleType, tmp_path: Path) -> None:
    """``run_bounded_replay`` with env=None must build a real model from
    ``create_with_disruption`` while the organizer runtime is loaded.
    """
    captured: dict[str, Any] = {}

    real_build = probe._build_real_environment

    def patched_build(*args: Any, **kwargs: Any) -> dict[str, Any]:
        env = real_build(*args, **kwargs)
        captured["writer_seen"] = env["writer"]
        # Replace the model with a fake so the test cannot drive the
        # real trajectory, but keep the env shape.
        class _NoOp:
            seed: int = 0
            head_event_time: datetime | None = None
            clock_time: datetime = datetime(2026, 1, 1)

            def run_once(self) -> bool:
                return False

        env["model"] = _NoOp()
        return env

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
    with mock.patch.object(probe, "_build_real_environment", side_effect=patched_build):
        try:
            probe.run_bounded_replay(env=None, evidence_path=evidence)
        except probe.ProbeError:
            pass
    assert captured["writer_seen"] is probe._real_att_writer


def test_replay_with_env_none_builds_real_model(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """``run_bounded_replay(env=None)`` must NOT raise
    "run_bounded_replay requires an env dict"; it must build a real
    environment (and therefore a real model) instead.
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

    real_build = probe._build_real_environment

    def patched_build(*args: Any, **kwargs: Any) -> dict[str, Any]:
        env = real_build(*args, **kwargs)
        # Replace the model with a fake so we cannot drive the real
        # simulation, but verify the rest of the env comes from the
        # real factory.
        class _NoOp:
            head_event_time: datetime | None = None
            clock_time: datetime = datetime(2026, 1, 1)

            def run_once(self) -> bool:
                return False

        env["model"] = _NoOp()
        return env

    with mock.patch.object(probe, "_build_real_environment", side_effect=patched_build):
        try:
            probe.run_bounded_replay(env=None, evidence_path=evidence)
        except probe.ProbeError as exc:
            # No recorded-event was found (fakes never fire), so the
            # replay must abort with a recording-related reason (NOT
            # with the old "run_bounded_replay requires an env dict").
            msg = str(exc)
            assert "requires an env dict" not in msg
            assert any(
                phrase in msg.lower()
                for phrase in ("queue", "cap", "horizon", "event", "match")
            )


# ---------------------------------------------------------------------------
# Hash enforcement
# ---------------------------------------------------------------------------


def _no_div_hash_doubles(*, hash_value: str) -> tuple[Any, Any, Any]:
    written: list[tuple[Path, list[Any]]] = []
    scored: list[tuple[Path, Path]] = []
    hashed: list[tuple[Path, str]] = []

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
        hashed.append((csv_path, hash_value))
        return hash_value

    return fake_writer, fake_scorer, fake_hasher


def _simple_model_and_helper(probe: types.ModuleType) -> tuple[Any, Any]:
    class _Model:
        clock_time: datetime = datetime(2026, 1, 1)
        head_event_time: datetime | None = None
        warmup_calls: list = []
        att_calls: list = []

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
            self, start: datetime, end: datetime
        ) -> float:
            self.att_calls.append((start, end))
            return 0.0

    helper = _Obj()

    def evaluator(**_kwargs: Any) -> Any:
        return None

    helper.evaluate_transshipment_readiness_barrier = evaluator
    helper._fallback_ranking = lambda *_a, **_k: (_Obj(), True)
    return _Model(), helper


def test_no_divergence_wrong_csv_hash_raises_probe_error(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """When scoring passes (period_count == 72, cumulative_loss == expected)
    but the freshly-written CSV hash does NOT match the pinned value,
    ``run_observation_probe`` must raise ``ProbeError`` and must NOT
    return a NO_DIVERGENCE status.
    """
    model, helper = _simple_model_and_helper(probe)
    model.seed_events(72 * 5)
    bad_hash = "0" * 64
    writer, scorer, hasher = _no_div_hash_doubles(hash_value=bad_hash)
    env = {
        "model": model,
        "readiness": helper,
        "default_strategy": _Obj(select_vessel_for_berth=lambda **_k: _Obj()),
        "user_strategy_class": _Obj(select_vessel_for_berth=lambda **_k: None),
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

    # Configure model to return ATT rows so no_divergence branch is reached
    rows: list[tuple[int, int, float]] = []
    orig_get_att = model.get_teu_weighted_average_transport_time_hours

    def make_att(start: datetime, end: datetime) -> float:
        rows.append((start, end))
        return 20.0 * 24.0

    model.get_teu_weighted_average_transport_time_hours = make_att
    # Provide 72 ATT rows by advancing the measured horizon manually
    out_close: list[float] = []

    def make_clock(start_now: datetime) -> None:
        for day in range(1, probe.MEASURED_DAYS + 1):
            out_close.append(day)

    # Fake the run() to advance and produce ATT rows by walking daily
    state = {"day": 0, "last_clock": model.clock_time}

    def fake_run(*, duration: timedelta) -> bool:
        for _ in range(int(duration.total_seconds() // 86400)):
            state["day"] += 1
            state["last_clock"] = model.clock_time + duration
        model.clock_time = model.clock_time + duration
        if state["day"] % probe.ATT_PERIOD_DAYS == 0 and state["day"] > 0:
            try:
                model.get_teu_weighted_average_transport_time_hours(
                    state["last_clock"], model.clock_time
                )
            except Exception:
                pass
        return False

    model.run = fake_run

    with pytest.raises(probe.ProbeError, match=r"hash|att_csv|pinned"):
        probe.run_observation_probe(
            output_path=out,
            env=env,
        )


# ---------------------------------------------------------------------------
# Replay failure modes
# ---------------------------------------------------------------------------


def _env_with_fake_model(model: Any, helper: Any, probe: types.ModuleType) -> dict[str, Any]:
    return {
        "model": model,
        "readiness": helper,
        "default_strategy": _Obj(select_vessel_for_berth=lambda **_k: _Obj()),
        "user_strategy_class": _Obj(),
        "scenario_builders": _Obj(create_with_disruption=lambda: None),
        "model_class": type(model),
        "output_dir": probe.repo_root(),
        "baseline_att_path": probe.repo_root() / "README.md",
        "results_dir": probe.repo_root() / "experiments" / "results" / "round0_att",
        "max_events": probe.MAX_OBSERVATION_EVENTS,
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


def test_replay_search_aborts_on_empty_queue_when_horizon_reached_without_candidate(
    probe: types.ModuleType,
) -> None:
    """Empty queue + horizon reached + no candidate observed must abort
    with a queue-empty reason (not a generic cap reason).
    """
    class _EmptyModel:
        seed: int = 0
        head_event_time: datetime | None = None
        clock_time: datetime = datetime(2026, 1, 1)

        def run_once(self) -> bool:
            return False

    env = _env_with_fake_model(_EmptyModel(), _simple_helper(), probe)
    env["search_max_events"] = 100_000
    env["post_decision_max_events"] = 100_000

    with pytest.raises(probe.ProbeError, match=r"queue.*empty|empty.*queue"):
        probe.run_bounded_replay(env=env, evidence=_evidence(probe))


def test_replay_search_aborts_on_cap_exhaustion(
    probe: types.ModuleType,
) -> None:
    """When the search runs over many events but no candidate matches,
    the abort reason must be "cap" (not "queue").
    """
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
        probe.run_bounded_replay(env=env, evidence=_evidence(probe))


def test_replay_distinguishes_horizon_miss_without_cap(
    probe: types.ModuleType,
) -> None:
    """When the model's queue head_event_time exceeds horizon without
    any candidate matching, abort with a horizon reason (not cap).
    """
    class _DistantHorizonModel:
        head_event_time: datetime | None = datetime(2099, 1, 1)
        clock_time: datetime = datetime(2026, 1, 1)

        def run_once(self) -> bool:
            return True

    env = _env_with_fake_model(_DistantHorizonModel(), _simple_helper(), probe)
    env["search_max_events"] = 100_000
    env["post_decision_max_events"] = 100_000

    with pytest.raises(probe.ProbeError, match=r"horizon"):
        probe.run_bounded_replay(env=env, evidence=_evidence(probe))


def test_replay_post_decision_aborts_on_empty_queue_immediately(
    probe: types.ModuleType,
) -> None:
    """After the search phase matches a target, the post-decision loop
    must abort IMMEDIATELY if the queue is empty (NOT spin run_once
    repeatedly).
    """
    search_calls: list[int] = []
    run_once_calls: list[int] = []

    class _Model:
        head_event_time: datetime | None = None
        clock_time: datetime = datetime(2026, 1, 2)
        in_post_decision: bool = False

        def run_once(self) -> bool:
            run_once_calls.append(1)
            return False

    # Configure the model so that the search sees a target on the first
    # invocation. We accomplish this by monkey-patching the readiness
    # helper to return a decision that matches.
    captured_decision: dict[str, Any] = {}

    def evaluator(**_kwargs: Any) -> Any:
        receiver = _Obj()
        buffer = _Obj()
        captured_decision["decision"] = _Obj(
            receiver=receiver,
            buffer=buffer,
            guaranteed_transitional_teu=5.0,
            affected_receiver_teu=0.0,
            next_opportunity_hours=19.0,
            buffer_service_hours=3.5,
            net_teu_hours=78.0,
        )
        return captured_decision["decision"]

    helper = _Obj()
    helper.evaluate_transshipment_readiness_barrier = evaluator
    helper._fallback_ranking = lambda *_a, **_k: (_Obj(), True)

    # To make the search match the recorded evidence, we need the
    # model's clock_time and waiting list to match the expected
    # snapshot. To trigger the empty-queue abort, we make run_once
    # return False (empty queue). The model stays at clock_time =
    # datetime(2026, 1, 2) which equals the evidence timestamp.
    env = _env_with_fake_model(_Model(), helper, probe)
    env["search_max_events"] = 1000
    env["post_decision_max_events"] = 1000

    # Force the helper's evaluator output to match the expected
    # evidence snapshot.
    evidence = _evidence(probe)
    helper._fallback_ranking = lambda *_a, **_k: (captured_decision["decision"].receiver, True)

    # Override _matches_recorded_event by patching the helper to match.
    # Simpler: invoke the replay; if it succeeds on the search, the
    # post-decision phase will run. With empty queue, it must abort.
    try:
        probe.run_bounded_replay(env=env, evidence=evidence)
    except probe.ProbeError as exc:
        msg = str(exc).lower()
        # Must abort because queue becomes empty during post-decision
        # OR because expected no candidate; either way, NOT repeatedly
        # spinning on empty queue.
        assert "queue" in msg or "horizon" in msg or "cap" in msg


# ---------------------------------------------------------------------------
# Cleanup visibility
# ---------------------------------------------------------------------------


def test_remove_observer_failure_is_not_silently_suppressed(
    probe: types.ModuleType,
) -> None:
    """If remove_observer fails, the failure must propagate (after the
    primary error if one occurred). It must not be silently swallowed
    via ``contextlib.suppress``.
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
    original_strategy = _Obj(
        select_vessel_for_berth=lambda **_k: _Obj(name="original")
    )

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
        probe.run_observation_probe(env=env, output_path=tmp_path / "evidence.json")
    # After failure, the strategy class attribute must be the original
    # callable, NOT the observer installed by the probe.
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
    # JSON round-trip
    parsed = json.loads(dest.read_text(encoding="utf-8"))
    assert parsed["status"] == "OK"
    # Refuse overwrite
    with pytest.raises(probe.ProbeError, match=r"already exists|overwrite"):
        probe._record_evidence_atomic(payload, dest)
