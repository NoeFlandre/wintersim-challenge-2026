"""RED contract for the Round 1 equal-distance one-transfer tie v27 policy."""

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


def _two_to_one_fixture() -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace, dict[str, Any]]:
    origin, first, second, transfer, destination = (
        _port(name) for name in ("Origin", "First", "Second", "Transfer", "Destination")
    )
    nominal = _route("nominal", [origin, destination, origin], [1000.0, 1000.0])
    fallback_a = _route("fallback-a", [origin, first, origin], [30.0, 30.0])
    fallback_b = _route("fallback-b", [first, second, first], [30.0, 30.0])
    fallback_c = _route("fallback-c", [second, destination, second], [40.0, 40.0])
    fewer_a = _route("fewer-a", [origin, transfer, origin], [80.0, 80.0])
    fewer_b = _route("fewer-b", [transfer, destination, transfer], [20.0, 20.0])
    plan = SimpleNamespace(
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
        disruption_plans=[plan],
    )
    return (
        context,
        ANCHOR + dt.timedelta(days=14.5),
        _shipment(origin, destination),
        {"fallback": (fallback_a, fallback_b, fallback_c), "fewer": (fewer_a, fewer_b)},
    )


def _one_to_zero_fixture() -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace]:
    origin, transfer, destination = (_port(name) for name in ("Origin", "Transfer", "Destination"))
    nominal = _route("nominal", [origin, destination, origin], [1000.0, 1000.0])
    fallback_a = _route("fallback-a", [origin, transfer, origin], [40.0, 40.0])
    fallback_b = _route("fallback-b", [transfer, destination, transfer], [60.0, 60.0])
    direct = _route("direct", [origin, destination, origin], [100.0, 100.0])
    plan = SimpleNamespace(
        target_leg=nominal.segments[0].associated_leg,
        target_berth=None,
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=2.0,
        close_berth=False,
    )
    context = SimpleNamespace(
        ports=[origin, transfer, destination],
        service_routes=[nominal, fallback_a, fallback_b, direct],
        disruption_plans=[plan],
    )
    return context, ANCHOR + dt.timedelta(days=14.5), _shipment(origin, destination)


def _install_booking_module(monkeypatch: Any) -> None:
    module = ModuleType("maritime_data_context")
    module.__dict__["Booking"] = _Booking
    monkeypatch.setitem(sys.modules, "maritime_data_context", module)


def test_two_to_one_equal_distance_tie_installs_fewer_transfer_path(monkeypatch: Any) -> None:
    _install_booking_module(monkeypatch)
    context, now, shipment, items = _two_to_one_fixture()

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


def test_one_to_zero_equal_distance_tie_delegates_without_mutation(monkeypatch: Any) -> None:
    _install_booking_module(monkeypatch)
    context, now, shipment = _one_to_zero_fixture()
    before = (list(shipment.associated_bookings), shipment.current_booking_index)

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is None
    assert (shipment.associated_bookings, shipment.current_booking_index) == before


def test_v3_recovery_hold_precedes_tie_installation(monkeypatch: Any) -> None:
    _install_booking_module(monkeypatch)
    context, now, shipment, items = _two_to_one_fixture()
    nominal = context.service_routes[0]
    nominal.segments[0].associated_leg.sailing_distance = 10.0
    nominal.segments[1].associated_leg.sailing_distance = 10.0
    for route in context.service_routes[1:]:
        for segment in route.segments:
            segment.associated_leg.sailing_distance = 1000.0
    context.service_routes = [nominal, *items["fallback"]]

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False
    assert shipment.associated_bookings == []


def test_non_tie_delegates_without_mutation(monkeypatch: Any) -> None:
    _install_booking_module(monkeypatch)
    context, now, shipment, items = _two_to_one_fixture()
    items["fewer"][1].segments[0].associated_leg.sailing_distance = 21.0
    before = (list(shipment.associated_bookings), shipment.current_booking_index)

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is None
    assert (shipment.associated_bookings, shipment.current_booking_index) == before
    assert all(not route.associated_bookings for route in items["fewer"])


def test_installation_append_failure_rolls_back(monkeypatch: Any) -> None:
    _install_booking_module(monkeypatch)
    context, now, shipment, items = _two_to_one_fixture()
    items["fewer"][1].associated_bookings = _FailingList()

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is None
    assert shipment.associated_bookings == []
    assert shipment.current_booking_index is None
    assert items["fewer"][0].associated_bookings == []
    assert items["fewer"][1].associated_bookings == []


