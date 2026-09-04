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
    speeds: list[float] | None = None,
    multipliers: list[float] | None = None,
    positions: list[int] | None = None,
    alongside: bool = False,
    stranded: bool = False,
) -> SimpleNamespace:
    """Build a cyclic route visiting ``ports`` in order and returning to start.

    ``ports`` lists the departure port of each leg; the cycle closes back onto
    ``ports[0]``. ``distances`` has one entry per leg.

    Each deployed vessel is given a position on the rotation, because the
    strategy reads live vessel positions to price the first boarding. By
    default the vessels are spread evenly around the cycle, which is what a
    settled service looks like. ``positions`` places them explicitly,
    ``alongside`` puts them at a berth rather than at sea, and ``stranded``
    points them at a segment of another route so they cannot be located, which
    is the case that falls back to the headway expectation.
    """
    route = SimpleNamespace(
        id=route_id,
        name=route_id,
        source_service_route=None,
        disruption_key=None,
        associated_bookings=[],
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
    count = len(route.segments)
    if positions is None:
        positions = [(index * count) // vessels for index in range(vessels)]
    vessel_speeds = speeds if speeds is not None else [speed] * vessels
    foreign = SimpleNamespace(sequence_index=1, associated_leg=None)
    route.deployed_vessels = [
        SimpleNamespace(
            index=index,
            vessel_class=SimpleNamespace(sailing_speed=vessel_speeds[index]),
            current_segment=(foreign if stranded else route.segments[positions[index] % count]),
            current_berth=SimpleNamespace() if alongside else None,
            carried_shipments=[],
        )
        for index in range(vessels)
    ]
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


def test_closed_transshipment_port_is_not_booked() -> None:
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


def test_delegates_when_the_destination_port_is_closed() -> None:
    origin = _port("Origin")
    destination = _port("Destination", closed=True)
    direct = _route("DIRECT", [origin, destination], [1000.0, 1000.0])
    context = _context([origin, destination], [direct])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is None
    assert shipment.associated_bookings == []


def test_intermediate_call_at_a_closed_port_is_not_booked_through() -> None:
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


def _vessel_count_fixture(*, direct_vessels: int) -> tuple[Any, Any]:
    origin = _port("Origin")
    destination = _port("Destination")
    hub = _port("Hub")
    direct = _route("DIRECT", [origin, destination], [500.0, 500.0], vessels=direct_vessels)
    feeder = _route("FEEDER", [origin, hub], [300.0, 300.0], vessels=2)
    trunk = _route("TRUNK", [hub, destination], [300.0, 300.0], vessels=2)
    context = _context([origin, hub, destination], [direct, feeder, trunk])
    return context, _shipment(origin, destination)


def test_more_vessels_around_the_rotation_shorten_the_wait_and_flip_the_choice() -> None:
    """Deploying a second vessel on the direct service must change the plan.

    One vessel on DIRECT has just left the origin, so the next sailing is a
    whole cycle away and the two-leg path wins:

      direct   = (0.5 * 25 + 3 + 25 + 3) + 25                    = 68.5 h
      transfer = (0.5 * 15 + 3) + 15  + (600/20)/2 + 15          = 55.5 h

    A second DIRECT vessel on the return leg is about to arrive, which is what
    a higher-frequency service actually means:

      direct   = (0.5 * 25 + 3) + 25                             = 40.5 h
    """
    infrequent_context, infrequent = _vessel_count_fixture(direct_vessels=1)
    assert UserStrategy.assign_associated_bookings(infrequent_context, NOW, infrequent) is True
    assert _chain(infrequent) == [("FEEDER", 1, 1), ("TRUNK", 1, 1)]

    frequent_context, frequent = _vessel_count_fixture(direct_vessels=2)
    assert UserStrategy.assign_associated_bookings(frequent_context, NOW, frequent) is True
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


def test_other_hooks_remain_delegated() -> None:
    assert UserStrategy.select_vessel_for_berth(object(), object(), [], [], NOW) is None
    assert UserStrategy.create_alternative_service_routes(object(), NOW) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(object(), NOW, object()) is None


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
    """Two chains that share their first boarding, so only a transfer differs.

    Both options start on ``MAIN`` at the same segment, so the live
    first-boarding wait is identical and cancels out. What is left is whether
    staying on ``MAIN`` to the destination beats hopping onto the
    single-vessel ``BRANCH``:

      stay    = 100/20 + 900/20 + 3 (one intermediate call)      = 53.0 h
      hop     = 100/20 + BRANCH boarding + 400/20
                with a full headway  = 5 + 40 + 20               = 65.0 h
                with half a headway  = 5 + 20 + 20               = 45.0 h

    So a full headway keeps the cargo on MAIN and half a headway would move it
    onto BRANCH.
    """
    origin = _port("Origin")
    hub = _port("Hub")
    destination = _port("Destination")
    main = _route("MAIN", [origin, hub, destination], [100.0, 900.0, 100.0], vessels=1)
    branch = _route("BRANCH", [hub, destination], [400.0, 400.0], vessels=1)
    context = _context([origin, hub, destination], [main, branch])
    return context, _shipment(origin, destination)


def test_a_transfer_boarding_costs_a_full_headway_not_half() -> None:
    context, shipment = _headway_coefficient_fixture()

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("MAIN", 1, 2)]


# ---------------------------------------------------------------------------
# The first boarding is read from live vessel positions.
# ---------------------------------------------------------------------------


def _live_phase_fixture(*, imminent: str) -> tuple[Any, Any]:
    """Two interchangeable services; only their vessel positions differ.

    ``EARLY`` and ``LATE`` are the same shape, so under a headway-only costing
    they tie and the tie-break is arbitrary. Placing one route's vessel just
    short of the origin and the other's just past it must decide the choice.
    """
    origin = _port("Origin")
    destination = _port("Destination")
    early = _route(
        "EARLY",
        [origin, destination],
        [400.0, 400.0],
        vessels=1,
        positions=[1] if imminent == "EARLY" else [0],
    )
    late = _route(
        "LATE",
        [origin, destination],
        [400.0, 400.0],
        vessels=1,
        positions=[1] if imminent == "LATE" else [0],
    )
    context = _context([origin, destination], [early, late])
    return context, _shipment(origin, destination)


def test_prefers_the_service_whose_vessel_departs_sooner() -> None:
    # A vessel sailing the return leg (position 1) is about to reach the origin;
    # one that has just left it (position 0) is a whole cycle away.
    context, shipment = _live_phase_fixture(imminent="LATE")

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("LATE", 1, 1)]


