"""Real Round 1 runtime contract for the carried-TEU berth selector."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _source_or_skip() -> Path:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip("Round 1 source not bootstrapped; skipping real-runtime integration test.")
    return source


def _load_organizer_context(source: Path):
    source_text = str(source)
    o2des_text = str(source / "o2despy")
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    if o2des_text not in sys.path:
        sys.path.insert(0, o2des_text)
    prefixes = (
        "response_strategies",
        "scenario_builders",
        "simulation_model",
        "maritime_data_context",
        "config",
        "o2despy",
        "o2des",
    )
    for module_name in list(sys.modules):
        if any(
            module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes
        ):
            sys.modules.pop(module_name, None)
    import scenario_builders  # type: ignore[import-not-found]

    return scenario_builders.create_with_disruption()


def _load_participant_strategy():
    path = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_round1_participant_strategy", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def test_real_round1_objects_are_read_only_and_queue_safe() -> None:
    source = _source_or_skip()
    context = _load_organizer_context(source)
    user_strategy = _load_participant_strategy()
    assert context.vessels, "Round 1 context must contain vessels"
    assert context.disruption_plans, "Round 1 context must contain disruptions"

    plan = context.disruption_plans[0]
    now = dt.datetime.min + dt.timedelta(days=plan.start_offset_days + plan.duration_days / 2.0)
    first, second = context.vessels[:2]
    route_before = {first: first.assigned_service_route, second: second.assigned_service_route}
    carried_before = {vessel: list(vessel.carried_shipments) for vessel in (first, second)}

    booking = SimpleNamespace(
        service_route=second.assigned_service_route,
        departure_segment_index=10_000,
        arrival_segment_index=10_000,
    )
    cargo = SimpleNamespace(teu_size=1_000, get_current_booking=lambda: booking)
    second.carried_shipments.append(cargo)
    try:
        selected = user_strategy.select_vessel_for_berth(
            context,
            object(),
            [first, second],
            [object()],
            now,
            {
                first: now - dt.timedelta(hours=2),
                second: now - dt.timedelta(hours=1),
            },
        )
    finally:
        second.carried_shipments[:] = carried_before[second]

    assert selected is None or selected in (first, second)
    assert route_before == {
        first: first.assigned_service_route,
        second: second.assigned_service_route,
    }
    assert carried_before[first] == first.carried_shipments
    assert carried_before[second] == second.carried_shipments
