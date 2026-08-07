"""Participant strategy for the Round 1 recovery-aware origin hold.

The strategy never changes routes, vessels, bookings, or simulation state.  It
returns ``False`` only when a model-derived estimate says that letting the
organizer's existing origin-retry lifecycle wait for a disrupted nominal path
to recover is faster than the organizer's currently safe detour.  Every other
case returns ``None`` and delegates to the organizer fallback.
"""

from __future__ import annotations

import datetime as dt
import math
import numbers
from typing import Any, NamedTuple


_NARROW_EXCEPTIONS = (
    AttributeError,
    IndexError,
    KeyError,
    TypeError,
    ValueError,
    ZeroDivisionError,
    FloatingPointError,
    OverflowError,
)


class _Edge:
    __slots__ = (
        "service_route",
        "departure_port",
        "arrival_port",
        "departure_segment_index",
        "arrival_segment_index",
        "segments",
        "total_distance",
    )

    def __init__(
        self,
        service_route: Any,
        departure_port: Any,
        arrival_port: Any,
        departure_segment_index: int,
        arrival_segment_index: int,
        segments: list[Any],
    ) -> None:
        self.service_route = service_route
        self.departure_port = departure_port
        self.arrival_port = arrival_port
        self.departure_segment_index = int(departure_segment_index)
        self.arrival_segment_index = int(arrival_segment_index)
        self.segments = tuple(segments)
        total = 0.0
        for segment in self.segments:
            leg = getattr(segment, "associated_leg")
            distance = _positive_float(getattr(leg, "sailing_distance"))
            if distance is None:
                raise ValueError("invalid sailing distance")
            total += distance
        if not math.isfinite(total) or total <= 0.0:
            raise ValueError("invalid edge distance")
        self.total_distance = total


class _Constraint(NamedTuple):
    kind: str
    target: Any
    recovery: dt.datetime


class _ActiveState(NamedTuple):
    closed_ports: tuple[Any, ...]
    closed_names: tuple[str, ...]
    congested_legs: tuple[Any, ...]
    congested_ids: frozenset[int]
    disruption_key: tuple[tuple[str, ...], tuple[tuple[str, str], ...]]
    constraints: tuple[_Constraint, ...]


def _positive_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        return None
    return result


def _nonnegative_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        return None
    return result


def _plan_window(plan: Any, now: dt.datetime) -> tuple[dt.datetime, dt.datetime] | None:
    start_offset = _nonnegative_float(getattr(plan, "start_offset_days", None))
    duration = _positive_float(getattr(plan, "duration_days", None))
    if start_offset is None or duration is None:
        return None
    try:
        start = dt.datetime.min + dt.timedelta(days=start_offset)
        end = start + dt.timedelta(days=duration)
    except (OverflowError, TypeError, ValueError):
        return None
    if start <= now < end:
        return start, end
    return None


def _port_name(port: Any) -> str | None:
    name = getattr(port, "name", None)
    return name.casefold() if isinstance(name, str) else None


def _leg_key(leg: Any) -> tuple[str, str] | None:
    departure = _port_name(getattr(leg, "departure_port", None))
    arrival = _port_name(getattr(leg, "arrival_port", None))
    if departure is None or arrival is None:
        return None
    return departure, arrival


def _active_state(context: Any, now: dt.datetime) -> _ActiveState | None:
    plans = getattr(context, "disruption_plans", None)
    if plans is None:
        return None

    closed_ports: list[Any] = []
    closed_names: set[str] = set()
    congested_legs: list[Any] = []
    congested_ids: set[int] = set()
    congested_keys: set[tuple[str, str]] = set()
    constraints: list[_Constraint] = []

    for plan in list(plans):
        window = _plan_window(plan, now)
        if window is None:
            continue
        _start, recovery = window
        target_leg = getattr(plan, "target_leg", None)
        target_berth = getattr(plan, "target_berth", None)
        if (target_leg is None) == (target_berth is None):
            return None

        if target_berth is not None:
            if not bool(getattr(plan, "close_berth", False)):
                continue
            port = getattr(target_berth, "port", None)
            name = _port_name(port)
            if port is None or name is None:
                return None
            if not any(existing is port for existing in closed_ports):
                closed_ports.append(port)
            closed_names.add(name)
            constraints.append(_Constraint("port", port, recovery))
            continue

        multiplier = _positive_float(getattr(plan, "multiplier", None))
        leg_key = _leg_key(target_leg)
        if multiplier is None or leg_key is None:
            return None
        if multiplier <= 1.0:
            continue
        if not any(existing is target_leg for existing in congested_legs):
            congested_legs.append(target_leg)
        congested_ids.add(id(target_leg))
        congested_keys.add(leg_key)
        constraints.append(_Constraint("leg", target_leg, recovery))

    if not constraints:
        return None
    return _ActiveState(
        tuple(closed_ports),
        tuple(sorted(closed_names)),
        tuple(congested_legs),
        frozenset(congested_ids),
        (tuple(sorted(closed_names)), tuple(sorted(congested_keys))),
        tuple(constraints),
    )


