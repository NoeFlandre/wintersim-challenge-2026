"""Participant-owned response strategy for the WSC 2026 challenge.

The active experiment is deliberately narrow: while a disruption is active,
new cargo may remain at origin when an interrupted one-booking direct service
is estimated to recover sooner than a safe detour requiring at least two
changes between service routes.
Every decision is derived from the supplied runtime objects. The strategy is
read-only, deterministic, standard-library-only, and delegates on uncertainty.
"""

from __future__ import annotations

import datetime as dt
import math
import numbers
from typing import Any, NamedTuple


class _Constraint(NamedTuple):
    kind: str
    target_identity: int
    departure_name: str | None
    arrival_name: str
    recovery: dt.datetime


class _ActiveState(NamedTuple):
    constraints: tuple[_Constraint, ...]
    closed_port_names: frozenset[str]
    congested_leg_identities: frozenset[int]
    congested_leg_keys: frozenset[tuple[str, str]]
    disruption_key: tuple[tuple[str, ...], tuple[tuple[str, str], ...]]


class _Edge(NamedTuple):
    departure: Any
    arrival: Any
    intermediate_ports: tuple[Any, ...]
    route: Any
    distance: float
    legs: tuple[Any, ...]


class _RouteData(NamedTuple):
    edges: tuple[_Edge, ...]
    cycle_distance: float


class _RouteProfile(NamedTuple):
    mean_speed: float
    headway_hours: float


_DATA_ERRORS = (
    AttributeError,
    IndexError,
    KeyError,
    TypeError,
    ValueError,
    ZeroDivisionError,
    FloatingPointError,
    OverflowError,
)


