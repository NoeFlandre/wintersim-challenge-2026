"""RED/GREEN contract tests for the Round 1 direct-next-leg experiment."""

from __future__ import annotations

import datetime as dt
import sys
import types

import response_strategies.user_strategy as strategy
from response_strategies.user_strategy import UserStrategy


class FakeBooking:
    def __init__(
        self,
        sequence_index,
        shipment,
        service_route,
        departure_segment_index,
        arrival_segment_index,
    ):
        self.sequence_index = sequence_index
        self.shipment = shipment
        self.service_route = service_route
        self.departure_segment_index = departure_segment_index
        self.arrival_segment_index = arrival_segment_index


class FakePort:
    def __init__(self, name: str):
        self.name = name


class FakeLeg:
    def __init__(self, departure_port, arrival_port):
        self.departure_port = departure_port
        self.arrival_port = arrival_port
        self.sailing_time_multiplier = 1.0


class FakeSegment:
    def __init__(self, sequence_index, leg):
        self.sequence_index = sequence_index
        self.associated_leg = leg


class FakeRoute:
    def __init__(self, segments, vessels):
        self.segments = segments
        self.deployed_vessels = vessels
        self.source_service_route = None
        self.disruption_key = None
        self.associated_bookings = []


class FakeVessel:
    def __init__(self, route, next_segment):
        self.assigned_service_route = route
        self.pending_assigned_service_route = None
        self.current_segment = None
        self._next_segment = next_segment

    def get_next_segment(self):
        return self._next_segment


class FakeDemand:
    def __init__(self, origin_port, destination_port):
        self.origin_port = origin_port
        self.destination_port = destination_port


class FakeShipment:
    def __init__(self, demand):
        self.demand = demand
        self.associated_bookings = []
        self.current_booking_index = None


class FakePlan:
    def __init__(
        self,
        *,
        start=10.0,
        duration=20.0,
        target_leg=None,
        target_berth=None,
        multiplier=1.0,
        close_berth=False,
    ):
        self.start_offset_days = start
        self.duration_days = duration
        self.target_leg = target_leg
        self.target_berth = target_berth
        self.multiplier = multiplier
        self.close_berth = close_berth


class FakeBerth:
    def __init__(self, port):
        self.port = port


class FakeContext:
    def __init__(self, routes, plans):
        self.service_routes = routes
        self.disruption_plans = plans


def _install_booking_module(monkeypatch):
    module = types.ModuleType("maritime_data_context")
    module.Booking = FakeBooking
    monkeypatch.setitem(sys.modules, "maritime_data_context", module)


def _fixture():
    origin = FakePort("Origin")
    destination = FakePort("Destination")
    direct_leg = FakeLeg(origin, destination)
    direct_segment = FakeSegment(2, direct_leg)
    route = FakeRoute([direct_segment], [])
    vessel = FakeVessel(route, direct_segment)
    route.deployed_vessels.append(vessel)
    shipment = FakeShipment(FakeDemand(origin, destination))
    context = FakeContext(
        [route],
        [
            FakePlan(
                target_leg=FakeLeg(FakePort("Other"), FakePort("Else")),
                multiplier=2.0,
            )
        ],
    )
    now = dt.datetime.min + dt.timedelta(days=15)
    return context, shipment, route, direct_segment, direct_leg, vessel, now


def test_assigns_exact_direct_booking_when_next_leg_is_ready(monkeypatch):
    _install_booking_module(monkeypatch)
    context, shipment, route, segment, _leg, _vessel, now = _fixture()

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is True
    assert shipment.current_booking_index == 1
    assert len(shipment.associated_bookings) == 1
    booking = shipment.associated_bookings[0]
    assert booking.service_route is route
    assert booking.departure_segment_index == segment.sequence_index
    assert booking.arrival_segment_index == segment.sequence_index
    assert route.associated_bookings == [booking]


def test_delegates_when_no_disruption_is_active(monkeypatch):
    _install_booking_module(monkeypatch)
    context, shipment, _route, _segment, _leg, _vessel, now = _fixture()
    context.disruption_plans[0].start_offset_days = 100.0

    before = (list(shipment.associated_bookings), shipment.current_booking_index)
    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is None
    assert (shipment.associated_bookings, shipment.current_booking_index) == before


def test_active_window_end_is_exclusive(monkeypatch):
    _install_booking_module(monkeypatch)
    context, shipment, _route, _segment, _leg, _vessel, _now = _fixture()
    plan = context.disruption_plans[0]
    at_end = dt.datetime.min + dt.timedelta(days=plan.start_offset_days + plan.duration_days)

    assert UserStrategy.assign_associated_bookings(context, at_end, shipment) is None


