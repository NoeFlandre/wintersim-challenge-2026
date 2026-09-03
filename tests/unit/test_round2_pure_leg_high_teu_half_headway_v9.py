"""Behavioral contract for the Round 2 v9 pure-leg timing guard."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

import response_strategies.user_strategy as strategy_module
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


def _fixture(
    *,
    safe_distance: float,
    annual_teus: float = 400.0,
) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace]:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer_a, origin], [safe_distance, safe_distance])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [safe_distance, safe_distance])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [safe_distance, safe_distance])
    target = SimpleNamespace(
        origin_port=origin,
        destination_port=destination,
        annual_teus=annual_teus,
    )
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[_leg_plan(nominal.segments[0].associated_leg)],
        demands=[
            SimpleNamespace(origin_port=origin, destination_port=transfer_a, annual_teus=100.0),
            SimpleNamespace(origin_port=origin, destination_port=transfer_b, annual_teus=300.0),
            SimpleNamespace(origin_port=origin, destination_port=destination, annual_teus=400.0),
            target,
        ],
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


def _margin(context: Any, now: dt.datetime, shipment: Any) -> float:
    state = strategy_module._active_state(context, now)
    assert state is not None
    graphs = strategy_module._graphs(context, state)
    assert graphs is not None
    demand = shipment.demand
    nominal = strategy_module._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[0]
    )
    safe = strategy_module._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[1]
    )
    assert nominal is not None and safe is not None
    recovery = strategy_module._edge_constraint_recovery(nominal[0], state)
    nominal_hours = strategy_module._path_service_hours(nominal)
    detour_hours = strategy_module._path_service_hours(safe)
    assert recovery is not None and nominal_hours is not None and detour_hours is not None
    hold_hours = max(0.0, (recovery - now).total_seconds() / 3600.0) + nominal_hours
    return detour_hours - hold_hours


def test_high_teu_margin_at_or_below_half_headway_delegates() -> None:
    context, now, shipment = _fixture(safe_distance=62.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_high_teu_margin_above_half_headway_retains_hold() -> None:
    context, now, shipment = _fixture(safe_distance=100.0)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_half_headway_boundary_is_strict(monkeypatch: Any) -> None:
    context, now, shipment = _fixture(safe_distance=100.0)
    margin = _margin(context, now, shipment)
    assert margin > 0.0
    monkeypatch.setattr(strategy_module, "_max_path_headway", lambda _path: 2.0 * margin)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_new_timing_guard_is_read_only() -> None:
    context, now, shipment = _fixture(safe_distance=62.0)
    before = _freeze((context, shipment))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
    assert _freeze((context, shipment)) == before