def _finite_real(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _positive_real(value: Any) -> float | None:
    result = _finite_real(value)
    return result if result is not None and result > 0.0 else None


def _port_name(port: Any) -> str | None:
    name = getattr(port, "name", None)
    if not isinstance(name, str) or not name:
        return None
    folded = name.casefold()
    return folded if folded else None


def _leg_key(leg: Any) -> tuple[str, str] | None:
    departure = _port_name(getattr(leg, "departure_port", None))
    arrival = _port_name(getattr(leg, "arrival_port", None))
    if departure is None or arrival is None or departure == arrival:
        return None
    return departure, arrival


def _active_state(context: Any, now: Any) -> _ActiveState | None:
    if not isinstance(now, dt.datetime):
        return None
    plans = getattr(context, "disruption_plans", None)
    if not isinstance(plans, (list, tuple)):
        return None

    constraints: list[_Constraint] = []
    for plan in plans:
        close_berth = getattr(plan, "close_berth", None)
        multiplier = _finite_real(getattr(plan, "multiplier", None))
        if not isinstance(close_berth, bool) or multiplier is None:
            return None
        relevant = close_berth or multiplier > 1.0
        if not relevant:
            continue

        start_days = _finite_real(getattr(plan, "start_offset_days", None))
        duration_days = _positive_real(getattr(plan, "duration_days", None))
        if start_days is None or duration_days is None:
            return None
        start = dt.datetime.min + dt.timedelta(days=start_days)
        end = start + dt.timedelta(days=duration_days)
        if not start <= now < end:
            continue

        target_leg = getattr(plan, "target_leg", None)
        target_berth = getattr(plan, "target_berth", None)
        is_closed_port = close_berth
        is_congested_leg = multiplier > 1.0
        if is_closed_port == is_congested_leg:
            return None
        if is_closed_port:
            if target_berth is None or target_leg is not None:
                return None
            port_name = _port_name(getattr(target_berth, "port", None))
            if port_name is None:
                return None
            constraints.append(
                _Constraint(
                    "port",
                    id(target_berth.port),
                    None,
                    port_name,
                    end,
                )
            )
        else:
            if target_leg is None or target_berth is not None:
                return None
            key = _leg_key(target_leg)
            if key is None:
                return None
            constraints.append(_Constraint("leg", id(target_leg), key[0], key[1], end))

    if not constraints:
        return None
    closed_names = frozenset(
        constraint.arrival_name for constraint in constraints if constraint.kind == "port"
    )
    congested_keys = frozenset(
        (constraint.departure_name, constraint.arrival_name)
        for constraint in constraints
        if constraint.kind == "leg" and constraint.departure_name is not None
    )
    ordered_leg_keys = tuple(sorted(congested_keys))
    congested_identities = frozenset(
        constraint.target_identity for constraint in constraints if constraint.kind == "leg"
    )
    disruption_key = (tuple(sorted(closed_names)), ordered_leg_keys)
    return _ActiveState(
        tuple(constraints),
        closed_names,
        congested_identities,
        congested_keys,
        disruption_key,
    )


def _route_data(route: Any) -> _RouteData | None:
    raw_segments = getattr(route, "segments", None)
    if not isinstance(raw_segments, (list, tuple)) or len(raw_segments) < 2:
        return None
    segments = list(raw_segments)
    indexes: list[int] = []
    for segment in segments:
        index = getattr(segment, "sequence_index", None)
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            return None
        indexes.append(index)
    if len(set(indexes)) != len(indexes):
        return None
    segments.sort(key=lambda segment: segment.sequence_index)

    legs: list[Any] = []
    distances: list[float] = []
    for segment in segments:
        leg = getattr(segment, "associated_leg", None)
        if leg is None or _leg_key(leg) is None:
            return None
        distance = _positive_real(getattr(leg, "sailing_distance", None))
        if distance is None:
            return None
        legs.append(leg)
        distances.append(distance)
    for index, leg in enumerate(legs):
        next_leg = legs[(index + 1) % len(legs)]
        if getattr(leg, "arrival_port", None) is not getattr(next_leg, "departure_port", None):
            return None

    cycle_distance = math.fsum(distances)
    if not math.isfinite(cycle_distance) or cycle_distance <= 0.0:
        return None

    edges: list[_Edge] = []
    segment_count = len(segments)
    for start_index in range(segment_count):
        traversed_legs: list[Any] = []
        traversed_distances: list[float] = []
        departure = getattr(legs[start_index], "departure_port", None)
        for step in range(1, segment_count):
            leg_index = (start_index + step - 1) % segment_count
            leg = legs[leg_index]
            traversed_legs.append(leg)
            traversed_distances.append(distances[leg_index])
            arrival = getattr(leg, "arrival_port", None)
            if departure is arrival:
                continue
            distance = math.fsum(traversed_distances)
            if not math.isfinite(distance) or distance <= 0.0:
                return None
            intermediate_ports = tuple(
                getattr(item, "arrival_port", None) for item in traversed_legs[:-1]
            )
            if any(_port_name(port) is None for port in intermediate_ports):
                return None
            edges.append(
                _Edge(
                    departure,
                    arrival,
                    intermediate_ports,
                    route,
                    distance,
                    tuple(traversed_legs),
                )
            )
    return _RouteData(tuple(edges), cycle_distance)


def _edge_is_safe(edge: _Edge, state: _ActiveState) -> bool:
    for leg in edge.legs:
        key = _leg_key(leg)
        if key is None or id(leg) in state.congested_leg_identities:
            return False
    arrivals = (*edge.intermediate_ports, edge.arrival)
    for port in arrivals:
        name = _port_name(port)
        if name is None or name in state.closed_port_names:
            return False
    return True


def _graphs(
    context: Any, state: _ActiveState
) -> tuple[tuple[_Edge, ...], tuple[_Edge, ...]] | None:
    raw_routes = getattr(context, "service_routes", None)
    if not isinstance(raw_routes, (list, tuple)):
        return None
    nominal_edges: list[_Edge] = []
    safe_edges: list[_Edge] = []
    for route in raw_routes:
        route_data = _route_data(route)
        if route_data is None:
            return None
        source = getattr(route, "source_service_route", None)
        if source is None:
            nominal_edges.extend(route_data.edges)
            safe_edges.extend(edge for edge in route_data.edges if _edge_is_safe(edge, state))
            continue
        disruption_key = getattr(route, "disruption_key", None)
        deployed = getattr(route, "deployed_vessels", None)
        if (
            disruption_key == state.disruption_key
            and isinstance(deployed, (list, tuple))
            and bool(deployed)
        ):
            safe_edges.extend(edge for edge in route_data.edges if _edge_is_safe(edge, state))
    return tuple(nominal_edges), tuple(safe_edges)


def _shortest_path(
    context: Any, origin: Any, destination: Any, edges: tuple[_Edge, ...]
) -> tuple[_Edge, ...] | None:
    raw_ports = getattr(context, "ports", None)
    if not isinstance(raw_ports, (list, tuple)):
        return None
    ports = list(raw_ports)
    port_ids = [id(port) for port in ports]
    if len(set(port_ids)) != len(port_ids):
        return None
    origin_id = id(origin)
    destination_id = id(destination)
    if origin_id not in port_ids or destination_id not in port_ids:
        return None
    if origin_id == destination_id:
        return ()

    distances: dict[int, float] = dict.fromkeys(port_ids, math.inf)
    previous: dict[int, _Edge] = {}
    unvisited = list(port_ids)
    unvisited_members = set(unvisited)
    distances[origin_id] = 0.0
    outgoing: dict[int, list[_Edge]] = {}
    for edge in edges:
        departure_id = id(edge.departure)
        arrival_id = id(edge.arrival)
        if departure_id not in distances or arrival_id not in distances:
            return None
        outgoing.setdefault(departure_id, []).append(edge)

    while unvisited:
        current_index = min(range(len(unvisited)), key=lambda index: distances[unvisited[index]])
        current_id = unvisited.pop(current_index)
        unvisited_members.remove(current_id)
        current_distance = distances[current_id]
        if not math.isfinite(current_distance) or current_id == destination_id:
            break
        for edge in outgoing.get(current_id, []):
            next_id = id(edge.arrival)
            if next_id not in unvisited_members:
                continue
            alternative = current_distance + edge.distance
            if not math.isfinite(alternative):
                return None
            if alternative < distances[next_id]:
                distances[next_id] = alternative
                previous[next_id] = edge

    if destination_id not in previous:
        return None
    path: list[_Edge] = []
    cursor = destination_id
    visited: set[int] = set()
    while cursor != origin_id:
        if cursor in visited:
            return None
        visited.add(cursor)
        predecessor = previous.get(cursor)
        if predecessor is None:
            return None
        path.append(predecessor)
        cursor = id(predecessor.departure)
    path.reverse()
    return tuple(path)


def _edge_constraint_recovery(edge: _Edge, state: _ActiveState) -> dt.datetime | None:
    recoveries = tuple(
        constraint.recovery for constraint in _matching_edge_constraints(edge, state)
    )
    return max(recoveries) if recoveries else None


def _matching_edge_constraints(edge: _Edge, state: _ActiveState) -> tuple[_Constraint, ...]:
    """Return active constraints matching an edge under the v3 semantics."""
    leg_identities = frozenset(id(leg) for leg in edge.legs)
    arrival_names = frozenset(_port_name(port) for port in (*edge.intermediate_ports, edge.arrival))
    return tuple(
        constraint
        for constraint in state.constraints
        if (constraint.kind == "leg" and constraint.target_identity in leg_identities)
        or (constraint.kind == "port" and constraint.arrival_name in arrival_names)
    )


def _route_profile(route: Any) -> _RouteProfile | None:
    route_data = _route_data(route)
    if route_data is None:
        return None
    deployed = getattr(route, "deployed_vessels", None)
    if not isinstance(deployed, (list, tuple)) or not deployed:
        return None
    speeds: list[float] = []
    for vessel in deployed:
        vessel_class = getattr(vessel, "vessel_class", None)
        speed = _positive_real(getattr(vessel_class, "sailing_speed", None))
        if speed is None:
            return None
        speeds.append(speed)
    speed_sum = math.fsum(speeds)
    mean_speed = speed_sum / len(speeds)
    headway = route_data.cycle_distance / speed_sum
    if not all(math.isfinite(value) and value > 0.0 for value in (mean_speed, headway)):
        return None
    return _RouteProfile(mean_speed, headway)


def _path_service_hours(path: tuple[_Edge, ...]) -> float | None:
    profiles: dict[int, _RouteProfile] = {}
    total = 0.0
    previous_route: Any = None
    for edge in path:
        route_id = id(edge.route)
        profile = profiles.get(route_id)
        if profile is None:
            profile = _route_profile(edge.route)
            if profile is None:
                return None
            profiles[route_id] = profile
        if previous_route is not edge.route:
            total += 0.5 * profile.headway_hours
        total += edge.distance / profile.mean_speed
        if not math.isfinite(total):
            return None
        previous_route = edge.route
    return total if total > 0.0 else None


def _should_hold(context: Any, now: Any, shipment: Any) -> bool:
    if not isinstance(now, dt.datetime):
        return False
    bookings = getattr(shipment, "associated_bookings", None)
    if not isinstance(bookings, list) or bookings:
        return False
    if getattr(shipment, "current_booking_index", None) is not None:
        return False
    demand = getattr(shipment, "demand", None)
    origin = getattr(demand, "origin_port", None)
    destination = getattr(demand, "destination_port", None)
    if origin is None or destination is None or origin is destination:
        return False

    state = _active_state(context, now)
    if state is None:
        return False
    graphs = _graphs(context, state)
    if graphs is None:
        return False
    nominal_path = _shortest_path(context, origin, destination, graphs[0])
    safe_path = _shortest_path(context, origin, destination, graphs[1])
    if nominal_path is None or safe_path is None:
        return False
    if len(nominal_path) != 1 or len(safe_path) < 2:
        return False
    route_change_count = sum(
        left.route is not right.route for left, right in zip(safe_path, safe_path[1:], strict=False)
    )
    if route_change_count == 1:
        matching_kinds = {
            constraint.kind for constraint in _matching_edge_constraints(nominal_path[0], state)
        }
        if matching_kinds != {"leg", "port"}:
            return False
    elif route_change_count < 2:
        return False

    recovery = _edge_constraint_recovery(nominal_path[0], state)
    if recovery is None:
        return False
    nominal_hours = _path_service_hours(nominal_path)
    detour_hours = _path_service_hours(safe_path)
    if nominal_hours is None or detour_hours is None:
        return False
    wait_hours = max(0.0, (recovery - now).total_seconds() / 3600.0)
    hold_hours = wait_hours + nominal_hours
    if not all(math.isfinite(value) and value > 0.0 for value in (hold_hours, detour_hours)):
        return False
    return hold_hours < detour_hours


class UserStrategy:
    """Deterministic participant strategy with one read-only cargo policy."""

    @staticmethod
    def select_vessel_for_berth(
        maritime_data_context: Any,
        port: Any,
        waiting_vessels: Any,
        available_berths: Any,
        current_time: Any,
        waiting_since_by_vessel: Any = None,
    ) -> Any:
        """Delegate vessel selection to the organizer fallback."""
        return None

    @staticmethod
    def create_alternative_service_routes(context: Any, now: Any, vessel: Any = None) -> Any:
        """Delegate alternative-route creation to the organizer fallback."""
        return None

    @staticmethod
    def assign_associated_bookings(context: Any, now: Any, shipment: Any) -> Any:
        """Hold a direct-service shipment instead of a two-transfer detour."""
        try:
            return False if _should_hold(context, now, shipment) else None
        except _DATA_ERRORS:
            return None

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Delegate in-transit booking changes to the organizer fallback."""
        return None
