"""RED contract for the Round 1 multi-leg congestion-hold v6 policy."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

from response_strategies.user_strategy import UserStrategy

ANCHOR = dt.datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(
    ports: list[SimpleNamespace],
    distances: list[float],
    *,
    speed: float = 10.0,
) -> SimpleNamespace:
    route = SimpleNamespace(source_service_route=None, disruption_key=None, associated_bookings=[])
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


def _shipment(origin: Any, destination: Any) -> SimpleNamespace:
    return SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
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


def _berth_plan(port: Any) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=None,
        target_berth=SimpleNamespace(port=port),
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=1.0,
        close_berth=True,
    )


def _candidate_fixture() -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace, dict[str, Any]]:
    origin = _port("Origin")
    direct_midpoint = _port("Direct midpoint")
    destination = _port("Destination")
    transfer = _port("Transfer")
    nominal = _route(
        [origin, direct_midpoint, destination, origin],
        [100.0, 100.0, 100.0],
    )
    safe_a = _route([origin, transfer, origin], [1_000.0, 1_000.0])
    safe_b = _route([transfer, destination, transfer], [1_000.0, 1_000.0])
    context = SimpleNamespace(
        ports=[origin, direct_midpoint, destination, transfer],
        service_routes=[nominal, safe_a, safe_b],
        disruption_plans=[_leg_plan(nominal.segments[0].associated_leg)],
    )
    return (
        context,
        ANCHOR + dt.timedelta(days=14.5),
        _shipment(origin, destination),
        {"origin": origin, "destination": destination, "nominal": nominal},
    )


def _freeze(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str, dt.datetime)):
        return (type(value).__name__, repr(value))
    if isinstance(value, list):
        return ("list", id(value), tuple(_freeze(item) for item in value))
    if isinstance(value, tuple):
        return ("tuple", tuple(_freeze(item) for item in value))
    if isinstance(value, dict):
        return ("dict", id(value), tuple((repr(k), _freeze(v)) for k, v in value.items()))
    if hasattr(value, "__dict__"):
        return (
            type(value).__name__,
            id(value),
            tuple((key, _freeze(item)) for key, item in sorted(vars(value).items())),
        )
    return (type(value).__name__, id(value), repr(value))


def test_multi_leg_pure_congestion_one_transfer_returns_false_without_mutation() -> None:
    context, now, shipment, _ = _candidate_fixture()
    before = _freeze((context, shipment))

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is False
    assert _freeze((context, shipment)) == before


def test_single_leg_pure_congestion_one_transfer_still_delegates() -> None:
    origin = _port("Origin")
    destination = _port("Destination")
    transfer = _port("Transfer")
    nominal = _route([origin, destination, origin], [100.0, 100.0])
    safe_a = _route([origin, transfer, origin], [1_000.0, 1_000.0])
    safe_b = _route([transfer, destination, transfer], [1_000.0, 1_000.0])
    context = SimpleNamespace(
        ports=[origin, destination, transfer],
        service_routes=[nominal, safe_a, safe_b],
        disruption_plans=[_leg_plan(nominal.segments[0].associated_leg)],
    )

    assert (
        UserStrategy.assign_associated_bookings(
            context,
            ANCHOR + dt.timedelta(days=14.5),
            _shipment(origin, destination),
        )
        is None
    )


def test_multi_leg_closed_port_one_transfer_delegates() -> None:
    context, now, shipment, items = _candidate_fixture()
    context.disruption_plans = [
        _berth_plan(items["nominal"].segments[0].associated_leg.arrival_port)
    ]

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_multi_leg_mixed_constraints_one_transfer_delegates() -> None:
    context, now, shipment, items = _candidate_fixture()
    context.disruption_plans = [
        _leg_plan(items["nominal"].segments[0].associated_leg),
        _berth_plan(items["nominal"].segments[1].associated_leg.arrival_port),
    ]

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_multi_leg_pure_congestion_candidate_is_inactive_outside_window() -> None:
    context, _, shipment, _ = _candidate_fixture()

    assert (
        UserStrategy.assign_associated_bookings(
            context,
            ANCHOR + dt.timedelta(days=1),
            shipment,
        )
        is None
    )