def test_the_same_network_flips_when_the_imminent_vessel_changes() -> None:
    context, shipment = _live_phase_fixture(imminent="EARLY")

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("EARLY", 1, 1)]


def test_a_vessel_alongside_a_berth_is_treated_as_about_to_depart() -> None:
    origin = _port("Origin")
    destination = _port("Destination")
    # Both vessels sit at position 0; only ALONGSIDE has finished sailing.
    sailing = _route("SAILING", [origin, destination], [400.0, 400.0], positions=[0])
    berthed = _route(
        "ALONGSIDE", [origin, destination], [400.0, 400.0], positions=[1], alongside=True
    )
    context = _context([origin, destination], [sailing, berthed])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("ALONGSIDE", 1, 1)]


def test_unlocatable_vessels_fall_back_to_the_headway_expectation() -> None:
    """A route whose vessels cannot be placed must still be usable.

    ``STRANDED`` carries a foreign current segment, so no live phase can be
    read. It must not be dropped: with a far shorter cycle than ``SLOW`` its
    headway expectation still wins.
    """
    origin = _port("Origin")
    destination = _port("Destination")
    stranded = _route("STRANDED", [origin, destination], [100.0, 100.0], vessels=1, stranded=True)
    slow = _route("SLOW", [origin, destination], [4000.0, 4000.0], vessels=1, positions=[1])
    context = _context([origin, destination], [stranded, slow])
    shipment = _shipment(origin, destination)

    assert UserStrategy.assign_associated_bookings(context, NOW, shipment) is True
    assert _chain(shipment) == [("STRANDED", 1, 1)]


def test_equal_speeds_give_exactly_the_cycle_over_vessel_count_headway() -> None:
    """The mixed-speed headway must be an identity when speeds match.

    The reciprocal-of-rates form generalises to vessels of differing speed;
    for the usual equal-speed deployment it must reproduce the plain
    cycle / vessel-count headway bit for bit, so it cannot perturb a settled
    result.
    """
    import response_strategies.user_strategy as strategy

    origin = _port("Origin")
    hub = _port("Hub")
    destination = _port("Destination")
    route = _route("R", [origin, hub, destination], [100.0, 200.0, 300.0], vessels=3)
    context = _context([origin, hub, destination], [route])
    network = strategy._network(context, strategy._port_indexes(context))

    assert network is not None
    cycle_hours = (100.0 + 200.0 + 300.0) / 20.0
    assert network.boarding_hours[0] == cycle_hours / 3


def test_mixed_speeds_board_faster_than_the_slowest_vessel_alone() -> None:
    import response_strategies.user_strategy as strategy

    origin = _port("Origin")
    destination = _port("Destination")
    mixed = _route("MIXED", [origin, destination], [400.0, 400.0], vessels=2, speeds=[10.0, 40.0])
    context = _context([origin, destination], [mixed])
    network = strategy._network(context, strategy._port_indexes(context))

    assert network is not None
    slow_cycle = 800.0 / 10.0
    fast_cycle = 800.0 / 40.0
    assert network.boarding_hours[0] == 1.0 / (1.0 / slow_cycle + 1.0 / fast_cycle)
    assert network.boarding_hours[0] < fast_cycle
