"""Real Round 2 context contract for the time-aware booking policy.

Loads the organizer's own disruption scenario, applies the runtime disruption
state exactly as ``DisruptionManager`` does, and checks that the participant
strategy produces booking chains that are valid against the organizer's data
model and strictly faster than the organizer's distance-optimal chain. Nothing
is advanced and no ``Output`` file is written.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration

SIM_START = dt.datetime.min


def _bootstrap_or_skip() -> Path:
    source = round_source_dir("round2")
    if not source.is_dir():
        pytest.skip(
            "Round 2 source is unavailable; bootstrap the organizer archive "
            "to run this integration contract."
        )
    return source


def _prepare_imports(source: Path) -> None:
    for path in (str(source), str(source / "o2despy")):
        if path not in sys.path:
            sys.path.insert(0, path)
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
    for module_name in list(sys.modules):
        if any(
            module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes
        ):
            sys.modules.pop(module_name, None)


def _load_participant_module() -> Any:
    participant_file = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location(
        "wsc_round2_time_aware_booking_v9_participant", participant_file
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply_runtime_disruption_state(context: Any, now: dt.datetime) -> None:
    """Mirror ``DisruptionManager._check_plans`` for a single instant."""
    for plan in context.disruption_plans:
        if plan.start_offset_days is None or plan.duration_days is None:
            continue
        start = SIM_START + dt.timedelta(days=plan.start_offset_days)
        end = start + dt.timedelta(days=plan.duration_days)
        active = start <= now < end
        if plan.target_leg is not None:
            plan.target_leg.sailing_time_multiplier = plan.multiplier if active else 1.0
        if plan.target_berth is not None and plan.close_berth:
            plan.target_berth.is_available = not active


def _new_shipment(context: Any, demand: Any) -> Any:
    from maritime_data_context.shipment import Shipment

    return Shipment(
        index=1,
        teu_size=10,
        demand=demand,
        current_storage_port=demand.origin_port,
        generated_time=SIM_START,
    )


def _chain_hours(module: Any, context: Any, shipment: Any, now: Any) -> float:
    """Estimated hours of an assigned chain, using the strategy's own model."""
    port_indexes = module._port_indexes(context)
    network = module._network(context, now, port_indexes, {})
    assert network is not None
    total = 0.0
    previous = None
    for booking in sorted(shipment.associated_bookings, key=lambda b: b.sequence_index):
        route_index = network.routes.index(booking.service_route)
        edge = next(
            edge
            for edge in network.edges
            if edge.route_index == route_index
            and edge.departure_segment_index == booking.departure_segment_index
            and edge.arrival_segment_index == booking.arrival_segment_index
        )
        if previous != route_index:
            total += network.boarding_hours[route_index]
        total += edge.hours
        previous = route_index
    return total


@pytest.fixture(scope="module")
def real_context_environment() -> Any:
    source = _bootstrap_or_skip()
    _prepare_imports(source)
    module = _load_participant_module()
    import scenario_builders  # noqa: PLC0415

    return module, scenario_builders


def test_assigned_chain_is_valid_against_the_organizer_model(
    real_context_environment: Any,
) -> None:
    module, scenario_builders = real_context_environment
    context = scenario_builders.create_with_disruption()
    now = SIM_START + dt.timedelta(days=200.5)
    _apply_runtime_disruption_state(context, now)

    assigned = 0
    for demand in context.demands:
        if demand.origin_port is demand.destination_port:
            continue
        shipment = _new_shipment(context, demand)
        result = module.UserStrategy.assign_associated_bookings(context, now, shipment)
        if result is None:
            assert shipment.associated_bookings == []
            continue
        assert result is True
        assigned += 1
        bookings = sorted(shipment.associated_bookings, key=lambda b: b.sequence_index)
        assert [b.sequence_index for b in bookings] == list(range(1, len(bookings) + 1))
        assert shipment.current_booking_index == 1
        # Each booking must name real segments of its own route, and the chain
        # must connect origin to destination through matching ports.
        cursor = demand.origin_port
        for booking in bookings:
            route = booking.service_route
            assert route.source_service_route is None
            assert route.deployed_vessels
            assert booking in route.associated_bookings
            assert booking.shipment is shipment
            departure = next(
                segment
                for segment in route.segments
                if segment.sequence_index == booking.departure_segment_index
            )
            arrival = next(
                segment
                for segment in route.segments
                if segment.sequence_index == booking.arrival_segment_index
            )
            assert departure.associated_leg.departure_port is cursor
            cursor = arrival.associated_leg.arrival_port
        assert cursor is demand.destination_port
        # Consecutive bookings always change service route.
        routes = [booking.service_route for booking in bookings]
        assert all(left is not right for left, right in zip(routes, routes[1:], strict=False))

    assert assigned > 0, "the policy must assign at least one real chain"


