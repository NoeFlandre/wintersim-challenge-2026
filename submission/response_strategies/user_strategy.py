"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling.

Round 0 experiment: temporal lower-bound safe routing during active
disruptions (v1).

Policy
------

The candidate overrides ``assign_associated_bookings`` only when **all** of
these are true:

1. At least one disruption plan is currently active.
2. The shipment's nominal distance-shortest path over original service routes
   touches at least one currently active closed port or congested leg.
3. For every active disrupted resource touched by that nominal path, the
   earliest physically possible encounter is at or after that plan's recovery
   time, using the documented optimistic lower-bound model:

   - transfer waits, berth waits, cargo handling, and all other delays are
     zero in this calculation (intentionally optimistic);
   - each booking edge is sailed at 1.05x the fastest valid sailing speed
     among the original route's currently deployed vessels (the organizer's
     maximum fast-sailing variation);
   - disruption multipliers are ignored (ignoring them makes arrival earlier
     and therefore keeps the proof conservative);
   - an encounter at exactly the recovery instant is safe because the
     active interval is end-exclusive (``start <= now < end``).
4. A complete valid nominal booking chain exists.

If all conditions hold, the candidate atomically assigns that nominal path and
returns exactly ``True``. Otherwise, it returns exactly ``None`` without
mutating any input.

The other three hooks remain unconditional ``None`` delegates.

The candidate never returns ``False``.

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only, plus documented organizer modules available at
  evaluation runtime.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterable
from typing import Any, NamedTuple

# The Booking type lives in the organizer's ``maritime_data_context`` module
# and is imported lazily at runtime so that unit tests can inject a fake
# module into ``sys.modules`` before triggering the override path. The
# fallback no-op hooks never touch this binding.
_Booking: Any = None


def _get_booking_class() -> Any:
    """Lazy lookup of the organizer Booking class.

    Falls back to ``None`` if the module is unavailable, in which case the
    override path simply delegates.
    """
    global _Booking
    if _Booking is not None:
        return _Booking
    try:
        from maritime_data_context import Booking as OrganizerBooking
    except Exception:
        return None
    _Booking = OrganizerBooking
    return _Booking


class _Edge(NamedTuple):
    """Immutable candidate booking edge over original service routes."""

    service_route: Any
    departure_port: Any
    arrival_port: Any
    departure_segment_index: int
    arrival_segment_index: int
    total_distance: float


class _ActiveConstraint(NamedTuple):
    """One active disruption resource encountered along the path."""

    target: Any
    recovery_time: dt.datetime
    encounter_time: dt.datetime


# Lower-bound physical constants.
_FAST_SAILING_FACTOR: float = 1.05


class UserStrategy:
    """Participant adapter for the temporal safe-routing experiment."""

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

        Unconditional ``None`` delegate to the organizer fallback.
        """
        return None

    @staticmethod
    def create_alternative_service_routes(context: Any, now: Any, vessel: Any = None) -> Any:
        """Build alternative service routes for a vessel.

        Unconditional ``None`` delegate ("not handled") which must leave
        ``context`` unchanged.
        """
        return None

    @staticmethod
    def assign_associated_bookings(context: Any, now: Any, shipment: Any) -> Any:
        """Assign a complete booking chain for a shipment.

        Returns ``True`` only when the temporal lower-bound proof shows that
        every active disrupted resource touched by the nominal path is
        encountered strictly after its recovery instant (end-exclusive). The
        path is installed atomically.

        Otherwise returns ``None`` to use the organizer fallback, leaving all
        reachable state unchanged.
        """
        return _assign_associated_bookings_temporal_lower_bound(context, now, shipment)

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Adjust booking chains before a vessel handles cargo.

        Unconditional ``None`` delegate to the organizer fallback.
        """
        return None


# ---------------------------------------------------------------------------
# Public entry point for the temporal-safe-routing experiment
# ---------------------------------------------------------------------------


