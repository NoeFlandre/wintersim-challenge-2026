"""RED/GREEN behavior tests for the Round 1 weighted booking experiment."""

from __future__ import annotations

import datetime as dt
import sys
import types
from types import SimpleNamespace

import pytest
from response_strategies.user_strategy import UserStrategy


class FakeBooking:
    def __init__(
        self,
        sequence_index: int,
        shipment: object,
        service_route: object,
        departure_segment_index: int,
        arrival_segment_index: int,
    ) -> None:
        self.sequence_index = sequence_index
        self.shipment = shipment
        self.service_route = service_route
        self.departure_segment_index = departure_segment_index
        self.arrival_segment_index = arrival_segment_index


class FakePort:
    def __init__(self, name: str) -> None:
        self.name = name
        self.berths: list[object] = []

    __hash__ = object.__hash__


def _port(name: str) -> FakePort:
    return FakePort(name)


def _route(name: str, pairs: list[tuple[str, str, float]], ports: dict[str, object]):
    route = SimpleNamespace(
        id=name,
        name=name,
        start_day_of_week=0.0,
        segments=[],
        deployed_vessels=[],
        associated_bookings=[],
        source_service_route=None,
        disruption_key=None,
    )
    legs = []
    for sequence_index, (departure, arrival, distance) in enumerate(pairs, start=1):
        leg = SimpleNamespace(
            departure_port=ports[departure],
            arrival_port=ports[arrival],
            sailing_distance=distance,
            sailing_time_multiplier=1.0,
            segments=[],
        )
        segment = SimpleNamespace(
            sequence_index=sequence_index,
            associated_leg=leg,
            associated_service_route=route,
            current_vessels=[],
        )
        leg.segments.append(segment)
        route.segments.append(segment)
        legs.append(leg)
    vessel = SimpleNamespace(
        index=len(route.deployed_vessels) + 1,
        vessel_class=SimpleNamespace(sailing_speed=20.0),
        assigned_service_route=route,
        pending_assigned_service_route=None,
    )
    route.deployed_vessels.append(vessel)
    return route, legs


def _context(
    routes: list[object],
    legs: list[object],
    ports: dict[str, object],
    plans: list[object],
) -> SimpleNamespace:
    return SimpleNamespace(
        ports=list(ports.values()),
        legs=legs,
        service_routes=routes,
        initial_service_routes=list(routes),
        disruption_plans=plans,
        vessels=[vessel for route in routes for vessel in route.deployed_vessels],
    )


def _shipment(origin: object, destination: object) -> SimpleNamespace:
    return SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )


def _leg_plan(leg: object, *, multiplier: float, duration_days: float = 10.0):
    return SimpleNamespace(
        target_leg=leg,
        target_berth=None,
        start_offset_days=0.0,
        duration_days=duration_days,
        multiplier=multiplier,
        close_berth=False,
    )


def _closed_port_plan(port: object, *, duration_days: float = 10.0):
    berth = SimpleNamespace(port=port)
    return SimpleNamespace(
        target_leg=None,
        target_berth=berth,
        start_offset_days=0.0,
        duration_days=duration_days,
        multiplier=1.0,
        close_berth=True,
    )


def _install_fake_booking(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = types.ModuleType("maritime_data_context")
    fake_module.Booking = FakeBooking  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "maritime_data_context", fake_module)


def _active_now(hours: float = 1.0) -> dt.datetime:
    return dt.datetime.min + dt.timedelta(hours=hours)


def test_active_policy_prefers_shorter_effective_congested_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ports = {name: _port(name) for name in ("Origin", "Hub", "Destination", "Return")}
    direct, direct_legs = _route(
        "direct",
        [("Origin", "Destination", 100.0), ("Destination", "Origin", 100.0)],
        ports,
    )
    safe, safe_legs = _route(
        "safe",
        [
            ("Origin", "Hub", 80.0),
            ("Hub", "Destination", 80.0),
            ("Destination", "Origin", 160.0),
        ],
        ports,
    )
    context = _context(
        [direct, safe],
        direct_legs + safe_legs,
        ports,
        [_leg_plan(direct_legs[0], multiplier=1.5)],
    )
    shipment = _shipment(ports["Origin"], ports["Destination"])
    _install_fake_booking(monkeypatch)

    assert UserStrategy.assign_associated_bookings(context, _active_now(), shipment) is True
    assert shipment.associated_bookings[0].service_route is direct
    assert shipment.associated_bookings[0].arrival_segment_index == 1
    assert direct.associated_bookings == shipment.associated_bookings


def test_active_policy_uses_congested_path_when_no_safe_path_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ports = {name: _port(name) for name in ("Origin", "Destination")}
    route, legs = _route(
        "only",
        [("Origin", "Destination", 100.0), ("Destination", "Origin", 100.0)],
        ports,
    )
    context = _context([route], legs, ports, [_leg_plan(legs[0], multiplier=4.0)])
    shipment = _shipment(ports["Origin"], ports["Destination"])
    _install_fake_booking(monkeypatch)

    assert UserStrategy.assign_associated_bookings(context, _active_now(), shipment) is True
    assert shipment.current_booking_index == 1
    assert shipment.associated_bookings[0].service_route is route


