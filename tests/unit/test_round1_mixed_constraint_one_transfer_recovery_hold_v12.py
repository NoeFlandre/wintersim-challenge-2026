"""RED contract for the Round 1 v12 mixed one-transfer extension."""

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
    route.deployed_vessels = [SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=speed))]
    return route


def _mixed_fixture(
    *,
    safe_distance: float = 100.0,
    include_leg: bool = True,
    include_port: bool = True,
) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace, dict[str, Any]]:
    origin = _port("Origin")
    closed = _port("Closed")
    transfer = _port("Transfer")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, closed, destination, origin], [50.0, 50.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer, origin], [safe_distance, safe_distance])
    safe_b = _route("safe-b", [transfer, destination, transfer], [safe_distance, safe_distance])
    plans: list[SimpleNamespace] = []
    if include_leg:
        plans.append(
            SimpleNamespace(
                target_leg=nominal.segments[0].associated_leg,
                target_berth=None,
                start_offset_days=10.0,
                duration_days=5.0,
                multiplier=2.0,
                close_berth=False,
            )
        )
    if include_port:
        plans.append(
            SimpleNamespace(
                target_leg=None,
                target_berth=SimpleNamespace(port=closed),
                start_offset_days=10.0,
                duration_days=5.0,
                multiplier=1.0,
                close_berth=True,
            )
        )
    context = SimpleNamespace(
        ports=[origin, closed, transfer, destination],
        service_routes=[nominal, safe_a, safe_b],
        disruption_plans=plans,
    )
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )
    return (
        context,
        ANCHOR + dt.timedelta(days=14.5),
        shipment,
        {
            "nominal": nominal,
            "closed": closed,
            "origin": origin,
            "destination": destination,
        },
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
            tuple((key, _freeze(item, seen)) for key, item in sorted(vars(value).items())),
        )
    return (type(value).__name__, identity, repr(value))


def test_mixed_leg_and_port_one_transfer_hold_is_candidate_behavior() -> None:
    context, now, shipment, _ = _mixed_fixture()

    # RED: untouched v3 delegates; v12 must return the exact boolean False.
    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_mixed_candidate_path_is_read_only() -> None:
    context, now, shipment, _ = _mixed_fixture()
    before = _freeze((context, shipment))

    UserStrategy.assign_associated_bookings(context, now, shipment)

    assert _freeze((context, shipment)) == before


def test_pure_leg_one_transfer_still_delegates() -> None:
    context, now, shipment, _ = _mixed_fixture(include_port=False)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_port_only_one_transfer_still_delegates() -> None:
    context, now, shipment, _ = _mixed_fixture(include_leg=False)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_equal_mixed_hold_and_detour_delegates() -> None:
    context, now, shipment, _ = _mixed_fixture(safe_distance=80.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_existing_multi_transfer_hold_remains_active() -> None:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer_a, origin], [100.0, 100.0])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [100.0, 100.0])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [100.0, 100.0])
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[
            SimpleNamespace(
                target_leg=nominal.segments[0].associated_leg,
                target_berth=None,
                start_offset_days=10.0,
                duration_days=5.0,
                multiplier=2.0,
                close_berth=False,
            )
        ],
    )
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )

    assert (
        UserStrategy.assign_associated_bookings(context, ANCHOR + dt.timedelta(days=14.5), shipment)
        is False
    )