def _assign_associated_bookings_temporal_lower_bound(context: Any, now: Any, shipment: Any) -> Any:
    """Return ``True`` with a valid nominal chain, or ``None`` to delegate."""
    # The other hooks are always None; this entry point is the only override.
    if context is None or shipment is None or now is None:
        return None

    demand = getattr(shipment, "demand", None)
    if demand is None:
        return None
    origin_port = getattr(demand, "origin_port", None)
    destination_port = getattr(demand, "destination_port", None)
    if origin_port is None or destination_port is None:
        return None
    if origin_port is destination_port:
        # Trivial same-origin/destination case: delegate to organizer.
        return None

    # Build the active recovery constraints FIRST so we can early-out cheaply
    # when there is no active disruption at all.
    active_constraints = _collect_active_constraints(context, now)
    if not active_constraints:
        return None

    edges, speed_per_route = _build_nominal_edges(context)
    if not edges:
        return None

    path = _find_shortest_path(context, origin_port, destination_port, edges)
    if not path:
        return None

    constraints = _evaluate_path(path, speed_per_route, now, active_constraints)
    if constraints is None:
        return None

    try:
        return _install_path(shipment, path)
    except _BookingUnavailable:
        # The organizer's Booking class is unavailable at runtime; safe-fail
        # to delegation so the candidate never returns ``False``.
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_plan_active(plan: Any, now: dt.datetime) -> bool:
    """True iff ``start <= now < end`` for the given disruption plan."""
    start_offset = getattr(plan, "start_offset_days", None)
    duration = getattr(plan, "duration_days", None)
    if start_offset is None or duration is None:
        return False
    start = dt.datetime.min + dt.timedelta(days=float(start_offset))
    end = start + dt.timedelta(days=float(duration))
    return start <= now < end


def _collect_active_constraints(context: Any, now: dt.datetime) -> dict[Any, dt.datetime]:
    """Return ``{target: latest_recovery_time}`` for every active disruption.

    For duplicate closed-berth plans at one port, the latest active recovery
    time for that port controls. A congested leg plan keys on the leg
    instance directly.
    """
    latest_recovery: dict[Any, dt.datetime] = {}
    for plan in context.disruption_plans:
        if not _is_plan_active(plan, now):
            continue
        target_berth = getattr(plan, "target_berth", None)
        target_leg = getattr(plan, "target_leg", None)
        close_berth = bool(getattr(plan, "close_berth", False))
        multiplier = float(getattr(plan, "multiplier", 1.0) or 1.0)
        start_offset = float(getattr(plan, "start_offset_days", 0.0))
        duration = float(getattr(plan, "duration_days", 0.0))
        end = dt.datetime.min + dt.timedelta(days=start_offset + duration)
        if close_berth and target_berth is not None:
            port = getattr(target_berth, "port", None)
            if port is not None:
                current = latest_recovery.get(port)
                if current is None or end > current:
                    latest_recovery[port] = end
        elif multiplier > 1.0 and target_leg is not None:
            current = latest_recovery.get(target_leg)
            if current is None or end > current:
                latest_recovery[target_leg] = end
    return latest_recovery


def _build_nominal_edges(context: Any) -> tuple[list[_Edge], dict[int, float]]:
    """Build every proper contiguous slice of every original cyclic route.

    Returns:
        edges: list of candidate booking edges
        speed_per_route: dict mapping ``id(route)`` to its fastest deployed
            vessel's sailing speed (knots). Routes without deployed vessels or
            with nonpositive/missing speed are excluded.
    """
    speed_per_route: dict[int, float] = {}
    for route in context.service_routes:
        if getattr(route, "source_service_route", None) is not None:
            # Alternative route: exclude from the nominal graph.
            continue
        speed = _fastest_deployed_speed(route)
        if speed is None:
            continue
        speed_per_route[id(route)] = speed

    edges: list[_Edge] = []
    for route in context.service_routes:
        if id(route) not in speed_per_route:
            continue
        segments = sorted(
            getattr(route, "segments", []),
            key=lambda segment: segment.sequence_index,
        )
        segment_count = len(segments)
        if segment_count == 0:
            continue
        for start_index in range(segment_count):
            departure_port = segments[start_index].associated_leg.departure_port
            cumulative_distance = 0.0
            # Proper contiguous slices: length 1..segment_count. A slice of
            # length ``segment_count`` is the full cycle; if the cycle
            # returns to its origin port we drop it (never create a
            # same-origin same-origin edge). Otherwise the cycle is a
            # legitimate edge (rare in practice).
            for step in range(1, segment_count + 1):
                segment_index = (start_index + step - 1) % segment_count
                leg = segments[segment_index].associated_leg
                cumulative_distance += float(leg.sailing_distance)
                arrival_port = leg.arrival_port
                if departure_port is arrival_port:
                    # Whole-cycle origin-to-same-origin edge: never create.
                    continue
                edges.append(
                    _Edge(
                        service_route=route,
                        departure_port=departure_port,
                        arrival_port=arrival_port,
                        departure_segment_index=start_index + 1,
                        arrival_segment_index=segment_index + 1,
                        total_distance=cumulative_distance,
                    )
                )
    return edges, speed_per_route


