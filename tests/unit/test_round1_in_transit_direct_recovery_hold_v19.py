"""RED/GREEN contract for the Round 1 v19 in-transit policy."""

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
    *,
    speed: float = 10.0,
    source: Any = None,
) -> SimpleNamespace:
    route = SimpleNamespace(
        name=name,
        source_service_route=source,
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
            current_vessels=[],
        )
        for index, distance in enumerate(distances, start=1)
    ]
    route.deployed_vessels = [
        SimpleNamespace(
            vessel_class=SimpleNamespace(sailing_speed=speed),
            assigned_service_route=route,
            current_segment=None,
            carried_shipments=[],
        )
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
    safe_distances: tuple[float, float, float] = (1000.0, 1000.0, 1000.0),
) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace, SimpleNamespace, dict[str, Any]]:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer_a, origin], [safe_distances[0], safe_distances[0]])
    safe_b = _route(
        "safe-b", [transfer_a, transfer_b, transfer_a], [safe_distances[1], safe_distances[1]]
    )
    safe_c = _route(
        "safe-c", [transfer_b, destination, transfer_b], [safe_distances[2], safe_distances[2]]
    )
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[_leg_plan(nominal.segments[0].associated_leg)],
    )
    now = ANCHOR + dt.timedelta(days=14.5)
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=1,
        carrying_vessel=None,
    )
    booking = SimpleNamespace(
        sequence_index=1,
        service_route=nominal,
        departure_segment_index=1,
        arrival_segment_index=1,
        shipment=shipment,
    )
    shipment.associated_bookings.append(booking)
    vessel = nominal.deployed_vessels[0]
    vessel.current_segment = nominal.segments[1]
    vessel.current_segment.current_vessels.append(vessel)
    vessel.carried_shipments.append(shipment)
    shipment.carrying_vessel = vessel
    return (
        context,
        now,
        shipment,
        vessel,
        {
            "origin": origin,
            "destination": destination,
            "nominal": nominal,
            "safe_a": safe_a,
            "safe_b": safe_b,
            "safe_c": safe_c,
            "shipment": shipment,
            "vessel": vessel,
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
        return ("list", tuple(_freeze(item, seen) for item in value))
    if isinstance(value, tuple):
        return ("tuple", tuple(_freeze(item, seen) for item in value))
    if hasattr(value, "__dict__"):
        return (
            type(value).__name__,
            tuple((key, _freeze(item, seen)) for key, item in sorted(vars(value).items())),
        )
    return (type(value).__name__, repr(value))


def _decision(context: Any, now: Any, vessel: Any) -> Any:
    return UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)


def test_qualifying_direct_current_edge_holds_without_mutation() -> None:
    context, now, shipment, vessel, _ = _fixture()
    before = _freeze((context, shipment, vessel))

    assert _decision(context, now, vessel) is False
    assert _freeze((context, shipment, vessel)) == before


def test_inactive_disruption_delegates_without_mutation() -> None:
    context, _, shipment, vessel, _ = _fixture()
    before = _freeze((context, shipment, vessel))

    assert _decision(context, ANCHOR + dt.timedelta(days=1), vessel) is None
    assert _freeze((context, shipment, vessel)) == before


def test_future_only_disruption_does_not_hold_current_cargo() -> None:
    context, now, shipment, vessel, items = _fixture()
    context.disruption_plans = [_leg_plan(items["safe_a"].segments[0].associated_leg)]

    assert _decision(context, now, vessel) is None
    assert shipment.associated_bookings[0].service_route is items["nominal"]


def test_active_multi_booking_current_edge_delegates() -> None:
    context, now, shipment, vessel, items = _fixture()
    later = SimpleNamespace(
        sequence_index=2,
        service_route=items["safe_c"],
        departure_segment_index=1,
        arrival_segment_index=1,
        shipment=shipment,
    )
    shipment.associated_bookings.append(later)

    assert _decision(context, now, vessel) is None


def test_malformed_carried_state_delegates() -> None:
    context, now, shipment, vessel, _ = _fixture()
    shipment.current_booking_index = 99

    assert _decision(context, now, vessel) is None


def test_nonqualifying_active_direct_edge_delegates() -> None:
    context, now, _, vessel, _ = _fixture(safe_distances=(40.0, 40.0, 80.0))

    assert _decision(context, now, vessel) is None


def test_missing_safe_graph_delegates() -> None:
    context, now, _, vessel, _ = _fixture()
    context.service_routes = [context.service_routes[0]]

    assert _decision(context, now, vessel) is None


def test_malformed_carried_bookings_delegate() -> None:
    context, now, shipment, vessel, _ = _fixture()
    shipment.associated_bookings = None

    assert _decision(context, now, vessel) is None


def test_current_segment_not_on_booking_route_delegates() -> None:
    context, now, _, vessel, _ = _fixture()
    vessel.current_segment = SimpleNamespace(
        associated_leg=SimpleNamespace(arrival_port=context.ports[0])
    )

    assert _decision(context, now, vessel) is None


def test_shorter_nominal_edge_not_matching_booking_delegates() -> None:
    context, now, _, vessel, items = _fixture()
    context.service_routes.append(
        _route("other-direct", [items["origin"], items["destination"], items["origin"]], [1.0, 1.0])
    )

    assert _decision(context, now, vessel) is None


def test_one_transfer_safe_path_delegates() -> None:
    context, now, _, vessel, items = _fixture()
    context.service_routes = [items["nominal"], items["safe_a"], items["safe_b"]]

    assert _decision(context, now, vessel) is None


def test_safe_path_without_deployed_vessel_delegates() -> None:
    context, now, _, vessel, items = _fixture()
    items["safe_a"].deployed_vessels = []

    assert _decision(context, now, vessel) is None


def test_nonfinite_service_estimate_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    context, now, _, vessel, _ = _fixture()
    monkeypatch.setitem(
        UserStrategy.adjust_bookings_before_cargo_handling.__globals__,
        "_path_service_hours",
        lambda path: 1.0 if len(path) == 1 else math.nan,
    )

    assert _decision(context, now, vessel) is None


def test_public_hook_catches_data_errors() -> None:
    class BrokenVessel:
        @property
        def carried_shipments(self) -> list[Any]:
            raise AttributeError("broken")

    assert (
        UserStrategy.adjust_bookings_before_cargo_handling(
            SimpleNamespace(), ANCHOR, BrokenVessel()
        )
        is None
    )