def test_assigned_chain_is_never_slower_than_the_organizer_choice(
    real_context_environment: Any,
) -> None:
    module, scenario_builders = real_context_environment
    # simulation_model must be imported first: response_strategies and
    # simulation_model import each other at module scope.
    import simulation_model  # noqa: F401, PLC0415
    from response_strategies import default_strategy as organizer  # noqa: PLC0415

    context = scenario_builders.create_with_disruption()
    now = SIM_START + dt.timedelta(days=200.5)
    _apply_runtime_disruption_state(context, now)

    close_plans, leg_plans = organizer._get_active_disruption_plans(context, now)
    avoid = organizer._get_avoid_port_names(close_plans)
    congested = organizer._get_congested_legs(leg_plans)
    organizer_edges = organizer._build_all_candidate_bookings(context, avoid, congested)

    strictly_faster = 0
    compared = 0
    for demand in context.demands:
        if demand.origin_port is demand.destination_port:
            continue
        if demand.destination_port.name.casefold() in avoid:
            continue
        organizer_path = organizer._find_shortest_booking_path(
            context, demand.origin_port, demand.destination_port, organizer_edges
        )
        if not organizer_path:
            continue
        shipment = _new_shipment(context, demand)
        if module.UserStrategy.assign_associated_bookings(context, now, shipment) is not True:
            continue
        reference = _new_shipment(context, demand)
        for index, edge in enumerate(organizer_path, start=1):
            from maritime_data_context import Booking  # noqa: PLC0415

            reference.associated_bookings.append(
                Booking(
                    sequence_index=index,
                    shipment=reference,
                    service_route=edge.service_route,
                    departure_segment_index=edge.departure_segment_index,
                    arrival_segment_index=edge.arrival_segment_index,
                )
            )
        try:
            organizer_hours = _chain_hours(module, context, reference, now)
        except StopIteration:
            # The organizer chose an alternative route, which the policy
            # deliberately never books; nothing to compare.
            continue
        chosen_hours = _chain_hours(module, context, shipment, now)
        compared += 1
        assert chosen_hours <= organizer_hours + 1e-6, (
            f"{demand.origin_port.name}->{demand.destination_port.name}: "
            f"chose {chosen_hours:.2f} h over the organizer's {organizer_hours:.2f} h"
        )
        if chosen_hours < organizer_hours - 1e-6:
            strictly_faster += 1

    assert compared > 0
    assert strictly_faster > 0, "the policy must improve on at least one real chain"


def test_policy_does_not_advance_the_model_or_write_output(
    real_context_environment: Any,
) -> None:
    module, scenario_builders = real_context_environment
    source = round_source_dir("round2")
    att_path = source / "Output" / "Scenario_ATT_By_Statistics_Interval.csv"
    before = att_path.stat().st_mtime_ns if att_path.exists() else None

    context = scenario_builders.create_with_disruption()
    now = SIM_START + dt.timedelta(days=460.5)
    _apply_runtime_disruption_state(context, now)
    vessel_total = len(context.vessels)
    route_total = len(context.service_routes)

    for demand in context.demands[:40]:
        if demand.origin_port is demand.destination_port:
            continue
        module.UserStrategy.assign_associated_bookings(context, now, _new_shipment(context, demand))

    assert len(context.vessels) == vessel_total
    assert len(context.service_routes) == route_total
    after = att_path.stat().st_mtime_ns if att_path.exists() else None
    assert after == before


