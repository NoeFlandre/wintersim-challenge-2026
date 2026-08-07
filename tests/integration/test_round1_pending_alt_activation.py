"""Integration contract for pending alternative-route berth activation.

The test uses the real ignored Round 1 scenario and organizer fallback to
create a pending alternative route, then calls only the participant hook.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _source_or_skip() -> Path:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip(
            "Round 1 source not bootstrapped at "
            f"{source}; bootstrap the private archive to enable this check."
        )
    return source


def _load_organizer_tree(source: Path) -> None:
    for root in (str(source), str(source / "o2despy")):
        if root not in sys.path:
            sys.path.insert(0, root)
    prefixes = (
        "response_strategies",
        "scenario_builders",
        "simulation_model",
        "maritime_data_context",
        "config",
        "o2despy",
        "o2des",
    )
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)


def _load_participant() -> type:
    path = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_round1_participant", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load participant strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def test_real_pending_alternative_vessel_is_selected_without_mutation() -> None:
    source = _source_or_skip()
    _load_organizer_tree(source)

    import scenario_builders  # type: ignore[import-not-found]
    import simulation_model  # type: ignore[import-not-found]  # noqa: F401
    from response_strategies.default_strategy import (
        DefaultStrategy,  # type: ignore[import-not-found]
    )

    context = scenario_builders.create_with_disruption()
    plan = min(context.disruption_plans, key=lambda item: item.start_offset_days)
    now = datetime.min + timedelta(days=plan.start_offset_days + plan.duration_days / 2.0)
    DefaultStrategy.create_alternative_service_routes(context, now, None)

    pending = next(
        (vessel for vessel in context.vessels if vessel.pending_assigned_service_route is not None),
        None,
    )
    assert pending is not None, "the real fallback must reserve a pending alternative vessel"
    route = pending.pending_assigned_service_route
    assert route is not None and route.segments
    first_segment = min(route.segments, key=lambda segment: segment.sequence_index)
    port = first_segment.associated_leg.departure_port

    before = {
        "vessels": tuple(context.vessels),
        "routes": tuple(context.service_routes),
        "pending": tuple(
            (vessel, vessel.pending_assigned_service_route) for vessel in context.vessels
        ),
        "plans": tuple(context.disruption_plans),
    }
    UserStrategy = _load_participant()
    result = UserStrategy.select_vessel_for_berth(context, port, [pending], [], now, {})

    assert result is pending
    assert tuple(context.vessels) == before["vessels"]
    assert tuple(context.service_routes) == before["routes"]
    assert (
        tuple((vessel, vessel.pending_assigned_service_route) for vessel in context.vessels)
        == before["pending"]
    )
    assert tuple(context.disruption_plans) == before["plans"]


def test_real_round1_inactive_time_delegates() -> None:
    source = _source_or_skip()
    _load_organizer_tree(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    plan = min(context.disruption_plans, key=lambda item: item.start_offset_days)
    after = datetime.min + timedelta(days=plan.start_offset_days + plan.duration_days)
    UserStrategy = _load_participant()

    assert UserStrategy.select_vessel_for_berth(context, object(), [], [], after, {}) is None
