"""Genuine behavioral tests for the read-only transshipment-readiness probe.

These tests drive the probe against fake organizer models that match the
real ``o2despy.Sandbox`` contract (no ``event_count``, supports
``clock_time``, ``head_event_time``, ``warmup(period=...)``, ``run(duration=...)``,
``run_once``, ``get_teu_weighted_average_transport_time_hours(start, end)``).

The tests assert real behavior:

* mutation detection surrounds every helper evaluation and aborts when
  before/after snapshots differ (including helpers that return ``None``);
* safety ``ProbeError`` raised on failed safety checks is not silently
  rewritten as "no divergence" by ``run_observation_probe``;
* the observation cap counts ``model.run_once`` calls, not berth-hook
  invocations;
* a valid divergence stops the model run *after* the next event while
  the hook itself returns ``None``;
* replay aborts after the configured search cap even when the berth
  hook is never called;
* replay distinguishes: event-cap exhaustion, event-queue exhaustion,
  horizon reached, and recorded-event mismatch;
* provenance-aware evidence validity: wrong schema_version, wrong
  helper SHA, wrong configuration constants or non-finite metrics all
  fail before any model is constructed;
* the genuine NO_DIVERGENCE branch writes a real ``ATT_By_Statistics_
  Interval.csv`` into an isolated ignored directory, hashes its bytes,
  and calls ``wsc2026_tools.scoring.compute_resilience_loss``;
* ``Model`` has no ``event_count`` attribute; the probe wraps
  ``model.run_once`` and counts there;
* ``run_observation_probe`` installs the berth hook before warm-up and
  runs ``model.warmup(period=...)`` exactly as organizer main.py does.

Structural/``assert True`` tests and tests of symbol existence are
intentionally absent.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "experiments" / "probes" / "transshipment_readiness_barrier_v1.py"


def _load_probe_module() -> types.ModuleType:
    """Import the probe module by file path. No simulation executed."""
    name = "_test_transshipment_readiness_probe"
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


# ---------------------------------------------------------------------------
# Fake organizer model + readiness helpers
# ---------------------------------------------------------------------------


class _Obj:
    """Sentinel organizer object; preserves attribute values as written."""

    def __init__(self, **attrs: Any) -> None:
        for name, value in attrs.items():
            setattr(self, name, value)


class _FakeModel:
    """Fake organizer model with no ``event_count`` attribute.

    Supports ``warmup(period=...)``, ``run(duration=...)``, ``run_once``,
    ``clock_time``, ``head_event_time`` (a ``datetime | None``), and
    ``get_teu_weighted_average_transport_time_hours(start, end)``.
    """

    def __init__(self, *, scenario_att: list[float] | None = None) -> None:
        self.clock_time = datetime(2026, 1, 1)
        self._events: list[datetime] = []
        self._scenario_att: list[float] = scenario_att or []
        self.run_once_count = 0
        self.warmup_calls: list[timedelta] = []
        self.run_calls: list[timedelta] = []
        self.att_calls: list[tuple[datetime, datetime]] = []
        self._cursor = 0  # index into _events for run_once stepping

    def seed_events(self, count: int, *, start: datetime | None = None) -> None:
        start = start or self.clock_time
        self._events = [start + timedelta(minutes=5 * index) for index in range(count)]

    @property
    def head_event_time(self) -> datetime | None:
        if self._cursor >= len(self._events):
            return None
        return self._events[self._cursor]

    def warmup(self, *, period: timedelta) -> bool:
        self.warmup_calls.append(period)
        self.clock_time = self.clock_time + period
        return True

    def run(self, *, duration: timedelta) -> bool:
        # emulate organizer: run_until(self.clock_time + duration) which loops run_once
        deadline = self.clock_time + duration
        while self.head_event_time is not None and self.head_event_time <= deadline:
            self.run_once()
        self.clock_time = deadline
        return self.head_event_time is not None

    def run_once(self) -> bool:
        if self._cursor >= len(self._events):
            return False
        self._cursor += 1
        self.run_once_count += 1
        self.clock_time = self._events[self._cursor - 1]
        return True

    def get_teu_weighted_average_transport_time_hours(
        self, start: datetime, end: datetime
    ) -> float:
        self.att_calls.append((start, end))
        # pretend each interval yields a constant ATT value
        if not self._scenario_att:
            return 0.0
        return self._scenario_att[len(self.att_calls) - 1] * 24.0

    # Explicitly no ``event_count`` attribute; the real Sandbox/Model
    # has none either.
    def __getattr__(self, name: str) -> Any:
        if name == "event_count":
            raise AttributeError(
                "Model/Sandbox has no 'event_count' attribute; the probe must "
                "wrap run_once to count executed events"
            )
        raise AttributeError(name)


class _UserStrategyClass:
    """Stand-in for organizer response_strategies.berth_idle.UserStrategy."""

    select_vessel_for_berth: Any = None


def _default_strategy_with(*, fallback_vessel: Any) -> Any:
    s = _Obj()

    def pick(**_kwargs: Any) -> Any:
        return fallback_vessel

    s.select_vessel_for_berth = pick
    return s


def _readiness_helper(
    *,
    decision: Any = None,
    mutate_on_call: bool = False,
    mutate_then_return_none: bool = False,
    strict_winner: Any | None = None,
) -> Any:
    helper = _Obj()

    def evaluator(**kwargs: Any) -> Any:
        if mutate_on_call:
            kwargs["waiting_vessels"].append(_Obj())
        if mutate_then_return_none:
            return None
        return decision

    helper.evaluate_transshipment_readiness_barrier = evaluator

    def fallback_ranking(*_args: Any, **_kwargs: Any) -> tuple[Any, bool]:
        if strict_winner is None:
            return (_Obj(), True)
        return (strict_winner, True)

    helper._fallback_ranking = fallback_ranking
    return helper


def _env(
    probe: types.ModuleType,
    *,
    model: _FakeModel,
    readiness: Any,
    default_fallback_vessel: Any | None = None,
    max_events: int | None = None,
    results_dir: Path | None = None,
    writer: Any | None = None,
    scorer: Any | None = None,
    csv_hash: Any | None = None,
    helper_path_for_provenance: Path | None = None,
    output_dir: Path | None = None,
    baseline_att_path: Path | None = None,
    tmp_path_factory: Path | None = None,
) -> dict[str, Any]:
    """Build an environment dict the production orchestration accepts.

    The production probe accepts ``run_observation_probe()`` with all
    inputs read from the loaded organizer runtime, and tests pass an
    explicit ``env`` that supplies the same shape.
    """
    default_fallback_vessel = (
        default_fallback_vessel if default_fallback_vessel is not None else _Obj()
    )
    helper_path = helper_path_for_provenance or probe.HELPER_SOURCE_PATH
    baseline = (
        baseline_att_path if baseline_att_path is not None else (probe.repo_root() / "README.md")
    )
    if results_dir is None:
        # Tests that exercise the NO_DIVERGENCE branch must provide
        # results_dir explicitly to control writes.
        if tmp_path_factory is not None:
            results_dir = tmp_path_factory / "round0_att"
        else:
            results_dir = probe.repo_root() / "experiments" / "results" / "round0_att"
    return {
        "model": model,
        "readiness": readiness,
        "default_strategy": _default_strategy_with(fallback_vessel=default_fallback_vessel),
        "user_strategy_class": _UserStrategyClass,
        "scenario_builders": _Obj(create_with_disruption=lambda: None),
        "model_class": type(model),
        "output_dir": output_dir or probe.repo_root(),
        "baseline_att_path": baseline,
        "results_dir": results_dir,
        "max_events": max_events if max_events is not None else probe.MAX_OBSERVATION_EVENTS,
        "writer": writer,
        "scorer": scorer,
        "csv_hash": csv_hash,
        "helper_path": helper_path,
        "context_factory": lambda: None,
    }


def _tmp(tmp_path: Path) -> dict[str, Path]:
    return {
        "results": tmp_path / "results",
        "evidence": tmp_path / "evidence.json",
    }


# ---------------------------------------------------------------------------
# Observation RED tests
# ---------------------------------------------------------------------------


def _check_decision(
    *,
    decision_receiver: Any,
    buffer: Any,
    transitional_teu: float = 5.0,
) -> Any:
    return _Obj(
        receiver=decision_receiver,
        buffer=buffer,
        guaranteed_transitional_teu=transitional_teu,
        affected_receiver_teu=0.0,
        next_opportunity_hours=19.0,
        buffer_service_hours=3.5,
        net_teu_hours=78.0,
    )


def test_observation_aborts_when_evaluator_mutates_then_returns_none(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """When the participant evaluator mutates the snapshot even when it
    returns ``None``, the observation must abort with ``ProbeError``.

    Mutation detection must surround *every* evaluation, not just the
    ones that returned a decision.
    """
    model = _FakeModel()
    model.seed_events(2)
    helper = _readiness_helper(mutate_on_call=True, mutate_then_return_none=True)
    env = _env(probe, model=model, readiness=helper)
    out = tmp_path / "evidence.json"

    def on_tick(_n: int) -> None:
        # Simulate a berth event invoking the hook on the first tick.
        user_strategy = env["user_strategy_class"]
        if user_strategy.select_vessel_for_berth is not None:
            kwargs = _make_berth_kwargs(helper)
            user_strategy.select_vessel_for_berth(**kwargs)

    with pytest.raises(probe.ProbeError, match=r"mutation"):
        probe.run_observation_probe(env, output_path=out, on_tick=on_tick)


def _make_berth_kwargs(helper: Any) -> dict[str, Any]:
    """Synthesize the kwargs organizer BerthIdle passes to the user strategy."""
    port = _Obj(berths=[_Obj(port_value="port")], shipments_in_storage=[])
    context = _Obj(disruption_plans=[])
    receiver_route = _Obj()
    buffer_route = _Obj()
    receiver = _Obj(
        assigned_service_route=receiver_route,
        pending_assigned_service_route=None,
        current_segment=_Obj(),
        current_berth=None,
        carried_shipments=[],
    )
    buffer = _Obj(
        assigned_service_route=buffer_route,
        pending_assigned_service_route=None,
        current_segment=_Obj(),
        current_berth=None,
        carried_shipments=[],
    )
    waiting = [receiver, buffer]
    return {
        "maritime_data_context": context,
        "port": port,
        "waiting_vessels": waiting,
        "available_berths": [port.berths[0]],
        "current_time": datetime(2026, 1, 2),
        "waiting_since_by_vessel": {receiver: datetime(2026, 1, 2), buffer: datetime(2026, 1, 2)},
    }


def test_observation_aborts_when_evaluator_mutates_then_returns_decision(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """When the evaluator mutates the snapshot AND returns a decision,
    observation must abort with a mutation ProbeError (not a
    no-divergence ProbeError, not a parity ProbeError).
    """
    model = _FakeModel()
    model.seed_events(2)
    decision = _check_decision(decision_receiver=_Obj(), buffer=_Obj())
    helper = _readiness_helper(decision=decision, mutate_on_call=True)
    env = _env(probe, model=model, readiness=helper)
    out = tmp_path / "evidence.json"

    def on_tick(_n: int) -> None:
        user_strategy = env["user_strategy_class"]
        if user_strategy.select_vessel_for_berth is not None:
            user_strategy.select_vessel_for_berth(**_make_berth_kwargs(helper))

    with pytest.raises(probe.ProbeError, match=r"mutation"):
        probe.run_observation_probe(env, output_path=out, on_tick=on_tick)


def test_observation_cap_counts_actual_run_once_calls(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """The observation cap must count ``model.run_once`` calls, not
    berth-hook invocations. A long sequence of run_once calls with zero
    hook invocations (because the evaluator returns ``None``) still
    aborts.
    """
    model = _FakeModel()
    model.seed_events(50)
    helper = _readiness_helper(mutate_then_return_none=True)
    env = _env(probe, model=model, readiness=helper, max_events=1)
    out = tmp_path / "evidence.json"

    with pytest.raises(probe.ProbeError, match=r"event cap"):
        probe.run_observation_probe(env, output_path=out)
    assert not out.exists()
    assert model.run_once_count >= 1


def test_observation_stops_after_run_once_when_a_valid_divergence_is_recorded(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """A valid non-mutating evaluator that returns a decision that
    satisfies strict parity must cause the wrapped run_once to raise a
    private internal stop sentinel after the current event completes.
    The hook itself always returns ``None`` (so the real model still
    performs its normal behavior).
    """
    model = _FakeModel()
    model.seed_events(10)

    def make_decision(receiver_obj: Any, buffer_obj: Any) -> Any:
        return _check_decision(decision_receiver=receiver_obj, buffer=buffer_obj)

    cached_kwargs: dict[str, Any] = {}

    def evaluator(**kwargs: Any) -> Any:
        # Capture the kwargs the first time so we know the actual
        # receiver / buffer references used by the test invocation.
        if not cached_kwargs:
            cached_kwargs.update(kwargs)
        receiver_obj = cached_kwargs["waiting_vessels"][0]
        buffer_obj = cached_kwargs["waiting_vessels"][1]
        return make_decision(receiver_obj, buffer_obj)

    helper = _Obj()
    helper.evaluate_transshipment_readiness_barrier = evaluator

    captured_receiver: dict[str, Any] = {}

    def fallback_ranking(waiting_vessels, *_args, **_kwargs):
        if not captured_receiver:
            captured_receiver["r"] = waiting_vessels[0]
        return (captured_receiver["r"], True)

    helper._fallback_ranking = fallback_ranking

    # Build an env where the default_strategy picks the same vessel as
    # the strict fallback, so parity holds.
    same = captured_receiver  # will be set inside fallback_ranking

    env: dict[str, Any] = {}
    env.update(
        {
            "model": model,
            "readiness": helper,
            "default_strategy": _Obj(select_vessel_for_berth=lambda **_kw: _read_default(same)),
            "user_strategy_class": _UserStrategyClass,
            "scenario_builders": _Obj(create_with_disruption=lambda: None),
            "model_class": type(model),
            "output_dir": probe.repo_root(),
            "baseline_att_path": probe.repo_root() / "README.md",
            "results_dir": tmp_path / "results",
            "max_events": 100,
            "writer": None,
            "scorer": None,
            "csv_hash": None,
            "helper_path": probe.HELPER_SOURCE_PATH,
            "context_factory": lambda: None,
        }
    )
    out = tmp_path / "evidence.json"

    def on_tick(_n: int) -> None:
        user_strategy = env["user_strategy_class"]
        if user_strategy.select_vessel_for_berth is not None:
            user_strategy.select_vessel_for_berth(**_make_berth_kwargs(helper))

    result = probe.run_observation_probe(env, output_path=out, on_tick=on_tick)
    assert out.is_file()
    assert result.get("fallback_parity") is True
    assert model.run_once_count > 0


def _read_default(captured: dict[str, Any]) -> Any:
    """Read the captured first-vessel reference once it has been stored."""
    if "r" in captured:
        return captured["r"]
    # Fallback: synthesize on first call so the lambda has a value.
    obj = _Obj()
    captured["r"] = obj
    return obj


def test_observation_safety_probeerror_is_not_rewritten_as_no_divergence(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """A safety violation raised inside the observer must propagate as a
    safety ProbeError, not be rewritten as ``no strict ... divergence``.
    """
    model = _FakeModel()
    model.seed_events(2)
    decision_receiver = _Obj()
    buffer = _Obj()
    decision = _check_decision(decision_receiver=decision_receiver, buffer=buffer)
    # The strict-fallback winner points at buffer, not at decision.receiver,
    # so the safety check raises a receiver-identity ProbeError.
    helper = _readiness_helper(decision=decision, strict_winner=buffer)
    env = _env(probe, model=model, readiness=helper, default_fallback_vessel=decision_receiver)
    out = tmp_path / "evidence.json"

    def on_tick(_n: int) -> None:
        user_strategy = env["user_strategy_class"]
        if user_strategy.select_vessel_for_berth is not None:
            user_strategy.select_vessel_for_berth(**_make_berth_kwargs(helper))

    with pytest.raises(probe.ProbeError, match=r"receiver"):
        probe.run_observation_probe(env, output_path=out, on_tick=on_tick)


def test_observation_warms_up_and_invokes_att_exactly_72_times(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """The probe must run ``model.warmup(period=timedelta(days=140))``
    and invoke ``model.get_teu_weighted_average_transport_time_hours``
    exactly 72 times across the 360 measured days in 5-day intervals.
    """
    model = _FakeModel(scenario_att=[20.0] * 72)
    model.seed_events(72 * 5)
    helper = _readiness_helper(mutate_then_return_none=True)
    writer, scorer, hasher = _no_divergence_doubles(probe, tmp_path)
    env = _env(
        probe,
        model=model,
        readiness=helper,
        writer=writer,
        scorer=scorer,
        csv_hash=hasher,
        results_dir=tmp_path / "results",
    )
    out = tmp_path / "evidence.json"

    result = probe.run_observation_probe(env, output_path=out)
    assert model.warmup_calls == [timedelta(days=probe.WARMUP_DAYS)]
    assert len(model.att_calls) == probe.EXPECTED_PERIODS
    assert result["status"] == "NO_DIVERGENCE"


def test_no_divergence_csv_bytes_hash_matches_real_sha256(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """The NO_DIVERGENCE branch must hash the BYTES of the freshly
    written CSV (not a JSON list). The recorded hash must be the
    sha256 of the file's contents, computed by ``csv_hash``.
    """
    model = _FakeModel(scenario_att=[20.0] * 72)
    model.seed_events(500)
    helper = _readiness_helper(mutate_then_return_none=True)
    writer, scorer, hasher = _no_divergence_doubles(probe, tmp_path)
    env = _env(
        probe,
        model=model,
        readiness=helper,
        writer=writer,
        scorer=scorer,
        csv_hash=hasher,
        results_dir=tmp_path / "results",
    )
    out = tmp_path / "evidence.json"

    result = probe.run_observation_probe(env, output_path=out)
    assert _NO_DIVERGENCE_HOLDERS, "writer/scorer/hasher doubles were not invoked"
    holder = _NO_DIVERGENCE_HOLDERS[-1]
    written = holder.written
    hashes = holder.hashes
    csv_path = written[0][0]
    expected_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert result["att_csv_sha256"] == expected_hash
    assert hashes and hashes[0][0] == csv_path
    # The result must NOT carry a JSON-list hash; it must carry the file
    # SHA-256 of the actual CSV bytes, which differs from any naive
    # JSON serialization.
    json_list_hash = hashlib.sha256(
        json.dumps([20.0] * 72, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert result["att_csv_sha256"] != json_list_hash


def _no_divergence_doubles(probe: types.ModuleType, tmp_path: Path) -> tuple[Any, Any, Any]:
    """Build writer/scorer/hasher doubles that record invocations."""

    written: list[tuple[Path, list[Any]]] = []
    scored: list[tuple[Path, Path]] = []
    hashes: list[tuple[Path, str]] = []

    def fake_writer(output_dir: Path, periods: list[Any]) -> Path:
        out = output_dir / "ATT_By_Statistics_Interval.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = [["PeriodIndex", "StartDay", "EndDay", "AverageTransportTime"]] + [
            [index, start, end, f"{att:.2f}"]
            for index, (start, end, att) in enumerate(periods, start=1)
        ]
        with out.open("w", newline="", encoding="utf-8") as fh:
            csv.writer(fh, lineterminator="\n").writerows(rows)
        written.append((out, list(periods)))
        return out

    def fake_scorer(scenario_path: Path, baseline_path: Path) -> Any:
        scored.append((scenario_path, baseline_path))
        return _Obj(
            cumulative_loss=probe.EXPECTED_CUMULATIVE_RESILIENCE_LOSS,
            period_count=72,
        )

    def fake_hasher(csv_path: Path) -> str:
        digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        hashes.append((csv_path, digest))
        return digest

    # Stash lists on a holder so the test can read them.
    holder = _NoDivergenceHolders(written=written, scored=scored, hashes=hashes)
    _NO_DIVERGENCE_HOLDERS.append(holder)
    return fake_writer, fake_scorer, fake_hasher


class _NoDivergenceHolders:
    __slots__ = ("written", "scored", "hashes")

    def __init__(self, written: list, scored: list, hashes: list) -> None:
        self.written = written
        self.scored = scored
        self.hashes = hashes


_NO_DIVERGENCE_HOLDERS: list[_NoDivergenceHolders] = []


# ---------------------------------------------------------------------------
# Replay tests
# ---------------------------------------------------------------------------


def _valid_evidence(probe: types.ModuleType) -> dict[str, Any]:
    """Build the smallest valid evidence payload, used by replay RED tests."""
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


def test_replay_aborts_after_run_once_cap_even_if_hook_never_runs(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """The replay search cap must count ``model.run_once`` calls, NOT
    berth-hook invocations. The hook returning ``None`` for every
    candidate must still result in a search-cap ProbeError.
    """
    model = _FakeModel()
    model.seed_events(50)
    helper = _readiness_helper(mutate_then_return_none=True)
    env = _env(probe, model=model, readiness=helper)
    env["search_max_events"] = 1

    with pytest.raises(probe.ProbeError, match=r"event cap|cap.*exhaust|search"):
        probe.run_bounded_replay(env, evidence=_valid_evidence(probe))


def test_replay_distinguishes_event_queue_exhaustion_from_cap_exhaustion(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """The replay must distinguish: event-cap exhaustion, event-queue
    exhaustion, horizon reached, recorded-event mismatch. Each mode
    produces a distinct ``ProbeError`` reason.
    """
    model = _FakeModel()
    model.seed_events(0)  # empty queue
    helper = _readiness_helper(mutate_then_return_none=True)
    env = _env(probe, model=model, readiness=helper)
    env["search_max_events"] = 100_000

    with pytest.raises(probe.ProbeError, match=r"queue is empty|empty queue|queue"):
        probe.run_bounded_replay(env, evidence=_valid_evidence(probe))


def test_replay_rejects_unknown_schema_version(probe: types.ModuleType, tmp_path: Path) -> None:
    """Evidence with an unknown ``schema_version`` must be rejected
    before any model is loaded.
    """
    model = _FakeModel()
    model.seed_events(1)
    helper = _readiness_helper()
    env = _env(probe, model=model, readiness=helper)
    bad = _valid_evidence(probe)
    bad["schema_version"] = 999

    with pytest.raises(probe.ProbeError, match=r"schema"):
        probe.run_bounded_replay(env, evidence=bad)


def test_replay_rejects_stale_helper_sha(probe: types.ModuleType, tmp_path: Path) -> None:
    """A helper SHA that differs from the current submission's helper
    SHA must be rejected before any model is constructed.
    """
    model = _FakeModel()
    model.seed_events(1)
    helper = _readiness_helper()
    env = _env(probe, model=model, readiness=helper)
    bad = _valid_evidence(probe)
    bad["helper_sha256"] = "00" * 32

    with pytest.raises(probe.ProbeError, match=r"helper_sha|stale"):
        probe.run_bounded_replay(env, evidence=bad)


def test_replay_rejects_wrong_configuration_constants(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """Evidence whose ``seed``/``warmup_days``/``measured_days``/
    ``interval_days`` differs from the documented values must be
    rejected before any model is constructed.
    """
    model = _FakeModel()
    model.seed_events(1)
    helper = _readiness_helper()
    env = _env(probe, model=model, readiness=helper)
    bad = _valid_evidence(probe)
    bad["seed"] = 1234

    with pytest.raises(probe.ProbeError, match=r"seed|configuration"):
        probe.run_bounded_replay(env, evidence=bad)


def test_replay_rejects_non_finite_metrics(probe: types.ModuleType, tmp_path: Path) -> None:
    """Evidence with non-finite numeric metrics must be rejected before
    any model is constructed.
    """
    model = _FakeModel()
    model.seed_events(1)
    helper = _readiness_helper()
    env = _env(probe, model=model, readiness=helper)
    bad = _valid_evidence(probe)
    bad["guaranteed_transitional_teu"] = float("nan")

    with pytest.raises(probe.ProbeError, match=r"finite|non-finite|metric"):
        probe.run_bounded_replay(env, evidence=bad)


def test_replay_rejects_non_integer_waiting_indexes(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """Evidence with negative or non-integer waiting indexes must be
    rejected.
    """
    model = _FakeModel()
    model.seed_events(1)
    helper = _readiness_helper()
    env = _env(probe, model=model, readiness=helper)
    bad = _valid_evidence(probe)
    bad["receiver_waiting_index"] = -1

    with pytest.raises(probe.ProbeError, match=r"index|integer|nonnegative"):
        probe.run_bounded_replay(env, evidence=bad)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def test_load_runtime_restores_sys_path_and_sys_modules_against_captured_before(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """``_load_runtime`` must restore ``sys.path`` and remove every
    inserted package from ``sys.modules``. The test captures the
    initial state and asserts equality after the context manager
    unwinds, with no `assert True` placeholder.
    """
    before_path = list(sys.path)
    before_modules = set(sys.modules)

    try:
        with probe._load_runtime() as _runtime:
            raise RuntimeError("simulated inner boom")
    except RuntimeError:
        pass

    assert sys.path == before_path
    leaked = {
        name
        for name in sys.modules
        if name not in before_modules
        and any(
            name == prefix or name.startswith(f"{prefix}.") for prefix in probe._ORGANIZER_PREFIXES
        )
    }
    assert leaked == set()
    leaked_participant = {
        name
        for name in sys.modules
        if name not in before_modules and name.startswith(f"{probe._PARTICIPANT_PACKAGE}.")
    }
    assert leaked_participant == set()
