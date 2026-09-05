"""Participant-owned response strategy for the WSC 2026 challenge.

The strategy owns one decision: the initial booking chain for newly generated
cargo. The organizer's fallback chooses that chain by minimising sailing
distance, which ignores how often each service actually departs; a booking that
saves a few nautical miles by adding a transshipment can cost days of waiting
for the next vessel. This strategy instead minimises *estimated transport
time* - sailing time at the live leg multipliers, one departure wait per
service route used, and the organizer's fixed berthing time for each
intermediate port call.

Every quantity is read from the supplied runtime objects. The strategy is
deterministic, standard-library-only, performs no I/O, keeps no state between
calls, and delegates to the organizer fallback whenever the runtime data is
malformed, ambiguous, or would force cargo across a congested leg that no
alternative path avoids.

It also owns one veto. When a disruption appears after cargo is already at sea,
the organizer replans the rest of its journey by sailing distance and by
refusing the disrupted ports and legs outright, which can be much slower than
simply staying aboard and waiting the disruption out. Where the same cost model
says the booked chain already beats the best alternative, the strategy keeps it.

Finally it owns the fleet decision. When a slowdown lands on a service's
rotation, the strategy moves the *whole* service onto a detour around it built
from existing legs - but only when that detour still calls every port the
rotation calls and its cycle is strictly shorter at the speeds now in force.
The organizer's own response reserves a single vessel onto such a route, which
leaves the original rotation both slow and thinned; moving the service keeps
its frequency and drops the slowdown. A shut port is never routed around, and
a rotation is never left without vessels while cargo is still booked on it.
Berth selection stays delegated.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import heapq
import math
import numbers
from typing import Any, NamedTuple

from maritime_data_context import Booking, Segment, ServiceRoute

# The organizer's BerthBerthing activity has a fixed three-hour duration. It is
# charged once for every intermediate port call inside a single booking, so a
# long way round the same rotation is not treated as free.
_BERTHING_HOURS = 3.0


class _Edge(NamedTuple):
    """One bookable ride: route ``route_index`` from one port to another."""

    departure_index: int
    arrival_index: int
    route_index: int
    departure_segment_index: int
    arrival_segment_index: int
    hours: float
    crosses_congestion: bool
    # Per-leg schedule, present only when this ride meets a live disruption.
    # Each entry is (hours at normal speed, the multiplier in force now, hours
    # until that multiplier lifts, hours until the arrival port reopens), with
    # ``inf`` for a multiplier whose end cannot be established and ``0.0`` for
    # an arrival that is open. ``None`` means nothing on this ride is disrupted,
    # which keeps the common case a single addition.
    timeline: tuple[tuple[float, float, float, float], ...] | None


class _Network(NamedTuple):
    edges: tuple[_Edge, ...]
    routes: tuple[Any, ...]
    boarding_hours: tuple[float, ...]


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


def _sequence(value: Any) -> tuple[Any, ...] | None:
    return tuple(value) if isinstance(value, (list, tuple)) else None


def _port_indexes(context: Any) -> dict[int, int] | None:
    """Map port identity to its position in ``context.ports``."""
    ports = _sequence(getattr(context, "ports", None))
    if not ports:
        return None
    indexes: dict[int, int] = {}
    for position, port in enumerate(ports):
        if not isinstance(getattr(port, "name", None), str):
            return None
        identity = id(port)
        if identity in indexes:
            return None
        indexes[identity] = position
    return indexes


def _port_is_closed(port: Any) -> bool | None:
    """A port is closed when it has berths and none of them is available."""
    berths = _sequence(getattr(port, "berths", None))
    if berths is None:
        return None
    available = 0
    for berth in berths:
        state = getattr(berth, "is_available", None)
        if not isinstance(state, bool):
            return None
        available += int(state)
    return bool(berths) and available == 0


def _closure_recovery(context: Any, now: Any) -> dict[int, float] | None:
    """Hours from ``now`` until each port whose closure is active reopens.

    A closure is temporary, so a port that is shut today is perfectly usable by
    cargo that will not reach it until after it reopens. The reopening time is
    only taken when the plan arithmetic agrees with the live berth state: the
    plan offsets are relative to the start of the simulation, which is taken to
    be ``datetime.min``, and requiring the two to agree means a different epoch
    degrades to treating the port as unusable rather than mis-timing it.
    """
    if not isinstance(now, dt.datetime):
        return None
    plans = getattr(context, "disruption_plans", None)
    if not isinstance(plans, (list, tuple)):
        return None
    recovery: dict[int, float] = {}
    for plan in plans:
        closes = getattr(plan, "close_berth", None)
        if not isinstance(closes, bool):
            return None
        if not closes:
            continue
        port = getattr(getattr(plan, "target_berth", None), "port", None)
        if port is None:
            return None
        start_days = _finite_real(getattr(plan, "start_offset_days", None))
        duration_days = _positive_real(getattr(plan, "duration_days", None))
        if start_days is None or duration_days is None:
            return None
        try:
            start = dt.datetime.min + dt.timedelta(days=start_days)
            end = start + dt.timedelta(days=duration_days)
        except (OverflowError, OSError):
            return None
        if not start <= now < end:
            continue
        hours = (end - now).total_seconds() / 3600.0
        if not math.isfinite(hours) or hours <= 0.0:
            return None
        identity = id(port)
        if hours > recovery.get(identity, 0.0):
            recovery[identity] = hours
    return recovery


def _congestion_recovery(context: Any, now: Any) -> dict[int, float] | None:
    """Hours from ``now`` until each leg whose congestion is active clears.

    A congestion multiplier is as temporary as a closure, so cargo that will
    not reach a slowed leg until after it clears should not be charged for it.
    As with closures the plan arithmetic is only trusted where it agrees with
    live state - here that the leg's multiplier really is raised - so a
    different simulation epoch degrades to assuming the slowdown persists.
    """
    if not isinstance(now, dt.datetime):
        return None
    plans = getattr(context, "disruption_plans", None)
    if not isinstance(plans, (list, tuple)):
        return None
    recovery: dict[int, float] = {}
    for plan in plans:
        closes = getattr(plan, "close_berth", None)
        if not isinstance(closes, bool):
            return None
        leg = getattr(plan, "target_leg", None)
        if closes or leg is None:
            continue
        multiplier = _positive_real(getattr(plan, "multiplier", None))
        live = _positive_real(getattr(leg, "sailing_time_multiplier", None))
        if multiplier is None or live is None:
            return None
        if multiplier <= 1.0 or live <= 1.0:
            continue
        start_days = _finite_real(getattr(plan, "start_offset_days", None))
        duration_days = _positive_real(getattr(plan, "duration_days", None))
        if start_days is None or duration_days is None:
            return None
        try:
            start = dt.datetime.min + dt.timedelta(days=start_days)
            end = start + dt.timedelta(days=duration_days)
        except (OverflowError, OSError):
            return None
        if not start <= now < end:
            continue
        hours = (end - now).total_seconds() / 3600.0
        if not math.isfinite(hours) or hours <= 0.0:
            return None
        identity = id(leg)
        if hours > recovery.get(identity, 0.0):
            recovery[identity] = hours
    return recovery


def _mean_speed(route: Any) -> float | None:
    vessels = _sequence(getattr(route, "deployed_vessels", None))
    if not vessels:
        return None
    speeds: list[float] = []
    for vessel in vessels:
        vessel_class = getattr(vessel, "vessel_class", None)
        speed = _positive_real(getattr(vessel_class, "sailing_speed", None))
        if speed is None:
            return None
        speeds.append(speed)
    mean = math.fsum(speeds) / len(speeds)
    return mean if math.isfinite(mean) and mean > 0.0 else None


def _ordered_legs(route: Any) -> tuple[tuple[Any, ...], tuple[int, ...]] | None:
    """Return the route's legs in rotation order plus their sequence indexes."""
    segments = _sequence(getattr(route, "segments", None))
    if segments is None or len(segments) < 2:
        return None
    ordered: list[tuple[int, Any]] = []
    seen: set[int] = set()
    for segment in segments:
        index = getattr(segment, "sequence_index", None)
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            return None
        if index in seen:
            return None
        seen.add(index)
        leg = getattr(segment, "associated_leg", None)
        if leg is None:
            return None
        ordered.append((index, leg))
    ordered.sort(key=lambda item: item[0])
    legs = tuple(leg for _index, leg in ordered)
    indexes = tuple(index for index, _leg in ordered)
    for position, leg in enumerate(legs):
        following = legs[(position + 1) % len(legs)]
        if getattr(leg, "arrival_port", None) is not getattr(following, "departure_port", None):
            return None
    return legs, indexes


