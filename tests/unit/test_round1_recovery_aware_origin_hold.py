"""RED/GREEN contract tests for the recovery-aware origin-hold policy."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from response_strategies.user_strategy import UserStrategy


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(route_id: str, legs: list[tuple[SimpleNamespace, SimpleNamespace, float]]):
    route = SimpleNamespace(
        id=route_id,
        segments=[],
        deployed_vessels=[],
        source_service_route=None,
        disruption_key=None,
        associated_bookings=[],
    )
    for sequence, (departure, arrival, distance) in enumerate(legs, start=1):
        leg = SimpleNamespace(
            departure_port=departure,
            arrival_port=arrival,
            sailing_distance=distance,
            segments=[],
        )
        segment = SimpleNamespace(
            sequence_index=sequence,
            associated_leg=leg,
            associated_service_route=route,
            current_vessels=[],
        )
        leg.segments.append(segment)
        route.segments.append(segment)
    vessel = SimpleNamespace(
        assigned_service_route=route,
        vessel_class=SimpleNamespace(sailing_speed=20.0),
    )
    route.deployed_vessels.append(vessel)
    return route


def _fixture(*, safe_distance: float = 1_000.0):
    origin = _port("Origin")
    destination = _port("Destination")
    detour = _port("Detour")
    nominal = _route(
        "NOMINAL",
        [(origin, destination, 100.0), (destination, origin, 100.0)],
    )
    safe = _route(
        "SAFE",
        [
            (origin, detour, safe_distance / 2.0),
            (detour, destination, safe_distance / 2.0),
            (destination, origin, 20.0),
        ],
    )
    target_leg = nominal.segments[0].associated_leg
    plan = SimpleNamespace(
        start_offset_days=10.0,
        duration_days=5.0,
        target_leg=target_leg,
        target_berth=None,
        multiplier=2.0,
        close_berth=False,
    )
    context = SimpleNamespace(
        ports=[origin, destination, detour],
        service_routes=[nominal, safe],
        disruption_plans=[plan],
    )
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )
    return context, shipment, plan, nominal, safe


def _now(day: float) -> dt.datetime:
    return dt.datetime.min + dt.timedelta(days=day)


def test_returns_false_when_waiting_for_recovery_beats_safe_detour() -> None:
    context, shipment, _plan, _nominal, _safe = _fixture(safe_distance=1_000.0)
    before = (
        tuple(context.service_routes),
        tuple(context.ports),
        list(shipment.associated_bookings),
        shipment.current_booking_index,
    )

    result = UserStrategy.assign_associated_bookings(
        context, _now(14.5), shipment
    )

    assert result is False
    assert (
        tuple(context.service_routes),
        tuple(context.ports),
        shipment.associated_bookings,
        shipment.current_booking_index,
    ) == before


def test_delegates_when_safe_detour_is_faster() -> None:
    context, shipment, _plan, _nominal, _safe = _fixture(safe_distance=20.0)

    result = UserStrategy.assign_associated_bookings(context, _now(14.5), shipment)

    assert result is None
    assert shipment.associated_bookings == []
    assert shipment.current_booking_index is None


def test_active_window_start_is_inclusive() -> None:
    context, shipment, _plan, _nominal, _safe = _fixture(safe_distance=1_000.0)

    assert UserStrategy.assign_associated_bookings(context, _now(10.0), shipment) is False


def test_active_window_end_is_exclusive() -> None:
    context, shipment, plan, _nominal, _safe = _fixture(safe_distance=1_000.0)
    at_end = _now(plan.start_offset_days + plan.duration_days)

    assert UserStrategy.assign_associated_bookings(context, at_end, shipment) is None


def test_delegates_when_active_plan_does_not_touch_nominal_path() -> None:
    context, shipment, plan, _nominal, _safe = _fixture(safe_distance=1_000.0)
    other_origin = _port("Other origin")
    other_destination = _port("Other destination")
    plan.target_leg = SimpleNamespace(
        departure_port=other_origin,
        arrival_port=other_destination,
        sailing_distance=10.0,
        segments=[],
    )

    assert UserStrategy.assign_associated_bookings(context, _now(14.5), shipment) is None


def test_delegates_when_no_complete_safe_path_exists() -> None:
    context, shipment, _plan, nominal, safe = _fixture(safe_distance=1_000.0)
    context.service_routes = [nominal]

    assert UserStrategy.assign_associated_bookings(context, _now(14.5), shipment) is None


def test_delegates_without_active_disruption() -> None:
    context, shipment, plan, _nominal, _safe = _fixture(safe_distance=1_000.0)
    plan.start_offset_days = 100.0

    assert UserStrategy.assign_associated_bookings(context, _now(14.5), shipment) is None


def test_malformed_context_fails_closed_without_mutation() -> None:
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=_port("A"), destination_port=_port("B")),
        associated_bookings=[],
        current_booking_index=None,
    )
    context = SimpleNamespace(
        ports=[],
        service_routes=[],
        disruption_plans=[object()],
    )

    assert UserStrategy.assign_associated_bookings(context, _now(14.5), shipment) is None
    assert shipment.associated_bookings == []
    assert shipment.current_booking_index is None


def test_all_other_hooks_delegate() -> None:
    assert UserStrategy.select_vessel_for_berth(None, None, [], [], None) is None
    assert UserStrategy.create_alternative_service_routes(None, None) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(None, None, None) is None