def test_malformed_context_delegates() -> None:
    assert UserStrategy.assign_associated_bookings({}, ANCHOR, object()) is None


def test_tie_solver_fail_closed_guards() -> None:
    context, now, shipment, items = _two_to_one_fixture()
    state = strategy._active_state(context, now)
    assert state is not None
    graphs = strategy._graphs(context, state)
    assert graphs is not None
    fallback = strategy._shortest_path(
        context,
        shipment.demand.origin_port,
        shipment.demand.destination_port,
        graphs[1],
    )
    assert fallback is not None
    assert strategy._path_distance(()) is None
    assert (
        strategy._fewer_transfer_equal_path(
            context,
            shipment.demand.origin_port,
            shipment.demand.destination_port,
            graphs[1],
            (),
        )
        is None
    )
    assert (
        strategy._fewer_transfer_equal_path(
            context,
            shipment.demand.origin_port,
            shipment.demand.destination_port,
            graphs[1],
            fallback[:1],
        )
        is None
    )
    assert (
        strategy._fewer_transfer_equal_path(
            SimpleNamespace(ports=None),
            shipment.demand.origin_port,
            shipment.demand.destination_port,
            graphs[1],
            fallback,
        )
        is None
    )
    duplicate_context = SimpleNamespace(ports=[context.ports[0], context.ports[0]])
    assert (
        strategy._fewer_transfer_equal_path(
            duplicate_context,
            shipment.demand.origin_port,
            shipment.demand.destination_port,
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
            shipment.demand.destination_port,
            graphs[1],
            fallback,
        )
        is None
    )
    foreign_edge = strategy._Edge(outside, context.ports[-1], (), items["fewer"][0], 1.0, ())
    assert (
        strategy._fewer_transfer_equal_path(
            context,
            shipment.demand.origin_port,
            shipment.demand.destination_port,
            (foreign_edge,),
            fallback,
        )
        is None
    )


def test_installation_guards_and_booking_failures(monkeypatch: Any) -> None:
    _install_booking_module(monkeypatch)
    context, now, shipment, items = _two_to_one_fixture()
    state = strategy._active_state(context, now)
    assert state is not None
    graphs = strategy._graphs(context, state)
    assert graphs is not None
    fallback = strategy._shortest_path(
        context,
        shipment.demand.origin_port,
        shipment.demand.destination_port,
        graphs[1],
    )
    assert fallback is not None
    path = strategy._fewer_transfer_equal_path(
        context,
        shipment.demand.origin_port,
        shipment.demand.destination_port,
        graphs[1],
        fallback,
    )
    assert path is not None
    assert strategy._booking_path_is_contiguous(shipment, ()) is False
    wrong_origin = _shipment(_port("Wrong"), shipment.demand.destination_port)
    assert strategy._booking_path_is_contiguous(wrong_origin, path) is False
    disconnected = path[:1] + (
        strategy._Edge(
            _port("Elsewhere"), shipment.demand.destination_port, (), path[-1].route, 1.0, ()
        ),
    )
    assert strategy._booking_path_is_contiguous(shipment, disconnected) is False

    invalid_segment = SimpleNamespace(sequence_index=True, associated_leg=path[0].legs[0])
    path[0].route.segments = [invalid_segment]
    assert strategy._segment_bounds(path[0]) is None

    context, now, shipment, items = _two_to_one_fixture()
    state = strategy._active_state(context, now)
    assert state is not None
    graphs = strategy._graphs(context, state)
    assert graphs is not None
    fallback = strategy._shortest_path(
        context,
        shipment.demand.origin_port,
        shipment.demand.destination_port,
        graphs[1],
    )
    assert fallback is not None
    path = strategy._fewer_transfer_equal_path(
        context,
        shipment.demand.origin_port,
        shipment.demand.destination_port,
        graphs[1],
        fallback,
    )
    assert path is not None
    module = sys.modules["maritime_data_context"]
    module.Booking = object()
    assert strategy._install_equal_tie_path(shipment, path) is None

    class _BrokenBooking:
        def __init__(self, **_: Any) -> None:
            raise TypeError("injected constructor failure")

    module.Booking = _BrokenBooking
    assert strategy._install_equal_tie_path(shipment, path) is None
    path[0].route.associated_bookings = None
    assert strategy._install_equal_tie_path(shipment, path) is None
