"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. Returning ``None`` from any method
signals "not handled; use the organizer fallback", leaving the maritime data
context, routes, bookings, and vessel state exactly as the framework built
them.

Candidate behavior (Round 0 recovery-aware origin hold vs. disruption detour):

Only ``assign_associated_bookings`` is changed. The hook returns ``False``
when waiting for the relevant disruption recovery is predicted to complete
strictly earlier than taking the fallback's currently available safe
detour; otherwise it returns ``None`` and the organizer fallback handles
the assignment. ``False`` means "no booking can currently be assigned
(may cause retry/wait)" and uses the existing organizer retry lifecycle.

The other three hooks return ``None`` unconditionally:

* ``select_vessel_for_berth``
* ``create_alternative_service_routes``
* ``adjust_bookings_before_cargo_handling``

The candidate never creates bookings, routes, legs, vessels, or events. It
does not mutate any organizer state. It does not import organizer source.

Runtime constraints (enforced by the challenge rules):

- Standard-library imports only (``datetime`` is used; ``math`` is used).
- No network, subprocess, filesystem, environment, cwd, wall-clock,
  unseeded randomness, or mutable cross-run global state.
- No port names, route IDs, seed-specific maps, scenario constants, dates,
  or tuned thresholds.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

_NARROW_EXCEPTIONS = (
    AttributeError,
    TypeError,
    ValueError,
    ZeroDivisionError,
    FloatingPointError,
    OverflowError,
)


class _BookingEdge:
    """Immutable booking edge used for both nominal and safe path construction.

    The same shape is used for both paths because the only difference is
    which edges are filtered out before pathfinding. The fields are
    identical to the organizer's ``_CandidateBookingEdge`` dataclass:
    service route, departure and arrival ports, departure and arrival
    segment indices, candidate segments, and total distance.
    """

    __slots__ = (
        "service_route",
        "departure_port",
        "arrival_port",
        "departure_segment_index",
        "arrival_segment_index",
        "candidate_segments",
        "total_distance",
    )

    def __init__(
        self,
        service_route: Any,
        departure_port: Any,
        arrival_port: Any,
        departure_segment_index: int,
        arrival_segment_index: int,
        candidate_segments: list[Any],
    ) -> None:
        self.service_route = service_route
        self.departure_port = departure_port
        self.arrival_port = arrival_port
        self.departure_segment_index = int(departure_segment_index)
        self.arrival_segment_index = int(arrival_segment_index)
        self.candidate_segments = list(candidate_segments)
        self.total_distance = 0.0
        for segment in self.candidate_segments:
            leg = getattr(segment, "associated_leg", None)
            distance = getattr(leg, "sailing_distance", 0.0)
            self.total_distance += float(distance)