def test_delegates_when_direct_leg_is_currently_congested(monkeypatch):
    _install_booking_module(monkeypatch)
    context, shipment, _route, _segment, direct_leg, _vessel, now = _fixture()
    context.disruption_plans = [FakePlan(target_leg=direct_leg, multiplier=3.0)]

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
    assert shipment.associated_bookings == []


def test_delegates_when_endpoint_berth_is_closed(monkeypatch):
    _install_booking_module(monkeypatch)
    context, shipment, _route, _segment, _leg, _vessel, now = _fixture()
    context.disruption_plans = [
        FakePlan(target_berth=FakeBerth(shipment.demand.destination_port), close_berth=True)
    ]

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_delegates_when_route_has_no_ready_next_leg_vessel(monkeypatch):
    _install_booking_module(monkeypatch)
    context, shipment, route, segment, _leg, vessel, now = _fixture()
    vessel._next_segment = FakeSegment(99, segment.associated_leg)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
    assert route.associated_bookings == []


def test_success_replaces_old_booking_and_reverse_reference(monkeypatch):
    _install_booking_module(monkeypatch)
    context, shipment, route, _segment, _leg, _vessel, now = _fixture()
    old_route = FakeRoute([], [])
    old_booking = FakeBooking(1, shipment, old_route, 1, 1)
    shipment.associated_bookings = [old_booking]
    shipment.current_booking_index = 1
    old_route.associated_bookings = [old_booking]

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is True
    assert old_route.associated_bookings == []
    assert len(shipment.associated_bookings) == 1
    assert shipment.associated_bookings[0].service_route is route


def test_booking_constructor_failure_restores_all_state(monkeypatch):
    context, shipment, _route, _segment, _leg, _vessel, now = _fixture()
    old_route = FakeRoute([], [])
    old_booking = FakeBooking(1, shipment, old_route, 1, 1)
    shipment.associated_bookings = [old_booking]
    shipment.current_booking_index = 1
    old_route.associated_bookings = [old_booking]

    class ExplodingBooking:
        def __init__(self, **_kwargs):
            raise RuntimeError("construction failed")

    module = types.ModuleType("maritime_data_context")
    module.Booking = ExplodingBooking
    monkeypatch.setitem(sys.modules, "maritime_data_context", module)

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is None
    assert shipment.associated_bookings == [old_booking]
    assert shipment.current_booking_index == 1
    assert old_route.associated_bookings == [old_booking]


def test_all_other_hooks_delegate():
    assert UserStrategy.select_vessel_for_berth(None, None, [], [], None) is None
    assert UserStrategy.create_alternative_service_routes(None, None) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(None, None, None) is None


def test_active_disruption_helper_fails_closed_for_missing_or_malformed_plans():
    assert strategy._active_disruption_targets(object(), dt.datetime.min) is None
    assert (
        strategy._active_disruption_targets(
            types.SimpleNamespace(disruption_plans=3), dt.datetime.min
        )
        is None
    )

    bad_start = FakePlan(target_leg=object(), multiplier=2.0)
    bad_start.start_offset_days = "bad"
    assert (
        strategy._active_disruption_targets(
            types.SimpleNamespace(disruption_plans=[bad_start]), dt.datetime.min
        )
        is None
    )

    both_targets = FakePlan(target_leg=object(), target_berth=FakeBerth(object()), multiplier=2.0)
    assert (
        strategy._active_disruption_targets(
            types.SimpleNamespace(disruption_plans=[both_targets]), dt.datetime.min
        )
        is None
    )

    bad_window = FakePlan(target_leg=object(), multiplier=2.0)
    bad_window.start_offset_days = float("inf")
    assert (
        strategy._active_disruption_targets(
            types.SimpleNamespace(disruption_plans=[bad_window]), dt.datetime.min
        )
        is None
    )

    bad_multiplier = FakePlan(target_leg=object(), multiplier="bad")
    assert (
        strategy._active_disruption_targets(
            types.SimpleNamespace(disruption_plans=[bad_multiplier]),
            dt.datetime.min + dt.timedelta(days=15),
        )
        is None
    )

    bad_port = FakePlan(target_berth=FakeBerth(None), close_berth=True)
    assert (
        strategy._active_disruption_targets(
            types.SimpleNamespace(disruption_plans=[bad_port]),
            dt.datetime.min + dt.timedelta(days=15),
        )
        is None
    )