def test_recovery_during_leg_is_accounted_for(monkeypatch: pytest.MonkeyPatch) -> None:
    ports = {name: _port(name) for name in ("Origin", "Hub", "Destination")}
    direct, direct_legs = _route(
        "direct",
        [("Origin", "Destination", 100.0), ("Destination", "Origin", 100.0)],
        ports,
    )
    safe, safe_legs = _route(
        "safe",
        [("Origin", "Hub", 55.0), ("Hub", "Destination", 55.0), ("Destination", "Origin", 110.0)],
        ports,
    )
    context = _context(
        [direct, safe],
        direct_legs + safe_legs,
        ports,
        [_leg_plan(direct_legs[0], multiplier=5.0, duration_days=0.00005)],
    )
    shipment = _shipment(ports["Origin"], ports["Destination"])
    _install_fake_booking(monkeypatch)

    assert UserStrategy.assign_associated_bookings(context, dt.datetime.min, shipment) is True
    assert shipment.associated_bookings[0].service_route is direct


def test_closed_port_is_hard_exclusion(monkeypatch: pytest.MonkeyPatch) -> None:
    ports = {name: _port(name) for name in ("Origin", "Closed", "Destination")}
    via_closed, via_closed_legs = _route(
        "via-closed",
        [
            ("Origin", "Closed", 10.0),
            ("Closed", "Destination", 10.0),
            ("Destination", "Origin", 20.0),
        ],
        ports,
    )
    direct, direct_legs = _route(
        "direct",
        [("Origin", "Destination", 100.0), ("Destination", "Origin", 100.0)],
        ports,
    )
    context = _context(
        [via_closed, direct],
        via_closed_legs + direct_legs,
        ports,
        [_closed_port_plan(ports["Closed"])],
    )
    shipment = _shipment(ports["Origin"], ports["Destination"])
    _install_fake_booking(monkeypatch)

    assert UserStrategy.assign_associated_bookings(context, _active_now(), shipment) is True
    assert shipment.associated_bookings[0].service_route is direct


def test_equal_cost_paths_use_context_order(monkeypatch: pytest.MonkeyPatch) -> None:
    ports = {name: _port(name) for name in ("Origin", "Destination")}
    first, first_legs = _route(
        "first",
        [("Origin", "Destination", 100.0), ("Destination", "Origin", 100.0)],
        ports,
    )
    second, second_legs = _route(
        "second",
        [("Origin", "Destination", 100.0), ("Destination", "Origin", 100.0)],
        ports,
    )
    context = _context(
        [first, second],
        first_legs + second_legs,
        ports,
        [_closed_port_plan(_port("Unrelated"))],
    )
    shipment = _shipment(ports["Origin"], ports["Destination"])
    _install_fake_booking(monkeypatch)

    assert UserStrategy.assign_associated_bookings(context, _active_now(), shipment) is True
    assert shipment.associated_bookings[0].service_route is first


def test_inactive_or_malformed_inputs_delegate_without_mutation() -> None:
    assert UserStrategy.assign_associated_bookings({}, _active_now(), object()) is None

    ports = {name: _port(name) for name in ("Origin", "Destination")}
    route, legs = _route(
        "malformed",
        [("Origin", "Destination", 100.0), ("Destination", "Origin", 100.0)],
        ports,
    )
    route.deployed_vessels[0].vessel_class.sailing_speed = "not-a-number"
    context = _context([route], legs, ports, [_leg_plan(legs[0], multiplier=2.0)])
    old_booking = SimpleNamespace(service_route=route, sequence_index=1)
    route.associated_bookings.append(old_booking)
    shipment = _shipment(ports["Origin"], ports["Destination"])
    shipment.associated_bookings = [old_booking]
    before = list(shipment.associated_bookings)

    assert UserStrategy.assign_associated_bookings(context, _active_now(), shipment) is None
    assert shipment.associated_bookings == before
    assert route.associated_bookings == [old_booking]


def test_no_path_delegates_without_clearing_old_bookings(monkeypatch: pytest.MonkeyPatch) -> None:
    ports = {name: _port(name) for name in ("Origin", "Destination", "Other")}
    route, legs = _route(
        "other",
        [("Other", "Destination", 20.0), ("Destination", "Other", 20.0)],
        ports,
    )
    context = _context([route], legs, ports, [_leg_plan(legs[0], multiplier=2.0)])
    old_booking = SimpleNamespace(service_route=route, sequence_index=1)
    route.associated_bookings.append(old_booking)
    shipment = _shipment(ports["Origin"], ports["Destination"])
    shipment.associated_bookings = [old_booking]
    _install_fake_booking(monkeypatch)

    assert UserStrategy.assign_associated_bookings(context, _active_now(), shipment) is None
    assert shipment.associated_bookings == [old_booking]
    assert route.associated_bookings == [old_booking]