def _route_edges(
    route: Any,
    route_index: int,
    port_indexes: dict[int, int],
    closed: frozenset[int],
    reopen_hours: dict[int, float],
    clears_hours: dict[int, float],
) -> tuple[tuple[_Edge, ...], float] | None:
    """Build every bookable edge of one route and its expected boarding wait."""
    resolved = _ordered_legs(route)
    speed = _mean_speed(route)
    if resolved is None or speed is None:
        return None
    legs, sequence_indexes = resolved
    vessel_count = len(tuple(route.deployed_vessels))

    # Per leg: hours at normal speed, the multiplier in force now, and when
    # that multiplier lifts. A raised multiplier whose end cannot be
    # established never lifts, which reproduces the earlier behaviour.
    base_hours: list[float] = []
    multipliers: list[float] = []
    clears: list[float] = []
    for leg in legs:
        distance = _positive_real(getattr(leg, "sailing_distance", None))
        multiplier = _positive_real(getattr(leg, "sailing_time_multiplier", None))
        if distance is None or multiplier is None:
            return None
        departure = getattr(leg, "departure_port", None)
        arrival = getattr(leg, "arrival_port", None)
        if id(departure) not in port_indexes or id(arrival) not in port_indexes:
            return None
        base_hours.append(distance / speed)
        multipliers.append(multiplier)
        clears.append(0.0 if multiplier <= 1.0 else clears_hours.get(id(leg), math.inf))

    # The rotation runs at the speeds in force now, so the headway reflects the
    # slowdown the vessels are actually suffering.
    cycle_hours = math.fsum(
        base * multiplier for base, multiplier in zip(base_hours, multipliers, strict=True)
    )
    if not math.isfinite(cycle_hours) or cycle_hours <= 0.0:
        return None
    # Waiting for a departure costs one headway, not half of one. Cargo is
    # loaded only if it is already waiting when a vessel begins its port call,
    # so cargo that becomes ready during the connecting vessel's handling misses
    # it and waits a further headway; and because sailing duration varies by
    # +/-5%, vessels on a route drift out of even spacing, which lifts the mean
    # wait for a random arrival to E[gap^2] / (2 * E[gap]) above headway / 2.
    boarding_hours = cycle_hours / vessel_count
    if not math.isfinite(boarding_hours) or boarding_hours <= 0.0:
        return None

    count = len(legs)
    edges: list[_Edge] = []
    for start in range(count):
        departure = getattr(legs[start], "departure_port", None)
        departure_index = port_indexes[id(departure)]
        sailing = 0.0
        congested = False
        blocked = False
        disrupted = False
        steps: list[tuple[float, float, float, float]] = []
        for step in range(1, count):
            position = (start + step - 1) % count
            leg = legs[position]
            sailing += base_hours[position] * multipliers[position]
            if multipliers[position] > 1.0:
                congested = True
                disrupted = True
            arrival = getattr(leg, "arrival_port", None)
            arrival_index = port_indexes[id(arrival)]
            if blocked:
                break
            hours = sailing + _BERTHING_HOURS * (step - 1)
            if not math.isfinite(hours) or hours <= 0.0:
                return None
            reopen = 0.0
            if arrival_index in closed:
                known = reopen_hours.get(arrival_index)
                if known is None:
                    # A closure with no readable reopening time is impassable,
                    # as is every longer ride from this start.
                    blocked = True
                    continue
                reopen = known
                disrupted = True
            steps.append((base_hours[position], multipliers[position], clears[position], reopen))
            if arrival is departure:
                continue
            edges.append(
                _Edge(
                    departure_index,
                    arrival_index,
                    route_index,
                    sequence_indexes[start],
                    sequence_indexes[position],
                    hours,
                    congested,
                    tuple(steps) if disrupted else None,
                )
            )
    return tuple(edges), boarding_hours


