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
The remaining two decision points stay delegated.
"""

from __future__ import annotations

import datetime as dt
import heapq
import math
import numbers
from typing import Any, NamedTuple

from maritime_data_context import Booking

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
    port_indexes: dict[int, int],
    reopen_hours: dict[int, float],
    clears_hours: dict[int, float] | None = None,
) -> _Network | None:
    """Build the bookable network from the live nominal service routes."""
    closed = _closed_port_indexes(context)
    if closed is None:
        return None

    raw_routes = _sequence(getattr(context, "service_routes", None))
    if raw_routes is None:
        return None
    edges: list[_Edge] = []
    routes: list[Any] = []
    boarding: list[float] = []
    for route in raw_routes:
        # Alternative routes carry a single reserved vessel and are withdrawn
        # when the disruption ends, which would orphan a booking made on them.
        if getattr(route, "source_service_route", None) is not None:
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
    network = _network(context, port_indexes, reopen_hours, clears_hours)
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
            network = _network(context, port_indexes, reopen_hours, clears_hours)
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
        """Delegate alternative-route creation to the organizer fallback."""
        return None

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
