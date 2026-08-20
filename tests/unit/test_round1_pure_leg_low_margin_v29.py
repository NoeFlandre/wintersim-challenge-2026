"""RED contract for the Round 1 pure-leg low-margin v29 refinement."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from response_strategies.user_strategy import UserStrategy

from tests.unit.test_round1_multi_transfer_recovery_hold_v3 import (
    ANCHOR,
    _berth_plan,
    _freeze,
    _leg,
    _leg_plan,
    _port,
    _route,
    _shipment,
)


def test_pure_leg_margin_below_first_safe_headway_delegates_without_mutation() -> None:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer_a, origin], [41.0, 41.0])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [41.0, 41.0])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [82.0, 82.0])
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[_leg_plan(_leg(nominal))],
    )
    shipment = _shipment(origin, destination)
    before = _freeze((context, shipment))

    result = UserStrategy.assign_associated_bookings(
        context, ANCHOR + dt.timedelta(days=14.5), shipment
    )

    assert result is None
    assert _freeze((context, shipment)) == before


def test_pure_leg_margin_equal_first_safe_headway_retains_v3_hold() -> None:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    unit = 160.0 / 3.0
    safe_a = _route("safe-a", [origin, transfer_a, origin], [unit, unit])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [unit, unit])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [2.0 * unit, 2.0 * unit])
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[_leg_plan(_leg(nominal))],
    )
    shipment = _shipment(origin, destination)

    assert (
        UserStrategy.assign_associated_bookings(context, ANCHOR + dt.timedelta(days=14.5), shipment)
        is False
    )


def test_mixed_low_margin_hold_is_never_suppressed() -> None:
    origin = _port("Origin")
    closed = _port("Closed")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route(
        "nominal",
        [origin, closed, destination, origin],
        [50.0, 50.0, 100.0],
    )
    safe_a = _route("safe-a", [origin, transfer_a, origin], [60.0, 60.0])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [60.0, 60.0])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [120.0, 120.0])
    context = SimpleNamespace(
        ports=[origin, closed, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[
            _leg_plan(_leg(nominal)),
            _berth_plan(closed),
        ],
    )
    shipment = _shipment(origin, destination)

    assert (
        UserStrategy.assign_associated_bookings(context, ANCHOR + dt.timedelta(days=14.5), shipment)
        is False
    )
