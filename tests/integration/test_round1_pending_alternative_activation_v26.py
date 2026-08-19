"""Real Round 1 context contract for v26 pending-route selection."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _source_or_skip() -> Path:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip(f"Round 1 source is not bootstrapped at {source}")
    return source


def _load_organizer_tree(source: Path) -> None:
    for root in (str(source), str(source / "o2despy")):
        if root not in sys.path:
            sys.path.insert(0, root)
    prefixes = (
        "config",
        "main",
        "maritime_data_context",
        "o2des",
        "o2despy",
        "response_strategies",
        "scenario_builders",
        "simulation_model",
    )
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)


def _load_participant() -> type:
    path = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_round1_v26_participant", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load participant from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def test_real_pending_alternative_is_selected_without_mutation() -> None:
    source = _source_or_skip()
    _load_organizer_tree(source)
    import main as _runtime_main  # type: ignore[import-not-found]  # noqa: F401
    import scenario_builders  # type: ignore[import-not-found]
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )

    context = scenario_builders.create_with_disruption()
    plan = min(context.disruption_plans, key=lambda item: item.start_offset_days)
    now = dt.datetime.min + dt.timedelta(days=plan.start_offset_days + plan.duration_days / 2.0)
    DefaultStrategy.create_alternative_service_routes(context, now, None)
    pending = next(
        (vessel for vessel in context.vessels if vessel.pending_assigned_service_route is not None),
        None,
    )
    assert pending is not None
    route = pending.pending_assigned_service_route
    first = min(route.segments, key=lambda segment: segment.sequence_index)
    port = first.associated_leg.departure_port
    before = (
        tuple(context.vessels),
        tuple(context.service_routes),
        tuple((vessel, vessel.pending_assigned_service_route) for vessel in context.vessels),
        tuple(context.disruption_plans),
    )

    UserStrategy = _load_participant()
    result = UserStrategy.select_vessel_for_berth(context, port, [pending], [], now, {})

    assert result is pending
    assert tuple(context.vessels) == before[0]
    assert tuple(context.service_routes) == before[1]
    assert (
        tuple((vessel, vessel.pending_assigned_service_route) for vessel in context.vessels)
        == before[2]
    )
    assert tuple(context.disruption_plans) == before[3]
