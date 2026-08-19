"""RED contract for the Round 1 equal-distance route tie-break experiment."""

from __future__ import annotations

import datetime as dt
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import response_strategies.user_strategy as strategy
from response_strategies.user_strategy import UserStrategy

ANCHOR = dt.datetime.min


class _Booking:
    def __init__(
        self,
        *,
        sequence_index: int,
        shipment: Any,
        service_route: Any,
        departure_segment_index: int,
        arrival_segment_index: int,
    ) -> None:
        self.sequence_index = sequence_index
        self.shipment = shipment
        self.service_route = service_route
        self.departure_segment_index = departure_segment_index
        self.arrival_segment_index = arrival_segment_index


class _FailingList(list[Any]):
    def append(self, value: Any) -> None:
        raise RuntimeError("injected route-install failure")


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(
    name: str,
    ports: list[SimpleNamespace],
    distances: list[float],
) -> SimpleNamespace:
    assert len(ports) == len(distances) + 1
    route = SimpleNamespace(
        name=name,
        source_service_route=None,
        disruption_key=None,
        associated_bookings=[],
    )
    route.segments = [
        SimpleNamespace(
            sequence_index=index,
            associated_leg=SimpleNamespace(
                departure_port=ports[index - 1],
                arrival_port=ports[index],
                sailing_distance=distance,
            ),
        )
        for index, distance in enumerate(distances, start=1)
    ]
    route.deployed_vessels = [SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=10.0))]
    return route


def _shipment(origin: Any, destination: Any) -> SimpleNamespace:
    return SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )


def _tie_fixture() -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace, dict[str, Any]]:
    origin, first, second, transfer, destination = (
        _port(name) for name in ("Origin", "First", "Second", "Transfer", "Destination")
    )
    nominal = _route("nominal", [origin, destination, origin], [1000.0, 1000.0])
    fallback_a = _route("fallback-a", [origin, first, origin], [30.0, 30.0])
    fallback_b = _route("fallback-b", [first, second, first], [30.0, 30.0])
    fallback_c = _route("fallback-c", [second, destination, second], [40.0, 40.0])
    fewer_a = _route("fewer-a", [origin, transfer, origin], [80.0, 80.0])
    fewer_b = _route("fewer-b", [transfer, destination, transfer], [20.0, 20.0])
    disruption = SimpleNamespace(
        target_leg=nominal.segments[0].associated_leg,
        target_berth=None,
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=2.0,
        close_berth=False,
    )
    context = SimpleNamespace(
        ports=[origin, first, second, transfer, destination],
        service_routes=[nominal, fallback_a, fallback_b, fallback_c, fewer_a, fewer_b],
        disruption_plans=[disruption],
    )
    shipment = _shipment(origin, destination)
    return (
        context,
        ANCHOR + dt.timedelta(days=14.5),
        shipment,
        {
            "origin": origin,
            "destination": destination,
            "fallback": (fallback_a, fallback_b, fallback_c),
            "fewer": (fewer_a, fewer_b),
        },
    )


def _install_booking_module(monkeypatch: Any) -> None:
    module = ModuleType("maritime_data_context")
    module.__dict__["Booking"] = _Booking
    monkeypatch.setitem(sys.modules, "maritime_data_context", module)


def test_equal_distance_tie_installs_fewer_route_changes(monkeypatch: Any) -> None:
    _install_booking_module(monkeypatch)
    context, now, shipment, items = _tie_fixture()

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is True
    assert [booking.service_route for booking in shipment.associated_bookings] == list(
        items["fewer"]
    )
    assert shipment.current_booking_index == 1
    assert all(
        shipment.associated_bookings[index] in route.associated_bookings
        for index, route in enumerate(items["fewer"])
    )
    assert all(not route.associated_bookings for route in items["fallback"])


def test_no_strictly_better_equal_distance_path_delegates_without_mutation(
    monkeypatch: Any,
) -> None:
    _install_booking_module(monkeypatch)
    context, now, shipment, items = _tie_fixture()
    items["fewer"][1].segments[0].associated_leg.sailing_distance = 21.0
    before = (list(shipment.associated_bookings), shipment.current_booking_index)

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is None
    assert (shipment.associated_bookings, shipment.current_booking_index) == before
    assert all(not route.associated_bookings for route in items["fewer"])


def test_existing_v3_recovery_hold_has_precedence(monkeypatch: Any) -> None:
    _install_booking_module(monkeypatch)
    origin, transfer_a, transfer_b, destination = (
        _port(name) for name in ("Origin", "Transfer A", "Transfer B", "Destination")
    )
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer_a, origin], [1000.0, 1000.0])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [1000.0, 1000.0])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [1000.0, 1000.0])
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[
            SimpleNamespace(
                target_leg=nominal.segments[0].associated_leg,
                target_berth=None,
                start_offset_days=10.0,
                duration_days=5.0,
                multiplier=2.0,
                close_berth=False,
            )
        ],
    )
    shipment = _shipment(origin, destination)

    assert (
        UserStrategy.assign_associated_bookings(context, ANCHOR + dt.timedelta(days=14.5), shipment)
        is False
    )
    assert shipment.associated_bookings == []