def _fastest_deployed_speed(route: Any) -> float | None:
    """Return the fastest positive sailing speed among ``route.deployed_vessels``."""
    vessels: Iterable[Any] = getattr(route, "deployed_vessels", [])
    fastest: float | None = None
    for vessel in vessels:
        vessel_class = getattr(vessel, "vessel_class", None)
        if vessel_class is None:
            continue
        speed = getattr(vessel_class, "sailing_speed", None)
        if speed is None:
            continue
        try:
            speed_value = float(speed)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(speed_value) or speed_value <= 0.0:
            continue
        if fastest is None or speed_value > fastest:
            fastest = speed_value
    return fastest


def _find_shortest_path(
    context: Any, origin_port: Any, destination_port: Any, edges: list[_Edge]
) -> list[_Edge] | None:
    """Deterministic Dijkstra over the original-route edge set."""
    outgoing: dict[Any, list[_Edge]] = {}
    for edge in edges:
        outgoing.setdefault(edge.departure_port, []).append(edge)

    # Initial distances in ``context.ports`` order so ties are deterministic.
    distances: dict[Any, float] = dict.fromkeys(context.ports, math.inf)
    previous_edge: dict[Any, _Edge] = {}
    distances[origin_port] = 0.0
    unvisited: set[Any] = set(distances)

    while unvisited:
        current = min(unvisited, key=lambda port: distances[port])
        if math.isinf(distances[current]) or current is destination_port:
            break
        unvisited.remove(current)
        for outgoing_edge in outgoing.get(current, []):
            next_port = outgoing_edge.arrival_port
            if next_port not in unvisited:
                continue
            alternative = distances[current] + outgoing_edge.total_distance
            # Strict-less-only update preserves Dijkstra determinism.
            if alternative < distances[next_port]:
                distances[next_port] = alternative
                previous_edge[next_port] = outgoing_edge

    if destination_port not in previous_edge:
        return None
    path: list[_Edge] = []
    cursor: Any = destination_port
    while cursor is not origin_port:
        back_edge: _Edge | None = previous_edge.get(cursor)
        if back_edge is None:
            return None
        path.append(back_edge)
        cursor = back_edge.departure_port
    path.reverse()
    return path