def test_active_disruption_helper_accepts_closed_port_and_ignores_inactive_or_neutral_plans():
    port = FakePort("Closed")
    closed = FakePlan(target_berth=FakeBerth(port), close_berth=True)
    inactive = FakePlan(target_leg=object(), start=100.0, multiplier=2.0)
    neutral = FakePlan(target_leg=object(), multiplier=1.0)
    result = strategy._active_disruption_targets(
        types.SimpleNamespace(disruption_plans=[closed, inactive, neutral]),
        dt.datetime.min + dt.timedelta(days=15),
    )
    assert result is not None
    legs, ports = result
    assert legs == []
    assert ports == [port]


def test_ordered_segments_and_ready_vessel_helpers_fail_closed():
    assert strategy._ordered_segments(types.SimpleNamespace()) is None
    assert strategy._ordered_segments(types.SimpleNamespace(segments=[])) is None
    assert strategy._ordered_segments(types.SimpleNamespace(segments=[object()])) is None

    route = types.SimpleNamespace(deployed_vessels=None)
    segment = types.SimpleNamespace(associated_leg=None)
    assert strategy._next_leg_is_ready(route, segment) is False

    route.deployed_vessels = 3
    assert strategy._next_leg_is_ready(route, segment) is False

    leg = FakeLeg(FakePort("A"), FakePort("B"))
    segment.associated_leg = leg
    route.deployed_vessels = [types.SimpleNamespace()]
    assert strategy._next_leg_is_ready(route, segment) is False


def test_ready_vessel_helper_handles_mismatches_and_current_position():
    origin = FakePort("A")
    destination = FakePort("B")
    leg = FakeLeg(origin, destination)
    segment = FakeSegment(1, leg)
    route = FakeRoute([segment], [])

    wrong_route = FakeRoute([], [])
    route.deployed_vessels.append(FakeVessel(wrong_route, segment))
    pending = FakeVessel(route, segment)
    pending.pending_assigned_service_route = object()
    route.deployed_vessels.append(pending)
    route.deployed_vessels.append(types.SimpleNamespace(assigned_service_route=route))

    class RaisingVessel(FakeVessel):
        def get_next_segment(self):
            raise RuntimeError("bad vessel")

    route.deployed_vessels.append(RaisingVessel(route, segment))
    wrong_next = FakeVessel(route, FakeSegment(9, leg))
    route.deployed_vessels.append(wrong_next)
    bad_current = FakeVessel(route, segment)
    bad_current.current_segment = types.SimpleNamespace(associated_leg=None)
    route.deployed_vessels.append(bad_current)
    wrong_current = FakeVessel(route, segment)
    wrong_current.current_segment = types.SimpleNamespace(
        associated_leg=FakeLeg(FakePort("X"), FakePort("Y"))
    )
    route.deployed_vessels.append(wrong_current)
    assert strategy._next_leg_is_ready(route, segment) is False

    good = FakeVessel(route, segment)
    good.current_segment = types.SimpleNamespace(associated_leg=FakeLeg(FakePort("X"), origin))
    route.deployed_vessels.append(good)
    assert strategy._next_leg_is_ready(route, segment) is True


def test_install_helper_fails_closed_before_mutation(monkeypatch):
    context, shipment, route, segment, _leg, _vessel, now = _fixture()
    monkeypatch.setitem(
        sys.modules, "maritime_data_context", types.ModuleType("maritime_data_context")
    )
    assert strategy._install_direct_booking(shipment, route, segment) is None

    _install_booking_module(monkeypatch)
    malformed_shipment = types.SimpleNamespace(associated_bookings=(), current_booking_index=None)
    assert strategy._install_direct_booking(malformed_shipment, route, segment) is None

    old = FakeBooking(1, shipment, types.SimpleNamespace(associated_bookings=()), 1, 1)
    shipment.associated_bookings = [old]
    before = list(shipment.associated_bookings)
    assert strategy._install_direct_booking(shipment, route, segment) is None
    assert shipment.associated_bookings == before
    assert now is not None


def test_assignment_fail_closed_for_malformed_contexts():
    context, shipment, route, segment, _leg, _vessel, now = _fixture()
    assert UserStrategy.assign_associated_bookings(None, now, shipment) is None
    assert UserStrategy.assign_associated_bookings(context, "not-a-time", shipment) is None
    assert UserStrategy.assign_associated_bookings(context, now, None) is None
    assert (
        UserStrategy.assign_associated_bookings(context, now, types.SimpleNamespace(demand=None))
        is None
    )

    same_port = shipment.demand.origin_port
    same = FakeShipment(FakeDemand(same_port, same_port))
    assert UserStrategy.assign_associated_bookings(context, now, same) is None

    context.service_routes = None
    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
    context.service_routes = 3
    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None

    context.service_routes = [types.SimpleNamespace(source_service_route=object())]
    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
    assert segment is not None and route is not None
