"""RED/GREEN tests for the no-safe-path congestion-tail policy."""

from __future__ import annotations

import datetime as dt
import sys
import types
from types import SimpleNamespace

import pytest
from response_strategies import user_strategy as strategy_module
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
    return_leg = SimpleNamespace(
        departure_port=destination,
        arrival_port=origin,
        sailing_distance=distance,
        segments=[],
    )
    segment = SimpleNamespace(
        sequence_index=1,
        associated_leg=leg,
        associated_service_route=route,
        current_vessels=[],
    )
    return_segment = SimpleNamespace(
        sequence_index=2,
        associated_leg=return_leg,
        associated_service_route=route,
        current_vessels=[],
    )
    leg.segments.append(segment)
    return_leg.segments.append(return_segment)
    route.segments.append(segment)
    route.segments.append(return_segment)
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


def test_invalid_context_and_clock_fail_closed() -> None:
    context, _route, _leg, shipment, start, _plan = _case()

    assert UserStrategy.assign_associated_bookings(None, start, shipment) is None
    assert UserStrategy.assign_associated_bookings(context, "not-a-time", shipment) is None
    assert UserStrategy.assign_associated_bookings(context, start, None) is None
    assert UserStrategy.assign_associated_bookings(context, start, object()) is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda _context, _route, _leg, _shipment, plan: setattr(plan, "duration_days", 0.0),
        lambda _context, _route, _leg, _shipment, plan: setattr(
            plan, "start_offset_days", float("nan")
        ),
        lambda _context, _route, _leg, _shipment, plan: setattr(plan, "target_leg", None),
    ],
)
def test_invalid_active_plan_data_delegates_without_mutation(mutate) -> None:
    context, route, _leg, shipment, start, plan = _case()
    mutate(context, route, _leg, shipment, plan)
    before = (list(shipment.associated_bookings), shipment.current_booking_index)

    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None
    assert (shipment.associated_bookings, shipment.current_booking_index) == before


def test_active_state_handles_duplicate_congestion_and_inactive_closure() -> None:
    context, _route, _leg, _shipment, start, plan = _case()
    context.disruption_plans.append(plan)
    inactive_closure = SimpleNamespace(
        target_leg=None,
        target_berth=SimpleNamespace(port=_port("Closed")),
        start_offset_days=100.0,
        duration_days=2.0,
        multiplier=1.0,
        close_berth=True,
    )
    context.disruption_plans.append(inactive_closure)

    state = strategy_module._active_state(context, start)  # noqa: SLF001

    assert state is not None
    assert state.congested_legs == (plan.target_leg,)
    assert state.closed_names == ()


def test_malformed_active_closure_fails_closed() -> None:
    context, _route, _leg, shipment, start, plan = _case()
    plan.close_berth = True
    plan.target_berth = SimpleNamespace(port=None)
    plan.target_leg = None
    plan.multiplier = 1.0

    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None


def test_graph_helpers_reject_malformed_routes_and_edges() -> None:
    context, route, leg, _shipment, start, _plan = _case()
    state = strategy_module._active_state(context, start)  # noqa: SLF001
    assert state is not None

    assert strategy_module._ordered_segments(SimpleNamespace(segments=None)) is None  # noqa: SLF001
    assert strategy_module._ordered_segments(SimpleNamespace(segments=[object()])) is None  # noqa: SLF001
    assert strategy_module._safe_edges(SimpleNamespace(segments=None), state) == []  # noqa: SLF001

    route.segments[0].associated_leg.sailing_distance = 0.0
    assert strategy_module._edge(route, route.segments, 0, 1) is None  # noqa: SLF001
    route.segments[0].associated_leg.sailing_distance = 100.0
    route.segments[0].associated_leg.arrival_port = route.segments[0].associated_leg.departure_port
    assert strategy_module._edge(route, route.segments, 0, 1) is None  # noqa: SLF001
    assert leg is route.segments[0].associated_leg


def test_alternative_routes_must_match_active_key_and_have_vessels() -> None:
    context, route, _leg, _shipment, start, _plan = _case()
    state = strategy_module._active_state(context, start)  # noqa: SLF001
    assert state is not None

    alternative = SimpleNamespace(
        source_service_route=route,
        disruption_key=(("other",), (("origin", "destination"),)),
        deployed_vessels=[object()],
        segments=route.segments,
    )
    assert strategy_module._safe_edges(alternative, state) == []  # noqa: SLF001
    alternative.disruption_key = state.disruption_key
    alternative.deployed_vessels = []
    assert strategy_module._safe_edges(alternative, state) == []  # noqa: SLF001


def test_path_search_rejects_missing_ports_and_unreachable_graph() -> None:
    context, _route, _leg, _shipment, start, _plan = _case()
    state = strategy_module._active_state(context, start)  # noqa: SLF001
    assert state is not None
    origin, destination = context.ports

    assert strategy_module._has_safe_path(context, origin, _port("Other"), state) is False  # noqa: SLF001
    assert (
        strategy_module._has_safe_path(SimpleNamespace(ports=None), origin, destination, state)
        is False
    )  # noqa: SLF001
    assert strategy_module._has_safe_path(context, origin, destination, state) is False  # noqa: SLF001


def test_direct_segment_and_installation_reject_bad_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, leg, _shipment, start, _plan = _case()

    route.deployed_vessels = []
    assert strategy_module._find_direct_segment(context, leg) is None  # noqa: SLF001
    route.deployed_vessels = [object()]
    route.associated_bookings = None
    assert strategy_module._find_direct_segment(context, leg) is None  # noqa: SLF001

    malformed_shipment = SimpleNamespace(associated_bookings=None)
    assert strategy_module._install_direct_booking(malformed_shipment, route, 1) is None  # noqa: SLF001
    assert strategy_module._decision(context, start, object()) is None  # noqa: SLF001


def test_installation_rejects_old_booking_with_invalid_reverse_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_booking_module(monkeypatch)
    context, route, _leg, shipment, start, _plan = _case()
    old_route = SimpleNamespace(associated_bookings=None)
    old = _Booking(
        sequence_index=1,
        shipment=shipment,
        service_route=old_route,
        departure_segment_index=1,
        arrival_segment_index=1,
    )
    shipment.associated_bookings = [old]

    assert UserStrategy.assign_associated_bookings(context, start, shipment) is None
    assert shipment.associated_bookings == [old]
