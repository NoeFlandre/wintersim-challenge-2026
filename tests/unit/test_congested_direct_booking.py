"""RED/GREEN contract tests for the narrow Round 1 direct-booking policy."""

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


def _case(*, close_berth: bool = False, deployed: bool = True, start: float = 10.0):
    origin = SimpleNamespace(name="Origin")
    destination = SimpleNamespace(name="Destination")
    leg = SimpleNamespace(
        departure_port=origin,
        arrival_port=destination,
        sailing_distance=100.0,
    )
    route = SimpleNamespace(
        source_service_route=None,
        disruption_key=None,
        deployed_vessels=[object()] if deployed else [],
        associated_bookings=[],
        segments=[
            SimpleNamespace(
                sequence_index=1,
                associated_leg=leg,
                associated_service_route=None,
            )
        ],
    )
    route.segments[0].associated_service_route = route
    plan = SimpleNamespace(
        target_leg=leg if not close_berth else None,
        target_berth=SimpleNamespace(port=origin) if close_berth else None,
        start_offset_days=start,
        duration_days=5.0,
        multiplier=3.0 if not close_berth else 1.0,
        close_berth=close_berth,
    )
    context = SimpleNamespace(
        ports=[origin, destination],
        service_routes=[route],
        disruption_plans=[plan],
    )
    demand = SimpleNamespace(origin_port=origin, destination_port=destination)
    shipment = SimpleNamespace(
        demand=demand,
        associated_bookings=[],
        current_booking_index=None,
    )
    start_time = dt.datetime.min + dt.timedelta(days=start)
    return context, route, leg, shipment, start_time


def test_active_congestion_exact_endpoints_install_one_direct_booking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, leg, shipment, start = _case()

    result = UserStrategy.assign_associated_bookings(
        context, start + dt.timedelta(seconds=1), shipment
    )

    assert result is True
    assert len(shipment.associated_bookings) == 1
    booking = shipment.associated_bookings[0]
    assert booking.service_route is route
    assert booking.departure_segment_index == 1
    assert booking.arrival_segment_index == 1
    assert route.associated_bookings == [booking]
    assert shipment.current_booking_index == 1
    assert booking.service_route.segments[0].associated_leg is leg


def test_active_window_start_is_inclusive_and_end_is_exclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, _route, _leg, at_start, start = _case()
    assert UserStrategy.assign_associated_bookings(context, start, at_start) is True

    _context, _route, _leg, at_end, start = _case()
    end = start + dt.timedelta(days=5)
    assert UserStrategy.assign_associated_bookings(context, end, at_end) is None


def test_any_active_berth_closure_delegates_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, _leg, shipment, start = _case(close_berth=True)
    before = (
        list(shipment.associated_bookings),
        shipment.current_booking_index,
        list(route.associated_bookings),
    )

    result = UserStrategy.assign_associated_bookings(context, start, shipment)

    assert result is None
    assert (
        shipment.associated_bookings,
        shipment.current_booking_index,
        route.associated_bookings,
    ) == before


@pytest.mark.parametrize(
    "mutate",
    [
        lambda context, route, leg, shipment: setattr(
            shipment.demand, "destination_port", SimpleNamespace(name="Other")
        ),
        lambda context, route, leg, shipment: setattr(
            context.disruption_plans[0], "start_offset_days", "bad"
        ),
        lambda context, route, leg, shipment: setattr(route, "deployed_vessels", []),
        lambda context, route, leg, shipment: setattr(route, "source_service_route", object()),
    ],
)
def test_nonmatching_or_malformed_state_delegates_without_mutation(
    monkeypatch: pytest.MonkeyPatch, mutate
) -> None:
    _install_booking_module(monkeypatch)
    context, route, _leg, shipment, start = _case()
    mutate(context, route, _leg, shipment)
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


def test_installation_failure_restores_shipment_and_reverse_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, leg, shipment, start = _case()
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
    assert old.service_route is route
    assert leg is route.segments[0].associated_leg