def _evaluate_path(
    path: list[_Edge],
    speed_per_route: dict[int, float],
    now: dt.datetime,
    active_constraints: dict[Any, dt.datetime],
) -> dict[Any, dt.datetime] | None:
    """Forecast every active-resource encounter along ``path``.

    Returns a ``{target: encounter_time}`` mapping on success. Returns
    ``None`` if:

    * any active constraint has an unsafe encounter (its encounter happens
      before its recovery instant);
    * the path touches no active disruption (the override condition #2 is
      not met, so the candidate must delegate).

    The forecast uses the documented optimistic lower-bound model: zero
    transfer/berth/handling waits; each leg is sailed at 1.05x the route's
    fastest deployed speed; disruption multipliers are ignored.
    """
    encounters: dict[Any, dt.datetime] = {}
    elapsed_days = 0.0

    for edge in path:
        speed = speed_per_route.get(id(edge.service_route))
        if speed is None or speed <= 0.0:
            return None
        speed_effective = speed * _FAST_SAILING_FACTOR

        # Closed origin port: encounter at elapsed zero.
        origin_target = active_constraints.get(edge.departure_port)
        if origin_target is not None:
            encounter = now + dt.timedelta(days=elapsed_days)
            if encounter < origin_target:
                return None
            encounters[edge.departure_port] = encounter

        # Walk every leg in this edge in order, recording the time the
        # vessel arrives at the end of each leg and the time it is about
        # to sail it.
        segments = sorted(
            getattr(edge.service_route, "segments", []),
            key=lambda segment: segment.sequence_index,
        )
        segment_indexes = _segment_indexes_for_edge(edge, segments)
        leg_elapsed_within_edge = 0.0
        for seq_index in segment_indexes:
            seg = segments[seq_index - 1]
            leg = seg.associated_leg
            leg_distance = float(leg.sailing_distance)
            leg_travel_days = leg_distance / speed_effective / 24.0

            # Congested-leg constraint: encountered immediately BEFORE
            # sailing this leg (i.e. at the start of the leg).
            leg_target = active_constraints.get(leg)
            if leg_target is not None:
                before_sailing = elapsed_days + leg_elapsed_within_edge
                encounter = now + dt.timedelta(days=before_sailing)
                if encounter < leg_target:
                    return None
                encounters[leg] = encounter

            # Advance within-edge elapsed time so we can also check the
            # arrival port of this leg AFTER sailing it.
            leg_elapsed_within_edge += leg_travel_days

            # Closed port constraint at this leg's arrival port: encountered
            # AFTER sailing into it. The final leg's arrival port equals the
            # edge's arrival port; this check covers both.
            leg_arrival_port = leg.arrival_port
            port_target = active_constraints.get(leg_arrival_port)
            if port_target is not None:
                after_arrival = elapsed_days + leg_elapsed_within_edge
                encounter = now + dt.timedelta(days=after_arrival)
                if encounter < port_target:
                    return None
                encounters[leg_arrival_port] = encounter

        # Advance the global elapsed counter to the end of this edge.
        elapsed_days += leg_elapsed_within_edge

    # Condition #2: the path must touch at least one currently active
    # disrupted resource. If it does not, delegate so the organizer fallback
    # can apply its disruption-aware assignment.
    if not encounters:
        return None

    return encounters


def _segment_indexes_for_edge(edge: _Edge, segments: list[Any]) -> list[int]:
    """Return the segment sequence-indexes covered by ``edge``."""
    start = edge.departure_segment_index
    end = edge.arrival_segment_index
    count = len(segments)
    if start == end:
        return [start]
    indexes: list[int] = []
    cursor = start
    while True:
        indexes.append(cursor)
        if cursor == end:
            break
        cursor = cursor + 1 if cursor < count else 1
    return indexes


class _BookingUnavailable(Exception):
    """Raised internally when the organizer Booking class cannot be imported.

    The public override method catches this and returns ``None`` so that the
    candidate never returns ``False``.
    """


def _install_path(shipment: Any, path: list[_Edge]) -> bool:
    """Atomically install the booking chain and return ``True``.

    Raises :class:`_BookingUnavailable` when the organizer Booking class is
    not available at runtime; the public entry point translates that into a
    ``None`` delegation.
    """
    booking_cls = _get_booking_class()
    if booking_cls is None:
        raise _BookingUnavailable()

    # 1. Construct every Booking object before mutating any state.
    new_bookings: list[Any] = []
    for sequence_index, edge in enumerate(path, start=1):
        new_bookings.append(
            booking_cls(
                sequence_index=sequence_index,
                shipment=shipment,
                service_route=edge.service_route,
                departure_segment_index=edge.departure_segment_index,
                arrival_segment_index=edge.arrival_segment_index,
            )
        )

    # 2. Remove old bookings from their service routes' associated_bookings.
    old_bookings = list(getattr(shipment, "associated_bookings", []))
    for old in old_bookings:
        old_route = getattr(old, "service_route", None)
        if old_route is None:
            continue
        associated = getattr(old_route, "associated_bookings", None)
        if associated is None:
            continue
        while old in associated:
            associated.remove(old)

    # 3. Replace shipment.associated_bookings.
    shipment.associated_bookings = list(new_bookings)

    # 4. Append each new booking to its service route.
    for booking in new_bookings:
        route = booking.service_route
        associated = getattr(route, "associated_bookings", None)
        if associated is None:
            continue
        associated.append(booking)

    # 5. Set current_booking_index to 1.
    shipment.current_booking_index = 1

    return True