def _closed_port_indexes(context: Any) -> frozenset[int] | None:
    """Positions in ``context.ports`` of every port with no berth available."""
    closed: set[int] = set()
    for index, port in enumerate(tuple(context.ports)):
        state = _port_is_closed(port)
        if state is None:
            return None
        if state:
            closed.add(index)
    return frozenset(closed)


def _network(
    context: Any,
    now: Any,
    port_indexes: dict[int, int],
    reopen_hours: dict[int, float],
    clears_hours: dict[int, float] | None = None,
) -> _Network | None:
    """Build the bookable network from the rotations the fleet is running."""
    closed = _closed_port_indexes(context)
    if closed is None:
        return None

    raw_routes = _sequence(getattr(context, "service_routes", None))
    if raw_routes is None:
        return None
    # New cargo is booked only on the rotation each service is actually running
    # now. A rotation a service has moved off is left to the cargo already on
    # it, which is how it drains before its last vessel is allowed to leave.
    bookable = {
        id(route)
        for route in _service_targets(
            context, now, closed, port_indexes, clears_hours or {}, build=False
        ).values()
    }
    edges: list[_Edge] = []
    routes: list[Any] = []
    boarding: list[float] = []
    for route in raw_routes:
        if id(route) not in bookable:
            continue
        if not _sequence(getattr(route, "deployed_vessels", None)):
            continue
        if not isinstance(getattr(route, "associated_bookings", None), list):
            return None
        built = _route_edges(
            route, len(routes), port_indexes, closed, reopen_hours, clears_hours or {}
        )
        if built is None:
            return None
        route_edges, boarding_hours = built
        edges.extend(route_edges)
        routes.append(route)
        boarding.append(boarding_hours)
    if not routes:
        return None
    return _Network(tuple(edges), tuple(routes), tuple(boarding))


def _edge_arrival(edge: _Edge, depart_hours: float) -> float:
    """Hours from now at which this ride ends, given when it starts.

    Both kinds of disruption are temporary and both are timed. A leg sailed
    after its slowdown lifts runs at normal speed, and a call at a shut port
    cannot be served before it reopens, which delays everything after it. With
    nothing disrupted on the ride this is a single addition, so an undisrupted
    network is costed exactly as before.
    """
    if edge.timeline is None:
        return depart_hours + edge.hours
    clock = depart_hours
    last = len(edge.timeline) - 1
    for position, (base, multiplier, clears, reopen) in enumerate(edge.timeline):
        clock += base * (multiplier if clock < clears else 1.0)
        if clock < reopen:
            clock = reopen
        if position != last:
            clock += _BERTHING_HOURS
    return clock


def _fastest_path(
    network: _Network,
    origin_index: int,
    destination_index: int,
    *,
    allow_congestion: bool,
) -> tuple[_Edge, ...] | None:
    """Least-estimated-time chain of bookings, one booking per route change.

    Dijkstra over ``(port, route)`` states so that boarding a different service
    is charged its own expected wait. Consecutive edges on the same route are
    not allowed: the candidate set already holds the direct edge for every
    ordered pair of distinct ports on a rotation, so nothing is lost and every
    edge in the result becomes exactly one booking.
    """
    outgoing: dict[int, list[_Edge]] = {}
    for edge in network.edges:
        if edge.crosses_congestion and not allow_congestion:
            continue
        outgoing.setdefault(edge.departure_index, []).append(edge)

    best: dict[tuple[int, int], float] = {}
    previous: dict[tuple[int, int], tuple[int, int] | None] = {}
    arriving: dict[tuple[int, int], _Edge] = {}
    # Heap entries are fully ordered by numbers only, so the traversal order
    # never depends on object identity or hashing.
    heap: list[tuple[float, int, int, int, int]] = []

    def offer(edge: _Edge, cost: float, source: tuple[int, int] | None) -> None:
        state = (edge.arrival_index, edge.route_index)
        if state in best and best[state] <= cost + 1e-12:
            return
        best[state] = cost
        previous[state] = source
        arriving[state] = edge
        heapq.heappush(
            heap,
            (
                cost,
                edge.arrival_index,
                edge.route_index,
                edge.departure_segment_index,
                edge.arrival_segment_index,
            ),
        )

    for edge in outgoing.get(origin_index, []):
        depart = network.boarding_hours[edge.route_index]
        offer(edge, _edge_arrival(edge, depart), None)

    goal: tuple[int, int] | None = None
    while heap:
        cost, port_index, route_index, _departure, _arrival = heapq.heappop(heap)
        state = (port_index, route_index)
        if best.get(state, math.inf) < cost - 1e-12:
            continue
        if port_index == destination_index:
            goal = state
            break
        for edge in outgoing.get(port_index, []):
            if edge.route_index == route_index:
                continue
            depart = cost + network.boarding_hours[edge.route_index]
            offer(edge, _edge_arrival(edge, depart), state)
    if goal is None:
        return None

    path: list[_Edge] = []
    cursor: tuple[int, int] | None = goal
    while cursor is not None:
        edge = arriving[cursor]
        path.append(edge)
        cursor = previous[cursor]
        if len(path) > len(network.edges):
            return None
    path.reverse()
    return tuple(path)


def _ordered_segments(route: Any) -> tuple[Any, ...] | None:
    """The route's segments in rotation order, or ``None`` if malformed."""
    segments = _sequence(getattr(route, "segments", None))
    if not segments:
        return None
    ordered: list[tuple[int, Any]] = []
    seen: set[int] = set()
    for segment in segments:
        index = getattr(segment, "sequence_index", None)
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            return None
        if index in seen:
            return None
        seen.add(index)
        ordered.append((index, segment))
    ordered.sort(key=lambda item: item[0])
    return tuple(segment for _index, segment in ordered)


