"""Participant-owned Round 1 disruption-weighted booking strategy.

Only this module and the participant README are submission files.  The
initial-booking hook compares predicted sailing duration during active
disruptions; the other hooks delegate to the organizer fallback.

The module deliberately uses no organizer imports at import time.  The
organizer ``Booking`` class is looked up only after a complete candidate path
has been found, so the package remains independently importable for tests and
the fallback paths remain fail-closed.
"""

from __future__ import annotations

import datetime as dt
import importlib
import math
from collections.abc import Iterable
from typing import Any, NamedTuple


class _BookingEdge(NamedTuple):
    service_route: Any
    departure_port: Any
    arrival_port: Any
    departure_segment_index: int
    arrival_segment_index: int
    segments: tuple[Any, ...]
    sailing_speed: float


class _CongestedPlan(NamedTuple):
    target_leg: Any
    recovery_time: dt.datetime
    multiplier: float
    leg_key: tuple[str, str]


class _ActiveState(NamedTuple):
    closed_ports: tuple[Any, ...]
    disruption_key: tuple[tuple[str, ...], tuple[tuple[str, str], ...]]
    congested_plans: tuple[_CongestedPlan, ...]


class UserStrategy:
    """Participant adapter with one active-disruption booking decision."""

    @staticmethod
    def select_vessel_for_berth(
        maritime_data_context: Any,
        port: Any,
        waiting_vessels: Any,
        available_berths: Any,
        current_time: Any,
        waiting_since_by_vessel: Any = None,
    ) -> Any:
        """Return ``None`` so the organizer fallback selects the vessel."""
        return None

    @staticmethod
    def create_alternative_service_routes(context: Any, now: Any, vessel: Any = None) -> Any:
        """Return ``None`` so the organizer fallback owns route creation."""
        return None

    @staticmethod
    def assign_associated_bookings(context: Any, now: Any, shipment: Any) -> Any:
        """Assign the fastest predicted valid initial booking during disruption.

        Inactive, malformed, and no-path cases return ``None`` without
        mutation.  A successful result is ``True`` and installs a complete
        booking chain only after the path has been fully validated.
        """
        if context is None or shipment is None or not isinstance(now, dt.datetime):
            return None

        demand = getattr(shipment, "demand", None)
        origin = getattr(demand, "origin_port", None)
        destination = getattr(demand, "destination_port", None)
        if origin is None or destination is None or origin is destination:
            return None

        active_state = _collect_active_state(context, now)
        if (
            active_state is None
            or not active_state.congested_plans
            and not active_state.closed_ports
        ):
            return None

        edges = _build_booking_edges(context, active_state)
        if not edges:
            return None

        path = _find_fastest_path(context, origin, destination, now, edges, active_state)
        if not path:
            return None

        return _install_path(shipment, path)

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Return ``None`` so the organizer fallback owns in-transit replanning."""
        return None


def _collect_active_state(context: Any, now: dt.datetime) -> _ActiveState | None:
    """Collect valid active closed-port and congested-leg constraints."""
    plans = getattr(context, "disruption_plans", None)
    if plans is None:
        return None
    try:
        plan_values = tuple(plans)
    except (TypeError, ValueError):
        return None

    closed_ports: list[Any] = []
    closed_names: set[str] = set()
    congested: list[_CongestedPlan] = []
    congested_keys: set[tuple[str, str]] = set()

    for plan in plan_values:
        window = _plan_window(plan)
        if window is None:
            continue
        start, end, multiplier = window
        if not start <= now < end:
            continue

        if bool(getattr(plan, "close_berth", False)):
            berth = getattr(plan, "target_berth", None)
            port = getattr(berth, "port", None)
            name = _port_name(port)
            if port is None or name is None:
                return None
            if not any(existing is port for existing in closed_ports):
                closed_ports.append(port)
            closed_names.add(name)
            continue

        if multiplier <= 1.0:
            continue
        leg = getattr(plan, "target_leg", None)
        leg_key = _leg_key(leg)
        if leg is None or leg_key is None:
            return None
        congested.append(_CongestedPlan(leg, end, multiplier, leg_key))
        congested_keys.add(leg_key)

    disruption_key = (
        tuple(sorted(closed_names)),
        tuple(sorted(congested_keys)),
    )
    return _ActiveState(tuple(closed_ports), disruption_key, tuple(congested))


def _plan_window(plan: Any) -> tuple[dt.datetime, dt.datetime, float] | None:
    """Parse a finite positive disruption window without raising."""
    start_raw = getattr(plan, "start_offset_days", None)
    duration_raw = getattr(plan, "duration_days", None)
    multiplier_raw = getattr(plan, "multiplier", 1.0)
    if start_raw is None or duration_raw is None or multiplier_raw is None:
        return None
    try:
        start_offset = float(start_raw)
        duration = float(duration_raw)
        multiplier = float(multiplier_raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(value) for value in (start_offset, duration, multiplier)):
        return None
    if duration <= 0.0 or multiplier <= 0.0:
        return None
    try:
        start = dt.datetime.min + dt.timedelta(days=start_offset)
        end = start + dt.timedelta(days=duration)
    except (OverflowError, ValueError):
        return None
    if end <= start:
        return None
    return start, end, multiplier


def _port_name(port: Any) -> str | None:
    name = getattr(port, "name", None)
    return name.casefold() if isinstance(name, str) else None


def _leg_key(leg: Any) -> tuple[str, str] | None:
    departure = _port_name(getattr(leg, "departure_port", None))
    arrival = _port_name(getattr(leg, "arrival_port", None))
    if departure is None or arrival is None:
        return None
    return departure, arrival


def _route_speed(route: Any) -> float | None:
    """Choose the fastest positive deployed-vessel speed for a route."""
    vessels: Iterable[Any] = getattr(route, "deployed_vessels", ())
    fastest: float | None = None
    try:
        values = tuple(vessels)
    except (TypeError, ValueError):
        return None
    for vessel in values:
        vessel_class = getattr(vessel, "vessel_class", None)
        speed_raw = getattr(vessel_class, "sailing_speed", None)
        if speed_raw is None:
            continue
        try:
            speed = float(speed_raw)
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(speed) or speed <= 0.0:
            continue
        if fastest is None or speed > fastest:
            fastest = speed
    return fastest


def _route_is_available(route: Any, active_state: _ActiveState) -> bool:
    source_route = getattr(route, "source_service_route", None)
    if source_route is None:
        return True
    return getattr(route, "disruption_key", None) == active_state.disruption_key and bool(
        getattr(route, "deployed_vessels", ())
    )


def _build_booking_edges(
    context: Any, active_state: _ActiveState
) -> tuple[_BookingEdge, ...] | None:
    """Enumerate valid contiguous route slices in deterministic context order."""
    routes = getattr(context, "service_routes", None)
    if routes is None:
        return None
    try:
        route_values = tuple(routes)
    except (TypeError, ValueError):
        return None

    edges: list[_BookingEdge] = []
    for route in route_values:
        if not _route_is_available(route, active_state):
            continue
        speed = _route_speed(route)
        if speed is None:
            continue
        try:
            segments = tuple(
                sorted(
                    getattr(route, "segments", ()),
                    key=lambda segment: segment.sequence_index,
                )
            )
        except (AttributeError, TypeError, ValueError):
            continue
        if len(segments) < 2:
            continue

        for start_index, start_segment in enumerate(segments):
            departure_port = getattr(
                getattr(start_segment, "associated_leg", None), "departure_port", None
            )
            if departure_port is None or _is_closed(departure_port, active_state.closed_ports):
                continue
            for step in range(1, len(segments)):
                selected = tuple(
                    segments[(start_index + offset) % len(segments)] for offset in range(step)
                )
                legs = tuple(getattr(segment, "associated_leg", None) for segment in selected)
                if any(leg is None for leg in legs):
                    continue
                arrival_port = getattr(legs[-1], "arrival_port", None)
                if arrival_port is None or arrival_port is departure_port:
                    continue
                if any(
                    _is_closed(getattr(leg, "departure_port", None), active_state.closed_ports)
                    or _is_closed(getattr(leg, "arrival_port", None), active_state.closed_ports)
                    for leg in legs
                ):
                    continue
                try:
                    departure_index = int(start_segment.sequence_index)
                    arrival_index = int(selected[-1].sequence_index)
                except (AttributeError, TypeError, ValueError, OverflowError):
                    continue
                if departure_index <= 0 or arrival_index <= 0:
                    continue
                edges.append(
                    _BookingEdge(
                        route,
                        departure_port,
                        arrival_port,
                        departure_index,
                        arrival_index,
                        selected,
                        speed,
                    )
                )
    return tuple(edges)


def _is_closed(port: Any, closed_ports: tuple[Any, ...]) -> bool:
    return port is not None and any(port is closed for closed in closed_ports)


def _find_fastest_path(
    context: Any,
    origin: Any,
    destination: Any,
    now: dt.datetime,
    edges: tuple[_BookingEdge, ...],
    active_state: _ActiveState,
) -> tuple[_BookingEdge, ...] | None:
    """Run deterministic Dijkstra with time-dependent sailing costs."""
    try:
        ports = tuple(context.ports)
        distances = dict.fromkeys(ports, math.inf)
    except (AttributeError, TypeError, ValueError):
        return None
    if origin not in distances or destination not in distances:
        return None

    outgoing: dict[Any, list[_BookingEdge]] = {}
    try:
        for edge in edges:
            outgoing.setdefault(edge.departure_port, []).append(edge)
    except (TypeError, ValueError):
        return None

    distances[origin] = 0.0
    previous: dict[Any, _BookingEdge] = {}
    unvisited = list(ports)
    while unvisited:
        current = min(unvisited, key=lambda port: distances[port])
        if math.isinf(distances[current]) or current is destination:
            break
        unvisited.remove(current)
        try:
            current_time = now + dt.timedelta(hours=distances[current])
        except (OverflowError, ValueError):
            return None
        for edge in outgoing.get(current, ()):
            if edge.arrival_port not in unvisited:
                continue
            duration = _edge_duration_hours(edge, current_time, active_state.congested_plans)
            if duration is None:
                continue
            candidate = distances[current] + duration
            if not math.isfinite(candidate):
                continue
            if candidate < distances[edge.arrival_port]:
                distances[edge.arrival_port] = candidate
                previous[edge.arrival_port] = edge

    if destination not in previous:
        return None
    path: list[_BookingEdge] = []
    cursor = destination
    for _ in range(len(ports)):
        if cursor is origin:
            path.reverse()
            return tuple(path)
        previous_edge = previous.get(cursor)
        if previous_edge is None:
            return None
        path.append(previous_edge)
        cursor = previous_edge.departure_port
    return None


def _edge_duration_hours(
    edge: _BookingEdge,
    start_time: dt.datetime,
    congested_plans: tuple[_CongestedPlan, ...],
) -> float | None:
    elapsed = 0.0
    for segment in edge.segments:
        leg = getattr(segment, "associated_leg", None)
        leg_duration = _leg_duration_hours(leg, start_time, edge.sailing_speed, congested_plans)
        if leg_duration is None:
            return None
        elapsed += leg_duration
        if not math.isfinite(elapsed):
            return None
        try:
            start_time = start_time + dt.timedelta(hours=leg_duration)
        except (OverflowError, ValueError):
            return None
    return elapsed


def _leg_duration_hours(
    leg: Any,
    start_time: dt.datetime,
    sailing_speed: float,
    congested_plans: tuple[_CongestedPlan, ...],
) -> float | None:
    distance_raw = getattr(leg, "sailing_distance", None)
    if distance_raw is None:
        return None
    try:
        distance = float(distance_raw)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(distance) or distance <= 0.0 or sailing_speed <= 0.0:
        return None

    remaining_distance = distance
    elapsed = 0.0
    cursor = start_time
    for _ in range(len(congested_plans) + 1):
        active = [
            plan
            for plan in congested_plans
            if plan.target_leg is leg and plan.recovery_time > cursor
        ]
        if not active:
            normal_hours = remaining_distance / sailing_speed
            return elapsed + normal_hours if math.isfinite(normal_hours) else None

        plan = max(active, key=lambda item: item.multiplier)
        try:
            active_hours = (plan.recovery_time - cursor).total_seconds() / 3600.0
        except (AttributeError, OverflowError):
            return None
        if active_hours <= 0.0 or not math.isfinite(active_hours):
            return None
        active_distance = active_hours * sailing_speed / plan.multiplier
        if remaining_distance <= active_distance:
            return elapsed + remaining_distance * plan.multiplier / sailing_speed
        remaining_distance -= active_distance
        elapsed += active_hours
        cursor = plan.recovery_time
    return None


def _install_path(shipment: Any, path: tuple[_BookingEdge, ...]) -> bool | None:
    """Install a fully validated path with rollback on an unexpected failure."""
    old_bookings = getattr(shipment, "associated_bookings", None)
    if not isinstance(old_bookings, list):
        return None
    old_index = getattr(shipment, "current_booking_index", None)
    if not path or not _path_is_contiguous(shipment, path):
        return None

    try:
        module = importlib.import_module("maritime_data_context")
        Booking = getattr(module, "Booking", None)
    except Exception:
        return None
    if Booking is None:
        return None

    new_bookings: list[Any] = []
    try:
        for sequence_index, edge in enumerate(path, start=1):
            route_bookings = getattr(edge.service_route, "associated_bookings", None)
            if not isinstance(route_bookings, list):
                return None
            new_bookings.append(
                Booking(
                    sequence_index=sequence_index,
                    shipment=shipment,
                    service_route=edge.service_route,
                    departure_segment_index=edge.departure_segment_index,
                    arrival_segment_index=edge.arrival_segment_index,
                )
            )
    except Exception:
        return None

    touched_routes: list[tuple[Any, list[Any]]] = []
    for booking in old_bookings:
        route = getattr(booking, "service_route", None)
        route_bookings = getattr(route, "associated_bookings", None)
        if route is not None and isinstance(route_bookings, list):
            if not any(existing is route for existing, _ in touched_routes):
                touched_routes.append((route, list(route_bookings)))
        elif route is not None:
            return None

    try:
        for booking in old_bookings:
            route = getattr(booking, "service_route", None)
            route_bookings = getattr(route, "associated_bookings", None)
            if route_bookings is not None:
                while booking in route_bookings:
                    route_bookings.remove(booking)
        shipment.associated_bookings = new_bookings
        shipment.current_booking_index = 1
        for booking in new_bookings:
            booking.service_route.associated_bookings.append(booking)
    except Exception:
        for route, snapshot in touched_routes:
            route.associated_bookings[:] = snapshot
        shipment.associated_bookings = old_bookings
        shipment.current_booking_index = old_index
        return None
    return True


def _path_is_contiguous(shipment: Any, path: tuple[_BookingEdge, ...]) -> bool:
    demand = getattr(shipment, "demand", None)
    origin = getattr(demand, "origin_port", None)
    destination = getattr(demand, "destination_port", None)
    if origin is None or destination is None or path[0].departure_port is not origin:
        return False
    for previous, current in zip(path, path[1:], strict=False):
        if previous.arrival_port is not current.departure_port:
            return False
    return path[-1].arrival_port is destination
