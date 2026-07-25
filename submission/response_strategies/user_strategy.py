"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

Only ``create_alternative_service_routes`` extends behavior. It implements the
standard alternative-route reservation, switching, and recovery lifecycle,
then creates a deterministic recovery shuttle when an affected original route
has no complete safe alternative. The shuttle uses only existing safe legs and
can take one empty vessel at its start port. The other three hooks delegate.

Top-level imports are standard-library-only so public CI can import this module
without the private organizer tree. Documented maritime entity classes are
resolved locally inside the route hook and are never cached.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _DisruptionState:
    closed_ports: tuple[Any, ...]
    congested_legs: tuple[Any, ...]
    safe_legs: tuple[Any, ...]
    key: tuple[tuple[str, ...], tuple[tuple[str, str], ...]]


@dataclass(frozen=True)
class _RecoveryPlan:
    start_port: Any
    legs: tuple[Any, ...]


def _append_identity_unique(values: list[Any], value: Any) -> None:
    if not any(existing is value for existing in values):
        values.append(value)


def _leg_key(leg: Any) -> tuple[str, str]:
    return (
        leg.departure_port.name.casefold(),
        leg.arrival_port.name.casefold(),
    )


def _active_disruption_state(context: Any, now: Any) -> _DisruptionState | None:
    """Return active closed ports, congested legs, safe legs, and fallback key."""
    closed_ports: list[Any] = []
    congested_legs: list[Any] = []
    for disruption in context.disruption_plans:
        try:
            start_offset = disruption.start_offset_days
            duration = disruption.duration_days
            if start_offset is None or duration is None:
                continue
            start = dt.datetime.min + dt.timedelta(days=start_offset)
            end = start + dt.timedelta(days=duration)
        except (AttributeError, TypeError, ValueError, OverflowError):
            continue
        if not start <= now < end:
            continue

        berth = getattr(disruption, "target_berth", None)
        if bool(getattr(disruption, "close_berth", False)) and berth is not None:
            port = getattr(berth, "port", None)
            if port is not None:
                _append_identity_unique(closed_ports, port)

        leg = getattr(disruption, "target_leg", None)
        multiplier = getattr(disruption, "multiplier", 1)
        try:
            congested = multiplier > 1
        except TypeError:
            congested = False
        if congested and leg is not None:
            _append_identity_unique(congested_legs, leg)

    if not closed_ports and not congested_legs:
        return None

    safe_legs = tuple(
        leg for leg in context.legs if _is_safe_leg(leg, tuple(closed_ports), tuple(congested_legs))
    )
    key = (
        tuple(sorted(port.name.casefold() for port in closed_ports)),
        tuple(sorted(_leg_key(leg) for leg in congested_legs)),
    )
    return _DisruptionState(
        tuple(closed_ports),
        tuple(congested_legs),
        safe_legs,
        key,
    )


def _is_safe_leg(
    leg: Any,
    closed_ports: tuple[Any, ...],
    congested_legs: tuple[Any, ...],
) -> bool:
    if any(leg is congested for congested in congested_legs):
        return False
    departure = leg.departure_port
    arrival = leg.arrival_port
    return not any(port is departure or port is arrival for port in closed_ports)


def _reachable_ports(start: Any, safe_legs: tuple[Any, ...]) -> tuple[Any, ...]:
    reached = [start]
    cursor = 0
    while cursor < len(reached):
        current = reached[cursor]
        cursor += 1
        for leg in safe_legs:
            if leg.departure_port is not current:
                continue
            next_port = leg.arrival_port
            if not any(port is next_port for port in reached):
                reached.append(next_port)
    return tuple(reached)


def _find_shortest_leg_path(
    context: Any,
    origin_port: Any,
    destination_port: Any,
    safe_legs: tuple[Any, ...],
) -> tuple[Any, ...] | None:
    """Distance-shortest safe path with context-order deterministic ties."""
    if origin_port is destination_port:
        return ()
    distances = dict.fromkeys(context.ports, math.inf)
    if origin_port not in distances or destination_port not in distances:
        return None
    previous_leg: dict[Any, Any] = {}
    unvisited = list(context.ports)
    distances[origin_port] = 0.0

    while unvisited:
        current = min(unvisited, key=distances.__getitem__)
        if math.isinf(distances[current]) or current is destination_port:
            break
        unvisited.remove(current)
        for leg in safe_legs:
            if leg.departure_port is not current:
                continue
            next_port = leg.arrival_port
            if next_port not in unvisited:
                continue
            alternative = distances[current] + leg.sailing_distance
            if alternative < distances[next_port]:
                distances[next_port] = alternative
                previous_leg[next_port] = leg

    if destination_port not in previous_leg:
        return None
    path: list[Any] = []
    cursor = destination_port
    while cursor is not origin_port:
        leg = previous_leg.get(cursor)
        if leg is None:
            return None
        path.append(leg)
        cursor = leg.departure_port
    path.reverse()
    return tuple(path)


