\"\"\"RED contract for the Round 2 v8 pure-leg TEU guard.\"\"\"

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


def _leg_plan(leg: Any) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=leg,
        target_berth=None,
        start_offset_days=10.0,
        duration_days=5.0,
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
) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace]:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer_a, origin], [1000.0, 1000.0])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [1000.0, 1000.0])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [1000.0, 1000.0])
    target = SimpleNamespace(
        origin_port=origin,
        destination_port=destination,
        annual_teus=annual_teus,
    )
    population = demands if demands is not None else [
        SimpleNamespace(origin_port=origin, destination_port=transfer_a, annual_teus=100.0),
        SimpleNamespace(origin_port=origin, destination_port=transfer_b, annual_teus=200.0),
        SimpleNamespace(origin_port=origin, destination_port=destination, annual_teus=300.0),
        target,
    ]
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=plans if plans is not None else [_leg_plan(nominal.segments[0].associated_leg)],
        demands=population,
    )
    shipment = SimpleNamespace(
        demand=target,
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


def test_upper_quartile_pure_leg_multi_transfer_retains_existing_hold() -> None:
    context, now, shipment = _fixture(annual_teus=400.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_third_quartile_equality_is_inclusive() -> None:
    context, now, shipment = _fixture(annual_teus=300.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_lower_quartile_pure_leg_multi_transfer_delegates() -> None:
    context, now, shipment = _fixture(annual_teus=200.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_demand_identity_is_required_for_the_new_guard() -> None:
    context, now, shipment = _fixture(annual_teus=400.0)
    shipment.demand = SimpleNamespace(
        origin_port=context.ports[0],
        destination_port=context.ports[-1],
        annual_teus=400.0,
    )

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_malformed_demand_population_delegates_only_new_pure_leg_case() -> None:
    context, now, shipment = _fixture(annual_teus=400.0, demands=[SimpleNamespace(annual_teus=float("nan"))])

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_port_closure_multi_transfer_remains_unchanged() -> None:
    context, now, shipment = _fixture(plans=[_port_plan(context_port := _port("Closed"))])
    nominal = context.service_routes[0]
    context.ports.insert(1, context_port)
    nominal.segments[0].associated_leg.arrival_port = context_port
    nominal.segments[1].associated_leg.departure_port = context_port
    shipment.demand.destination_port = context.ports[-1]

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_mixed_constraints_remain_unchanged() -> None:
    context, now, shipment = _fixture()
    context.disruption_plans.append(_port_plan(context.ports[1]))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_new_guard_is_read_only() -> None:
    context, now, shipment = _fixture(annual_teus=200.0)
    before = _freeze((context, shipment))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
    assert _freeze((context, shipment)) == before
