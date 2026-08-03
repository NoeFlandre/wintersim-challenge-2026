"""Real Round 1 runtime checks for the deferred-rebooking hook."""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _source_or_skip() -> Path:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip("Round 1 source is not bootstrapped in the private workspace")
    return source


def _load_participant_strategy() -> type:
    directory = submission_strategies_dir()
    path = directory / "user_strategy.py"
    package_name = "wsc_round1_participant_response_strategies"
    package = types.ModuleType(package_name)
    package.__path__ = [str(directory)]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(f"{package_name}.user_strategy", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load participant strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def _install_source_imports(source: Path) -> None:
    for path in (source, source / "o2despy"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    for name in list(sys.modules):
        if name == "response_strategies" or name.startswith("response_strategies."):
            sys.modules.pop(name, None)


def _real_future_only_state(source: Path):
    _install_source_imports(source)
    import scenario_builders  # type: ignore[import-not-found]
    from maritime_data_context import Booking, Shipment  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    plan = next(
        plan
        for plan in context.disruption_plans
        if plan.target_leg is not None and plan.multiplier > 1.0
    )
    route_segment = next(
        segment
        for route in context.initial_service_routes
        for segment in route.segments
        if segment.associated_leg is plan.target_leg
    )
    route = route_segment.associated_service_route
    segments = sorted(route.segments, key=lambda segment: segment.sequence_index)
    target_position = segments.index(route_segment)
    current_segment = segments[(target_position - 1) % len(segments)]
    shipment = Shipment(index=999_001, teu_size=1)
    shipment.associated_bookings = [
        Booking(
            sequence_index=1,
            shipment=shipment,
            service_route=route,
            departure_segment_index=current_segment.sequence_index,
            arrival_segment_index=route_segment.sequence_index,
        )
    ]
    shipment.current_booking_index = 1
    vessel = route.deployed_vessels[0]
    vessel.current_segment = current_segment
    vessel.carried_shipments = [shipment]
    now = datetime.min + timedelta(days=plan.start_offset_days + 0.5)
    return context, vessel, now, current_segment, route_segment


def test_real_round1_future_only_impact_is_deferred_without_mutation() -> None:
    source = _source_or_skip()
    context, vessel, now, current_segment, target_segment = _real_future_only_state(source)
    UserStrategy = _load_participant_strategy()
    before = (
        vessel.current_segment,
        tuple(vessel.carried_shipments),
        tuple(vessel.carried_shipments[0].associated_bookings),
        tuple(context.disruption_plans),
    )

    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)

    assert result is False
    assert target_segment is not current_segment
    assert (
        vessel.current_segment,
        tuple(vessel.carried_shipments),
        tuple(vessel.carried_shipments[0].associated_bookings),
        tuple(context.disruption_plans),
    ) == before


def test_real_round1_direct_impact_delegates() -> None:
    source = _source_or_skip()
    context, vessel, now, _, target_segment = _real_future_only_state(source)
    vessel.current_segment = target_segment
    UserStrategy = _load_participant_strategy()

    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)

    assert result is None
