"""Behaviour contract for the Round 2 whole-service reroute (v18).

The fleet decision must move an entire service onto a detour around a
slowdown, but only when the detour still calls every port the rotation calls,
is strictly faster at the multipliers in force, and the slowdown will outlast
the changeover itself. A shut port is never routed around, and a rotation is
never left without vessels while cargo is still booked on it.

All fixtures are sentinel objects defined here; no organizer source is
imported.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

from response_strategies import user_strategy as strategy
from response_strategies.user_strategy import UserStrategy

NOW = dt.datetime.min + dt.timedelta(days=200)


def _port(name: str, *, closed: bool = False) -> SimpleNamespace:
    return SimpleNamespace(name=name, berths=[SimpleNamespace(is_available=not closed)])


def _leg(departure: Any, arrival: Any, distance: float, multiplier: float = 1.0) -> SimpleNamespace:
    return SimpleNamespace(
        departure_port=departure,
        arrival_port=arrival,
        sailing_distance=distance,
        sailing_time_multiplier=multiplier,
        segments=[],
    )


def _vessel(index: int, route: Any, speed: float = 20.0) -> SimpleNamespace:
    return SimpleNamespace(
        index=index,
        vessel_class=SimpleNamespace(sailing_speed=speed, teu_capacity=1000, loa=300.0),
        assigned_service_route=route,
        pending_assigned_service_route=None,
        carried_shipments=[],
        current_segment=None,
        current_berth=None,
    )


def _rotation(route_id: str, legs: list[Any]) -> SimpleNamespace:
    route = SimpleNamespace(
        id=route_id,
        name=route_id,
        start_day_of_week=0.0,
        source_service_route=None,
        disruption_key=None,
        associated_bookings=[],
        deployed_vessels=[],
        segments=[],
    )
    for index, leg in enumerate(legs, start=1):
        segment = SimpleNamespace(
            sequence_index=index,
            associated_leg=leg,
            associated_service_route=route,
            current_vessels=[],
        )
        route.segments.append(segment)
        leg.segments.append(segment)
    return route


def _fixture(*, multiplier: float = 5.0, closed: str | None = None) -> SimpleNamespace:
    """One rotation ``A -> B -> C -> A`` whose first leg can be slowed.

    A cheaper way from ``A`` to ``B`` exists through ``D``: ``300 + 350`` nm
    against the direct ``600``. The rotation's nominal cycle is `2600` nm; with
    the first leg at `5x` it is `5000`, and the detour is `2650`.
    """
    ports = {name: _port(name, closed=name == closed) for name in "ABCD"}
    ab = _leg(ports["A"], ports["B"], 600.0, multiplier)
    bc = _leg(ports["B"], ports["C"], 1000.0)
    ca = _leg(ports["C"], ports["A"], 1000.0)
    ad = _leg(ports["A"], ports["D"], 300.0)
    db = _leg(ports["D"], ports["B"], 350.0)
    route = _rotation("R1", [ab, bc, ca])
    context = SimpleNamespace(
        ports=list(ports.values()),
        legs=[ab, bc, ca, ad, db],
        service_routes=[route],
        partial_service_routes=[],
        vessels=[],
        demands=[],
        disruption_plans=[],
    )
    context.vessels = [_vessel(index, route) for index in (1, 2, 3)]
    route.deployed_vessels = list(context.vessels)
    return SimpleNamespace(context=context, route=route, ports=ports)


def _targets(fixture: Any, *, build: bool) -> dict[int, Any]:
    context = fixture.context
    return strategy._service_targets(
        context,
        strategy._closed_port_indexes(context),
        strategy._port_indexes(context),
        {},
        build=build,
    )


# ---------------------------------------------------------------------------
# Building the detour
# ---------------------------------------------------------------------------


def test_a_slowdown_gets_a_detour_that_calls_every_port() -> None:
    fixture = _fixture()
    assert UserStrategy.create_alternative_service_routes(fixture.context, NOW) is True

    built = [r for r in fixture.context.service_routes if r.source_service_route is not None]
    assert len(built) == 1
    detour = built[0]
    assert detour.source_service_route is fixture.route
    assert [s.sequence_index for s in detour.segments] == [1, 2, 3, 4]
    assert [s.associated_leg.departure_port.name for s in detour.segments] == ["A", "D", "B", "C"]
    # Every port the rotation calls is still called.
    assert {"A", "B", "C"} <= {s.associated_leg.departure_port.name for s in detour.segments}


def test_no_leg_is_invented_for_the_detour() -> None:
    fixture = _fixture()
    legs_before = list(fixture.context.legs)
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    detour = fixture.context.service_routes[-1]
    assert list(fixture.context.legs) == legs_before
    assert all(s.associated_leg in legs_before for s in detour.segments)


def test_the_whole_fleet_is_reserved_onto_the_detour() -> None:
    fixture = _fixture()
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    detour = fixture.context.service_routes[-1]
    assert [v.pending_assigned_service_route for v in fixture.context.vessels] == [detour] * 3


def test_a_slowdown_that_lifts_before_the_fleet_could_move_is_refused() -> None:
    """The changeover takes about one turn of the new rotation, so a shorter
    slowdown is not worth starting one for."""
    fixture = _fixture()
    slowed = fixture.context.legs[0]
    # The detour is 2650 nm at 20 kn = 132.5 h round. A slowdown with less
    # life than that must be left alone; one with more must not.
    fixture.context.disruption_plans = []
    targets = strategy._service_targets(
        fixture.context,
        strategy._closed_port_indexes(fixture.context),
        strategy._port_indexes(fixture.context),
        {id(slowed): 100.0},
        build=True,
    )
    assert targets[id(fixture.route)] is fixture.route
    assert all(r.source_service_route is None for r in fixture.context.service_routes)

    targets = strategy._service_targets(
        fixture.context,
        strategy._closed_port_indexes(fixture.context),
        strategy._port_indexes(fixture.context),
        {id(slowed): 200.0},
        build=True,
    )
    assert targets[id(fixture.route)].source_service_route is fixture.route


def test_a_changeover_already_under_way_is_not_reversed_early() -> None:
    """Once the cost is paid, a shrinking slowdown life must not undo it."""
    fixture = _fixture()
    slowed = fixture.context.legs[0]
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    detour = fixture.context.service_routes[-1]
    vessel = fixture.context.vessels[0]
    vessel.current_segment = fixture.route.segments[2]
    UserStrategy.create_alternative_service_routes(fixture.context, NOW, vessel)
    assert vessel.assigned_service_route is detour

    targets = strategy._service_targets(
        fixture.context,
        strategy._closed_port_indexes(fixture.context),
        strategy._port_indexes(fixture.context),
        {id(slowed): 1.0},
        build=True,
    )
    assert targets[id(fixture.route)] is detour


def test_a_detour_no_faster_than_the_slowdown_is_refused() -> None:
    # 600 * 1.05 = 630, so the stretched cycle is 2630 against a 2650 detour.
    fixture = _fixture(multiplier=1.05)
    assert UserStrategy.create_alternative_service_routes(fixture.context, NOW) is True
    assert all(r.source_service_route is None for r in fixture.context.service_routes)
    assert all(v.pending_assigned_service_route is None for v in fixture.context.vessels)


def test_a_closed_port_on_the_rotation_is_never_routed_around() -> None:
    fixture = _fixture(closed="B")
    assert UserStrategy.create_alternative_service_routes(fixture.context, NOW) is True
    assert all(r.source_service_route is None for r in fixture.context.service_routes)
    assert all(v.pending_assigned_service_route is None for v in fixture.context.vessels)


def test_a_calm_rotation_is_left_alone() -> None:
    fixture = _fixture(multiplier=1.0)
    assert UserStrategy.create_alternative_service_routes(fixture.context, NOW) is True
    assert all(r.source_service_route is None for r in fixture.context.service_routes)
    assert all(v.pending_assigned_service_route is None for v in fixture.context.vessels)


def test_a_detour_is_built_once_and_then_reused() -> None:
    fixture = _fixture()
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    routes_after_first = len(fixture.context.service_routes)
    for _ in range(5):
        UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    assert len(fixture.context.service_routes) == routes_after_first


# ---------------------------------------------------------------------------
# Moving vessels
# ---------------------------------------------------------------------------


def test_a_loaded_vessel_is_never_moved() -> None:
    fixture = _fixture()
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    detour = fixture.context.service_routes[-1]
    vessel = fixture.context.vessels[0]
    vessel.carried_shipments = [object()]
    vessel.current_segment = fixture.route.segments[2]  # arrived at A
    UserStrategy.create_alternative_service_routes(fixture.context, NOW, vessel)
    assert vessel.assigned_service_route is fixture.route
    assert vessel not in detour.deployed_vessels


def test_an_empty_vessel_joins_the_detour_where_it_stands() -> None:
    fixture = _fixture()
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    detour = fixture.context.service_routes[-1]
    vessel = fixture.context.vessels[0]
    vessel.current_segment = fixture.route.segments[2]  # arrived at A
    UserStrategy.create_alternative_service_routes(fixture.context, NOW, vessel)

    assert vessel.assigned_service_route is detour
    assert vessel.pending_assigned_service_route is None
    assert vessel in detour.deployed_vessels
    assert vessel not in fixture.route.deployed_vessels
    # It resumes from the detour segment that arrives where it is standing.
    assert vessel.current_segment.associated_service_route is detour
    assert vessel.current_segment.associated_leg.arrival_port is fixture.ports["A"]
    assert vessel in vessel.current_segment.current_vessels


def test_a_vessel_at_a_port_the_detour_does_not_call_stays_put() -> None:
    fixture = _fixture()
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    vessel = fixture.context.vessels[0]
    # Standing at a port that is on neither rotation.
    elsewhere = _port("Z")
    vessel.current_berth = SimpleNamespace(port=elsewhere)
    UserStrategy.create_alternative_service_routes(fixture.context, NOW, vessel)
    assert vessel.assigned_service_route is fixture.route


def test_the_last_vessel_stays_while_cargo_is_still_booked_on_the_rotation() -> None:
    fixture = _fixture()
    unfinished = SimpleNamespace(completion_time=None)
    fixture.route.associated_bookings = [SimpleNamespace(shipment=unfinished)]
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    detour = fixture.context.service_routes[-1]

    for vessel in fixture.context.vessels:
        vessel.current_segment = fixture.route.segments[2]
        UserStrategy.create_alternative_service_routes(fixture.context, NOW, vessel)

    assert len(fixture.route.deployed_vessels) == 1
    assert len(detour.deployed_vessels) == 2
    assert fixture.route.deployed_vessels[0].pending_assigned_service_route is None


def test_the_last_vessel_leaves_once_the_rotation_has_drained() -> None:
    fixture = _fixture()
    finished = SimpleNamespace(completion_time=NOW)
    fixture.route.associated_bookings = [SimpleNamespace(shipment=finished)]
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    detour = fixture.context.service_routes[-1]

    for vessel in fixture.context.vessels:
        vessel.current_segment = fixture.route.segments[2]
        UserStrategy.create_alternative_service_routes(fixture.context, NOW, vessel)

    assert fixture.route.deployed_vessels == []
    assert len(detour.deployed_vessels) == 3


def test_the_fleet_returns_once_the_slowdown_lifts() -> None:
    fixture = _fixture()
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    detour = fixture.context.service_routes[-1]
    for vessel in fixture.context.vessels:
        vessel.current_segment = fixture.route.segments[2]
        UserStrategy.create_alternative_service_routes(fixture.context, NOW, vessel)
    assert len(detour.deployed_vessels) == 3

    fixture.context.legs[0].sailing_time_multiplier = 1.0
    for vessel in fixture.context.vessels:
        vessel.current_segment = detour.segments[3]  # arrived at A on the detour
        UserStrategy.create_alternative_service_routes(fixture.context, NOW, vessel)

    assert detour.deployed_vessels == []
    assert len(fixture.route.deployed_vessels) == 3
    assert all(v.pending_assigned_service_route is None for v in fixture.context.vessels)


def test_a_rotation_being_drained_takes_no_new_cargo() -> None:
    fixture = _fixture()
    UserStrategy.create_alternative_service_routes(fixture.context, NOW)
    detour = fixture.context.service_routes[-1]
    targets = _targets(fixture, build=False)
    assert targets[id(fixture.route)] is detour

    vessel = fixture.context.vessels[0]
    vessel.current_segment = fixture.route.segments[2]
    UserStrategy.create_alternative_service_routes(fixture.context, NOW, vessel)

    network = strategy._network(fixture.context, strategy._port_indexes(fixture.context), {}, {})
    assert network is not None
    assert [route.id for route in network.routes] == [detour.id]


# ---------------------------------------------------------------------------
# Failing closed
# ---------------------------------------------------------------------------


def test_the_hook_owns_the_decision_even_on_unreadable_state() -> None:
    for broken in (
        SimpleNamespace(),
        SimpleNamespace(ports=None, legs=None, service_routes=None, vessels=None),
        SimpleNamespace(ports=[], legs=[], service_routes=[], vessels=[]),
        SimpleNamespace(
            ports=[_port("A")], legs=[SimpleNamespace()], service_routes=[], vessels=[]
        ),
    ):
        assert UserStrategy.create_alternative_service_routes(broken, NOW) is True


def test_a_slowdown_with_no_way_round_it_changes_nothing() -> None:
    fixture = _fixture()
    # Remove the alternative path from A to B.
    fixture.context.legs = [leg for leg in fixture.context.legs if leg.sailing_distance != 300.0]
    assert UserStrategy.create_alternative_service_routes(fixture.context, NOW) is True
    assert all(r.source_service_route is None for r in fixture.context.service_routes)
    assert all(v.pending_assigned_service_route is None for v in fixture.context.vessels)
