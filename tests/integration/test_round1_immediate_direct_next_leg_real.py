"""Real Round 1 context contract for the direct-next-leg policy."""

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
        pytest.skip(f"Round 1 source not bootstrapped at {source}")
    return source


def _load_runtime(source: Path):
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
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)

    import scenario_builders
    from maritime_data_context import Demand, Shipment

    participant_file = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location(
        "wsc_round1_immediate_direct_next_leg_participant", str(participant_file)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return scenario_builders, Demand, Shipment, module.UserStrategy


def test_real_round1_ready_direct_first_leg_is_bookable() -> None:
    source = _source_or_skip()
    scenario_builders, Demand, Shipment, UserStrategy = _load_runtime(source)
    context = scenario_builders.create_with_disruption()

    # The first plan's midpoint is a genuinely active disruption clock.  Use
    # the first segment of a different original route so the direct leg is
    # provably not the active target.
    plan = context.disruption_plans[0]
    now = dt.datetime.min + dt.timedelta(days=plan.start_offset_days + plan.duration_days / 2.0)
    target_leg = plan.target_leg
    target_port = plan.target_berth.port if plan.target_berth is not None else None

    selected = None
    for route in context.service_routes:
        if route.source_service_route is not None or not route.deployed_vessels:
            continue
        first_segment = min(route.segments, key=lambda segment: segment.sequence_index)
        leg = first_segment.associated_leg
        if (
            leg is target_leg
            or leg.departure_port is target_port
            or leg.arrival_port is target_port
        ):
            continue
        selected = (route, first_segment)
        break
    assert selected is not None, "Round 1 must expose an unaffected original first leg"

    route, segment = selected
    demand = Demand(segment.associated_leg.departure_port, segment.associated_leg.arrival_port, 1)
    shipment = Shipment(index=999_999, teu_size=1, demand=demand)

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is True
    assert len(shipment.associated_bookings) == 1
    booking = shipment.associated_bookings[0]
    assert booking.service_route is route
    assert booking.departure_segment_index == segment.sequence_index
    assert booking.arrival_segment_index == segment.sequence_index
    assert route.associated_bookings[-1] is booking