def _position_of(segments: tuple[Any, ...], sequence_index: Any) -> int:
    return next(
        (
            position
            for position, segment in enumerate(segments)
            if segment.sequence_index == sequence_index
        ),
        -1,
    )


def _ride_segments(
    segments: tuple[Any, ...], departure_index: Any, arrival_index: Any
) -> tuple[Any, ...] | None:
    """Segments sailed from ``departure_index`` to ``arrival_index`` inclusive."""
    start = _position_of(segments, departure_index)
    end = _position_of(segments, arrival_index)
    if start < 0 or end < 0:
        return None
    ridden: list[Any] = []
    cursor = start
    while True:
        ridden.append(segments[cursor])
        if cursor == end:
            return tuple(ridden)
        cursor = (cursor + 1) % len(segments)
        if len(ridden) > len(segments):
            return None


def _remaining_rides(
    shipment: Any, current_booking: Any, current_segment: Any
) -> tuple[tuple[Any, Any, Any], ...] | None:
    """The rides still to be sailed, as (route, departure index, arrival index).

    Mirrors how the organizer splits a chain at the vessel's current port: the
    part of the current booking already sailed is dropped, and a current
    booking that ends here contributes nothing.
    """
    bookings = _sequence(getattr(shipment, "associated_bookings", None))
    if not bookings:
        return None
    for booking in bookings:
        index = getattr(booking, "sequence_index", None)
        if isinstance(index, bool) or not isinstance(index, int):
            return None
    rides: list[tuple[Any, Any, Any]] = []
    for booking in sorted(bookings, key=lambda item: item.sequence_index):
        if booking.sequence_index < current_booking.sequence_index:
            continue
        route = getattr(booking, "service_route", None)
        segments = None if route is None else _ordered_segments(route)
        if segments is None:
            return None
        if booking is current_booking:
            here = _position_of(segments, current_segment.sequence_index)
            end = _position_of(segments, booking.arrival_segment_index)
            if here >= 0 and here == end:
                continue
            if here < 0:
                departure = booking.departure_segment_index
            else:
                departure = segments[(here + 1) % len(segments)].sequence_index
        else:
            departure = booking.departure_segment_index
        rides.append((route, departure, booking.arrival_segment_index))
    return tuple(rides)


def _ride_is_disrupted(
    route: Any,
    departure_index: Any,
    arrival_index: Any,
    closed: frozenset[int],
    port_indexes: dict[int, int],
) -> bool | None:
    """Whether this ride calls at a shut port or crosses a congested leg."""
    segments = _ordered_segments(route)
    if segments is None:
        return None
    ridden = _ride_segments(segments, departure_index, arrival_index)
    if ridden is None:
        return None
    for segment in ridden:
        leg = getattr(segment, "associated_leg", None)
        if leg is None:
            return None
        multiplier = _positive_real(getattr(leg, "sailing_time_multiplier", None))
        if multiplier is None:
            return None
        if multiplier > 1.0:
            return True
        position = port_indexes.get(id(getattr(leg, "arrival_port", None)))
        if position is None:
            return None
        if position in closed:
            return True
    return False


def _find_edge(network: _Network, route: Any, departure_index: Any, arrival_index: Any):
    for position, candidate in enumerate(network.routes):
        if candidate is not route:
            continue
        for edge in network.edges:
            if (
                edge.route_index == position
                and edge.departure_segment_index == departure_index
                and edge.arrival_segment_index == arrival_index
            ):
                return edge
        return None
    return None


def _rides_hours(network: _Network, rides: tuple[tuple[Any, Any, Any], ...]) -> float | None:
    """Estimated hours to sail ``rides``, already aboard the first one."""
    elapsed = 0.0
    previous: Any = None
    for position, (route, departure_index, arrival_index) in enumerate(rides):
        edge = _find_edge(network, route, departure_index, arrival_index)
        if edge is None:
            return None
        if position and previous is not route:
            elapsed += network.boarding_hours[edge.route_index]
        elapsed = _edge_arrival(edge, elapsed)
        if not math.isfinite(elapsed):
            return None
        previous = route
    return elapsed


def _plan(context: Any, now: Any, shipment: Any) -> tuple[_Network, tuple[_Edge, ...]] | None:
    """Choose the booking chain for one newly generated shipment."""
    bookings = getattr(shipment, "associated_bookings", None)
    if not isinstance(bookings, list) or bookings:
        return None
    if getattr(shipment, "current_booking_index", None) is not None:
        return None
    demand = getattr(shipment, "demand", None)
    origin = getattr(demand, "origin_port", None)
    destination = getattr(demand, "destination_port", None)
    if origin is None or destination is None or origin is destination:
        return None

    port_indexes = _port_indexes(context)
    if port_indexes is None:
        return None
    origin_index = port_indexes.get(id(origin))
    destination_index = port_indexes.get(id(destination))
    if origin_index is None or destination_index is None:
        return None

    # A missing or unreadable plan set leaves these maps empty, which reproduces
    # the earlier behaviour: shut ports impassable, slowdowns assumed permanent.
    reopen_hours = _reopen_positions(context, now, port_indexes)
    clears_hours = _congestion_recovery(context, now) or {}
    network = _network(context, now, port_indexes, reopen_hours, clears_hours)
    if network is None:
        return None

    # A path avoiding every congested leg must exist. When none does, the only
    # option would be to sail a multiplied leg for an unknown remaining
    # duration, so the organizer's protective wait keeps control instead.
    if _fastest_path(network, origin_index, destination_index, allow_congestion=False) is None:
        return None
    path = _fastest_path(network, origin_index, destination_index, allow_congestion=True)
    return None if path is None else (network, path)