def _unique_source_anchors(
    source_route: Any,
    closed_ports: tuple[Any, ...],
) -> list[Any]:
    anchors: list[Any] = []
    for segment in sorted(source_route.segments, key=lambda item: item.sequence_index):
        port = segment.associated_leg.departure_port
        if any(port is closed for closed in closed_ports):
            continue
        _append_identity_unique(anchors, port)
    return anchors


def _largest_mutually_reachable_component(
    anchors: list[Any],
    safe_legs: tuple[Any, ...],
) -> list[Any]:
    reachable = {anchor: _reachable_ports(anchor, safe_legs) for anchor in anchors}
    assigned: list[Any] = []
    best: list[Any] = []
    for anchor in anchors:
        if any(anchor is known for known in assigned):
            continue
        component = [
            candidate
            for candidate in anchors
            if any(candidate is port for port in reachable[anchor])
            and any(anchor is port for port in reachable[candidate])
        ]
        for member in component:
            _append_identity_unique(assigned, member)
        if len(component) > len(best):
            best = component
    return best


def _build_cycle_plan(
    context: Any,
    anchors: list[Any],
    start_port: Any,
    safe_legs: tuple[Any, ...],
) -> _RecoveryPlan | None:
    if len(anchors) < 2 or not any(start_port is port for port in anchors):
        return None

    start_index = next(index for index, port in enumerate(anchors) if port is start_port)
    ordered_anchors = anchors[start_index:] + anchors[:start_index]
    route_legs: list[Any] = []
    for index, departure in enumerate(ordered_anchors):
        arrival = ordered_anchors[(index + 1) % len(ordered_anchors)]
        path = _find_shortest_leg_path(
            context,
            departure,
            arrival,
            safe_legs,
        )
        if not path:
            return None
        route_legs.extend(path)

    if not route_legs or route_legs[0].departure_port is not start_port:
        return None
    for left, right in zip(route_legs, route_legs[1:], strict=False):
        if left.arrival_port is not right.departure_port:
            return None
    if route_legs[-1].arrival_port is not start_port:
        return None
    return _RecoveryPlan(start_port, tuple(route_legs))


def _build_complete_alternative_plan(
    context: Any,
    source_route: Any,
    closed_ports: tuple[Any, ...],
    congested_legs: tuple[Any, ...],
) -> _RecoveryPlan | None:
    safe_legs = tuple(
        leg for leg in context.legs if _is_safe_leg(leg, closed_ports, congested_legs)
    )
    anchors = _unique_source_anchors(source_route, closed_ports)
    if not anchors:
        return None
    return _build_cycle_plan(context, anchors, anchors[0], safe_legs)


def _build_recovery_plan(
    context: Any,
    source_route: Any,
    closed_ports: tuple[Any, ...],
    congested_legs: tuple[Any, ...],
) -> _RecoveryPlan | None:
    safe_legs = tuple(
        leg for leg in context.legs if _is_safe_leg(leg, closed_ports, congested_legs)
    )
    anchors = _unique_source_anchors(source_route, closed_ports)
    component = _largest_mutually_reachable_component(anchors, safe_legs)
    if len(component) < 2:
        return None

    start_port = component[0]
    for segment in sorted(source_route.segments, key=lambda item: item.sequence_index):
        leg = segment.associated_leg
        if _is_safe_leg(leg, closed_ports, congested_legs):
            continue
        departure = leg.departure_port
        if any(departure is port for port in component):
            start_port = departure
            break

    return _build_cycle_plan(context, component, start_port, safe_legs)


def _source_route_is_affected(source_route: Any, state: _DisruptionState) -> bool:
    return any(
        not _is_safe_leg(
            segment.associated_leg,
            state.closed_ports,
            state.congested_legs,
        )
        for segment in source_route.segments
    )


def _matching_alternatives(
    context: Any,
    source_route: Any,
    disruption_key: Any,
) -> list[Any]:
    return [
        route
        for route in context.service_routes
        if getattr(route, "source_service_route", None) is source_route
        and getattr(route, "disruption_key", None) == disruption_key
    ]