@pytest.mark.parametrize(
    "context_factory",
    [
        lambda: SimpleNamespace(),
        lambda: SimpleNamespace(disruption_plans=None),
        lambda: SimpleNamespace(disruption_plans=object()),
    ],
)
def test_missing_or_uniterable_disruption_plans_delegate(
    context_factory,
) -> None:
    _context, _route, _leg, shipment, start = _case()
    context = context_factory()
    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: setattr(plan, "multiplier", None),
        lambda plan: setattr(plan, "duration_days", float("nan")),
        lambda plan: setattr(plan, "duration_days", 0.0),
        lambda plan: setattr(plan, "start_offset_days", 1e300),
    ],
)
def test_invalid_plan_numbers_delegate(monkeypatch: pytest.MonkeyPatch, mutate) -> None:
    _install_booking_module(monkeypatch)
    context, _route, _leg, shipment, start = _case()
    mutate(context.disruption_plans[0])
    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None


def test_active_closure_without_a_valid_berth_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, _route, _leg, shipment, start = _case(close_berth=True)
    context.disruption_plans[0].target_berth = None
    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: setattr(plan, "target_leg", None),
        lambda plan: setattr(plan.target_leg, "departure_port", None),
        lambda plan: setattr(plan.target_leg, "arrival_port", None),
    ],
)
def test_active_congested_plan_without_a_valid_leg_delegates(
    monkeypatch: pytest.MonkeyPatch, mutate
) -> None:
    _install_booking_module(monkeypatch)
    context, _route, _leg, shipment, start = _case()
    mutate(context.disruption_plans[0])
    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None


def test_duplicate_target_plans_are_deduplicated_and_route_order_is_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, leg, shipment, start = _case()
    duplicate = SimpleNamespace(
        target_leg=leg,
        target_berth=None,
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=3.0,
        close_berth=False,
    )
    context.disruption_plans.append(duplicate)
    assert UserStrategy.assign_associated_bookings(context, start, shipment) is True
    assert shipment.associated_bookings[0].service_route is route


@pytest.mark.parametrize(
    "mutate",
    [
        lambda context, route, leg: setattr(context, "service_routes", None),
        lambda context, route, leg: setattr(context, "service_routes", object()),
        lambda context, route, leg: setattr(route, "segments", [object()]),
        lambda context, route, leg: setattr(
            route, "segments", [SimpleNamespace(associated_leg=leg, sequence_index=True)]
        ),
        lambda context, route, leg: setattr(
            route, "segments", [SimpleNamespace(associated_leg=leg, sequence_index=0)]
        ),
        lambda context, route, leg: setattr(route, "associated_bookings", ()),
    ],
)
def test_invalid_route_shape_delegates(monkeypatch: pytest.MonkeyPatch, mutate) -> None:
    _install_booking_module(monkeypatch)
    context, route, leg, shipment, start = _case()
    mutate(context, route, leg)
    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None


def test_original_route_is_required_when_an_alternative_precedes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, leg, shipment, start = _case()
    alternative = SimpleNamespace(
        source_service_route=route,
        deployed_vessels=[object()],
        associated_bookings=[],
        segments=[SimpleNamespace(associated_leg=leg, sequence_index=1)],
    )
    context.service_routes.insert(0, alternative)
    assert UserStrategy.assign_associated_bookings(context, start, shipment) is True
    assert shipment.associated_bookings[0].service_route is route


def test_old_booking_on_another_route_is_removed_transactionally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, _leg, shipment, start = _case()
    old_route = SimpleNamespace(associated_bookings=[])
    old = _Booking(
        sequence_index=4,
        shipment=shipment,
        service_route=old_route,
        departure_segment_index=1,
        arrival_segment_index=1,
    )
    old_route.associated_bookings.append(old)
    shipment.associated_bookings = [old]
    shipment.current_booking_index = 4

    assert UserStrategy.assign_associated_bookings(context, start, shipment) is True
    assert old not in old_route.associated_bookings
    assert shipment.current_booking_index == 1
    assert shipment.associated_bookings[0].service_route is route


def test_old_booking_without_a_reverse_route_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, _route, _leg, shipment, start = _case()
    old = SimpleNamespace(service_route=None)
    shipment.associated_bookings = [old]
    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None


def test_missing_runtime_booking_type_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("maritime_data_context")
    monkeypatch.setitem(sys.modules, "maritime_data_context", module)
    context, _route, _leg, shipment, start = _case()
    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None


def test_same_origin_and_destination_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_booking_module(monkeypatch)
    context, _route, _leg, shipment, start = _case()
    shipment.demand.destination_port = shipment.demand.origin_port
    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None
