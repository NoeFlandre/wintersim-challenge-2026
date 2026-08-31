"""RED contract for the Round 2 port-closure one-transfer experiment."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

from response_strategies.user_strategy import UserStrategy

ANCHOR = dt.datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(
    name: str,
    ports: list[SimpleNamespace],
    distances: list[float],
    *,
    speed: float = 10.0,
    vessel_count: int = 1,
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
    route.deployed_vessels = [
        SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=speed))
        for _ in range(vessel_count)
    ]
    return route


def _shipment(origin: Any, destination: Any) -> SimpleNamespace:
    return SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )


def _port_plan(port: Any) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=None,
        target_berth=SimpleNamespace(port=port),
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=1.0,
        close_berth=True,
    )


def _leg_plan(leg: Any) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=leg,
        target_berth=None,
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=2.0,
        close_berth=False,
    )


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


def _one_transfer_fixture(
    safe_distances: tuple[float, float] = (300.0, 300.0),
) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace, dict[str, Any]]:
    origin = _port("Origin")
    closed = _port("Closed")
    transfer = _port("Transfer")
    destination = _port("Destination")
    nominal = _route(
        "nominal",
        [origin, closed, destination, origin],
        [100.0, 100.0, 100.0],
    )
    safe_a = _route("safe-a", [origin, transfer, origin], [safe_distances[0]] * 2)
    safe_b = _route("safe-b", [transfer, destination, transfer], [safe_distances[1]] * 2)
    context = SimpleNamespace(
        ports=[origin, closed, transfer, destination],
        service_routes=[nominal, safe_a, safe_b],
        disruption_plans=[_port_plan(closed)],
    )
    shipment = _shipment(origin, destination)
    now = ANCHOR + dt.timedelta(days=14.5)
    return context, now, shipment, {"nominal": nominal, "closed": closed}


def test_strong_port_closure_one_transfer_holds_without_mutation() -> None:
    context, now, shipment, _ = _one_transfer_fixture()
    before = _freeze((context, shipment))

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is False
    assert _freeze((context, shipment)) == before


def test_below_full_headway_port_closure_one_transfer_delegates() -> None:
    context, now, shipment, _ = _one_transfer_fixture((125.0, 125.0))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_half_headway_port_closure_one_transfer_holds() -> None:
    context, now, shipment, _ = _one_transfer_fixture((157.0, 157.0))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_half_headway_equality_delegates() -> None:
    distance = 470.0 / 3.0
    context, now, shipment, _ = _one_transfer_fixture((distance, distance))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_below_half_headway_delegates() -> None:
    context, now, shipment, _ = _one_transfer_fixture((156.0, 156.0))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_full_headway_equality_holds_under_half_headway_policy() -> None:
    context, now, shipment, _ = _one_transfer_fixture((235.0, 235.0))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_maximum_safe_route_headway_is_used() -> None:
    context, now, shipment, _ = _one_transfer_fixture((50.0, 250.0))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_leg_only_one_transfer_never_uses_port_closure_extension() -> None:
    context, now, shipment, items = _one_transfer_fixture()
    context.disruption_plans = [_leg_plan(items["nominal"].segments[0].associated_leg)]

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_mixed_leg_and_port_one_transfer_delegates() -> None:
    context, now, shipment, items = _one_transfer_fixture()
    context.disruption_plans.append(_leg_plan(items["nominal"].segments[0].associated_leg))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_multi_transfer_port_closure_retains_v3_hold() -> None:
    origin = _port("Origin")
    closed = _port("Closed")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route(
        "nominal",
        [origin, closed, destination, origin],
        [100.0, 100.0, 100.0],
    )
    safe_a = _route("safe-a", [origin, transfer_a, origin], [300.0, 300.0])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [300.0, 300.0])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [300.0, 300.0])
    context = SimpleNamespace(
        ports=[origin, closed, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[_port_plan(closed)],
    )
    shipment = _shipment(origin, destination)
    now = ANCHOR + dt.timedelta(days=14.5)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False
