"""RED contract for the additive Round 1 weekly-phase recovery hold."""

from __future__ import annotations

import datetime as dt
import math
from types import SimpleNamespace
from typing import Any

from response_strategies.user_strategy import UserStrategy

ANCHOR = dt.datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(
    name: str,
    ports: list[SimpleNamespace],
    distance: float,
    start_day_of_week: float,
) -> SimpleNamespace:
    route = SimpleNamespace(
        name=name,
        source_service_route=None,
        disruption_key=None,
        associated_bookings=[],
        start_day_of_week=start_day_of_week,
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
    route.deployed_vessels = [
        SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=10.0))
    ]
    return route


def _leg_plan(leg: Any) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=leg,
        target_berth=None,
        start_offset_days=10.0,
        duration_days=6.166666666666667,
        multiplier=2.0,
        close_berth=False,
    )


def _shipment(origin: Any, destination: Any) -> SimpleNamespace:
    return SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )


def _phase_positive_fixture() -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace]:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    now = ANCHOR + dt.timedelta(days=14.5)
    current_phase = now.weekday() + 0.5
    nominal = _route("nominal", [origin, destination, origin], 50.0, current_phase)
    delayed_phase = (current_phase + 4.0) % 7.0
    safe_a = _route("safe-a", [origin, transfer_a, origin], 50.0, delayed_phase)
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], 50.0, delayed_phase)
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], 50.0, delayed_phase)
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[_leg_plan(nominal.segments[0].associated_leg)],
    )
    return context, now, _shipment(origin, destination)


def _freeze(value: Any, seen: dict[int, int] | None = None) -> Any:
    if seen is None:
        seen = {}
    if value is None or isinstance(value, (bool, int, float, str, dt.datetime)):
        return (type(value).__name__, repr(value))
    identity = id(value)
    if identity in seen:
        return ("ref", seen[identity])
    seen[identity] = len(seen)
    if isinstance(value, list):
        return ("list", identity, tuple(_freeze(item, seen) for item in value))
    if isinstance(value, tuple):
        return ("tuple", tuple(_freeze(item, seen) for item in value))
    if isinstance(value, dict):
        return (
            "dict",
            identity,
            tuple((repr(key), _freeze(item, seen)) for key, item in value.items()),
        )
    if hasattr(value, "__dict__"):
        return (
            type(value).__name__,
            identity,
            tuple((name, _freeze(item, seen)) for name, item in sorted(vars(value).items())),
        )
    return (type(value).__name__, identity, repr(value))


def test_phase_positive_v3_delegation_returns_false_without_mutation() -> None:
    context, now, shipment = _phase_positive_fixture()
    before = _freeze((context, shipment))

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is False
    assert _freeze((context, shipment)) == before


def test_phase_schedule_invalid_values_delegate_without_mutation() -> None:
    context, now, shipment = _phase_positive_fixture()
    context.service_routes[1].start_day_of_week = math.nan
    before = _freeze((context, shipment))

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is None
    assert _freeze((context, shipment)) == before


def test_existing_v3_hold_is_preserved_when_phase_estimate_is_unavailable() -> None:
    context, now, shipment = _phase_positive_fixture()
    for route in context.service_routes[1:]:
        for segment in route.segments:
            segment.associated_leg.sailing_distance = 1000.0
    for route in context.service_routes:
        route.start_day_of_week = None
    # A missing phase must not remove the existing v3 decision.  The fixture is
    # otherwise a valid three-change v3 hold.
    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is False
