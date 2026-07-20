"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. Returning ``None`` from any method
signals "not handled; use the organizer fallback", leaving the maritime data
context, routes, bookings, and vessel state exactly as the framework built
them.

The initial-booking hook uses a small transfer-aware shortest-path policy when
there is no active disruption. The remaining hooks, and booking assignment
during disruptions, delegate to the organizer fallback.

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

_TRANSFER_WAIT_HOURS = 84.0


class _BookingEdge:
    """Small participant-owned value object; avoids import-loader coupling."""

    __slots__ = (
        "service_route",
        "departure_port",
        "arrival_port",
        "departure_segment_index",
        "arrival_segment_index",
        "sailing_hours",
    )

    def __init__(
        self,
        service_route: Any,
        departure_port: Any,
        arrival_port: Any,
        departure_segment_index: int,
        arrival_segment_index: int,
        sailing_hours: float,
    ) -> None:
        self.service_route = service_route
        self.departure_port = departure_port
        self.arrival_port = arrival_port
        self.departure_segment_index = departure_segment_index
        self.arrival_segment_index = arrival_segment_index
        self.sailing_hours = sailing_hours


def _is_disruption_active(context: Any, now: Any) -> bool:
    """Mirror the organizer's simulation-relative active-window check."""
    if not isinstance(now, dt.datetime):
        return False
    for plan in getattr(context, "disruption_plans", ()):
        start_offset = getattr(plan, "start_offset_days", None)
        duration = getattr(plan, "duration_days", None)
        if start_offset is None or duration is None:
            continue
        start = dt.datetime.min + dt.timedelta(days=start_offset)
        if start <= now < start + dt.timedelta(days=duration):
            return True
    return False


def _route_speed(route: Any) -> float:
    """Return the mean positive sailing speed of vessels deployed on a route."""
    speeds = [
        float(speed)
        for vessel in getattr(route, "deployed_vessels", ())
        if (speed := getattr(getattr(vessel, "vessel_class", None), "sailing_speed", 0))
        and speed > 0
    ]
    return sum(speeds) / len(speeds) if speeds else 0.0


def _build_booking_edges(context: Any) -> list[_BookingEdge]:
    """Build every proper, contiguous route slice available for a booking."""
    edges: list[_BookingEdge] = []
    for route in context.service_routes:
        # Alternative routes belong to the organizer's disruption policy. They
        # may remain in the context after recovery but must not influence the
        # normal-state candidate.
        if getattr(route, "source_service_route", None) is not None:
            continue
        speed = _route_speed(route)
        if speed <= 0:
            continue
        segments = sorted(route.segments, key=lambda segment: segment.sequence_index)
        segment_count = len(segments)
        for start_index in range(segment_count):
            departure_port = segments[start_index].associated_leg.departure_port
            sailing_hours = 0.0
            for step in range(1, segment_count):
                segment_index = (start_index + step - 1) % segment_count
                segment = segments[segment_index]
                leg = segment.associated_leg
                multiplier = float(getattr(leg, "sailing_time_multiplier", 1.0))
                sailing_hours += float(leg.sailing_distance) * multiplier / speed
                arrival_port = leg.arrival_port
                if departure_port is arrival_port:
                    continue
                edges.append(
                    _BookingEdge(
                        service_route=route,
                        departure_port=departure_port,
                        arrival_port=arrival_port,
                        departure_segment_index=segments[start_index].sequence_index,
                        arrival_segment_index=segment.sequence_index,
                        sailing_hours=sailing_hours,
                    )
                )
    return edges


def _find_transfer_aware_path(context: Any, origin_port: Any, destination_port: Any):
    """Find the deterministic minimum sailing-plus-transfer-time booking path."""
    outgoing: dict[Any, list[_BookingEdge]] = {}
    for edge in _build_booking_edges(context):
        outgoing.setdefault(edge.departure_port, []).append(edge)

    costs = dict.fromkeys(context.ports, math.inf)
    previous_edge: dict[Any, _BookingEdge] = {}
    unvisited = list(context.ports)
    costs[origin_port] = 0.0

    while unvisited:
        current = min(unvisited, key=lambda port: costs[port])
        if math.isinf(costs[current]) or current is destination_port:
            break
        unvisited.remove(current)
        for edge in outgoing.get(current, ()):
            if edge.arrival_port not in unvisited:
                continue
            alternative = costs[current] + edge.sailing_hours + _TRANSFER_WAIT_HOURS
            if alternative < costs[edge.arrival_port]:
                costs[edge.arrival_port] = alternative
                previous_edge[edge.arrival_port] = edge

    if destination_port not in previous_edge:
        return None

    path = []
    cursor = destination_port
    while cursor is not origin_port:
        path_edge = previous_edge.get(cursor)
        if path_edge is None:
            return None
        path.append(path_edge)
        cursor = path_edge.departure_port
    path.reverse()
    return path


def _remove_existing_bookings(bookings: Any) -> None:
    for booking in bookings:
        route = getattr(booking, "service_route", None)
        if route is None:
            continue
        while booking in route.associated_bookings:
            route.associated_bookings.remove(booking)


class UserStrategy:
    """Participant adapter with one conservative initial-routing decision."""

    @staticmethod
    def select_vessel_for_berth(
        maritime_data_context: Any,
        port: Any,
        waiting_vessels: Any,
        available_berths: Any,
        current_time: Any,
        waiting_since_by_vessel: Any = None,
    ) -> Any:
        """Choose a waiting vessel to assign to a free berth.

        Returns ``None`` to use the organizer fallback; no input is mutated.
        """
        return None

    @staticmethod
    def create_alternative_service_routes(context: Any, now: Any, vessel: Any = None) -> Any:
        """Build alternative service routes for a vessel.

        Returns ``None`` ("not handled") which must leave ``context`` unchanged.
        """
        return None

    @staticmethod
    def assign_associated_bookings(context: Any, now: Any, shipment: Any) -> Any:
        """Assign a complete booking chain for a shipment.

        In normal operation, minimize nominal sailing time plus an expected
        weekly-service transfer wait. During disruptions or for an unsupported
        context shape, return ``None`` to use the organizer fallback.
        """
        if not all(hasattr(context, name) for name in ("ports", "service_routes")):
            return None
        if not hasattr(shipment, "demand") or _is_disruption_active(context, now):
            return None

        demand = shipment.demand
        origin_port = demand.origin_port
        destination_port = demand.destination_port
        if origin_port is destination_port:
            _remove_existing_bookings(shipment.associated_bookings)
            shipment.associated_bookings = []
            shipment.current_booking_index = None
            return True

        path = _find_transfer_aware_path(context, origin_port, destination_port)
        if not path:
            return None

        # Imported only at the organizer call boundary, so the participant
        # module remains independently importable by local contract tests.
        from maritime_data_context import Booking

        _remove_existing_bookings(shipment.associated_bookings)
        shipment.associated_bookings = []
        for sequence_index, edge in enumerate(path, start=1):
            booking = Booking(
                sequence_index=sequence_index,
                shipment=shipment,
                service_route=edge.service_route,
                departure_segment_index=edge.departure_segment_index,
                arrival_segment_index=edge.arrival_segment_index,
            )
            shipment.associated_bookings.append(booking)
            edge.service_route.associated_bookings.append(booking)
        shipment.current_booking_index = 1
        return True

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Adjust booking chains before a vessel handles cargo.

        Returns ``None`` to use the organizer fallback.
        """
        return None
