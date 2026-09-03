"""RED contract for the Round 2 v10 one-transfer pure-leg extension."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

from response_strategies.user_strategy import UserStrategy

ANCHOR = dt.datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(name: str, ports: list[Any], distances: list[float]) -> SimpleNamespace:
    route = SimpleNamespace(
        name=name,
        source_service_route=None,
        disruption_key=None,
        associated_bookings=[],
        deployed_vessels=[SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=10.0))],
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
    return route


def _leg_plan(leg: Any, *, duration_days: float = 5.0) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=leg,
        target_berth=None,
        start_offset_days=10.0,
        duration_days=duration_days,
        multiplier=2.0,
        close_berth=False,
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


def _fixture(
    *,
    annual_teus: float = 400.0,
    plans: list[Any] | None = None,
    demands: list[Any] | None = None,
    duration_days: float = 5.0,
) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace]:
    origin = _port("Origin")
    transfer = _port("Transfer")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer, origin], [1000.0, 1000.0])
    safe_b = _route("safe-b", [transfer, destination, transfer], [1000.0, 1000.0])
    target = SimpleNamespace(
        origin_port=origin,
        destination_port=destination,
        annual_teus=annual_teus,
    )
    population = (
        demands
        if demands is not None
        else [
            SimpleNamespace(origin_port=origin, destination_port=transfer, annual_teus=100.0),
            SimpleNamespace(origin_port=origin, destination_port=transfer, annual_teus=200.0),
            SimpleNamespace(origin_port=origin, destination_port=transfer, annual_teus=300.0),
            target,
        ]
    )
    context = SimpleNamespace(
        ports=[origin, transfer, destination],
        service_routes=[nominal, safe_a, safe_b],
        disruption_plans=plans
        if plans is not None
        else [_leg_plan(nominal.segments[0].associated_leg, duration_days=duration_days)],
        demands=population,
    )
    shipment = SimpleNamespace(
        demand=target,
        associated_bookings=[],
        current_booking_index=None,
    )
    return context, ANCHOR + dt.timedelta(days=14.5), shipment


def test_upper_quartile_pure_leg_one_transfer_positive_margin_holds() -> None:
    context, now, shipment = _fixture()

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_upper_quartile_equality_is_inclusive_for_one_transfer() -> None:
    context, now, shipment = _fixture(annual_teus=300.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_lower_quartile_pure_leg_one_transfer_delegates() -> None:
    context, now, shipment = _fixture(annual_teus=100.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_non_positive_recovery_margin_delegates() -> None:
    context, now, shipment = _fixture(duration_days=30.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_port_only_one_transfer_remains_unchanged() -> None:
    origin = _port("Origin")
    closed = _port("Closed")
    transfer = _port("Transfer")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, closed, destination, origin], [100.0, 100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer, origin], [1000.0, 1000.0])
    safe_b = _route("safe-b", [transfer, destination, transfer], [1000.0, 1000.0])
    target = SimpleNamespace(origin_port=origin, destination_port=destination, annual_teus=400.0)
    context = SimpleNamespace(
        ports=[origin, closed, transfer, destination],
        service_routes=[nominal, safe_a, safe_b],
        disruption_plans=[_port_plan(closed)],
        demands=[
            SimpleNamespace(origin_port=origin, destination_port=transfer, annual_teus=100.0),
            SimpleNamespace(origin_port=origin, destination_port=transfer, annual_teus=200.0),
            SimpleNamespace(origin_port=origin, destination_port=transfer, annual_teus=300.0),
            target,
        ],
    )
    shipment = SimpleNamespace(demand=target, associated_bookings=[], current_booking_index=None)
    now = ANCHOR + dt.timedelta(days=14.5)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_mixed_one_transfer_remains_delegated() -> None:
    context, now, shipment = _fixture()
    context.disruption_plans.append(_port_plan(context.ports[-1]))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_malformed_demand_population_delegates() -> None:
    context, now, shipment = _fixture(
        demands=[SimpleNamespace(origin_port=_port("x"), annual_teus=float("nan"))]
    )
    shipment.demand = context.demands[0]
    shipment.demand.origin_port = context.ports[0]
    shipment.demand.destination_port = context.ports[-1]

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_new_one_transfer_policy_is_read_only() -> None:
    context, now, shipment = _fixture()
    before = repr((context, shipment))

    UserStrategy.assign_associated_bookings(context, now, shipment)

    assert repr((context, shipment)) == before
