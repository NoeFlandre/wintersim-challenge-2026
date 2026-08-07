"""Real Round 1 context contract for congestion-only direct booking."""

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
        pytest.skip(f"Round 1 organizer source is not bootstrapped at {source}")
    return source


def _prepare_source(source: Path) -> None:
    for entry in (str(source), str(source / "o2despy")):
        if entry not in sys.path:
            sys.path.insert(0, entry)
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


def _load_participant(source: Path):
    path = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_round1_direct_booking", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def test_real_round1_exact_congested_od_gets_one_direct_booking() -> None:
    source = _source_or_skip()
    _prepare_source(source)
    import scenario_builders  # type: ignore[import-not-found]
    from maritime_data_context import Shipment  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    plan = next(
        plan
        for plan in context.disruption_plans
        if plan.target_leg is not None
        and plan.multiplier > 1
        and plan.target_leg.departure_port.name == "New Jersey"
        and plan.target_leg.arrival_port.name == "Cartagena"
    )
    now = dt.datetime.min + dt.timedelta(days=plan.start_offset_days + 1.0)
    assert not any(
        active.target_berth is not None
        and active.close_berth
        and active.start_offset_days
        <= (now - dt.datetime.min).total_seconds() / 86400.0
        < active.start_offset_days + active.duration_days
        for active in context.disruption_plans
    )
    demand = next(
        demand
        for demand in context.demands
        if demand.origin_port is plan.target_leg.departure_port
        and demand.destination_port is plan.target_leg.arrival_port
    )
    shipment = Shipment(index=999999, teu_size=1, demand=demand)
    UserStrategy = _load_participant(source)

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is True
    assert len(shipment.associated_bookings) == 1
    booking = shipment.associated_bookings[0]
    assert booking.service_route.source_service_route is None
    assert booking.service_route.deployed_vessels
    segment = next(
        segment
        for segment in booking.service_route.segments
        if segment.associated_leg is plan.target_leg
    )
    assert booking.departure_segment_index == segment.sequence_index
    assert booking.arrival_segment_index == segment.sequence_index
    assert booking in booking.service_route.associated_bookings