def _assign(context: Any, now: Any, shipment: Any) -> bool | None:
    """Build and register the chosen chain, or return ``None`` to delegate."""
    planned = _plan(context, now, shipment)
    if planned is None:
        return None
    network, path = planned
    created: list[tuple[Any, Booking]] = []
    for position, edge in enumerate(path, start=1):
        route = network.routes[edge.route_index]
        created.append(
            (
                route,
                Booking(
                    sequence_index=position,
                    shipment=shipment,
                    service_route=route,
                    departure_segment_index=edge.departure_segment_index,
                    arrival_segment_index=edge.arrival_segment_index,
                ),
            )
        )
    # Only mutate once the whole chain exists, so a failure cannot leave a
    # partially booked shipment behind.
    for route, booking in created:
        shipment.associated_bookings.append(booking)
        route.associated_bookings.append(booking)
    shipment.current_booking_index = 1
    return True


def _reopen_positions(context: Any, now: Any, port_indexes: dict[int, int]) -> dict[int, float]:
    recovery = _closure_recovery(context, now) or {}
    return {
        position: hours
        for identity, hours in recovery.items()
        if (position := port_indexes.get(identity)) is not None
    }


def _keep_booked_chains(context: Any, now: Any, vessel: Any) -> bool | None:
    """Keep in-transit chains when they already beat every alternative.

    The organizer replans a carried shipment whenever the unfinished part of
    its chain meets an active disruption, rebuilding by sailing distance and
    refusing the disrupted ports and legs outright. Staying aboard and waiting
    is often faster. This returns ``True`` — a decision to change nothing —
    only when the booked chain is at least as fast as the best alternative from
    here, judged by the same cost model that chose the chain in the first place.

    The alternative is costed the way it would actually be sailed: leaving the
    current service costs the wait for the next one, and only a rebuild that
    continues on the route the cargo is already riding avoids that wait, which
    is exactly what the organizer's merge does. Anything uncertain delegates,
    which restores the organizer's behaviour exactly - including a chain riding
    a disruption-alternative route, which this model does not carry and which
    the organizer may withdraw at recovery.
    """
    current_segment = getattr(vessel, "current_segment", None)
    leg = getattr(current_segment, "associated_leg", None)
    current_port = getattr(leg, "arrival_port", None)
    if current_port is None:
        return None
    carried = _sequence(getattr(vessel, "carried_shipments", None))
    if not carried:
        return None

    port_indexes = _port_indexes(context)
    if port_indexes is None:
        return None
    current_index = port_indexes.get(id(current_port))
    if current_index is None:
        return None
    closed = _closed_port_indexes(context)
    if closed is None:
        return None

    reopen_hours = _reopen_positions(context, now, port_indexes)
    clears_hours = _congestion_recovery(context, now) or {}
    network: _Network | None = None
    decided = 0

    for shipment in carried:
        bookings = _sequence(getattr(shipment, "associated_bookings", None))
        if not bookings:
            continue
        current_booking = next(
            (
                booking
                for booking in bookings
                if getattr(booking, "sequence_index", None)
                == getattr(shipment, "current_booking_index", None)
            ),
            None,
        )
        if current_booking is None:
            continue
        rides = _remaining_rides(shipment, current_booking, current_segment)
        if rides is None:
            return None
        if not rides:
            continue

        disrupted = False
        for route, departure_index, arrival_index in rides:
            state = _ride_is_disrupted(route, departure_index, arrival_index, closed, port_indexes)
            if state is None:
                return None
            disrupted = disrupted or state
        if not disrupted:
            # The organizer would leave this shipment alone too.
            continue

        final_route, _departure, final_arrival = rides[-1]
        final_segments = _ordered_segments(final_route)
        if final_segments is None:
            return None
        final_position = _position_of(final_segments, final_arrival)
        if final_position < 0:
            return None
        final_port = getattr(
            getattr(final_segments[final_position], "associated_leg", None),
            "arrival_port",
            None,
        )
        destination_index = port_indexes.get(id(final_port))
        if destination_index is None:
            return None
        if destination_index == current_index:
            continue

        if network is None:
            network = _network(context, now, port_indexes, reopen_hours, clears_hours)
            if network is None:
                return None

        keep_hours = _rides_hours(network, rides)
        if keep_hours is None:
            return None
        # The cargo is already at sea, so unlike a booking decision there is no
        # reason to insist on a congestion-free alternative: whatever exists is
        # costed and compared on its merits.
        best = _fastest_path(network, current_index, destination_index, allow_congestion=True)
        if not best:
            # With no alternative at all the organizer's own rebuild would find
            # none either and would leave the chain alone, so keeping is right.
            decided += 1
            continue
        alternative = _rides_hours(
            network,
            tuple(
                (
                    network.routes[edge.route_index],
                    edge.departure_segment_index,
                    edge.arrival_segment_index,
                )
                for edge in best
            ),
        )
        if alternative is None:
            return None
        if network.routes[best[0].route_index] is not current_booking.service_route:
            # Leaving this service costs the wait for the next one. Only a
            # rebuild that continues on the route the cargo is already riding
            # avoids that wait, which is what the organizer's merge does.
            alternative += network.boarding_hours[best[0].route_index]
        if keep_hours > alternative:
            return None
        decided += 1

    return True if decided else None


# ---------------------------------------------------------------------------
# The fleet decision: run every service on the fastest rotation that still
# calls all of its ports.
# ---------------------------------------------------------------------------

# Marks the rotations this strategy builds, so they are never confused with the
# ones the organizer fallback builds.
_ROUTE_MARK = "UALT"


def _leg_endpoints(leg: Any) -> tuple[str, str] | None:
    departure = getattr(getattr(leg, "departure_port", None), "name", None)
    arrival = getattr(getattr(leg, "arrival_port", None), "name", None)
    if not isinstance(departure, str) or not isinstance(arrival, str):
        return None
    return departure.casefold(), arrival.casefold()


def _cycle_distance(legs: tuple[Any, ...]) -> float | None:
    """Distance once round a rotation, stretched by the multipliers in force.

    Ranking two rotations of the same service by this quantity is the same
    comparison as by cycle hours: the vessels' speed divides both sides out.
    """
    total = 0.0
    for leg in legs:
        distance = _positive_real(getattr(leg, "sailing_distance", None))
        multiplier = _positive_real(getattr(leg, "sailing_time_multiplier", None))
        if distance is None or multiplier is None:
            return None
        total += distance * multiplier
    return total if math.isfinite(total) and total > 0.0 else None


