"""Real Round 1 runtime check for the weighted initial-booking policy."""

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
        pytest.skip(
            "Round 1 source not bootstrapped at "
            f"{source}; run 'wsc2026 bootstrap --round round1 --archive <path>'."
        )
    return source


def _clear_runtime_modules() -> None:
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


def _load_participant_strategy() -> type:
    participant_file = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location(
        "wsc_round1_weighted_booking_user_strategy", participant_file
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load participant module from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def test_real_round1_active_congested_booking_is_valid() -> None:
    source = _source_or_skip()
    source_text = str(source)
    o2des_text = str(source / "o2despy")
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    if o2des_text not in sys.path:
        sys.path.insert(0, o2des_text)
    _clear_runtime_modules()

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    UserStrategy = _load_participant_strategy()

    # This is a relative simulation time in the active leg-disruption window;
    # the test discovers the demand and plan objects instead of encoding the
    # policy's implementation around their names.
    plan = next(
        plan
        for plan in context.disruption_plans
        if plan.target_leg is not None and plan.multiplier > 1.0
    )
    now = dt.datetime.min + dt.timedelta(days=plan.start_offset_days + 1.0)
    demand = next(
        demand
        for demand in context.demands
        if demand.origin_port is plan.target_leg.departure_port
        and any(
            segment.associated_leg is plan.target_leg
            for route in context.service_routes
            for segment in route.segments
        )
    )

    # Importing the organizer domain class is test-only; participant code uses
    # its documented runtime module lazily at the actual hook boundary.
    from maritime_data_context import Shipment  # type: ignore[import-not-found]

    shipment = Shipment(
        index=1,
        teu_size=1,
        demand=demand,
        current_storage_port=demand.origin_port,
        generated_time=now,
    )
    routes_before = tuple(context.service_routes)
    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is True
    assert tuple(context.service_routes) == routes_before
    assert shipment.associated_bookings
    assert shipment.current_booking_index == 1
    final_booking = max(shipment.associated_bookings, key=lambda item: item.sequence_index)
    final_segment = next(
        segment
        for segment in final_booking.service_route.segments
        if segment.sequence_index == final_booking.arrival_segment_index
    )
    assert final_segment.associated_leg.arrival_port is demand.destination_port
    for booking in shipment.associated_bookings:
        assert booking in booking.service_route.associated_bookings
