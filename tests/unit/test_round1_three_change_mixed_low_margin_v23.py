"""RED contract for the narrow Round 1 v23 delegation guard."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

from response_strategies.user_strategy import UserStrategy

ANCHOR = dt.datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(name: str, ports: list[Any], distance: float) -> SimpleNamespace:
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
        for index in range(1, len(ports))
    ]
    route.deployed_vessels = [SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=10.0))]
    return route


def _leg_plan(leg: Any) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=leg,
        target_berth=None,
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=2.0,
        close_berth=False,
    )


def _berth_plan(port: Any) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=None,
        target_berth=SimpleNamespace(port=port),
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=1.0,
        close_berth=True,
    )


def _fixture(
    *, safe_distance: float = 20.0, safe_route_count: int = 4, mixed: bool = True
) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace]:
    origin = _port("Origin")
    closed = _port("Closed")
    destination = _port("Destination")
    transfer_ports = [_port(f"Transfer {index}") for index in range(safe_route_count)]
    nominal = _route("nominal", [origin, closed, destination, origin], 10.0)

    chain = [origin, *transfer_ports[: safe_route_count - 1], destination]
    safe_routes = [
        _route(f"safe-{index}", [chain[index], chain[index + 1], chain[index]], safe_distance)
        for index in range(safe_route_count)
    ]
    plans: list[Any] = [_leg_plan(nominal.segments[0].associated_leg)]
    if mixed:
        plans.append(_berth_plan(closed))
    context = SimpleNamespace(
        ports=[origin, closed, *transfer_ports, destination],
        service_routes=[nominal, *safe_routes],
        disruption_plans=plans,
    )
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )
    return context, ANCHOR + dt.timedelta(days=14.5), shipment


def _snapshot(context: Any, shipment: Any) -> tuple[Any, ...]:
    return (
        tuple(id(port) for port in context.ports),
        tuple(id(route) for route in context.service_routes),
        tuple(
            (
                id(route),
                tuple(
                    (
                        id(segment),
                        segment.sequence_index,
                        id(segment.associated_leg),
                        id(segment.associated_leg.departure_port),
                        id(segment.associated_leg.arrival_port),
                        segment.associated_leg.sailing_distance,
                    )
                    for segment in route.segments
                ),
                tuple(id(vessel) for vessel in route.deployed_vessels),
            )
            for route in context.service_routes
        ),
        tuple(
            (
                id(plan),
                id(getattr(plan, "target_leg", None)),
                id(getattr(plan, "target_berth", None)),
                plan.start_offset_days,
                plan.duration_days,
                plan.multiplier,
                plan.close_berth,
            )
            for plan in context.disruption_plans
        ),
        tuple(id(booking) for booking in shipment.associated_bookings),
        shipment.current_booking_index,
    )


def _decision(context: Any, now: Any, shipment: Any) -> Any:
    return UserStrategy.assign_associated_bookings(context, now, shipment)


def test_mixed_three_change_low_margin_delegates_without_mutation() -> None:
    context, now, shipment = _fixture()
    before = _snapshot(context, shipment)

    assert _decision(context, now, shipment) is None
    assert _snapshot(context, shipment) == before


def test_mixed_three_change_exact_headway_keeps_v3_hold() -> None:
    context, _, shipment = _fixture()
    now = ANCHOR + dt.timedelta(days=14, hours=15, minutes=30)

    assert _decision(context, now, shipment) is False


def test_mixed_three_change_above_headway_keeps_v3_hold() -> None:
    context, now, shipment = _fixture(safe_distance=30.0)

    assert _decision(context, now, shipment) is False


def test_mixed_two_change_keeps_v3_hold() -> None:
    context, now, shipment = _fixture(safe_distance=30.0, safe_route_count=3)

    assert _decision(context, now, shipment) is False


def test_pure_leg_three_change_keeps_v3_hold() -> None:
    context, now, shipment = _fixture(mixed=False)

    assert _decision(context, now, shipment) is False


def test_malformed_first_safe_route_delegates_fail_closed() -> None:
    context, now, shipment = _fixture()
    context.service_routes[1].deployed_vessels = []

    assert _decision(context, now, shipment) is None