def _ordered_segments(route: Any) -> list[Any] | None:
    segments = getattr(route, "segments", None)
    if segments is None:
        return None
    ordered = sorted(list(segments), key=lambda segment: segment.sequence_index)
    return ordered if len(ordered) >= 2 else None


def _route_available(route: Any, state: _ActiveState, safe: bool) -> bool:
    source = getattr(route, "source_service_route", None)
    if not safe:
        return source is None
    if source is None:
        return True
    return (
        getattr(route, "disruption_key", None) == state.disruption_key
        and bool(getattr(route, "deployed_vessels", None))
    )


def _route_edges(route: Any, state: _ActiveState, safe: bool) -> list[_Edge]:
    if not _route_available(route, state, safe):
        return []
    segments = _ordered_segments(route)
    if segments is None:
        return []
    edges: list[_Edge] = []
    count = len(segments)
    for start_index, start_segment in enumerate(segments):
        first_leg = getattr(start_segment, "associated_leg")
        departure_port = getattr(first_leg, "departure_port")
        if departure_port is None:
            continue
        for step in range(1, count):
            end_index = (start_index + step - 1) % count
            candidate = [segments[(start_index + offset) % count] for offset in range(step)]
            last_leg = getattr(candidate[-1], "associated_leg")
            arrival_port = getattr(last_leg, "arrival_port")
            if arrival_port is None or arrival_port is departure_port:
                continue
            if safe:
                if any(
                    id(getattr(segment, "associated_leg")) in state.congested_ids
                    for segment in candidate
                ):
                    continue
                intermediate_names = [
                    _port_name(getattr(getattr(segment, "associated_leg"), "arrival_port"))
                    for segment in candidate[:-1]
                ]
                if any(name in state.closed_names for name in intermediate_names):
                    continue
                if _port_name(arrival_port) in state.closed_names:
                    continue
            try:
                edges.append(
                    _Edge(
                        route,
                        departure_port,
                        arrival_port,
                        start_index + 1,
                        end_index + 1,
                        candidate,
                    )
                )
            except (AttributeError, TypeError, ValueError, OverflowError):
                continue
    return edges


def _pathfind(context: Any, edges: list[_Edge], origin: Any, destination: Any) -> list[_Edge] | None:
    ports = list(getattr(context, "ports"))
    if origin is destination or not ports or not edges:
        return None
    port_ids = {id(port) for port in ports}
    if id(origin) not in port_ids or id(destination) not in port_ids:
        return None
    distances = {id(port): math.inf for port in ports}
    previous: dict[int, _Edge] = {}
    distances[id(origin)] = 0.0
    unvisited = list(ports)
    outgoing: dict[int, list[_Edge]] = {}
    for edge in edges:
        outgoing.setdefault(id(edge.departure_port), []).append(edge)

    while unvisited:
        current = min(unvisited, key=lambda port: distances[id(port)])
        if math.isinf(distances[id(current)]) or current is destination:
            break
        unvisited.remove(current)
        for edge in outgoing.get(id(current), []):
            next_port = edge.arrival_port
            if id(next_port) not in port_ids or next_port not in unvisited:
                continue
            candidate_distance = distances[id(current)] + edge.total_distance
            if candidate_distance < distances[id(next_port)]:
                distances[id(next_port)] = candidate_distance
                previous[id(next_port)] = edge

    if id(destination) not in previous:
        return None
    path: list[_Edge] = []
    cursor = destination
    for _ in range(len(ports)):
        if cursor is origin:
            path.reverse()
            return path
        edge = previous.get(id(cursor))
        if edge is None:
            return None
        path.append(edge)
        cursor = edge.departure_port
    return None


