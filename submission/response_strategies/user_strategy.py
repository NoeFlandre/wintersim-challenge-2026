"""Participant strategy for no-safe-path congestion-tail direct bookings.

The candidate changes only initial booking assignment.  It permits an exact
original congested leg only when the organizer's disruption-filtered booking
graph has no complete path and no berth closure is active; all other cases
delegate to the organizer fallback.
"""

from __future__ import annotations

import datetime as dt
import importlib
import math
import numbers
from typing import Any, NamedTuple

_NARROW_EXCEPTIONS = (
    AttributeError,
    IndexError,
    ImportError,
    KeyError,
    TypeError,
    ValueError,
    ZeroDivisionError,
    FloatingPointError,
    OverflowError,
    RuntimeError,
)


class _Edge(NamedTuple):
    service_route: Any
    departure_port: Any
    arrival_port: Any
    departure_segment_index: int
    arrival_segment_index: int
    segments: tuple[Any, ...]
    total_distance: float


class _State(NamedTuple):
    congested_legs: tuple[Any, ...]
    congested_ids: frozenset[int]
    closed_names: tuple[str, ...]
    disruption_key: tuple[tuple[str, ...], tuple[tuple[str, str], ...]]


def _finite_number(value: Any, *, positive: bool = False) -> float | None:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    result = float(value)
    if not math.isfinite(result) or (result <= 0.0 if positive else result < 0.0):
        return None
    return result


def _port_name(port: Any) -> str | None:
    name = getattr(port, "name", None)
    return name.casefold() if isinstance(name, str) else None


def _leg_key(leg: Any) -> tuple[str, str] | None:
    departure = _port_name(getattr(leg, "departure_port", None))
    arrival = _port_name(getattr(leg, "arrival_port", None))
    if departure is None or arrival is None:
        return None
    return departure, arrival


def _active_state(context: Any, now: dt.datetime) -> _State | None:
    plans = getattr(context, "disruption_plans", None)
    if plans is None:
        return None
    try:
        plan_values = tuple(plans)
    except (TypeError, ValueError):
        return None

    congested: list[Any] = []
    congested_ids: set[int] = set()
    congested_keys: set[tuple[str, str]] = set()
    closed_names: set[str] = set()

    for plan in plan_values:
        start_offset = _finite_number(getattr(plan, "start_offset_days", None))
        duration = _finite_number(getattr(plan, "duration_days", None), positive=True)
        multiplier = _finite_number(getattr(plan, "multiplier", 1.0), positive=True)
        if start_offset is None or duration is None or multiplier is None:
            return None
        try:
            start = dt.datetime.min + dt.timedelta(days=start_offset)
            end = start + dt.timedelta(days=duration)
        except (OverflowError, TypeError, ValueError):
            return None
        if not start <= now < end:
            continue

        if bool(getattr(plan, "close_berth", False)):
            berth = getattr(plan, "target_berth", None)
            port = getattr(berth, "port", None)
            name = _port_name(port)
            if berth is None or port is None or name is None:
                return None
            closed_names.add(name)

        if multiplier <= 1.0:
            continue
        leg = getattr(plan, "target_leg", None)
        departure = getattr(leg, "departure_port", None)
        arrival = getattr(leg, "arrival_port", None)
        leg_key = _leg_key(leg)
        if leg is None or departure is None or arrival is None or leg_key is None:
            return None
        if not any(existing is leg for existing in congested):
            congested.append(leg)
        congested_ids.add(id(leg))
        congested_keys.add(leg_key)

    disruption_key = (tuple(sorted(closed_names)), tuple(sorted(congested_keys)))
    return _State(
        tuple(congested),
        frozenset(congested_ids),
        tuple(sorted(closed_names)),
        disruption_key,
    )


def _ordered_segments(route: Any) -> list[Any] | None:
    segments = getattr(route, "segments", None)
    if segments is None:
        return None
    try:
        ordered = sorted(segments, key=lambda segment: segment.sequence_index)
    except (AttributeError, TypeError, ValueError):
        return None
    return ordered if len(ordered) >= 2 else None


def _edge(route: Any, segments: list[Any], start: int, step: int) -> _Edge | None:
    candidate = [segments[(start + offset) % len(segments)] for offset in range(step)]
    first_leg = candidate[0].associated_leg
    last_leg = candidate[-1].associated_leg
    departure = first_leg.departure_port
    arrival = last_leg.arrival_port
    if departure is None or arrival is None or departure is arrival:
        return None
    total = 0.0
    for segment in candidate:
        distance = _finite_number(segment.associated_leg.sailing_distance, positive=True)
        if distance is None:
            return None
        total += distance
    if not math.isfinite(total) or total <= 0.0:
        return None
    return _Edge(
        route,
        departure,
        arrival,
        start + 1,
        (start + step - 1) % len(segments) + 1,
        tuple(candidate),
        total,
    )


def _safe_edges(route: Any, state: _State) -> list[_Edge]:
    source = getattr(route, "source_service_route", None)
    if source is not None:
        if getattr(route, "disruption_key", None) != state.disruption_key:
            return []
        if not getattr(route, "deployed_vessels", None):
            return []
    segments = _ordered_segments(route)
    if segments is None:
        return []
    edges: list[_Edge] = []
    for start in range(len(segments)):
        for step in range(1, len(segments)):
            candidate = [segments[(start + offset) % len(segments)] for offset in range(step)]
            leg_ids = {id(segment.associated_leg) for segment in candidate}
            if leg_ids & state.congested_ids:
                continue
            arrival_names = [
                _port_name(segment.associated_leg.arrival_port) for segment in candidate
            ]
            if any(name in state.closed_names for name in arrival_names):
                continue
            try:
                built = _edge(route, segments, start, step)
            except (AttributeError, TypeError, ValueError, IndexError, OverflowError):
                built = None
            if built is not None:
                edges.append(built)
    return edges


