"""RED contract for v17's exact two-route-change gate."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from response_strategies.user_strategy import UserStrategy

ANCHOR = dt.datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(name: str, ports: list[SimpleNamespace], distances: list[float]) -> SimpleNamespace:
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


def _shipment(origin: SimpleNamespace, destination: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )


def _context(*, three_changes: bool) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace]:
    origin = _port("Origin")
    destination = _port("Destination")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    transfer_c = _port("Transfer C")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer_a, origin], [1000.0, 1000.0])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [1000.0, 1000.0])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [1000.0, 1000.0])
    routes = [nominal, safe_a, safe_b, safe_c]
    ports = [origin, destination, transfer_a, transfer_b]
    if three_changes:
        safe_c = _route("safe-c", [transfer_b, transfer_c, transfer_b], [1000.0, 1000.0])
        safe_d = _route("safe-d", [transfer_c, destination, transfer_c], [1000.0, 1000.0])
        # The destination is reached only after the fourth service edge.
        routes = [nominal, safe_a, safe_b, safe_c, safe_d]
        ports.append(transfer_c)
    context = SimpleNamespace(
        ports=ports,
        service_routes=routes,
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
    return context, ANCHOR + dt.timedelta(days=14.5), _shipment(origin, destination)


def test_two_route_changes_remain_a_hold() -> None:
    context, now, shipment = _context(three_changes=False)

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_three_route_changes_delegate_under_v17() -> None:
    context, now, shipment = _context(three_changes=True)

    # RED: untouched v3 holds this more fragmented path; v17 must delegate.
    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
