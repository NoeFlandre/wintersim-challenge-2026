"""RED contract for the v18 TEU-size gate."""

from __future__ import annotations

import datetime as dt
import math
from types import SimpleNamespace
from typing import Any

import pytest
from response_strategies.user_strategy import UserStrategy


ANCHOR = dt.datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(
    name: str,
    ports: list[SimpleNamespace],
    distances: list[float],
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
    route.deployed_vessels = [SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=10.0))]
    return route


def _context(teu_size: Any) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace]:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer_a, origin], [1000.0, 1000.0])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [1000.0, 1000.0])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [1000.0, 1000.0])
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
        teu_size=teu_size,
        associated_bookings=[],
        current_booking_index=None,
    )
    return context, ANCHOR + dt.timedelta(days=14.5), shipment


def _state(context: Any, shipment: Any) -> tuple[Any, ...]:
    return (
        tuple(id(port) for port in context.ports),
        tuple(id(route) for route in context.service_routes),
        tuple(tuple(id(segment) for segment in route.segments) for route in context.service_routes),
        tuple(shipment.associated_bookings),
        shipment.current_booking_index,
        getattr(shipment, "teu_size", None),
    )


def test_multi_teu_qualifying_hold_retains_v3_behavior() -> None:
    context, now, shipment = _context(2)
    before = _state(context, shipment)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False
    assert _state(context, shipment) == before


def test_exact_one_teu_qualifying_shipment_delegates() -> None:
    context, now, shipment = _context(1)
    before = _state(context, shipment)

    # RED: untouched v3 holds this shipment; v18 must delegate it.
    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
    assert _state(context, shipment) == before


@pytest.mark.parametrize("teu_size", [None, 0, -1, float("nan"), True, 1.0])
def test_invalid_or_boundary_teu_size_delegates(teu_size: Any) -> None:
    context, now, shipment = _context(teu_size)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_multi_teu_guard_does_not_accept_infinity() -> None:
    context, now, shipment = _context(math.inf)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