def _has_safe_path(context: Any, origin: Any, destination: Any, state: _State) -> bool:
    if origin is destination:
        return True
    try:
        ports = list(context.ports)
        routes = list(context.service_routes)
    except (AttributeError, TypeError, ValueError):
        return False
    if (
        not ports
        or not any(port is origin for port in ports)
        or not any(port is destination for port in ports)
    ):
        return False
    edges: list[_Edge] = []
    for route in routes:
        edges.extend(_safe_edges(route, state))
    if not edges:
        return False

    distances = {id(port): math.inf for port in ports}
    distances[id(origin)] = 0.0
    unvisited = list(ports)
    outgoing: dict[int, list[_Edge]] = {}
    for edge in edges:
        outgoing.setdefault(id(edge.departure_port), []).append(edge)

    while unvisited:
        current = min(unvisited, key=lambda port: distances[id(port)])
        if math.isinf(distances[id(current)]):
            return False
        if current is destination:
            return True
        unvisited.remove(current)
        for edge in outgoing.get(id(current), []):
            next_port = edge.arrival_port
            if next_port not in unvisited:
                continue
            candidate = distances[id(current)] + edge.total_distance
            if candidate < distances[id(next_port)]:
                distances[id(next_port)] = candidate
    return False


def _find_direct_segment(context: Any, target_leg: Any) -> tuple[Any, int] | None:
    try:
        routes = tuple(context.service_routes)
    except (AttributeError, TypeError, ValueError):
        return None
    for route in routes:
        if getattr(route, "source_service_route", None) is not None:
            continue
        if not getattr(route, "deployed_vessels", None):
            continue
        segments = _ordered_segments(route)
        if segments is None:
            continue
        for segment in segments:
            if getattr(segment, "associated_leg", None) is not target_leg:
                continue
            sequence = getattr(segment, "sequence_index", None)
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
                return None
            if not isinstance(getattr(route, "associated_bookings", None), list):
                return None
            return route, sequence
    return None


def _install_direct_booking(shipment: Any, route: Any, sequence: int) -> bool | None:
    old_bookings = getattr(shipment, "associated_bookings", None)
    route_bookings = getattr(route, "associated_bookings", None)
    if not isinstance(old_bookings, list) or not isinstance(route_bookings, list):
        return None
    old_index = getattr(shipment, "current_booking_index", None)
    try:
        booking_type = importlib.import_module("maritime_data_context").Booking
        booking = booking_type(
            sequence_index=1,
            shipment=shipment,
            service_route=route,
            departure_segment_index=sequence,
            arrival_segment_index=sequence,
        )
        snapshots: list[tuple[Any, list[Any]]] = [(route, list(route_bookings))]
        for old_booking in old_bookings:
            old_route = old_booking.service_route
            old_route_bookings = old_route.associated_bookings
            if not isinstance(old_route_bookings, list):
                return None
            if not any(existing is old_route for existing, _ in snapshots):
                snapshots.append((old_route, list(old_route_bookings)))
        for old_booking in old_bookings:
            old_route = old_booking.service_route
            while old_booking in old_route.associated_bookings:
                old_route.associated_bookings.remove(old_booking)
        shipment.associated_bookings = [booking]
        shipment.current_booking_index = 1
        route_bookings.append(booking)
    except _NARROW_EXCEPTIONS:
        for touched_route, snapshot in locals().get("snapshots", []):
            touched_route.associated_bookings[:] = snapshot
        shipment.associated_bookings = old_bookings
        shipment.current_booking_index = old_index
        return None
    return True


def _decision(context: Any, now: Any, shipment: Any) -> bool | None:
    if context is None or shipment is None or not isinstance(now, dt.datetime):
        return None
    demand = getattr(shipment, "demand", None)
    origin = getattr(demand, "origin_port", None)
    destination = getattr(demand, "destination_port", None)
    if origin is None or destination is None or origin is destination:
        return None
    state = _active_state(context, now)
    if state is None or state.closed_names or not state.congested_legs:
        return None

    for target_leg in state.congested_legs:
        if origin is not getattr(target_leg, "departure_port", None) or destination is not getattr(
            target_leg, "arrival_port", None
        ):
            continue
        direct = _find_direct_segment(context, target_leg)
        if direct is None:
            return None
        if _has_safe_path(context, origin, destination, state):
            return None
        route, sequence = direct
        return _install_direct_booking(shipment, route, sequence)
    return None


class UserStrategy:
    """Participant adapter with one conservative congestion-tail override."""

    @staticmethod
    def select_vessel_for_berth(
        maritime_data_context: Any,
        port: Any,
        waiting_vessels: Any,
        available_berths: Any,
        current_time: Any,
        waiting_since_by_vessel: Any = None,
    ) -> Any:
        return None

    @staticmethod
    def create_alternative_service_routes(context: Any, now: Any, vessel: Any = None) -> Any:
        return None

    @staticmethod
    def assign_associated_bookings(context: Any, now: Any, shipment: Any) -> Any:
        try:
            return _decision(context, now, shipment)
        except _NARROW_EXCEPTIONS:
            return None

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        return None
