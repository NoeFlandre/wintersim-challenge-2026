"""RED/GREEN tests for the no-safe-path congestion-tail policy."""

from __future__ import annotations

import datetime as dt
import sys
import types
from types import SimpleNamespace

import pytest
from response_strategies.user_strategy import UserStrategy


class _Booking:
    def __init__(
        self,
        *,
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


class _FailingList(list):
    def append(self, value):
        raise RuntimeError("injected booking installation failure")


def _install_booking_module(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("maritime_data_context")
    module.Booking = _Booking
    monkeypatch.setitem(sys.modules, "maritime_data_context", module)


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(
    origin: SimpleNamespace,
    destination: SimpleNamespace,
    *,
    route_id: str = "R1",
    distance: float = 100.0,
    deployed: bool = True,
):
    route = SimpleNamespace(
        id=route_id,
        source_service_route=None,
        disruption_key=None,
        deployed_vessels=[object()] if deployed else [],
        associated_bookings=[],
        segments=[],
    )
    leg = SimpleNamespace(
        departure_port=origin,
        arrival_port=destination,
        sailing_distance=distance,
        segments=[],
    )
    segment = SimpleNamespace(
        sequence_index=1,
        associated_leg=leg,
        associated_service_route=route,
        current_vessels=[],
    )
    leg.segments.append(segment)
    route.segments.append(segment)
    return route, leg


def _case(*, safe_detour: bool = False, close_berth: bool = False):
    origin = _port("Origin")
    destination = _port("Destination")
    direct, target_leg = _route(origin, destination)
    routes = [direct]
    if safe_detour:
        middle = _port("Middle")
        first, _ = _route(origin, middle, route_id="SAFE-1", distance=50.0)
        second, _ = _route(middle, destination, route_id="SAFE-2", distance=50.0)
        routes.extend([first, second])
        ports = [origin, middle, destination]
    else:
        ports = [origin, destination]
    plan = SimpleNamespace(
        target_leg=None if close_berth else target_leg,
        target_berth=SimpleNamespace(port=origin) if close_berth else None,
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=1.0 if close_berth else 3.0,
        close_berth=close_berth,
    )
    context = SimpleNamespace(
        ports=ports,
        service_routes=routes,
        disruption_plans=[plan],
    )
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )
    start = dt.datetime.min + dt.timedelta(days=10.0)
    return context, direct, target_leg, shipment, start, plan


def test_no_safe_exact_congestion_installs_direct_booking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, leg, shipment, start, _plan = _case()

    result = UserStrategy.assign_associated_bookings(
        context, start + dt.timedelta(seconds=1), shipment
    )

    assert result is True
    assert len(shipment.associated_bookings) == 1
    booking = shipment.associated_bookings[0]
    assert booking.service_route is route
    assert booking.departure_segment_index == 1
    assert booking.arrival_segment_index == 1
    assert booking.service_route.segments[0].associated_leg is leg
    assert route.associated_bookings == [booking]
    assert shipment.current_booking_index == 1


def test_safe_detour_delegates_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, _leg, shipment, start, _plan = _case(safe_detour=True)
    before = (
        list(shipment.associated_bookings),
        shipment.current_booking_index,
        list(route.associated_bookings),
    )

    result = UserStrategy.assign_associated_bookings(
        context, start + dt.timedelta(seconds=1), shipment
    )

    assert result is None
    assert (
        shipment.associated_bookings,
        shipment.current_booking_index,
        route.associated_bookings,
    ) == before


def test_active_window_start_is_inclusive_and_end_is_exclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, _route, _leg, at_start, start, plan = _case()
    assert UserStrategy.assign_associated_bookings(context, start, at_start) is True

    context, _route, _leg, at_end, start, plan = _case()
    end = start + dt.timedelta(days=plan.duration_days)
    assert UserStrategy.assign_associated_bookings(context, end, at_end) is None


def test_active_closure_delegates_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, _leg, shipment, start, _plan = _case(close_berth=True)
    before = (
        list(shipment.associated_bookings),
        shipment.current_booking_index,
        list(route.associated_bookings),
    )

    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None
    assert (
        shipment.associated_bookings,
        shipment.current_booking_index,
        route.associated_bookings,
    ) == before


@pytest.mark.parametrize(
    "mutate",
    [
        lambda context, route, leg, shipment, plan: setattr(
            shipment.demand, "destination_port", _port("Other")
        ),
        lambda context, route, leg, shipment, plan: setattr(plan, "start_offset_days", 100.0),
        lambda context, route, leg, shipment, plan: setattr(route, "deployed_vessels", []),
        lambda context, route, leg, shipment, plan: setattr(plan, "multiplier", "bad"),
        lambda context, route, leg, shipment, plan: setattr(plan, "target_leg", None),
    ],
)
def test_nonmatching_or_malformed_state_delegates_without_mutation(
    monkeypatch: pytest.MonkeyPatch, mutate
) -> None:
    _install_booking_module(monkeypatch)
    context, route, leg, shipment, start, plan = _case()
    mutate(context, route, leg, shipment, plan)
    before = (
        list(shipment.associated_bookings),
        shipment.current_booking_index,
        list(route.associated_bookings),
    )

    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None
    assert (
        shipment.associated_bookings,
        shipment.current_booking_index,
        route.associated_bookings,
    ) == before


def test_installation_failure_rolls_back_old_booking_and_reverse_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, _leg, shipment, start, _plan = _case()
    old = _Booking(
        sequence_index=7,
        shipment=shipment,
        service_route=route,
        departure_segment_index=1,
        arrival_segment_index=1,
    )
    route.associated_bookings = _FailingList([old])
    shipment.associated_bookings = [old]
    shipment.current_booking_index = 7

    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None
    assert shipment.associated_bookings == [old]
    assert shipment.current_booking_index == 7
    assert route.associated_bookings == [old]


def test_other_hooks_delegate() -> None:
    assert UserStrategy.select_vessel_for_berth(None, None, [], [], None) is None
    assert UserStrategy.create_alternative_service_routes(None, None) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(None, None, None) is None
