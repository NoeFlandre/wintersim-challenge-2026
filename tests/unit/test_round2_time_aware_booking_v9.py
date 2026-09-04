"""Behaviour contract for the Round 2 time-aware booking assignment (v9).

The strategy must build its own booking chain, minimising estimated transport
time rather than sailing distance, and must fail closed to ``None`` on any
malformed, ambiguous, or protective case.

All fixtures are sentinel objects defined here; no organizer source is
imported. ``Booking`` is stubbed through the module the strategy imports it
from, so these tests stay independent of the organizer tree.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

from response_strategies.user_strategy import UserStrategy

NOW = dt.datetime.min + dt.timedelta(days=200)


def _port(name: str, *, closed: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        berths=[SimpleNamespace(is_available=not closed)],
    )


def _route(
    route_id: str,
    ports: list[Any],
    distances: list[float],
    *,
    vessels: int = 1,
    speed: float = 20.0,
    multipliers: list[float] | None = None,
) -> SimpleNamespace:
    """Build a cyclic route visiting ``ports`` in order and returning to start.

    ``ports`` lists the departure port of each leg; the cycle closes back onto
    ``ports[0]``. ``distances`` has one entry per leg.
    """
    route = SimpleNamespace(
        id=route_id,
        name=route_id,
        source_service_route=None,
        disruption_key=None,
        associated_bookings=[],
        deployed_vessels=[
            SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=speed))
            for _ in range(vessels)
        ],
        segments=[],
    )
    if multipliers is None:
        multipliers = [1.0] * len(distances)
    for index, (distance, multiplier) in enumerate(zip(distances, multipliers, strict=True)):
        departure = ports[index]
        arrival = ports[(index + 1) % len(ports)]
        leg = SimpleNamespace(
            departure_port=departure,
            arrival_port=arrival,
            sailing_distance=distance,
            sailing_time_multiplier=multiplier,
        )
        route.segments.append(
            SimpleNamespace(
                sequence_index=index + 1,
                associated_leg=leg,
                associated_service_route=route,
            )
        )
    return route


def _shipment(origin: Any, destination: Any, teu: float = 100.0) -> SimpleNamespace:
    return SimpleNamespace(
        teu_size=teu,
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )


def _context(ports: list[Any], routes: list[Any]) -> SimpleNamespace:
    return SimpleNamespace(ports=ports, service_routes=routes, disruption_plans=[], demands=[])


def _chain(shipment: Any) -> list[tuple[str, int, int]]:
    return [
        (
            booking.service_route.id,
            booking.departure_segment_index,
            booking.arrival_segment_index,
        )
        for booking in sorted(shipment.associated_bookings, key=lambda b: b.sequence_index)
    ]


# ---------------------------------------------------------------------------
# The core defect: a marginally shorter distance bought with an extra transfer.
# ---------------------------------------------------------------------------


def _transfer_penalty_fixture(
    *, direct_vessels: int = 4, feeder_vessels: int = 4, trunk_vessels: int = 1
) -> tuple[Any, Any]:
    """A direct service versus a two-leg path that is shorter in distance.

    ``direct`` covers Origin->Destination as a single 1000 nm edge on a 2000 nm
    rotation. ``feeder`` + ``trunk`` reach the destination in 400 + 450 = 850 nm,
    which wins on distance, but boarding the low-frequency trunk costs its full
    45-hour headway, so the direct service wins on time:

      direct  = (2000/20)/4 + 1000/20                           = 75.0 h
      transfer= (800/20)/4 + 400/20
                + (900/20)/1 + 450/20                           = 97.5 h
    """
    origin = _port("Origin")
    destination = _port("Destination")
    hub = _port("Hub")
    direct = _route("DIRECT", [origin, destination], [1000.0, 1000.0], vessels=direct_vessels)
    feeder = _route("FEEDER", [origin, hub], [400.0, 400.0], vessels=feeder_vessels)
    trunk = _route("TRUNK", [hub, destination], [450.0, 450.0], vessels=trunk_vessels)
    context = _context([origin, hub, destination], [direct, feeder, trunk])
    return context, _shipment(origin, destination)


def test_prefers_direct_service_over_shorter_distance_with_a_transfer() -> None:
    context, shipment = _transfer_penalty_fixture()

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("DIRECT", 1, 1)]
    assert shipment.current_booking_index == 1


def test_takes_the_transfer_when_frequent_services_make_it_genuinely_faster() -> None:
    # Nine vessels on the trunk shrink its boarding wait from 45 h to 5 h, so
    # the shorter-distance two-leg path becomes the faster one as well
    # (30.0 + 27.5 = 57.5 h against the direct service's 75.0 h).
    context, shipment = _transfer_penalty_fixture(trunk_vessels=9)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]
    assert [b.sequence_index for b in shipment.associated_bookings] == [1, 2]


def test_bookings_are_registered_on_their_service_routes() -> None:
    context, shipment = _transfer_penalty_fixture()

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    direct = context.service_routes[0]
    assert [b.shipment for b in direct.associated_bookings] == [shipment]
    assert direct.associated_bookings == shipment.associated_bookings


# ---------------------------------------------------------------------------
# Congestion handling.
# ---------------------------------------------------------------------------


def test_congested_direct_leg_is_used_when_it_still_beats_the_detour() -> None:
    origin = _port("Origin")
    destination = _port("Destination")
    hub = _port("Hub")
    # Direct leg is congested 2x: 100 nm -> 10 h. The detour is 4000 nm.
    direct = _route("DIRECT", [origin, destination], [100.0, 100.0], multipliers=[2.0, 1.0])
    feeder = _route("FEEDER", [origin, hub], [2000.0, 2000.0])
    trunk = _route("TRUNK", [hub, destination], [2000.0, 2000.0])
    context = _context([origin, hub, destination], [direct, feeder, trunk])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("DIRECT", 1, 1)]


def test_severely_congested_leg_is_avoided_when_a_clean_path_exists() -> None:
    origin = _port("Origin")
    destination = _port("Destination")
    hub = _port("Hub")
    direct = _route("DIRECT", [origin, destination], [1000.0, 1000.0], multipliers=[5.0, 1.0])
    feeder = _route("FEEDER", [origin, hub], [600.0, 600.0])
    trunk = _route("TRUNK", [hub, destination], [600.0, 600.0])
    context = _context([origin, hub, destination], [direct, feeder, trunk])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]


def test_delegates_when_every_path_must_cross_a_congested_leg() -> None:
    # The organizer's protective wait must stay in control here.
    origin = _port("Origin")
    destination = _port("Destination")
    direct = _route("DIRECT", [origin, destination], [1000.0, 1000.0], multipliers=[5.0, 1.0])
    context = _context([origin, destination], [direct])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None
    assert shipment.associated_bookings == []
    assert shipment.current_booking_index is None


# ---------------------------------------------------------------------------
# Port closures.
# ---------------------------------------------------------------------------


def test_closed_transshipment_port_without_a_reopening_time_is_not_booked() -> None:
    origin = _port("Origin")
    destination = _port("Destination")
    hub = _port("Hub", closed=True)
    direct = _route("DIRECT", [origin, destination], [3000.0, 3000.0])
    feeder = _route("FEEDER", [origin, hub], [100.0, 100.0], vessels=20)
    trunk = _route("TRUNK", [hub, destination], [100.0, 100.0], vessels=20)
    context = _context([origin, hub, destination], [direct, feeder, trunk])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("DIRECT", 1, 1)]


def test_delegates_when_a_closed_destination_has_no_reopening_time() -> None:
    origin = _port("Origin")
    destination = _port("Destination", closed=True)
    direct = _route("DIRECT", [origin, destination], [1000.0, 1000.0])
    context = _context([origin, destination], [direct])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None
    assert shipment.associated_bookings == []


def test_intermediate_closed_call_without_a_reopening_time_is_not_booked_through() -> None:
    origin = _port("Origin")
    middle = _port("Middle", closed=True)
    destination = _port("Destination")
    # A single route Origin -> Middle -> Destination -> Origin: the two-leg edge
    # Origin->Destination calls at the closed Middle and must be rejected.
    ring = _route("RING", [origin, middle, destination], [100.0, 100.0, 100.0])
    context = _context([origin, middle, destination], [ring])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


# ---------------------------------------------------------------------------
# Availability and orphan-booking guards.
# ---------------------------------------------------------------------------


def test_alternative_service_routes_are_never_booked() -> None:
    origin = _port("Origin")
    destination = _port("Destination")
    source = _route("SRC", [origin, _port("Elsewhere")], [10.0, 10.0])
    alternative = _route("SRC-ALT-1", [origin, destination], [10.0, 10.0])
    alternative.source_service_route = source
    context = _context([origin, destination], [alternative])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_route_without_deployed_vessels_is_never_booked() -> None:
    origin = _port("Origin")
    destination = _port("Destination")
    direct = _route("DIRECT", [origin, destination], [1000.0, 1000.0])
    direct.deployed_vessels = []
    context = _context([origin, destination], [direct])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_headway_uses_the_live_deployed_vessel_count() -> None:
    """The same network flips its decision purely on deployed vessel counts.

    direct (1 vessel)  = 0.5 * (1000/20)/1 + 500/20 = 50.0 h
    direct (5 vessels) = 0.5 * (1000/20)/5 + 500/20 = 30.0 h
    transfer           = 2 * (0.5 * (600/20)/2 + 300/20) = 45.0 h
    """
    origin = _port("Origin")
    destination = _port("Destination")
    hub = _port("Hub")
    direct = _route("DIRECT", [origin, destination], [500.0, 500.0], vessels=1)
    feeder = _route("FEEDER", [origin, hub], [300.0, 300.0], vessels=2)
    trunk = _route("TRUNK", [hub, destination], [300.0, 300.0], vessels=2)
    context = _context([origin, hub, destination], [direct, feeder, trunk])

    infrequent = _shipment(origin, destination)
    assert UserStrategy.assign_associated_bookings(context, NOW, infrequent) is True
    assert _chain(infrequent) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]

    direct.deployed_vessels = direct.deployed_vessels * 5
    frequent = _shipment(origin, destination)
    assert UserStrategy.assign_associated_bookings(context, NOW, frequent) is True
    assert _chain(frequent) == [("DIRECT", 1, 1)]


# ---------------------------------------------------------------------------
# Delegation and fail-closed behaviour.
# ---------------------------------------------------------------------------


def test_shipment_that_already_has_bookings_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    shipment.associated_bookings = [object()]

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_shipment_with_a_current_booking_index_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    shipment.current_booking_index = 1

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_same_origin_and_destination_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    shipment.demand.destination_port = shipment.demand.origin_port

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_unreachable_destination_delegates() -> None:
    origin = _port("Origin")
    destination = _port("Destination")
    island = _route("ISLAND", [origin, _port("Elsewhere")], [10.0, 10.0])
    context = _context([origin, destination], [island])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_non_finite_distance_delegates_without_partial_chain() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments[0].associated_leg.sailing_distance = float("nan")

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None
    assert shipment.associated_bookings == []
    assert all(route.associated_bookings == [] for route in context.service_routes)


def test_non_finite_multiplier_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments[0].associated_leg.sailing_time_multiplier = float("inf")

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_non_positive_speed_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].deployed_vessels[0].vessel_class.sailing_speed = 0.0

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_discontinuous_route_cycle_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments[1].associated_leg.departure_port = _port("Stray")

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_duplicate_segment_sequence_index_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments[1].sequence_index = 1

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_malformed_context_delegates() -> None:
    assert UserStrategy.assign_associated_bookings({"k": 1}, NOW, object()) is None


def test_missing_ports_collection_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.ports = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_port_missing_from_the_context_collection_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.ports = list(context.ports)[:-1]

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_repeated_calls_are_deterministic() -> None:
    first_context, first = _transfer_penalty_fixture()
    second_context, second = _transfer_penalty_fixture()

    assert UserStrategy.assign_associated_bookings(first_context, NOW, first) is True
    assert UserStrategy.assign_associated_bookings(second_context, NOW, second) is True
    assert _chain(first) == _chain(second)


# ---------------------------------------------------------------------------
# The other three hooks stay delegated.
# ---------------------------------------------------------------------------


def test_berth_selection_remains_delegated() -> None:
    assert UserStrategy.select_vessel_for_berth(object(), object(), [], [], NOW) is None


def test_the_fleet_decision_is_owned_and_creates_nothing() -> None:
    """Every vessel stays on its rotation, whatever the context looks like."""
    routes = [object(), object()]
    vessels = [object()]
    context = SimpleNamespace(service_routes=routes, vessels=vessels, disruption_plans=[])

    assert UserStrategy.create_alternative_service_routes(context, NOW) is not None
    assert UserStrategy.create_alternative_service_routes(context, NOW, vessels[0]) is not None
    assert context.service_routes == routes
    assert context.vessels == vessels


def test_the_fleet_decision_holds_even_for_a_malformed_context() -> None:
    assert UserStrategy.create_alternative_service_routes(object(), NOW) is not None
    assert UserStrategy.create_alternative_service_routes(None, None, None) is not None


# ---------------------------------------------------------------------------
# Remaining fail-closed guards.
# ---------------------------------------------------------------------------


def test_non_real_distance_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments[0].associated_leg.sailing_distance = "far"

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_boolean_distance_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments[0].associated_leg.sailing_distance = True

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_unnamed_port_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.ports[1].name = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_duplicate_port_in_context_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.ports.append(context.ports[0])

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_port_without_a_berths_collection_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.ports[1].berths = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_non_boolean_berth_availability_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.ports[1].berths[0].is_available = 1

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_port_without_berths_is_treated_as_open() -> None:
    context, shipment = _transfer_penalty_fixture()
    for port in context.ports:
        port.berths = []

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("DIRECT", 1, 1)]


def test_missing_service_routes_collection_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_route_without_a_bookings_list_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].associated_bookings = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_route_with_a_single_segment_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments = context.service_routes[0].segments[:1]

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_missing_segments_collection_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_negative_segment_sequence_index_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments[0].sequence_index = -1

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_missing_associated_leg_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments[0].associated_leg = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_leg_port_outside_the_context_collection_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].segments[0].associated_leg.arrival_port = _port("Ghost")
    context.service_routes[0].segments[1].associated_leg.departure_port = (
        context.service_routes[0].segments[0].associated_leg.arrival_port
    )

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_missing_vessel_class_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    context.service_routes[0].deployed_vessels[0].vessel_class = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_missing_demand_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    shipment.demand = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_bookings_attribute_that_is_not_a_list_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    shipment.associated_bookings = ()

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_origin_absent_from_the_context_port_collection_delegates() -> None:
    context, shipment = _transfer_penalty_fixture()
    shipment.demand.origin_port = _port("Nowhere")

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None


def test_a_long_way_round_edge_is_costed_with_intermediate_berthing() -> None:
    # One ring route: Origin -> A -> Destination -> Origin. The long-way-round
    # single booking pays 3 h for its intermediate call at A.
    origin = _port("Origin")
    middle = _port("A")
    destination = _port("Destination")
    ring = _route("RING", [origin, middle, destination], [200.0, 200.0, 200.0], vessels=2)
    context = _context([origin, middle, destination], [ring])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    # Segments 1 and 2 carry the shipment from Origin through A to Destination.
    assert _chain(shipment) == [("RING", 1, 2)]


def _headway_coefficient_fixture() -> tuple[Any, Any]:
    """A network whose cheapest chain depends on the price of one boarding.

    ``direct`` is a high-frequency 800 nm service; ``feeder`` + ``trunk`` reach
    the destination in 200 + 200 nm but each runs a single vessel, so each
    boarding is expensive:

      direct   = (1600/20)/8 + 800/20                     = 10 + 40 = 50.0 h
      transfer = (400/20)/1 + 200/20  (feeder)
               + (400/20)/1 + 200/20  (trunk)             = 30 + 30 = 60.0 h

    Charging only half a headway per boarding would instead make the transfer
    look cheaper (40.0 h against 45.0 h) and would pick it, so this fixture
    discriminates between the two costings.
    """
    origin = _port("Origin")
    destination = _port("Destination")
    hub = _port("Hub")
    direct = _route("DIRECT", [origin, destination], [800.0, 800.0], vessels=8)
    feeder = _route("FEEDER", [origin, hub], [200.0, 200.0], vessels=1)
    trunk = _route("TRUNK", [hub, destination], [200.0, 200.0], vessels=1)
    context = _context([origin, hub, destination], [direct, feeder, trunk])
    return context, _shipment(origin, destination)


def test_a_boarding_costs_a_full_headway_not_half() -> None:
    context, shipment = _headway_coefficient_fixture()

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("DIRECT", 1, 1)]


# ---------------------------------------------------------------------------
# A closure is temporary: cargo arriving after it lifts may pass through.
# ---------------------------------------------------------------------------

NOW_DAYS = 200.0


def _closure_plan(port: Any, reopen_hours: float, duration_days: float = 5.0) -> Any:
    """A close-berth plan for ``port`` that lifts ``reopen_hours`` from ``NOW``."""
    return SimpleNamespace(
        target_leg=None,
        target_berth=SimpleNamespace(port=port),
        start_offset_days=NOW_DAYS + reopen_hours / 24.0 - duration_days,
        duration_days=duration_days,
        multiplier=1.0,
        close_berth=True,
    )


def _timed_closure_fixture(reopen_hours: float) -> tuple[Any, Any]:
    """A short ride through a shut hub against a long ride that avoids it.

    ``VIA`` reaches the destination in two 100 nm legs but calls at the shut
    ``Hub`` five hours in; ``LONG`` sails 400 nm straight there. Boarding costs
    a full headway on each: 15 h for VIA, 40 h for LONG.

      VIA  = max(15 + 5, reopen) - 5 + 13   (13 h of sailing plus one call)
      LONG = 40 + 20                                              = 60.0 h

    So VIA costs 28 h once the hub has reopened by the time cargo gets there,
    and reopen + 8 h while it has not.
    """
    origin = _port("Origin")
    hub = _port("Hub", closed=True)
    destination = _port("Destination")
    via = _route("VIA", [origin, hub, destination], [100.0, 100.0, 100.0], vessels=1)
    long_way = _route("LONG", [origin, destination], [400.0, 400.0], vessels=1)
    context = _context([origin, hub, destination], [via, long_way])
    context.disruption_plans = [_closure_plan(hub, reopen_hours)]
    return context, _shipment(origin, destination)


def test_shut_hub_is_used_when_cargo_arrives_after_it_reopens() -> None:
    # Reopens in 20 h; the ride reaches the hub at 20 h, so nothing is lost.
    context, shipment = _timed_closure_fixture(20.0)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("VIA", 1, 2)]


def test_shut_hub_is_avoided_when_it_reopens_too_late() -> None:
    # Reopens in 100 h, so VIA would cost 108 h against LONG's 60 h.
    context, shipment = _timed_closure_fixture(100.0)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("LONG", 1, 1)]


def test_a_closed_destination_is_booked_rather_than_held_when_it_reopens() -> None:
    """Cargo bound for a shut port should travel and arrive as it reopens.

    Holding it at the origin and only then sailing can never be faster than
    sailing now and waiting at the far end, so a readable reopening time turns
    this from a delegation into a booking.
    """
    origin = _port("Origin")
    destination = _port("Destination", closed=True)
    direct = _route("DIRECT", [origin, destination], [400.0, 400.0], vessels=1)
    context = _context([origin, destination], [direct])
    context.disruption_plans = [_closure_plan(destination, 100.0)]
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("DIRECT", 1, 1)]


def test_a_closure_wait_delays_the_rest_of_the_ride() -> None:
    import response_strategies.user_strategy as strategy

    # Two 20 h legs at normal speed with a 3 h call between them, and the port
    # reached after the first leg is shut until hour 100.
    edge = strategy._Edge(
        departure_index=0,
        arrival_index=1,
        route_index=0,
        departure_segment_index=1,
        arrival_segment_index=2,
        hours=43.0,
        crosses_congestion=False,
        timeline=((20.0, 1.0, 0.0, 100.0), (20.0, 1.0, 0.0, 0.0)),
    )
    # Setting off now, the call at hour 20 waits until 100, then 3 h alongside
    # and a 20 h leg finish at 123 rather than 43.
    assert strategy._edge_arrival(edge, 0.0) == 123.0
    # Setting off late enough that the port is already open costs nothing extra.
    assert strategy._edge_arrival(edge, 110.0) == 153.0


def test_a_ride_with_nothing_disrupted_is_a_single_addition() -> None:
    import response_strategies.user_strategy as strategy

    edge = strategy._Edge(
        departure_index=0,
        arrival_index=1,
        route_index=0,
        departure_segment_index=1,
        arrival_segment_index=1,
        hours=50.0,
        crosses_congestion=False,
        timeline=None,
    )
    assert strategy._edge_arrival(edge, 7.0) == 57.0


def test_a_slowdown_that_lifts_before_the_leg_starts_is_not_charged() -> None:
    import response_strategies.user_strategy as strategy

    # One 20 h leg currently running at 5x, with the slowdown lifting at hour 10.
    edge = strategy._Edge(
        departure_index=0,
        arrival_index=1,
        route_index=0,
        departure_segment_index=1,
        arrival_segment_index=1,
        hours=100.0,
        crosses_congestion=True,
        timeline=((20.0, 5.0, 10.0, 0.0),),
    )
    # Sailing now, while the slowdown still applies: 20 * 5.
    assert strategy._edge_arrival(edge, 0.0) == 100.0
    # Setting off after it lifts: full speed.
    assert strategy._edge_arrival(edge, 10.0) == 30.0


def test_a_slowdown_with_no_known_end_is_charged_forever() -> None:
    import response_strategies.user_strategy as strategy

    edge = strategy._Edge(
        departure_index=0,
        arrival_index=1,
        route_index=0,
        departure_segment_index=1,
        arrival_segment_index=1,
        hours=100.0,
        crosses_congestion=True,
        timeline=((20.0, 5.0, float("inf"), 0.0),),
    )
    assert strategy._edge_arrival(edge, 0.0) == 100.0
    assert strategy._edge_arrival(edge, 10_000.0) == 10_100.0


def test_an_inactive_closure_plan_leaves_the_port_impassable() -> None:
    # The plan has already lifted, so the live berth state and the plan
    # disagree; the port is treated as impassable rather than mis-timed.
    context, shipment = _timed_closure_fixture(20.0)
    context.disruption_plans = [
        SimpleNamespace(
            target_leg=None,
            target_berth=SimpleNamespace(port=context.ports[1]),
            start_offset_days=1.0,
            duration_days=2.0,
            multiplier=1.0,
            close_berth=True,
        )
    ]

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("LONG", 1, 1)]


def test_a_malformed_closure_plan_leaves_the_port_impassable() -> None:
    context, shipment = _timed_closure_fixture(20.0)
    context.disruption_plans = [_closure_plan(context.ports[1], 20.0)]
    context.disruption_plans[0].duration_days = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("LONG", 1, 1)]


def test_a_non_datetime_now_leaves_closures_impassable() -> None:
    context, shipment = _timed_closure_fixture(20.0)

    assert UserStrategy.assign_associated_bookings(context, 12345, shipment) is True
    assert _chain(shipment) == [("LONG", 1, 1)]


def test_congested_leg_plans_do_not_produce_reopening_times() -> None:
    context, shipment = _timed_closure_fixture(20.0)
    leg = context.service_routes[0].segments[0].associated_leg
    context.disruption_plans.append(
        SimpleNamespace(
            target_leg=leg,
            target_berth=None,
            start_offset_days=NOW_DAYS - 1.0,
            duration_days=5.0,
            multiplier=2.0,
            close_berth=False,
        )
    )

    # The congested-leg plan is ignored by the closure map, so the hub's own
    # reopening time still applies and the short ride is still chosen.
    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("VIA", 1, 2)]


# ---------------------------------------------------------------------------
# In-transit chains are kept when they already beat every alternative.
# ---------------------------------------------------------------------------


def _booking(
    sequence_index: int, shipment: Any, route: Any, departure: int, arrival: int
) -> SimpleNamespace:
    booking = SimpleNamespace(
        sequence_index=sequence_index,
        shipment=shipment,
        service_route=route,
        departure_segment_index=departure,
        arrival_segment_index=arrival,
    )
    route.associated_bookings.append(booking)
    return booking


def _in_transit_fixture(reopen_hours: float, *, closed: bool = True) -> tuple[Any, Any, Any]:
    """A vessel at ``Mid`` carrying cargo booked onward through a shut port.

    ``MAIN`` runs Origin -> Mid -> Shut -> Dest -> Origin on 100 nm legs with one
    vessel, so a boarding costs its 20 h cycle. ``BYPASS`` runs Mid -> Dest on
    1000 nm legs with one vessel, so boarding it costs 100 h.

      keep      = ride Mid->Dest on MAIN: 10 h sailing + 3 h call, with the shut
                  call 5 h in held until it reopens
      bypass    = 50 h of sailing, costed with no wait to board
    """
    origin = _port("Origin")
    mid = _port("Mid")
    shut = _port("Shut", closed=closed)
    dest = _port("Dest")
    main = _route("MAIN", [origin, mid, shut, dest], [100.0, 100.0, 100.0, 100.0], vessels=1)
    bypass = _route("BYPASS", [mid, dest], [1000.0, 1000.0], vessels=1)
    context = _context([origin, mid, shut, dest], [main, bypass])
    context.disruption_plans = [_closure_plan(shut, reopen_hours)] if closed else []

    shipment = SimpleNamespace(
        teu_size=10.0,
        demand=SimpleNamespace(origin_port=origin, destination_port=dest),
        associated_bookings=[],
        current_booking_index=1,
    )
    shipment.associated_bookings.append(_booking(1, shipment, main, 1, 3))
    vessel = SimpleNamespace(
        index=0,
        vessel_class=SimpleNamespace(sailing_speed=20.0),
        assigned_service_route=main,
        current_segment=main.segments[0],
        current_berth=None,
        carried_shipments=[shipment],
    )
    return context, vessel, shipment


def _freeze_chain(shipment: Any) -> list[tuple[str, int, int, int]]:
    return [
        (
            b.service_route.id,
            b.sequence_index,
            b.departure_segment_index,
            b.arrival_segment_index,
        )
        for b in shipment.associated_bookings
    ]


def test_a_booked_chain_that_beats_every_alternative_is_kept() -> None:
    # The shut port reopens in 8 h, well before the cargo could reach the
    # destination any other way, so staying aboard wins.
    context, vessel, shipment = _in_transit_fixture(8.0)
    before = _freeze_chain(shipment)
    index_before = shipment.current_booking_index

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is True
    assert _freeze_chain(shipment) == before
    assert shipment.current_booking_index == index_before


def test_a_long_closure_delegates_so_the_organizer_can_replan() -> None:
    # Reopening in 500 h makes staying aboard far worse than the bypass, so the
    # organizer keeps control of the replan.
    context, vessel, shipment = _in_transit_fixture(500.0)

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_an_undisrupted_remaining_chain_delegates() -> None:
    # Nothing on the rest of the journey is disrupted, so the organizer would
    # not replan either and there is no decision to take.
    context, vessel, shipment = _in_transit_fixture(8.0, closed=False)

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_vessel_carrying_nothing_delegates() -> None:
    context, vessel, _shipment = _in_transit_fixture(8.0)
    vessel.carried_shipments = []

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_vessel_with_no_current_segment_delegates() -> None:
    context, vessel, _shipment = _in_transit_fixture(8.0)
    vessel.current_segment = None

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_shipment_whose_current_booking_ends_here_delegates() -> None:
    # The booking finishes at Mid, so there is nothing left to compare.
    context, vessel, shipment = _in_transit_fixture(8.0)
    shipment.associated_bookings[0].arrival_segment_index = 1

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_shipment_with_an_unknown_current_booking_index_delegates() -> None:
    context, vessel, shipment = _in_transit_fixture(8.0)
    shipment.current_booking_index = 99

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_malformed_booking_sequence_delegates() -> None:
    context, vessel, shipment = _in_transit_fixture(8.0)
    shipment.associated_bookings[0].sequence_index = "first"

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_booking_on_an_unknown_route_delegates() -> None:
    context, vessel, shipment = _in_transit_fixture(8.0)
    shipment.associated_bookings[0].service_route = None

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_the_veto_never_mutates_the_context() -> None:
    context, vessel, shipment = _in_transit_fixture(8.0)
    routes_before = [list(route.associated_bookings) for route in context.service_routes]
    carried_before = list(vessel.carried_shipments)

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is True
    assert [list(route.associated_bookings) for route in context.service_routes] == routes_before
    assert vessel.carried_shipments == carried_before


def test_a_multi_booking_chain_is_walked_from_the_current_port() -> None:
    """A later booking on another service must be costed too, not ignored."""
    context, vessel, shipment = _in_transit_fixture(8.0)
    main, bypass = context.service_routes
    # Re-book as MAIN Origin->Shut then BYPASS is not connected from Shut, so
    # use MAIN Origin->Mid->Shut then MAIN Shut->Dest as a second booking.
    shipment.associated_bookings.clear()
    main.associated_bookings.clear()
    shipment.associated_bookings.append(_booking(1, shipment, main, 1, 2))
    shipment.associated_bookings.append(_booking(2, shipment, main, 3, 3))
    shipment.current_booking_index = 1

    result = UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel)
    assert result in (True, None)
    # Whatever it decides, it must not have touched the chain.
    assert [b.sequence_index for b in shipment.associated_bookings] == [1, 2]


def test_a_vessel_whose_current_leg_has_no_arrival_port_delegates() -> None:
    context, vessel, _shipment = _in_transit_fixture(8.0)
    vessel.current_segment.associated_leg.arrival_port = None

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_veto_needs_the_current_port_in_the_context() -> None:
    context, vessel, _shipment = _in_transit_fixture(8.0)
    context.ports = [port for port in context.ports if port.name != "Mid"]

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_veto_delegates_on_a_malformed_port_collection() -> None:
    context, vessel, _shipment = _in_transit_fixture(8.0)
    context.ports = None

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_veto_delegates_on_a_non_boolean_berth_state() -> None:
    context, vessel, _shipment = _in_transit_fixture(8.0)
    context.ports[1].berths[0].is_available = "yes"

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_shipment_without_bookings_is_skipped_by_the_veto() -> None:
    context, vessel, shipment = _in_transit_fixture(8.0)
    bare = SimpleNamespace(
        teu_size=1.0,
        demand=shipment.demand,
        associated_bookings=[],
        current_booking_index=None,
    )
    vessel.carried_shipments = [bare, shipment]

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is True


def test_a_veto_delegates_when_a_booked_route_is_malformed() -> None:
    context, vessel, _shipment = _in_transit_fixture(8.0)
    context.service_routes[0].segments[1].sequence_index = 1

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_veto_delegates_when_a_booked_leg_is_malformed() -> None:
    context, vessel, _shipment = _in_transit_fixture(8.0)
    context.service_routes[0].segments[1].associated_leg.sailing_time_multiplier = None

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_veto_delegates_when_a_booked_leg_leaves_the_context() -> None:
    context, vessel, _shipment = _in_transit_fixture(8.0)
    context.service_routes[0].segments[1].associated_leg.arrival_port = _port("Ghost")

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_veto_delegates_when_the_arrival_segment_is_unknown() -> None:
    context, vessel, shipment = _in_transit_fixture(8.0)
    shipment.associated_bookings[0].arrival_segment_index = 99

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_fully_congested_network_still_gets_a_decision() -> None:
    """Cargo already at sea needs no congestion-free alternative to exist.

    Insisting on one is right when *booking* cargo, because committing it to a
    leg with no way round is a choice. Here the cargo is aboard already, so
    whatever alternative exists is simply costed and compared.
    """
    context, vessel, _shipment = _in_transit_fixture(8.0)
    for route in context.service_routes:
        for segment in route.segments:
            segment.associated_leg.sailing_time_multiplier = 5.0

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is True


def _fair_cost_fixture() -> tuple[Any, Any, Any]:
    """Staying aboard beats transferring, but not the transfer's sailing alone.

      keep      = MAIN Mid->Shut->Dest: 15 + 15 h sailing + 3 h call  = 33 h
      bypass    = 20 h of sailing, plus 20 h to board BYPASS          = 40 h
                  (sailing alone, ignoring the wait, would be only 20 h)

    So costing the alternative fairly keeps the cargo aboard, while costing it
    with no boarding wait would hand the replan back to the organizer.
    """
    origin = _port("Origin")
    mid = _port("Mid")
    shut = _port("Shut", closed=True)
    dest = _port("Dest")
    main = _route("MAIN", [origin, mid, shut, dest], [100.0, 300.0, 300.0, 100.0], vessels=1)
    bypass = _route("BYPASS", [mid, dest], [400.0, 400.0], vessels=2)
    context = _context([origin, mid, shut, dest], [main, bypass])
    context.disruption_plans = [_closure_plan(shut, 1.0)]

    shipment = SimpleNamespace(
        teu_size=10.0,
        demand=SimpleNamespace(origin_port=origin, destination_port=dest),
        associated_bookings=[],
        current_booking_index=1,
    )
    shipment.associated_bookings.append(_booking(1, shipment, main, 1, 3))
    vessel = SimpleNamespace(
        index=0,
        vessel_class=SimpleNamespace(sailing_speed=20.0),
        assigned_service_route=main,
        current_segment=main.segments[0],
        current_berth=None,
        carried_shipments=[shipment],
    )
    return context, vessel, shipment


def test_the_alternative_pays_the_wait_to_board_a_different_service() -> None:
    context, vessel, shipment = _fair_cost_fixture()
    before = _freeze_chain(shipment)

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is True
    assert _freeze_chain(shipment) == before


def test_no_alternative_at_all_keeps_the_chain() -> None:
    # BYPASS removed: nothing else reaches the destination, so the organizer
    # would leave the chain alone too and keeping is the right call.
    context, vessel, _shipment = _in_transit_fixture(8.0)
    context.service_routes = [context.service_routes[0]]

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is True


def test_a_veto_delegates_when_the_network_cannot_be_built() -> None:
    context, vessel, _shipment = _in_transit_fixture(8.0)
    context.service_routes[1].deployed_vessels[0].vessel_class.sailing_speed = -1.0

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_a_chain_ending_at_the_current_port_is_skipped() -> None:
    context, vessel, shipment = _in_transit_fixture(8.0)
    main = context.service_routes[0]
    shipment.associated_bookings.clear()
    main.associated_bookings.clear()
    # Booked Origin -> Shut -> Dest -> Origin -> back to Mid: ends where we are.
    shipment.associated_bookings.append(_booking(1, shipment, main, 1, 1))
    shipment.associated_bookings.append(_booking(2, shipment, main, 2, 1))
    shipment.current_booking_index = 2

    assert UserStrategy.adjust_bookings_before_cargo_handling(context, NOW, vessel) is None


def test_the_booking_hook_still_fails_closed_on_junk() -> None:
    assert UserStrategy.assign_associated_bookings(object(), NOW, object()) is None


def test_the_veto_hook_fails_closed_on_junk() -> None:
    assert UserStrategy.adjust_bookings_before_cargo_handling(object(), NOW, object()) is None


# ---------------------------------------------------------------------------
# A slowdown is temporary too: cargo sailing after it lifts is not charged.
# ---------------------------------------------------------------------------


def _congestion_plan(
    leg: Any, clears_hours: float, *, duration_days: float = 5.0, multiplier: float = 5.0
) -> Any:
    """A congested-leg plan for ``leg`` that lifts ``clears_hours`` from ``NOW``."""
    return SimpleNamespace(
        target_leg=leg,
        target_berth=None,
        start_offset_days=NOW_DAYS + clears_hours / 24.0 - duration_days,
        duration_days=duration_days,
        multiplier=multiplier,
        close_berth=False,
    )


def _timed_congestion_fixture(clears_hours: float) -> tuple[Any, Any]:
    """A slowed direct service against a clean two-leg detour.

    ``DIRECT``'s outbound leg is running at 5x right now. Sailing it while
    slowed costs 50 h; once the slowdown lifts it costs 10 h.

      direct while slowed = (400 * 5 / 20)/4 boarding + 200 * 5 / 20  = 75.0 h
      direct once clear   = (400 * 5 / 20)/4 boarding + 200 / 20      = 35.0 h
      detour              = 2 * ((600/20)/4 + 300/20)                 = 45.0 h
    """
    origin = _port("Origin")
    destination = _port("Destination")
    hub = _port("Hub")
    direct = _route(
        "DIRECT", [origin, destination], [200.0, 200.0], vessels=4, multipliers=[5.0, 1.0]
    )
    feeder = _route("FEEDER", [origin, hub], [300.0, 300.0], vessels=4)
    trunk = _route("TRUNK", [hub, destination], [300.0, 300.0], vessels=4)
    context = _context([origin, hub, destination], [direct, feeder, trunk])
    context.disruption_plans = [_congestion_plan(direct.segments[0].associated_leg, clears_hours)]
    return context, _shipment(origin, destination)


def test_a_slowed_leg_is_used_when_it_clears_before_the_cargo_sails_it() -> None:
    context, shipment = _timed_congestion_fixture(2.0)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("DIRECT", 1, 1)]


def test_a_slowed_leg_is_avoided_when_it_is_still_slow_on_arrival() -> None:
    context, shipment = _timed_congestion_fixture(500.0)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]


def test_a_slowdown_with_no_matching_plan_is_assumed_permanent() -> None:
    context, shipment = _timed_congestion_fixture(2.0)
    context.disruption_plans = []

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]


def test_an_expired_congestion_plan_is_assumed_permanent() -> None:
    context, shipment = _timed_congestion_fixture(2.0)
    context.disruption_plans[0].start_offset_days = 1.0
    context.disruption_plans[0].duration_days = 2.0

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]


def test_a_malformed_congestion_plan_assumes_the_slowdown_is_permanent() -> None:
    """An unreadable plan must not be read optimistically.

    Failing closed here means assuming the slowdown lasts, which is the
    conservative reading and matches how an unreadable closure is treated. The
    booking still goes ahead; it just takes the detour.
    """
    context, shipment = _timed_congestion_fixture(2.0)
    context.disruption_plans[0].duration_days = None

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]


def test_a_non_boolean_close_flag_assumes_the_slowdown_is_permanent() -> None:
    context, shipment = _timed_congestion_fixture(2.0)
    context.disruption_plans[0].close_berth = 0

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]


def test_a_congestion_plan_whose_leg_is_no_longer_slowed_is_ignored() -> None:
    context, shipment = _timed_congestion_fixture(2.0)
    # The plan is active but the live multiplier has already been restored, so
    # plan and live state disagree and the leg is simply not slowed.
    for segment in context.service_routes[0].segments:
        segment.associated_leg.sailing_time_multiplier = 1.0

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("DIRECT", 1, 1)]


def test_a_non_positive_planned_multiplier_assumes_the_slowdown_is_permanent() -> None:
    context, shipment = _timed_congestion_fixture(2.0)
    context.disruption_plans[0].multiplier = 0.0

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]


def test_a_non_datetime_now_assumes_slowdowns_are_permanent() -> None:
    context, shipment = _timed_congestion_fixture(2.0)

    assert UserStrategy.assign_associated_bookings(context, 12345, shipment) is True
    assert _chain(shipment) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]


def test_closure_and_slowdown_timings_combine_on_one_ride() -> None:
    import response_strategies.user_strategy as strategy

    # Leg 1: 20 h at 3x until hour 30, arriving at a port shut until hour 90.
    # Leg 2: 20 h at 2x until hour 200.
    edge = strategy._Edge(
        departure_index=0,
        arrival_index=2,
        route_index=0,
        departure_segment_index=1,
        arrival_segment_index=2,
        hours=103.0,
        crosses_congestion=True,
        timeline=((20.0, 3.0, 30.0, 90.0), (20.0, 2.0, 200.0, 0.0)),
    )
    # From hour 0: leg 1 slowed to 60 h, waits for the port until 90, 3 h
    # alongside, then leg 2 still slowed at 40 h -> 133.
    assert strategy._edge_arrival(edge, 0.0) == 133.0
    # From hour 300 both have lifted and the port is open: 20 + 3 + 20.
    assert strategy._edge_arrival(edge, 300.0) == 343.0
