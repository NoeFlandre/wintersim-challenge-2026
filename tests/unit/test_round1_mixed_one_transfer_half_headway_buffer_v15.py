"""RED contract for the Round 1 v15 half-headway mixed-transfer guard."""

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
    ]
    return route


def _fixture(
    *,
    safe_distance: float = 100.0,
    invalid_first_safe_profile: bool = False,
) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace]:
    origin = _port("Origin")
    closed = _port("Closed")
    transfer = _port("Transfer")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, closed, destination, origin], [50.0, 50.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer, origin], [safe_distance, safe_distance])
    safe_b = _route("safe-b", [transfer, destination, transfer], [safe_distance, safe_distance])
    if invalid_first_safe_profile:
        safe_a.deployed_vessels = []
    context = SimpleNamespace(
        ports=[origin, closed, transfer, destination],
        service_routes=[nominal, safe_a, safe_b],
        disruption_plans=[
            SimpleNamespace(
                target_leg=nominal.segments[0].associated_leg,
                target_berth=None,
                start_offset_days=10.0,
                duration_days=6.0,
                multiplier=2.0,
                close_berth=False,
            ),
            SimpleNamespace(
                target_leg=None,
                target_berth=SimpleNamespace(port=closed),
                start_offset_days=10.0,
                duration_days=6.0,
                multiplier=1.0,
                close_berth=True,
            ),
        ],
    )
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )
    # The organizer's exclusive end is start + duration (day 16 here); use a
    # timestamp just before it so the recovery wait remains small and active.
    return context, ANCHOR + dt.timedelta(days=15.5), shipment


def _decision(context: Any, now: dt.datetime, shipment: Any) -> Any:
    return UserStrategy.assign_associated_bookings(context, now, shipment)


def test_mixed_one_transfer_above_half_headway_is_held() -> None:
    context, now, shipment = _fixture(safe_distance=120.0)

    # RED: v3 delegates this one-transfer mixed case; v15 must return False.
    assert _decision(context, now, shipment) is False


def test_mixed_one_transfer_below_half_headway_delegates() -> None:
    context, now, shipment = _fixture(safe_distance=100.0)

    assert _decision(context, now, shipment) is None


def test_mixed_one_transfer_at_half_headway_delegates() -> None:
    context, now, shipment = _fixture(safe_distance=106.6666666666666)

    assert _decision(context, now, shipment) is None


def test_invalid_first_safe_route_profile_delegates() -> None:
    context, now, shipment = _fixture(invalid_first_safe_profile=True)

    assert _decision(context, now, shipment) is None


def test_v3_multi_transfer_hold_remains_unchanged() -> None:
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

    assert _decision(context, ANCHOR + dt.timedelta(days=14.5), shipment) is False
