"""RED contract for the Round 1 v21 multi-TEU mixed extension."""

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
    route.deployed_vessels = [
        SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=speed))
    ]
    return route


def _mixed_fixture(
    *,
    teu_size: Any = 2.0,
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
        teu_size=teu_size,
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )
    return (
        context,
        ANCHOR + dt.timedelta(days=14.5),
        shipment,
        {"origin": origin, "destination": destination, "nominal": nominal},
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


def _decision(context: Any, now: Any, shipment: Any) -> Any:
    return UserStrategy.assign_associated_bookings(context, now, shipment)


def test_multi_teu_mixed_one_transfer_hold_is_candidate_behavior() -> None:
    context, now, shipment, _ = _mixed_fixture(teu_size=2.0)

    # RED: untouched v3 delegates; v21 must return the exact boolean False.
    assert _decision(context, now, shipment) is False


def test_multi_teu_candidate_is_read_only() -> None:
    context, now, shipment, _ = _mixed_fixture(teu_size=2.0)
    before = _freeze((context, shipment))

    assert _decision(context, now, shipment) is False
    assert _freeze((context, shipment)) == before


@pytest.mark.parametrize("teu_size", [1.0, 0.0, -1.0, math.nan, math.inf, True, False, "2"])
def test_non_multi_teu_mixed_one_transfer_delegates(teu_size: Any) -> None:
    context, now, shipment, _ = _mixed_fixture(teu_size=teu_size)

    assert _decision(context, now, shipment) is None


def test_missing_teu_size_delegates() -> None:
    context, now, shipment, _ = _mixed_fixture()
    del shipment.teu_size

    assert _decision(context, now, shipment) is None


def test_pure_constraint_one_transfer_delegates_for_multi_teu() -> None:
    for include_leg, include_port in ((True, False), (False, True)):
        context, now, shipment, _ = _mixed_fixture(
            teu_size=2.0,
            include_leg=include_leg,
            include_port=include_port,
        )

        assert _decision(context, now, shipment) is None


def test_equal_mixed_hold_and_detour_delegates_for_multi_teu() -> None:
    context, now, shipment, _ = _mixed_fixture(teu_size=2.0, safe_distance=80.0)

    assert _decision(context, now, shipment) is None


def test_mixed_extension_respects_disruption_boundaries() -> None:
    context, _, shipment, _ = _mixed_fixture(teu_size=2.0)

    assert _decision(context, ANCHOR + dt.timedelta(days=10), shipment) is False
    assert _decision(context, ANCHOR + dt.timedelta(days=15), shipment) is None


def test_existing_v3_multi_transfer_hold_is_preserved_for_one_teu() -> None:
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
        teu_size=1.0,
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )

    assert _decision(context, ANCHOR + dt.timedelta(days=14.5), shipment) is False