def _slowdown_present(context: Any) -> bool | None:
    legs = _sequence(getattr(context, "legs", None))
    if legs is None:
        return None
    for leg in legs:
        multiplier = _positive_real(getattr(leg, "sailing_time_multiplier", None))
        if multiplier is None:
            return None
        if multiplier > 1.0:
            return True
    return False


def _slowdown_of(
    legs: tuple[Any, ...], closed: frozenset[int], port_indexes: dict[int, int]
) -> tuple[tuple[tuple[str, str], ...], tuple[Any, ...]] | None:
    """The slowed legs of a rotation, or ``None`` if it must be left alone."""
    keys: list[tuple[str, str]] = []
    slowed: list[Any] = []
    for leg in legs:
        multiplier = _positive_real(getattr(leg, "sailing_time_multiplier", None))
        if multiplier is None:
            return None
        for port in (
            getattr(leg, "departure_port", None),
            getattr(leg, "arrival_port", None),
        ):
            # A shut port is a wait, not a reason to stop calling there.
            if port_indexes.get(id(port)) in closed:
                return None
        if multiplier > 1.0:
            key = _leg_endpoints(leg)
            if key is None:
                return None
            keys.append(key)
            slowed.append(leg)
    if not slowed:
        return None
    return tuple(sorted(keys)), tuple(slowed)


def _nominal_distance(legs: tuple[Any, ...]) -> float | None:
    """Distance once round a rotation at normal speed."""
    total = 0.0
    for leg in legs:
        distance = _positive_real(getattr(leg, "sailing_distance", None))
        if distance is None:
            return None
        total += distance
    return total if math.isfinite(total) and total > 0.0 else None


def _outlasts_a_changeover(
    source: Any,
    rotation_legs: tuple[Any, ...],
    slowed: tuple[Any, ...],
    clears: dict[int, float],
) -> bool:
    """Whether the slowdown will still be in force after the fleet has moved.

    Changing rotation is not free. Vessels move one at a time, only when empty,
    so the changeover takes about one turn of the new rotation - and it is paid
    again on the way back. The quantity that says whether it is worth paying is
    the slowdown's own remaining life against that turn, and both are read from
    the runtime state. An end that cannot be established counts as permanent,
    exactly as the booking cost model treats it.
    """
    speed = _mean_speed(source)
    turn = _nominal_distance(rotation_legs)
    if speed is None or turn is None:
        return False
    remaining = math.inf
    for leg in slowed:
        remaining = min(remaining, clears.get(id(leg), math.inf))
    return remaining > turn / speed


def _closures_within(
    context: Any, now: Any, horizon_hours: float, port_indexes: dict[int, int]
) -> frozenset[int] | None:
    """Positions of ports shut at any point between now and ``now + horizon``.

    A rotation is only worth changing to if it can be sailed for as long as it
    is needed, and a port that will be shut part-way through cannot be. The
    disruption plans are the same published set that v12 reads to time a
    reopening, and the same epoch guard applies: if the plan arithmetic cannot
    be trusted, no port is claimed to be safe and no detour is built.
    """
    if not isinstance(now, dt.datetime) or not math.isfinite(horizon_hours):
        return None
    plans = getattr(context, "disruption_plans", None)
    if not isinstance(plans, (list, tuple)):
        return None
    try:
        limit = now + dt.timedelta(hours=min(horizon_hours, 3650.0 * 24.0))
    except (OverflowError, OSError):
        return None
    shut: set[int] = set()
    for plan in plans:
        closes = getattr(plan, "close_berth", None)
        if not isinstance(closes, bool):
            return None
        if not closes:
            continue
        port = getattr(getattr(plan, "target_berth", None), "port", None)
        position = port_indexes.get(id(port))
        if position is None:
            return None
        start_days = _finite_real(getattr(plan, "start_offset_days", None))
        duration_days = _positive_real(getattr(plan, "duration_days", None))
        if start_days is None or duration_days is None:
            return None
        try:
            start = dt.datetime.min + dt.timedelta(days=start_days)
            end = start + dt.timedelta(days=duration_days)
        except (OverflowError, OSError):
            return None
        if start < limit and end > now:
            shut.add(position)
    return frozenset(shut)


def _undisrupted_leg_path(
    context: Any,
    origin: Any,
    destination: Any,
    closed: frozenset[int],
    port_indexes: dict[int, int],
) -> tuple[Any, ...] | None:
    """Shortest path between two ports over legs no disruption touches."""
    legs = _sequence(getattr(context, "legs", None))
    if legs is None:
        return None
    start = port_indexes.get(id(origin))
    goal = port_indexes.get(id(destination))
    if start is None or goal is None or start == goal or start in closed:
        return None

    outgoing: dict[int, list[tuple[float, int, Any]]] = {}
    for leg in legs:
        distance = _positive_real(getattr(leg, "sailing_distance", None))
        multiplier = _positive_real(getattr(leg, "sailing_time_multiplier", None))
        if distance is None or multiplier is None:
            return None
        if multiplier > 1.0:
            continue
        departure = port_indexes.get(id(getattr(leg, "departure_port", None)))
        arrival = port_indexes.get(id(getattr(leg, "arrival_port", None)))
        if departure is None or arrival is None:
            return None
        if departure in closed or arrival in closed:
            continue
        outgoing.setdefault(departure, []).append((distance, arrival, leg))

    best: dict[int, float] = {start: 0.0}
    previous: dict[int, tuple[int, Any]] = {}
    # Heap entries are ordered by numbers alone, so nothing depends on hashing.
    heap: list[tuple[float, int]] = [(0.0, start)]
    while heap:
        cost, port = heapq.heappop(heap)
        if best.get(port, math.inf) < cost - 1e-12:
            continue
        if port == goal:
            break
        for distance, arrival, leg in outgoing.get(port, []):
            candidate = cost + distance
            if candidate < best.get(arrival, math.inf) - 1e-12:
                best[arrival] = candidate
                previous[arrival] = (port, leg)
                heapq.heappush(heap, (candidate, arrival))

    if goal not in previous:
        return None
    path: list[Any] = []
    cursor = goal
    while cursor != start:
        step = previous.get(cursor)
        if step is None:
            return None
        cursor, leg = step
        path.append(leg)
        if len(path) > len(legs):
            return None
    path.reverse()
    return tuple(path)