def test_installation_failure_rolls_back_everything(monkeypatch: Any) -> None:
    _install_booking_module(monkeypatch)
    context, now, shipment, items = _tie_fixture()
    failing_route = items["fewer"][1]
    failing_route.associated_bookings = _FailingList()
    before_fallback = [list(route.associated_bookings) for route in items["fallback"]]

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is None
    assert shipment.associated_bookings == []
    assert shipment.current_booking_index is None
    assert [list(route.associated_bookings) for route in items["fallback"]] == before_fallback
    assert items["fewer"][0].associated_bookings == []
    assert items["fewer"][1].associated_bookings == []


def test_tie_solver_fail_closed_guards() -> None:
    context, _, _, items = _tie_fixture()
    state = strategy._active_state(context, ANCHOR + dt.timedelta(days=14.5))
    assert state is not None
    graphs = strategy._graphs(context, state)
    assert graphs is not None
    fallback = strategy._shortest_path(
        context,
        items["origin"],
        items["destination"],
        graphs[1],
    )
    assert fallback is not None
    assert strategy._path_distance(()) is None
    assert (
        strategy._fewer_transfer_equal_path(
            context, items["origin"], items["destination"], graphs[1], ()
        )
        is None
    )
    assert (
        strategy._fewer_transfer_equal_path(
            context, items["origin"], items["destination"], graphs[1], fallback[:1]
        )
        is None
    )

    same_route = _route(
        "same-route",
        [
            items["origin"],
            items["fewer"][0].segments[0].associated_leg.arrival_port,
            items["destination"],
            items["origin"],
        ],
        [10.0, 10.0, 10.0],
    )
    same_route_edges = strategy._route_data(same_route)
    assert same_route_edges is not None
    transfer = items["fewer"][0].segments[0].associated_leg.arrival_port
    same_path = (
        next(
            edge
            for edge in same_route_edges.edges
            if edge.departure is items["origin"] and edge.arrival is transfer
        ),
        next(
            edge
            for edge in same_route_edges.edges
            if edge.departure is transfer and edge.arrival is items["destination"]
        ),
    )
    assert (
        strategy._fewer_transfer_equal_path(
            context, items["origin"], transfer, graphs[1], same_path
        )
        is None
    )

    assert (
        strategy._fewer_transfer_equal_path(
            SimpleNamespace(ports=None),
            items["origin"],
            items["destination"],
            graphs[1],
            fallback,
        )
        is None
    )
    duplicate_context = SimpleNamespace(ports=[items["origin"], items["origin"]])
    assert (
        strategy._fewer_transfer_equal_path(
            duplicate_context,
            items["origin"],
            items["destination"],
            graphs[1],
            fallback,
        )
        is None
    )
    outside = _port("Outside")
    assert (
        strategy._fewer_transfer_equal_path(
            context,
            outside,
            items["destination"],
            graphs[1],
            fallback,
        )
        is None
    )
    foreign_edge = strategy._Edge(
        outside,
        items["destination"],
        (),
        items["fewer"][0],
        1.0,
        (),
    )
    assert (
        strategy._fewer_transfer_equal_path(
            context,
            items["origin"],
            items["destination"],
            (foreign_edge,),
            fallback,
        )
        is None
    )


def test_installation_guards_and_booking_failures(monkeypatch: Any) -> None:
    context, now, shipment, items = _tie_fixture()
    state = strategy._active_state(context, now)
    assert state is not None
    graphs = strategy._graphs(context, state)
    assert graphs is not None
    fallback = strategy._shortest_path(context, items["origin"], items["destination"], graphs[1])
    assert fallback is not None
    path = strategy._fewer_transfer_equal_path(
        context, items["origin"], items["destination"], graphs[1], fallback
    )
    assert path is not None
    assert strategy._booking_path_is_contiguous(shipment, ()) is False
    wrong_origin = _shipment(_port("Wrong"), items["destination"])
    assert strategy._booking_path_is_contiguous(wrong_origin, path) is False
    disconnected = tuple(
        path[:1]
        + (
            strategy._Edge(
                _port("Elsewhere"),
                items["destination"],
                (),
                path[-1].route,
                1.0,
                (),
            ),
        )
    )
    assert strategy._booking_path_is_contiguous(shipment, disconnected) is False

    invalid_segment = SimpleNamespace(sequence_index=True, associated_leg=path[0].legs[0])
    path[0].route.segments = [invalid_segment]
    assert strategy._segment_bounds(path[0]) is None
    context, now, shipment, items = _tie_fixture()
    state = strategy._active_state(context, now)
    assert state is not None
    graphs = strategy._graphs(context, state)
    assert graphs is not None
    fallback = strategy._shortest_path(context, items["origin"], items["destination"], graphs[1])
    assert fallback is not None
    path = strategy._fewer_transfer_equal_path(
        context, items["origin"], items["destination"], graphs[1], fallback
    )
    assert path is not None

    module = ModuleType("maritime_data_context")
    module.__dict__["Booking"] = object()
    monkeypatch.setitem(sys.modules, "maritime_data_context", module)
    assert strategy._install_equal_tie_path(shipment, path) is None

    class _BrokenBooking:
        def __init__(self, **_: Any) -> None:
            raise TypeError("injected constructor failure")

    module.__dict__["Booking"] = _BrokenBooking
    assert strategy._install_equal_tie_path(shipment, path) is None

    path[0].route.associated_bookings = None
    assert strategy._install_equal_tie_path(shipment, path) is None