def _is_finite_positive(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    as_float = float(value)
    return math.isfinite(as_float) and as_float > 0.0


def _is_finite_nonnegative(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    as_float = float(value)
    return math.isfinite(as_float) and as_float >= 0.0


def _as_finite_positive(value: object) -> float | None:
    if not _is_finite_positive(value):
        return None
    # _is_finite_positive has already validated the type as int or float,
    # so the cast is a no-op at runtime; it just satisfies mypy.
    return float(value if isinstance(value, (int, float)) else 0.0)


def _as_finite_nonnegative(value: object) -> float | None:
    if not _is_finite_nonnegative(value):
        return None
    return float(value if isinstance(value, (int, float)) else 0.0)


def _route_cycle_distance(route: Any) -> float:
    """Sum the sailing distances of a route's segments.

    Returns ``math.inf`` on invalid input; the caller delegates with
    ``None`` in that case.
    """
    total = 0.0
    segments = getattr(route, "segments", None)
    if segments is None:
        return math.inf
    for segment in segments:
        leg = getattr(segment, "associated_leg", None)
        distance = _as_finite_positive(getattr(leg, "sailing_distance", None))
        if distance is None:
            return math.inf
        total += distance
    return total


def _route_eligible_speeds(route: Any) -> list[float]:
    """Positive sailing speeds for the route's eligible vessels.

    Eligible vessels are the route's currently deployed vessels. If the
    route has none deployed, vessels on the route's segments are
    considered, but only vessels whose ``assigned_service_route is route``
    qualify. Identity-based deduplication is applied. Returns an empty
    list when no positive speed is available; the caller delegates with
    ``None`` in that case.
    """
    speeds: list[float] = []
    seen: set[int] = set()
    for vessel in list(getattr(route, "deployed_vessels", None) or []):
        vid = id(vessel)
        if vid in seen:
            continue
        seen.add(vid)
        vessel_class = getattr(vessel, "vessel_class", None)
        speed = _as_finite_positive(getattr(vessel_class, "sailing_speed", None))
        if speed is not None:
            speeds.append(speed)
    if not speeds:
        for segment in list(getattr(route, "segments", None) or []):
            for vessel in list(getattr(segment, "current_vessels", None) or []):
                if getattr(vessel, "assigned_service_route", None) is not route:
                    continue
                vid = id(vessel)
                if vid in seen:
                    continue
                seen.add(vid)
                vessel_class = getattr(vessel, "vessel_class", None)
                speed = _as_finite_positive(getattr(vessel_class, "sailing_speed", None))
                if speed is not None:
                    speeds.append(speed)
    return speeds


def _route_headway_hours(route: Any, cycle_distance: float) -> float:
    """Estimated route headway in hours.

    ``headway_hours = cycle_distance / sum(s for s in eligible speeds)``.
    Returns ``math.inf`` when the formula cannot be evaluated, so the
    caller delegates with ``None``.
    """
    if not _is_finite_positive(cycle_distance):
        return math.inf
    speeds = _route_eligible_speeds(route)
    if not speeds:
        return math.inf
    speed_sum = 0.0
    for speed in speeds:
        speed_sum += speed
    if not _is_finite_positive(speed_sum):
        return math.inf
    return cycle_distance / speed_sum


def _route_mean_speed(route: Any) -> float:
    """Arithmetic mean positive sailing speed of the route's eligible vessels."""
    speeds = _route_eligible_speeds(route)
    if not speeds:
        return math.inf
    return sum(speeds) / len(speeds)


def _route_is_available_for_booking(
    route: Any,
    disruption_key: tuple[tuple[str, ...], tuple[tuple[str, str], ...]],
) -> bool:
    """Match the organizer's fallback availability predicate exactly."""
    if getattr(route, "source_service_route", None) is None:
        return True
    if getattr(route, "disruption_key", None) != disruption_key:
        return False
    return bool(getattr(route, "deployed_vessels", None))


def _route_edges_for_nominal(route: Any) -> list[_BookingEdge]:
    """Build candidate booking edges for the nominal path on one route.

    Only original routes (``source_service_route is None``) are eligible.
    No avoid_port_names or congested_legs filtering is applied; the
    nominal path may pass through disruption resources. Whole-cycle
    origin-to-same-origin edges are excluded.
    """
    if getattr(route, "source_service_route", None) is not None:
        return []
    segments = sorted(
        getattr(route, "segments", []) or [],
        key=lambda segment: int(getattr(segment, "sequence_index", 0) or 0),
    )
    segment_count = len(segments)
    if segment_count < 2:
        return []
    return _enumerate_route_edges(route, segments)


def _route_edges_for_safe(
    route: Any,
    avoid_port_names: set[str],
    congested_legs: set[int],
    disruption_key: tuple[tuple[str, ...], tuple[tuple[str, str], ...]],
) -> list[_BookingEdge]:
    """Build candidate booking edges for the safe path on one route.

    Mirrors the organizer's fallback availability and filtering exactly:

    * Original routes are eligible.
    * Alternative routes are eligible only when their ``disruption_key``
      matches and they have at least one deployed vessel.
    * Closed ports are excluded as **arrival** or **intermediate** ports
      of the edge (the departure port is not independently filtered).
    * Congested legs are excluded as any segment of an edge.
    * Whole-cycle origin-to-same-origin edges are excluded.
    """
    if not _route_is_available_for_booking(route, disruption_key):
        return []
    segments = sorted(
        getattr(route, "segments", []) or [],
        key=lambda segment: int(getattr(segment, "sequence_index", 0) or 0),
    )
    segment_count = len(segments)
    if segment_count < 2:
        return []
    edges: list[_BookingEdge] = []
    for start_index in range(segment_count):
        departure_leg = segments[start_index].associated_leg
        departure_port = getattr(departure_leg, "departure_port", None)
        if departure_port is None:
            continue
        for step in range(1, segment_count):
            last_index = (start_index + step - 1) % segment_count
            last_leg = segments[last_index].associated_leg
            arrival_port = getattr(last_leg, "arrival_port", None)
            if arrival_port is None:
                continue
            if departure_port is arrival_port:
                continue
            candidate_segments = [
                segments[(start_index + offset) % segment_count] for offset in range(step)
            ]
            if any(
                id(getattr(segment, "associated_leg", None)) in congested_legs
                for segment in candidate_segments
            ):
                continue
            intermediate_ports = [
                getattr(getattr(segment, "associated_leg", None), "arrival_port", None)
                for segment in candidate_segments
            ]
            if any(
                port is not None
                and isinstance(getattr(port, "name", None), str)
                and port.name.casefold() in avoid_port_names
                for port in intermediate_ports[:-1]
            ):
                continue
            if (
                isinstance(getattr(arrival_port, "name", None), str)
                and arrival_port.name.casefold() in avoid_port_names
            ):
                continue
            edges.append(
                _BookingEdge(
                    service_route=route,
                    departure_port=departure_port,
                    arrival_port=arrival_port,
                    departure_segment_index=start_index + 1,
                    arrival_segment_index=last_index + 1,
                    candidate_segments=candidate_segments,
                )
            )
    return edges


def _enumerate_route_edges(route: Any, segments: list[Any]) -> list[_BookingEdge]:
    """Enumerate every proper contiguous slice of ``segments`` as a booking edge.

    Whole-cycle origin-to-same-origin edges are excluded.
    """
    segment_count = len(segments)
    edges: list[_BookingEdge] = []
    for start_index in range(segment_count):
        departure_leg = segments[start_index].associated_leg
        departure_port = getattr(departure_leg, "departure_port", None)
        if departure_port is None:
            continue
        for step in range(1, segment_count):
            last_index = (start_index + step - 1) % segment_count
            last_leg = segments[last_index].associated_leg
            arrival_port = getattr(last_leg, "arrival_port", None)
            if arrival_port is None:
                continue
            if departure_port is arrival_port:
                continue
            candidate_segments = [
                segments[(start_index + offset) % segment_count] for offset in range(step)
            ]
            edges.append(
                _BookingEdge(
                    service_route=route,
                    departure_port=departure_port,
                    arrival_port=arrival_port,
                    departure_segment_index=start_index + 1,
                    arrival_segment_index=last_index + 1,
                    candidate_segments=candidate_segments,
                )
            )
    return edges


def _pathfind(
    context: Any,
    edges: list[Any],
    origin_port: Any,
    destination_port: Any,
) -> list[Any]:
    """Deterministic Dijkstra pathfinder.

    Iterates unvisited ports in ``context.ports`` order, picking the
    unvisited port with strictly minimum distance. Ties on equal distance
    are resolved by the earlier ``context.ports`` index. Predecessor is
    updated only on strictly lower cost. Returns the ordered list of edges
    from origin to destination, or an empty list when no path exists.
    """
    ports = list(getattr(context, "ports", []) or [])
    if origin_port is None or destination_port is None:
        return []
    if origin_port is destination_port:
        return []
    if not ports or not edges:
        return []
    port_by_id = {id(port): port for port in ports}
    distances: dict[int, float] = {id(port): math.inf for port in ports}
    predecessors: dict[int, Any] = {}
    distances[id(origin_port)] = 0.0
    unvisited: list[Any] = list(ports)

    outgoing: dict[int, list[Any]] = {}
    for edge in edges:
        outgoing.setdefault(id(edge.departure_port), []).append(edge)

    while unvisited:
        best_port: Any = None
        best_distance = math.inf
        for port in unvisited:
            current = distances[id(port)]
            if current < best_distance:
                best_distance = current
                best_port = port
        if best_port is None or math.isinf(best_distance) or best_port is destination_port:
            break
        unvisited[:] = [port for port in unvisited if port is not best_port]
        for edge in outgoing.get(id(best_port), []):
            next_port = edge.arrival_port
            if id(next_port) not in port_by_id:
                continue
            edge_distance = _as_finite_positive(getattr(edge, "total_distance", None))
            if edge_distance is None:
                continue
            alternative = distances[id(best_port)] + edge_distance
            if alternative < distances[id(next_port)]:
                distances[id(next_port)] = alternative
                predecessors[id(next_port)] = edge

    if id(destination_port) not in predecessors:
        return []

    path: list[Any] = []
    cursor = destination_port
    while cursor is not origin_port:
        edge = predecessors.get(id(cursor))
        if edge is None:
            return []
        path.append(edge)
        next_cursor = edge.departure_port
        if next_cursor is cursor:
            return []
        cursor = next_cursor
    path.reverse()
    return path


def _plan_active_window(plan: Any, now: dt.datetime) -> tuple[dt.datetime, dt.datetime] | None:
    """Return (start, end) of an active disruption plan, or None if inactive.

    ``start`` is anchored at ``datetime.min + start_offset_days`` and
    ``end`` is ``start + duration_days``. The active window is half-open:
    ``start <= now < end``.
    """
    start_offset = getattr(plan, "start_offset_days", None)
    duration = getattr(plan, "duration_days", None)
    if start_offset is None or duration is None:
        return None
    if not _is_finite_nonnegative(start_offset):
        return None
    if not _is_finite_positive(duration):
        return None
    try:
        start = dt.datetime.min + dt.timedelta(days=float(start_offset))
        end = start + dt.timedelta(days=float(duration))
    except (TypeError, ValueError, OverflowError):
        return None
    if not (isinstance(now, dt.datetime) and start <= now < end):
        return None
    return start, end


def _plan_intersects_path(plan: Any, path: list[Any]) -> bool:
    """Whether a disruption plan intersects the nominal booking path.

    Independently checks the closed-berth and congested-leg effects; a
    plan carrying both contributes both, and either kind of intersection
    counts as a hit.
    """
    if getattr(plan, "close_berth", False):
        target_berth = getattr(plan, "target_berth", None)
        target_port = getattr(target_berth, "port", None) if target_berth is not None else None
        if target_port is not None:
            for edge in path:
                if edge.departure_port is target_port or edge.arrival_port is target_port:
                    return True
                for segment in getattr(edge, "candidate_segments", []) or []:
                    intermediate = getattr(
                        getattr(segment, "associated_leg", None),
                        "arrival_port",
                        None,
                    )
                    if intermediate is target_port:
                        return True
    if float(getattr(plan, "multiplier", 1.0) or 1.0) > 1.0:
        target_leg = getattr(plan, "target_leg", None)
        if target_leg is not None:
            target_id = id(target_leg)
            for edge in path:
                for segment in getattr(edge, "candidate_segments", []) or []:
                    if id(getattr(segment, "associated_leg", None)) == target_id:
                        return True
    return False


def _latest_intersecting_recovery(
    context: Any, now: dt.datetime, path: list[Any]
) -> dt.datetime | None:
    """Latest end time among active disruption plans intersecting ``path``."""
    plans = list(getattr(context, "disruption_plans", []) or [])
    latest: dt.datetime | None = None
    for plan in plans:
        window = _plan_active_window(plan, now)
        if window is None:
            continue
        if not _plan_intersects_path(plan, path):
            continue
        if latest is None or window[1] > latest:
            latest = window[1]
    return latest


def _collect_active_disruption_keys(
    context: Any, now: dt.datetime
) -> tuple[set[str], set[int], tuple[tuple[str, ...], tuple[tuple[str, str], ...]]]:
    """Avoid port names, congested-leg object ids, and matching disruption_key.

    The disruption_key mirrors the organizer's fallback format:
    ``(tuple_of_avoid_port_names, tuple_of_congested_leg_keys)`` where each
    congested_leg_key is ``(departure_port_name.casefold(),
    arrival_port_name.casefold())``. A plan carrying both valid effects
    contributes both; duplicate plans targeting the same leg collapse to a
    single key entry.
    """
    avoid_port_names: set[str] = set()
    congested_legs: set[int] = set()
    congested_leg_keys: set[tuple[str, str]] = set()
    for plan in list(getattr(context, "disruption_plans", []) or []):
        if _plan_active_window(plan, now) is None:
            continue
        if getattr(plan, "close_berth", False):
            target_berth = getattr(plan, "target_berth", None)
            target_port = getattr(target_berth, "port", None) if target_berth is not None else None
            target_name = getattr(target_port, "name", None)
            if isinstance(target_name, str):
                avoid_port_names.add(target_name.casefold())
        if float(getattr(plan, "multiplier", 1.0) or 1.0) > 1.0:
            target_leg = getattr(plan, "target_leg", None)
            if target_leg is not None:
                congested_legs.add(id(target_leg))
                departure_port = getattr(target_leg, "departure_port", None)
                arrival_port = getattr(target_leg, "arrival_port", None)
                departure_name = getattr(departure_port, "name", None)
                arrival_name = getattr(arrival_port, "name", None)
                if isinstance(departure_name, str) and isinstance(arrival_name, str):
                    congested_leg_keys.add((departure_name.casefold(), arrival_name.casefold()))
    disruption_key = (
        tuple(sorted(avoid_port_names)),
        tuple(sorted(congested_leg_keys)),
    )
    return avoid_port_names, congested_legs, disruption_key


def _edge_distance(edge: Any) -> float:
    return float(getattr(edge, "total_distance", math.inf))


def _path_duration_hours(path: list[Any]) -> float:
    """Sum of per-edge expected durations for the booking path.

    Each edge contributes ``edge_sailing_hours + 0.5 * headway_hours``.
    """
    total = 0.0
    for edge in path:
        route = getattr(edge, "service_route", None)
        if route is None:
            return math.inf
        edge_distance = _edge_distance(edge)
        if not _is_finite_positive(edge_distance):
            return math.inf
        mean_speed = _route_mean_speed(route)
        if not _is_finite_positive(mean_speed):
            return math.inf
        cycle_distance = _route_cycle_distance(route)
        if not _is_finite_positive(cycle_distance):
            return math.inf
        headway_hours = _route_headway_hours(route, cycle_distance)
        if not _is_finite_positive(headway_hours):
            return math.inf
        edge_sailing_hours = edge_distance / mean_speed
        if not _is_finite_positive(edge_sailing_hours):
            return math.inf
        edge_expected = edge_sailing_hours + 0.5 * headway_hours
        if not _is_finite_positive(edge_expected):
            return math.inf
        total += edge_expected
    return total


def _assign_associated_bookings_impl(context: Any, now: Any, shipment: Any) -> Any:
    """Implementation of the recovery-aware booking hook.

    Returns ``False`` only when every condition succeeds. All other cases
    return ``None``. No mutation occurs.
    """
    demand = getattr(shipment, "demand", None)
    origin_port = getattr(demand, "origin_port", None)
    destination_port = getattr(demand, "destination_port", None)
    if origin_port is None or destination_port is None:
        return None
    if origin_port is destination_port:
        return None
    if not isinstance(now, dt.datetime):
        return None

    # Condition 1: at least one active disruption.
    disruption_plans = list(getattr(context, "disruption_plans", []) or [])
    any_active = False
    for plan in disruption_plans:
        if _plan_active_window(plan, now) is not None:
            any_active = True
            break
    if not any_active:
        return None

    service_routes = list(getattr(context, "service_routes", []) or [])

    # Condition 2: complete nominal path exists using original routes only.
    nominal_edges: list[Any] = []
    for route in service_routes:
        nominal_edges.extend(_route_edges_for_nominal(route))
    nominal_path = _pathfind(
        context,
        nominal_edges,
        origin_port,
        destination_port,
    )
    if not nominal_path:
        return None

    # Condition 3: nominal path intersects at least one active disruption.
    avoid_port_names, congested_legs, disruption_key = _collect_active_disruption_keys(context, now)
    intersects = False
    for plan in disruption_plans:
        if _plan_active_window(plan, now) is None:
            continue
        if _plan_intersects_path(plan, nominal_path):
            intersects = True
            break
    if not intersects:
        return None

    # Recovery time is the latest end among active plans intersecting the
    # nominal path.
    recovery_time = _latest_intersecting_recovery(context, now, nominal_path)
    if recovery_time is None:
        return None

    # Condition 4: complete disruption-safe path currently exists.
    safe_edges: list[Any] = []
    for route in service_routes:
        safe_edges.extend(
            _route_edges_for_safe(route, avoid_port_names, congested_legs, disruption_key)
        )
    safe_path = _pathfind(
        context,
        safe_edges,
        origin_port,
        destination_port,
    )
    if not safe_path:
        return None

    # Condition 5: both paths have valid deterministic durations.
    nominal_hours = _path_duration_hours(nominal_path)
    safe_hours = _path_duration_hours(safe_path)
    if not _is_finite_positive(nominal_hours) or not _is_finite_positive(safe_hours):
        return None

    # Hours until relevant recovery.
    try:
        wait_hours = (recovery_time - now).total_seconds() / 3600.0
    except (TypeError, ValueError, OverflowError):
        return None
    if not _is_finite_nonnegative(wait_hours):
        return None

    wait_then_nominal = wait_hours + nominal_hours
    safe_now = safe_hours
    if not _is_finite_positive(wait_then_nominal) or not _is_finite_positive(safe_now):
        return None

    # Strict comparison only: equality delegates with ``None``.
    if wait_then_nominal < safe_now:
        return False
    return None


class UserStrategy:
    """Behavior-neutral participant adapter with a recovery-aware booking hook.

    Only ``assign_associated_bookings`` is non-trivial: it returns ``False``
    when waiting for the relevant disruption recovery is predicted to
    complete strictly earlier than the fallback's safe detour, and
    ``None`` otherwise. The other three hooks return ``None``
    unconditionally.
    """

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

        Returns ``False`` when waiting for the relevant disruption recovery
        is predicted to complete strictly earlier than the fallback's safe
        detour. Otherwise returns ``None`` to use the organizer fallback.
        No mutation occurs on either path.
        """
        try:
            return _assign_associated_bookings_impl(context, now, shipment)
        except _NARROW_EXCEPTIONS:
            return None

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Adjust booking chains before a vessel handles cargo.

        Returns ``None`` to use the organizer fallback.
        """
        return None