def test_closed_port_window_prices_the_wait_for_reopening(
    real_context_environment: Any,
) -> None:
    """During a closure, cargo may be routed through the port at its true cost.

    A closure is temporary, so the policy books cargo bound for or transiting a
    shut port instead of holding it at the origin. Arriving before the
    reopening is allowed — waiting there can genuinely be the best plan — but
    the estimate must charge that wait rather than pretend the call is free.
    """
    module, scenario_builders = real_context_environment
    context = scenario_builders.create_with_disruption()
    # Day 400.5 falls inside the Piraeus closure window.
    now = SIM_START + dt.timedelta(days=400.5)
    _apply_runtime_disruption_state(context, now)

    piraeus = next(port for port in context.ports if port.name == "Piraeus")
    assert all(not berth.is_available for berth in piraeus.berths)

    recovery = module._closure_recovery(context, now)
    assert recovery is not None
    reopen_hours = recovery.get(id(piraeus))
    assert reopen_hours is not None and reopen_hours > 0.0

    port_indexes = module._port_indexes(context)
    piraeus_index = port_indexes[id(piraeus)]
    network = module._network(context, now, port_indexes, {piraeus_index: reopen_hours})
    assert network is not None

    inbound = [
        demand
        for demand in context.demands
        if demand.destination_port is piraeus and demand.origin_port is not piraeus
    ]
    assert inbound
    booked = 0
    for demand in inbound:
        shipment = _new_shipment(context, demand)
        if module.UserStrategy.assign_associated_bookings(context, now, shipment) is True:
            booked += 1
    assert booked > 0, "a closure with a known reopening must not force a hold"

    # Every planned call at the shut port must be charged the wait it implies.
    checked = 0
    for demand in context.demands:
        if demand.origin_port is demand.destination_port:
            continue
        shipment = _new_shipment(context, demand)
        if module.UserStrategy.assign_associated_bookings(context, now, shipment) is not True:
            continue
        elapsed = 0.0
        previous = None
        for booking in sorted(shipment.associated_bookings, key=lambda b: b.sequence_index):
            route_index = network.routes.index(booking.service_route)
            edge = next(
                candidate
                for candidate in network.edges
                if candidate.route_index == route_index
                and candidate.departure_segment_index == booking.departure_segment_index
                and candidate.arrival_segment_index == booking.arrival_segment_index
            )
            if previous is None or previous != route_index:
                elapsed += network.boarding_hours[route_index]
            arrival = module._edge_arrival(edge, elapsed)
            for base, multiplier, clears, reopen in edge.timeline or ():
                if reopen <= 0.0:
                    continue
                checked += 1
                # The ride cannot end before it clears the shut port.
                assert arrival >= reopen - 1e-6, (
                    f"{demand.origin_port.name}->{demand.destination_port.name} is "
                    f"costed to end at hour {arrival:.2f} but calls at a port that "
                    f"reopens at {reopen:.2f}"
                )
                assert base > 0.0 and multiplier >= 1.0 and clears >= 0.0
            elapsed = arrival
            previous = route_index
    assert checked > 0, "the closure window must produce at least one timed call"


def test_estimated_hours_are_finite_and_positive(real_context_environment: Any) -> None:
    module, scenario_builders = real_context_environment
    context = scenario_builders.create_with_disruption()
    now = SIM_START + dt.timedelta(days=300.5)
    _apply_runtime_disruption_state(context, now)

    port_indexes = module._port_indexes(context)
    network = module._network(context, now, port_indexes, {})
    assert network is not None
    assert network.edges
    for edge in network.edges:
        assert math.isfinite(edge.hours) and edge.hours > 0.0
    for hours in network.boarding_hours:
        assert math.isfinite(hours) and hours > 0.0


def test_the_fleet_decision_moves_a_whole_service_around_a_slowdown(
    real_context_environment: Any,
) -> None:
    """The strategy must build one detour for S4 and reserve its whole fleet.

    Checked against the organizer's own validator, which runs after every call
    to this hook, and contrasted with what the fallback does to the same
    context: it builds the same kind of route but reserves a single vessel.
    """
    module, scenario_builders = real_context_environment
    import simulation_model  # noqa: F401, PLC0415
    from response_strategies import default_strategy as organizer  # noqa: PLC0415
    from response_strategies.strategy_validation import (  # noqa: PLC0415
        capture_alternative_route_strategy_state,
        validate_alternative_route_strategy_result,
    )

    # Mid-way through the Shanghai->Kaohsiung congestion window.
    now = SIM_START + dt.timedelta(days=310.5)

    context = scenario_builders.create_with_disruption()
    _apply_runtime_disruption_state(context, now)
    routes_before = len(context.service_routes)
    vessels_before = len(context.vessels)
    legs_before = list(context.legs)
    source = next(route for route in context.service_routes if route.id == "S4")
    fleet = [v for v in context.vessels if v.assigned_service_route is source]
    assert len(fleet) > 1

    snapshot = capture_alternative_route_strategy_state(context)
    decision = module.UserStrategy.create_alternative_service_routes(context, now)
    validate_alternative_route_strategy_result(context, snapshot)

    assert decision is not None, "the hook must own this decision"
    assert len(context.vessels) == vessels_before
    assert list(context.legs) == legs_before, "no leg may be created"
    built = [r for r in context.service_routes if r.source_service_route is not None]
    assert len(built) == 1, "exactly one detour, for the one slowed service"
    detour = built[0]
    assert detour.source_service_route is source
    assert len(context.service_routes) == routes_before + 1

    # It calls every port the rotation calls, and is strictly faster now.
    def ports(route: Any) -> set[str]:
        return {s.associated_leg.departure_port.name for s in route.segments}

    def stretched(route: Any) -> float:
        return sum(
            s.associated_leg.sailing_distance * s.associated_leg.sailing_time_multiplier
            for s in route.segments
        )

    assert ports(source) <= ports(detour)
    assert stretched(detour) < stretched(source)
    assert [s.sequence_index for s in sorted(detour.segments, key=lambda x: x.sequence_index)] == (
        list(range(1, len(detour.segments) + 1))
    )

    # The whole fleet is reserved: this is the difference from the fallback.
    reserved = [v for v in fleet if v.pending_assigned_service_route is detour]
    assert len(reserved) == len(fleet)

    fallback_context = scenario_builders.create_with_disruption()
    _apply_runtime_disruption_state(fallback_context, now)
    organizer.DefaultStrategy.create_alternative_service_routes(fallback_context, now)
    fallback_reserved = [
        v for v in fallback_context.vessels if v.pending_assigned_service_route is not None
    ]
    assert len(fallback_reserved) == 1, (
        "the fallback is expected to reserve exactly one vessel; moving the "
        "whole service is what this strategy adds"
    )