def _next_route_id(context: Any, source_route: Any, suffix: str) -> str:
    existing = {str(route.id).casefold() for route in context.service_routes}
    index = 1
    while True:
        route_id = f"{source_route.id}-{suffix}-{index}"
        if route_id.casefold() not in existing:
            return route_id
        index += 1


def _install_alternative_route(
    context: Any,
    source_route: Any,
    disruption_key: Any,
    plan: _RecoveryPlan,
    service_route_type: Any,
    segment_type: Any,
    *,
    recovery_shuttle: bool,
) -> Any:
    suffix = "RECOVERY" if recovery_shuttle else "ALT"
    label = "Recovery Shuttle" if recovery_shuttle else "Disruption Alternative"
    route_id = _next_route_id(context, source_route, suffix)
    route = service_route_type(
        route_id,
        f"{source_route.name} {label}",
        source_route.start_day_of_week,
    )
    route.source_service_route = source_route
    route.disruption_key = disruption_key
    route.is_participant_recovery_shuttle = recovery_shuttle
    segments = [segment_type(index, leg, route) for index, leg in enumerate(plan.legs, start=1)]
    route.segments.extend(segments)

    for segment in segments:
        segment.associated_leg.segments.append(segment)
        context.partial_service_routes.append(segment)
    context.service_routes.append(route)
    return route


def _vessel_current_port(vessel: Any) -> Any:
    current_segment = getattr(vessel, "current_segment", None)
    if current_segment is not None:
        leg = getattr(current_segment, "associated_leg", None)
        if leg is not None:
            return getattr(leg, "arrival_port", None)
    current_berth = getattr(vessel, "current_berth", None)
    return getattr(current_berth, "port", None)


def _clear_pending_shuttle_assignments(context: Any, shuttle: Any) -> None:
    for vessel in context.vessels:
        if getattr(vessel, "pending_assigned_service_route", None) is shuttle:
            vessel.pending_assigned_service_route = None


def _try_switch_empty_vessel(
    context: Any,
    vessel: Any,
    source_route: Any,
    shuttle: Any,
) -> bool:
    if vessel is None or source_route is None or getattr(vessel, "carried_shipments", None):
        return False
    if getattr(vessel, "assigned_service_route", None) is not source_route:
        return False
    if getattr(vessel, "pending_assigned_service_route", None) is not None:
        return False
    if any(candidate.assigned_service_route is shuttle for candidate in context.vessels):
        return False
    if not shuttle.segments:
        return False
    start_segment = min(shuttle.segments, key=lambda item: item.sequence_index)
    start_port = start_segment.associated_leg.departure_port
    if _vessel_current_port(vessel) is not start_port:
        return False

    current_segment = vessel.current_segment
    if current_segment is not None:
        while vessel in current_segment.current_vessels:
            current_segment.current_vessels.remove(vessel)
    source_deployed_vessels = getattr(source_route, "deployed_vessels", None)
    if source_deployed_vessels is None:
        return False
    while vessel in source_deployed_vessels:
        source_deployed_vessels.remove(vessel)
    if vessel not in shuttle.deployed_vessels:
        shuttle.deployed_vessels.append(vessel)
    vessel.assigned_service_route = shuttle
    vessel.pending_assigned_service_route = None
    vessel.current_segment = None
    return True


def _reserve_one_source_vessel(context: Any, source_route: Any, alternative: Any) -> None:
    if any(
        getattr(vessel, "assigned_service_route", None) is alternative
        or getattr(vessel, "pending_assigned_service_route", None) is alternative
        for vessel in context.vessels
    ):
        return
    for vessel in sorted(source_route.deployed_vessels, key=lambda item: item.index):
        if getattr(vessel, "assigned_service_route", None) is not source_route:
            continue
        if getattr(vessel, "pending_assigned_service_route", None) is not None:
            continue
        vessel.pending_assigned_service_route = alternative
        return


def _try_switch_pending_vessel(vessel: Any) -> bool:
    if vessel is None or getattr(vessel, "carried_shipments", None):
        return False
    alternative = getattr(vessel, "pending_assigned_service_route", None)
    if alternative is None or not getattr(alternative, "segments", None):
        return False
    first_segment = min(alternative.segments, key=lambda item: item.sequence_index)
    if _vessel_current_port(vessel) is not first_segment.associated_leg.departure_port:
        return False

    current_segment = getattr(vessel, "current_segment", None)
    if current_segment is not None:
        while vessel in current_segment.current_vessels:
            current_segment.current_vessels.remove(vessel)
    source_route = getattr(vessel, "assigned_service_route", None)
    if source_route is not None:
        while vessel in source_route.deployed_vessels:
            source_route.deployed_vessels.remove(vessel)
    if vessel not in alternative.deployed_vessels:
        alternative.deployed_vessels.append(vessel)
    vessel.assigned_service_route = alternative
    vessel.pending_assigned_service_route = None
    vessel.current_segment = None
    return True