def _route_speeds(route: Any) -> list[float]:
    speeds: list[float] = []
    seen: set[int] = set()
    vessels = list(getattr(route, "deployed_vessels", None) or [])
    if not vessels:
        for segment in list(getattr(route, "segments", None) or []):
            vessels.extend(list(getattr(segment, "current_vessels", None) or []))
    for vessel in vessels:
        if id(vessel) in seen:
            continue
        seen.add(id(vessel))
        speed = _positive_float(
            getattr(getattr(vessel, "vessel_class", None), "sailing_speed", None)
        )
        if speed is not None:
            speeds.append(speed)
    return speeds


def _route_cycle_distance(route: Any) -> float | None:
    total = 0.0
    for segment in list(getattr(route, "segments", None) or []):
        distance = _positive_float(
            getattr(getattr(segment, "associated_leg"), "sailing_distance")
        )
        if distance is None:
            return None
        total += distance
    return total if math.isfinite(total) and total > 0.0 else None


def _path_duration_hours(path: list[_Edge]) -> float | None:
    total = 0.0
    for edge in path:
        speeds = _route_speeds(edge.service_route)
        cycle_distance = _route_cycle_distance(edge.service_route)
        if not speeds or cycle_distance is None:
            return None
        mean_speed = sum(speeds) / len(speeds)
        headway = cycle_distance / sum(speeds)
        if not _positive_float(mean_speed) or not _positive_float(headway):
            return None
        edge_hours = edge.total_distance / mean_speed + 0.5 * headway
        if not _positive_float(edge_hours):
            return None
        total += edge_hours
    return total if _positive_float(total) is not None else None


def _edge_intersects_constraint(edge: _Edge, constraint: _Constraint) -> bool:
    if constraint.kind == "port":
        if edge.departure_port is constraint.target or edge.arrival_port is constraint.target:
            return True
        return any(
            getattr(getattr(segment, "associated_leg"), "arrival_port") is constraint.target
            for segment in edge.segments
        )
    return any(getattr(segment, "associated_leg") is constraint.target for segment in edge.segments)


def _latest_recovery(path: list[_Edge], constraints: tuple[_Constraint, ...]) -> dt.datetime | None:
    intersecting = [
        constraint
        for constraint in constraints
        if any(_edge_intersects_constraint(edge, constraint) for edge in path)
    ]
    if not intersecting:
        return None
    return max(constraint.recovery for constraint in intersecting)


def _should_hold(context: Any, now: Any, shipment: Any) -> bool:
    if not isinstance(now, dt.datetime):
        return False
    demand = getattr(shipment, "demand", None)
    origin = getattr(demand, "origin_port", None)
    destination = getattr(demand, "destination_port", None)
    if origin is None or destination is None or origin is destination:
        return False
    state = _active_state(context, now)
    if state is None:
        return False
    routes = list(getattr(context, "service_routes"))
    nominal_edges: list[_Edge] = []
    safe_edges: list[_Edge] = []
    for route in routes:
        nominal_edges.extend(_route_edges(route, state, safe=False))
        safe_edges.extend(_route_edges(route, state, safe=True))
    nominal_path = _pathfind(context, nominal_edges, origin, destination)
    if nominal_path is None:
        return False
    recovery = _latest_recovery(nominal_path, state.constraints)
    if recovery is None:
        return False
    safe_path = _pathfind(context, safe_edges, origin, destination)
    if safe_path is None:
        return False
    nominal_hours = _path_duration_hours(nominal_path)
    safe_hours = _path_duration_hours(safe_path)
    if nominal_hours is None or safe_hours is None:
        return False
    wait_hours = (recovery - now).total_seconds() / 3600.0
    if not math.isfinite(wait_hours) or wait_hours < 0.0:
        return False
    return wait_hours + nominal_hours < safe_hours


class UserStrategy:
    """Participant adapter with one recovery-aware booking decision."""

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
            return False if _should_hold(context, now, shipment) else None
        except _NARROW_EXCEPTIONS:
            return None

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        return None