def _detour_legs(
    context: Any,
    legs: tuple[Any, ...],
    closed: frozenset[int],
    port_indexes: dict[int, int],
) -> tuple[Any, ...] | None:
    """Replace every slowed leg of a rotation by the fastest way round it.

    Only insertions are made, so the detour calls every port the rotation
    calls, in the same order, and stays a connected cycle.
    """
    replaced: list[Any] = []
    for leg in legs:
        multiplier = _positive_real(getattr(leg, "sailing_time_multiplier", None))
        if multiplier is None:
            return None
        if multiplier <= 1.0:
            replaced.append(leg)
            continue
        detour = _undisrupted_leg_path(
            context,
            getattr(leg, "departure_port", None),
            getattr(leg, "arrival_port", None),
            closed,
            port_indexes,
        )
        if detour is None:
            return None
        replaced.extend(detour)
    return tuple(replaced)


def _rotation_beats(
    rotation: Any,
    legs: tuple[Any, ...],
    closed: frozenset[int],
    port_indexes: dict[int, int],
) -> bool:
    """Whether a built rotation is the better one to be running right now.

    A detour inserts ports the nominal rotation does not call, and one of those
    can be shut later. The same rule that keeps a service on a rotation whose
    own port is shut applies here in reverse: a detour that would sail into a
    closed port is not a detour worth being on, so the service goes home and
    waits the closure out on its own rotation.
    """
    resolved = _ordered_legs(rotation)
    if resolved is None:
        return False
    for leg in resolved[0]:
        for port in (
            getattr(leg, "departure_port", None),
            getattr(leg, "arrival_port", None),
        ):
            if port_indexes.get(id(port)) in closed:
                return False
    detoured = _cycle_distance(resolved[0])
    current = _cycle_distance(legs)
    return detoured is not None and current is not None and detoured < current


def _build_rotation(context: Any, source: Any, legs: tuple[Any, ...], key: Any) -> Any | None:
    """Register a new service route over existing legs. No leg is created."""
    routes = _sequence(getattr(context, "service_routes", None))
    register = getattr(context, "partial_service_routes", None)
    if routes is None or not isinstance(register, list) or not legs:
        return None
    taken = {getattr(route, "id", None) for route in routes}
    index = 1
    while f"{getattr(source, 'id', '')}-{_ROUTE_MARK}-{index}" in taken:
        index += 1
    rotation = ServiceRoute(
        id=f"{getattr(source, 'id', '')}-{_ROUTE_MARK}-{index}",
        name=f"{getattr(source, 'name', '')} Slowdown Detour",
        start_day_of_week=getattr(source, "start_day_of_week", 0.0),
    )
    rotation.source_service_route = source
    rotation.disruption_key = (_ROUTE_MARK, key)
    for sequence_index, leg in enumerate(legs, start=1):
        segment = Segment(sequence_index, leg, rotation)
        rotation.segments.append(segment)
        leg_segments = getattr(leg, "segments", None)
        if isinstance(leg_segments, list):
            leg_segments.append(segment)
        register.append(segment)
    context.service_routes.append(rotation)
    return rotation


def _service_targets(
    context: Any,
    now: Any,
    closed: frozenset[int],
    port_indexes: dict[int, int],
    clears: dict[int, float],
    *,
    build: bool,
) -> dict[int, Any]:
    """The rotation each service should be running, keyed by its nominal route.

    With ``build`` false this is read-only: a detour that has not been built
    yet simply leaves the service on its nominal rotation.

    A service that has not started its changeover has to clear the
    changeover-cost test; one already part-way through does not, since that
    cost has been paid and reversing early would only pay it twice.
    """
    routes = _sequence(getattr(context, "service_routes", None)) or ()
    nominal = tuple(
        route for route in routes if getattr(route, "source_service_route", None) is None
    )
    targets = {id(route): route for route in nominal}
    if _slowdown_present(context) is not True:
        return targets

    for source in nominal:
        resolved = _ordered_legs(source)
        if resolved is None:
            continue
        legs = resolved[0]
        found = _slowdown_of(legs, closed, port_indexes)
        if found is None:
            continue
        key, slowed = found
        rotation = None
        for candidate in routes:
            if (
                getattr(candidate, "source_service_route", None) is source
                and getattr(candidate, "disruption_key", None) == (_ROUTE_MARK, key)
                and _sequence(getattr(candidate, "segments", None))
            ):
                rotation = candidate
                break
        if rotation is None:
            if not build:
                continue
            # The detour has to be sailable for as long as it is needed, so a
            # port that will be shut inside that window is not available to it.
            horizon = math.inf
            for leg in slowed:
                horizon = min(horizon, clears.get(id(leg), math.inf))
            unavailable = closed
            if math.isfinite(horizon):
                shut = _closures_within(context, now, horizon, port_indexes)
                if shut is None:
                    continue
                unavailable = closed | shut
            detour = _detour_legs(context, legs, unavailable, port_indexes)
            if detour is None or _cycle_distance(detour) is None:
                continue
            if (_cycle_distance(detour) or math.inf) >= (_cycle_distance(legs) or 0.0):
                continue
            if not _outlasts_a_changeover(source, detour, slowed, clears):
                continue
            rotation = _build_rotation(context, source, detour, key)
            if rotation is None:
                continue
        elif not _sequence(getattr(rotation, "deployed_vessels", None)):
            built = _ordered_legs(rotation)
            if built is None or not _outlasts_a_changeover(source, built[0], slowed, clears):
                continue
        if _rotation_beats(rotation, legs, closed, port_indexes):
            targets[id(source)] = rotation
    return targets