def test_the_fleet_decision_leaves_a_closed_port_alone(
    real_context_environment: Any,
) -> None:
    """A shut port is a wait. Nothing is built and no vessel is reserved."""
    module, scenario_builders = real_context_environment
    import simulation_model  # noqa: F401, PLC0415
    from response_strategies.strategy_validation import (  # noqa: PLC0415
        capture_alternative_route_strategy_state,
        validate_alternative_route_strategy_result,
    )

    # Mid-way through the Piraeus closure, with no slowdown anywhere.
    now = SIM_START + dt.timedelta(days=405.0)

    context = scenario_builders.create_with_disruption()
    _apply_runtime_disruption_state(context, now)
    assert any(not berth.is_available for port in context.ports for berth in port.berths)
    assert all(leg.sailing_time_multiplier == 1.0 for leg in context.legs)
    routes_before = len(context.service_routes)

    snapshot = capture_alternative_route_strategy_state(context)
    decision = module.UserStrategy.create_alternative_service_routes(context, now)
    validate_alternative_route_strategy_result(context, snapshot)

    assert decision is not None
    assert len(context.service_routes) == routes_before
    assert all(v.pending_assigned_service_route is None for v in context.vessels)


def test_the_fleet_decision_builds_nothing_on_a_calm_network(
    real_context_environment: Any,
) -> None:
    """With no disruption in force the fleet is left exactly as deployed."""
    module, scenario_builders = real_context_environment
    import simulation_model  # noqa: F401, PLC0415

    # Between the Colombo->New Jersey and Shanghai->Kaohsiung windows.
    now = SIM_START + dt.timedelta(days=260.0)
    context = scenario_builders.create_with_disruption()
    _apply_runtime_disruption_state(context, now)
    assert all(leg.sailing_time_multiplier == 1.0 for leg in context.legs)
    assert all(berth.is_available for port in context.ports for berth in port.berths)
    deployed_before = {id(r): list(r.deployed_vessels) for r in context.service_routes}
    routes_before = len(context.service_routes)

    assert module.UserStrategy.create_alternative_service_routes(context, now) is not None
    assert len(context.service_routes) == routes_before
    assert {id(r): list(r.deployed_vessels) for r in context.service_routes} == deployed_before
    assert all(v.pending_assigned_service_route is None for v in context.vessels)


def test_a_staffed_detour_replaces_its_nominal_rotation_in_the_network(
    real_context_environment: Any,
) -> None:
    """New cargo is offered the rotation the service is actually running."""
    module, scenario_builders = real_context_environment
    import simulation_model  # noqa: F401, PLC0415

    now = SIM_START + dt.timedelta(days=310.5)
    context = scenario_builders.create_with_disruption()
    _apply_runtime_disruption_state(context, now)
    module.UserStrategy.create_alternative_service_routes(context, now)
    detour = next(r for r in context.service_routes if r.source_service_route is not None)
    source = detour.source_service_route

    # Staff the detour as the simulation would, one empty vessel at a time.
    for vessel in list(context.vessels):
        if vessel.pending_assigned_service_route is detour:
            vessel.carried_shipments.clear()
            vessel.current_segment = sorted(source.segments, key=lambda s: s.sequence_index)[0]
            module.UserStrategy.create_alternative_service_routes(context, now, vessel)

    assert detour.deployed_vessels, "at least one vessel must have switched"
    port_indexes = module._port_indexes(context)
    closed = module._closed_port_indexes(context)
    network = module._network(context, now, port_indexes, {}, {})
    booked = {route.id for route in network.routes}
    assert detour.id in booked
    if source.deployed_vessels:
        assert source.id not in booked, "a rotation being drained takes no new cargo"
    targets = module._service_targets(context, now, closed, port_indexes, {}, build=False)
    assert targets[id(source)] is detour
