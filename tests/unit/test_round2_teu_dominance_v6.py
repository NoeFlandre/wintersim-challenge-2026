"""RED contract for the Round 2 TEU-dominance v6 policy."""

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


def _shipment(origin: Any, destination: Any, annual_teus: float) -> SimpleNamespace:
    demand = SimpleNamespace(
        origin_port=origin,
        destination_port=destination,
        annual_teus=annual_teus,
    )
    return SimpleNamespace(
        demand=demand,
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


def _fixture(annual_teus: float) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace]:
    origin = _port("Origin")
    closed = _port("Closed")
    transfer = _port("Transfer")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, closed, destination, origin], [100.0, 100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer, origin], [300.0, 300.0])
    safe_b = _route("safe-b", [transfer, destination, transfer], [300.0, 300.0])
    shipment = _shipment(origin, destination, annual_teus)
    other_values = (100.0, 500.0, 1000.0, 1500.0, 2000.0, 4000.0)
    demands = [
        SimpleNamespace(origin_port=origin, destination_port=destination, annual_teus=value)
        for value in other_values
    ]
    demands[0] = shipment.demand
    context = SimpleNamespace(
        ports=[origin, closed, transfer, destination],
        demands=demands,
        service_routes=[nominal, safe_a, safe_b],
        disruption_plans=[_port_plan(closed)],
    )
    return context, ANCHOR + dt.timedelta(days=14.5), shipment


def test_high_volume_one_transfer_closure_still_holds() -> None:
    context, now, shipment = _fixture(4000.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_below_third_quartile_one_transfer_closure_delegates() -> None:
    context, now, shipment = _fixture(100.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_third_quartile_equality_is_inclusive() -> None:
    context, now, shipment = _fixture(1500.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_demand_not_in_context_delegates() -> None:
    context, now, shipment = _fixture(4000.0)
    context.demands = list(context.demands[1:])

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_malformed_demand_volume_delegates() -> None:
    context, now, shipment = _fixture(4000.0)
    context.demands[2].annual_teus = float("nan")

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_missing_demand_population_delegates() -> None:
    context, now, shipment = _fixture(4000.0)
    del context.demands

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_multi_transfer_control_is_unchanged() -> None:
    origin = _port("Origin")
    closed = _port("Closed")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, closed, destination, origin], [100.0, 100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer_a, origin], [300.0, 300.0])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [300.0, 300.0])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [300.0, 300.0])
    demand = SimpleNamespace(
        origin_port=origin,
        destination_port=destination,
        annual_teus=100.0,
    )
    shipment = SimpleNamespace(
        demand=demand,
        associated_bookings=[],
        current_booking_index=None,
    )
    context = SimpleNamespace(
        ports=[origin, closed, transfer_a, transfer_b, destination],
        demands=[demand],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[_port_plan(closed)],
    )
    now = ANCHOR + dt.timedelta(days=14.5)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False
