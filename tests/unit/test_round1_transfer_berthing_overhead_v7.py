"""RED contract for the Round 1 transfer-berthing overhead v7 experiment."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

from response_strategies.user_strategy import UserStrategy

ANCHOR = dt.datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(name: str, ports: list[SimpleNamespace], distances: list[float]) -> SimpleNamespace:
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


def _fixture(safe_distances: tuple[float, float, float]) -> tuple[Any, dt.datetime, Any]:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer_a, origin], [safe_distances[0]] * 2)
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [safe_distances[1]] * 2)
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [safe_distances[2]] * 2)
    plan = SimpleNamespace(
        target_leg=nominal.segments[0].associated_leg,
        target_berth=None,
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=2.0,
        close_berth=False,
    )
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[plan],
    )
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )
    return context, ANCHOR + dt.timedelta(days=14.5), shipment


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
    if hasattr(value, "__dict__"):
        return (
            type(value).__name__,
            identity,
            tuple((name, _freeze(item, seen)) for name, item in sorted(vars(value).items())),
        )
    return (type(value).__name__, identity, repr(value))


def test_marginal_two_transfer_detour_includes_two_three_hour_berths() -> None:
    context, now, shipment = _fixture((40.0, 40.0, 80.0))

    # v3 sees exact sailing/headway equality and delegates.  The candidate's
    # two transfer changes add 12 hours, so it must hold without mutation.
    before = _freeze((context, shipment))
    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False
    assert _freeze((context, shipment)) == before


def test_existing_large_margin_v3_hold_is_unchanged() -> None:
    context, now, shipment = _fixture((1000.0, 1000.0, 1000.0))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_non_transfer_safe_path_still_delegates() -> None:
    context, now, shipment = _fixture((1000.0, 1000.0, 1000.0))
    direct = _route(
        "direct", [context.ports[0], context.ports[3], context.ports[0]], [200.0, 200.0]
    )
    context.service_routes.append(direct)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