def _has_live_bookings(route: Any) -> bool:
    """Whether any shipment still needs this rotation to sail for it.

    A shipment needs it only for the bookings it has not passed yet. Cargo that
    has already sailed its leg here and is now several services further along
    is unfinished, but nothing it has left to do depends on this rotation, so
    holding a vessel here for it parks that vessel for the rest of the run.
    """
    bookings = getattr(route, "associated_bookings", None)
    if not isinstance(bookings, list):
        return True
    # Newest first: a rotation still in use answers on its first entry, so the
    # only full scan is the one that finds it finally drained.
    for booking in reversed(bookings):
        shipment = getattr(booking, "shipment", None)
        if shipment is None:
            return True
        if getattr(shipment, "completion_time", None) is not None:
            continue
        reached = getattr(shipment, "current_booking_index", None)
        sequence = getattr(booking, "sequence_index", None)
        if not isinstance(reached, int) or not isinstance(sequence, int):
            # Unreadable progress: assume the cargo still needs this rotation.
            return True
        if sequence >= reached:
            return True
    return False


def _vessel_port(vessel: Any) -> Any:
    segment = getattr(vessel, "current_segment", None)
    leg = getattr(segment, "associated_leg", None)
    if leg is not None:
        return getattr(leg, "arrival_port", None)
    berth = getattr(vessel, "current_berth", None)
    return getattr(berth, "port", None) if berth is not None else None


def _reentry_segment(route: Any, port: Any) -> Any:
    if port is None:
        return None
    for segment in _ordered_segments(route) or ():
        leg = getattr(segment, "associated_leg", None)
        if leg is not None and getattr(leg, "arrival_port", None) is port:
            return segment
    return None


def _place_vessel(vessel: Any, route: Any) -> bool:
    """Move an empty vessel to another rotation at the port it is standing at.

    The safety conditions are the organizer's own: the vessel carries nothing,
    and the rotation it joins calls the port it is at, so it resumes from
    there. Nothing is loaded, discharged, or completed here.
    """
    if getattr(vessel, "carried_shipments", None):
        return False
    deployed = getattr(route, "deployed_vessels", None)
    if not isinstance(deployed, list):
        return False
    segment = _reentry_segment(route, _vessel_port(vessel))
    if segment is None:
        return False
    current = getattr(vessel, "current_segment", None)
    occupants = getattr(current, "current_vessels", None)
    if isinstance(occupants, list):
        while vessel in occupants:
            occupants.remove(vessel)
    previous = getattr(vessel, "assigned_service_route", None)
    leaving = getattr(previous, "deployed_vessels", None)
    if isinstance(leaving, list):
        while vessel in leaving:
            leaving.remove(vessel)
    if vessel not in deployed:
        deployed.append(vessel)
    vessel.assigned_service_route = route
    vessel.pending_assigned_service_route = None
    vessel.current_segment = segment
    occupants = getattr(segment, "current_vessels", None)
    if isinstance(occupants, list) and vessel not in occupants:
        occupants.append(vessel)
    return True


def _run_fleet(context: Any, now: Any, vessel: Any) -> None:
    """Point every service at its target rotation, and move one vessel there."""
    port_indexes = _port_indexes(context)
    closed = _closed_port_indexes(context)
    vessels = _sequence(getattr(context, "vessels", None))
    if port_indexes is None or closed is None or vessels is None:
        return

    clears = _congestion_recovery(context, now) or {}
    targets = _service_targets(context, now, closed, port_indexes, clears, build=True)
    staffing: dict[int, int] = {}
    for candidate in vessels:
        assigned = getattr(candidate, "assigned_service_route", None)
        if assigned is not None:
            staffing[id(assigned)] = staffing.get(id(assigned), 0) + 1

    live: dict[int, bool] = {}
    for candidate in vessels:
        assigned = getattr(candidate, "assigned_service_route", None)
        if assigned is None:
            continue
        source = getattr(assigned, "source_service_route", None) or assigned
        target = targets.get(id(source))
        keep = target is None or target is assigned
        # Never take the last vessel off a rotation cargo is still booked on:
        # that cargo would have nothing left to sail on.
        if not keep and staffing.get(id(assigned), 0) <= 1:
            if id(assigned) not in live:
                live[id(assigned)] = _has_live_bookings(assigned)
            keep = live[id(assigned)]
        if keep:
            if getattr(candidate, "pending_assigned_service_route", None) is not None:
                candidate.pending_assigned_service_route = None
            continue
        candidate.pending_assigned_service_route = target

    if vessel is None:
        return
    pending = getattr(vessel, "pending_assigned_service_route", None)
    if pending is not None and pending is not getattr(vessel, "assigned_service_route", None):
        _place_vessel(vessel, pending)


class UserStrategy:
    """Deterministic participant strategy with one time-aware booking policy."""

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
        """Run every service on the fastest rotation that still calls its ports.

        The organizer's fallback answers a slowdown by building a rotation that
        avoids it and reserving *one* vessel from the affected service onto it.
        That is the worst of both worlds: the original rotation still crawls
        through the slowdown and has lost a share of its frequency, while the
        new one runs a single vessel around its whole cycle. Nothing in the
        validation rules limits a new rotation to one vessel, so this strategy
        moves the whole service instead, and only when the detour is strictly
        faster than sailing the slowdown and still calls every port.

        A shut port is never routed around: v12 established that a closure is
        a wait, and dropping the call would abandon the cargo booked there.

        Vessels move one at a time and only when empty at a port the new
        rotation calls, and a rotation is never left without vessels while
        cargo is still booked on it. No cargo is moved, loaded, or completed
        here.
        """
        with contextlib.suppress(*_DATA_ERRORS):
            _run_fleet(context, now, vessel)
        return True

    @staticmethod
    def assign_associated_bookings(context: Any, now: Any, shipment: Any) -> Any:
        """Assign the fastest booking chain available to new cargo."""
        try:
            return _assign(context, now, shipment)
        except _DATA_ERRORS:
            return None

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Keep an in-transit chain that already beats every alternative."""
        try:
            return _keep_booked_chains(context, now, vessel)
        except _DATA_ERRORS:
            return None
