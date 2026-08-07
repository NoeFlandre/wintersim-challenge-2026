"""Real Round 1 runtime contract for the exposed-cargo berth policy."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _source_or_skip():
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip(f"Round 1 source not bootstrapped at {source}")
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
            module_name == prefix or module_name.startswith(f"{prefix}.")
            for prefix in prefixes
        ):
            sys.modules.pop(module_name, None)
    return source


def _load_participant_strategy():
    participant_file = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location(
        "wsc_round1_exposed_cargo_participant", participant_file
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def test_real_round1_exposed_cargo_selection_is_read_only():
    _source_or_skip()
    import scenario_builders  # type: ignore[import-not-found]
    from maritime_data_context import Booking, Shipment  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    plan = next(plan for plan in context.disruption_plans if plan.target_leg is not None)
    target_leg = plan.target_leg
    route = next(
        route
        for route in context.initial_service_routes
        if any(segment.associated_leg is target_leg for segment in route.segments)
    )
    target_segment = next(
        segment for segment in route.segments if segment.associated_leg is target_leg
    )
    safe_segment = next(
        segment
        for candidate_route in context.initial_service_routes
        for segment in candidate_route.segments
        if segment.associated_leg is not target_leg
    )

    exposed_shipment = Shipment(index=900_001, teu_size=10)
    exposed_shipment.associated_bookings = [
        Booking(
            sequence_index=1,
            shipment=exposed_shipment,
            service_route=route,
            departure_segment_index=target_segment.sequence_index,
            arrival_segment_index=target_segment.sequence_index,
        )
    ]
    exposed_shipment.current_booking_index = 1

    safe_shipment = Shipment(index=900_002, teu_size=80)
    safe_shipment.associated_bookings = [
        Booking(
            sequence_index=1,
            shipment=safe_shipment,
            service_route=safe_segment.associated_service_route,
            departure_segment_index=safe_segment.sequence_index,
            arrival_segment_index=safe_segment.sequence_index,
        )
    ]
    safe_shipment.current_booking_index = 1

    exposed_vessel, safe_vessel = context.vessels[:2]
    original_carried = [
        list(exposed_vessel.carried_shipments),
        list(safe_vessel.carried_shipments),
    ]
    exposed_vessel.carried_shipments = [exposed_shipment]
    safe_vessel.carried_shipments = [safe_shipment]
    before = (
        tuple(context.legs),
        tuple(context.service_routes),
        tuple(exposed_vessel.carried_shipments),
        tuple(safe_vessel.carried_shipments),
    )

    try:
        UserStrategy = _load_participant_strategy()
        now = datetime.min + timedelta(
            days=plan.start_offset_days + (plan.duration_days / 2.0)
        )
        result = UserStrategy.select_vessel_for_berth(
            context,
            target_leg.arrival_port,
            [safe_vessel, exposed_vessel],
            list(target_leg.arrival_port.berths),
            now,
            {
                safe_vessel: datetime.min + timedelta(days=plan.start_offset_days),
                exposed_vessel: datetime.min
                + timedelta(days=plan.start_offset_days - 1.0),
            },
        )
        assert result is exposed_vessel
        assert (
            tuple(context.legs),
            tuple(context.service_routes),
            tuple(exposed_vessel.carried_shipments),
            tuple(safe_vessel.carried_shipments),
        ) == before
    finally:
        exposed_vessel.carried_shipments = original_carried[0]
        safe_vessel.carried_shipments = original_carried[1]