def _find_reentry_segment(source_route: Any, port: Any) -> Any:
    segments = sorted(source_route.segments, key=lambda item: item.sequence_index)
    for segment in segments:
        if segment.associated_leg.arrival_port is port:
            return segment
    return None


def _try_restore_empty_vessel(vessel: Any) -> bool:
    if vessel is None or getattr(vessel, "carried_shipments", None):
        return False
    alternative = getattr(vessel, "assigned_service_route", None)
    if alternative is None:
        return False
    source_route = getattr(alternative, "source_service_route", None)
    if source_route is None:
        return False
    port = _vessel_current_port(vessel)
    if port is None:
        return False
    reentry_segment = _find_reentry_segment(source_route, port)
    if reentry_segment is None:
        return False

    current_segment = getattr(vessel, "current_segment", None)
    if current_segment is not None:
        while vessel in current_segment.current_vessels:
            current_segment.current_vessels.remove(vessel)
    while vessel in alternative.deployed_vessels:
        alternative.deployed_vessels.remove(vessel)
    if vessel not in source_route.deployed_vessels:
        source_route.deployed_vessels.append(vessel)
    vessel.assigned_service_route = source_route
    vessel.pending_assigned_service_route = None
    vessel.current_segment = reentry_segment
    if vessel not in reentry_segment.current_vessels:
        reentry_segment.current_vessels.append(vessel)
    return True


def _restore_inactive_assignments(
    context: Any,
    active_disruption_key: Any,
    vessel: Any,
) -> None:
    candidates = [vessel] if vessel is not None else list(context.vessels)
    for candidate in candidates:
        if candidate is None:
            continue
        pending = getattr(candidate, "pending_assigned_service_route", None)
        if (
            getattr(pending, "source_service_route", None) is not None
            and getattr(pending, "disruption_key", None) != active_disruption_key
        ):
            candidate.pending_assigned_service_route = None

        assigned = getattr(candidate, "assigned_service_route", None)
        if (
            getattr(assigned, "source_service_route", None) is None
            or getattr(assigned, "disruption_key", None) == active_disruption_key
        ):
            continue
        _try_restore_empty_vessel(candidate)


class UserStrategy:
    """Participant adapter with one safe recovery-shuttle extension."""

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
    def create_alternative_service_routes(
        context: Any,
        now: Any,
        vessel: Any = None,
    ) -> Any:
        from maritime_data_context import Segment, ServiceRoute

        state = _active_disruption_state(context, now)
        active_key = state.key if state is not None else ((), ())
        _restore_inactive_assignments(context, active_key, vessel)
        if state is None:
            return True

        for source_route in tuple(context.initial_service_routes):
            if not _source_route_is_affected(source_route, state):
                continue
            matching = _matching_alternatives(context, source_route, state.key)
            alternative = matching[0] if matching else None
            if alternative is None:
                plan = _build_complete_alternative_plan(
                    context,
                    source_route,
                    state.closed_ports,
                    state.congested_legs,
                )
                recovery_shuttle = plan is None
                if recovery_shuttle:
                    plan = _build_recovery_plan(
                        context,
                        source_route,
                        state.closed_ports,
                        state.congested_legs,
                    )
                if plan is None:
                    continue
                alternative = _install_alternative_route(
                    context,
                    source_route,
                    state.key,
                    plan,
                    ServiceRoute,
                    Segment,
                    recovery_shuttle=recovery_shuttle,
                )
            if bool(getattr(alternative, "is_participant_recovery_shuttle", False)):
                _clear_pending_shuttle_assignments(context, alternative)
                _try_switch_empty_vessel(context, vessel, source_route, alternative)
            else:
                _reserve_one_source_vessel(context, source_route, alternative)
                _try_switch_pending_vessel(vessel)
        return True

    @staticmethod
    def assign_associated_bookings(
        context: Any,
        now: Any,
        shipment: Any,
    ) -> Any:
        return None

    @staticmethod
    def adjust_bookings_before_cargo_handling(
        context: Any,
        now: Any,
        vessel: Any,
    ) -> Any:
        return None
