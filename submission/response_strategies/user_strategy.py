"""Participant-owned response strategy for the WSC 2026 challenge.

The strategy owns one decision: the initial booking chain for newly generated
cargo. The organizer's fallback chooses that chain by minimising sailing
distance, which ignores how often each service actually departs; a booking that
saves a few nautical miles by adding a transshipment can cost days of waiting
for the next vessel. This strategy instead minimises *estimated transport
time* - sailing time at the live leg multipliers, one expected departure wait
per service route used, and the organizer's fixed berthing time for each
intermediate port call.

Every quantity is read from the supplied runtime objects. The strategy is
deterministic, standard-library-only, performs no I/O, keeps no state between
calls, and delegates to the organizer fallback whenever the runtime data is
malformed, ambiguous, or would force cargo across a congested leg that no
alternative path avoids. The other three decision points stay delegated.
"""

from __future__ import annotations

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
) -> tuple[tuple[_Edge, ...], float] | None:
    """Build every bookable edge of one route and its expected boarding wait."""
    resolved = _ordered_legs(route)
    speed = _mean_speed(route)
    if resolved is None or speed is None:
        return None
    legs, sequence_indexes = resolved
    vessel_count = len(tuple(route.deployed_vessels))

    leg_hours: list[float] = []
    for leg in legs:
        distance = _positive_real(getattr(leg, "sailing_distance", None))
        multiplier = _positive_real(getattr(leg, "sailing_time_multiplier", None))
        if distance is None or multiplier is None:
            return None
        departure = getattr(leg, "departure_port", None)
        arrival = getattr(leg, "arrival_port", None)
        if id(departure) not in port_indexes or id(arrival) not in port_indexes:
            return None
        leg_hours.append(distance * multiplier / speed)

    cycle_hours = math.fsum(leg_hours)
    if not math.isfinite(cycle_hours) or cycle_hours <= 0.0:
        return None
    boarding_hours = 0.5 * cycle_hours / vessel_count
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
        for step in range(1, count):
            position = (start + step - 1) % count
            leg = legs[position]
            sailing += leg_hours[position]
            if leg.sailing_time_multiplier > 1.0:
                congested = True
            arrival = getattr(leg, "arrival_port", None)
            arrival_index = port_indexes[id(arrival)]
            if blocked:
                break
            if arrival_index in closed:
                # Any later edge from this start would call here on the way.
                blocked = True
                continue
            if arrival is departure:
                continue
            hours = sailing + _BERTHING_HOURS * (step - 1)
            if not math.isfinite(hours) or hours <= 0.0:
                return None
            edges.append(
                _Edge(
                    departure_index,
                    arrival_index,
                    route_index,
                    sequence_indexes[start],
                    sequence_indexes[position],
                    hours,
                    congested,
                )
            )
    return tuple(edges), boarding_hours


def _network(context: Any, port_indexes: dict[int, int]) -> _Network | None:
    """Build the bookable network from the live nominal service routes."""
    ports = tuple(context.ports)
    closed_indexes: set[int] = set()
    for index, port in enumerate(ports):
        state = _port_is_closed(port)
        if state is None:
            return None
        if state:
            closed_indexes.add(index)
    closed = frozenset(closed_indexes)

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
        built = _route_edges(route, len(routes), port_indexes, closed)
        if built is None:
            return None
        route_edges, boarding_hours = built
        edges.extend(route_edges)
        routes.append(route)
        boarding.append(boarding_hours)
    if not routes:
        return None
    return _Network(tuple(edges), tuple(routes), tuple(boarding))


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
        offer(edge, network.boarding_hours[edge.route_index] + edge.hours, None)

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
            step = network.boarding_hours[edge.route_index] + edge.hours
            offer(edge, cost + step, state)
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


def _plan(context: Any, shipment: Any) -> tuple[_Network, tuple[_Edge, ...]] | None:
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

    network = _network(context, port_indexes)
    if network is None:
        return None

    # A path avoiding every congested leg must exist. When none does, the only
    # option would be to sail a multiplied leg for an unknown remaining
    # duration, so the organizer's protective wait keeps control instead.
    if _fastest_path(network, origin_index, destination_index, allow_congestion=False) is None:
        return None
    path = _fastest_path(network, origin_index, destination_index, allow_congestion=True)
    return None if path is None else (network, path)


def _assign(context: Any, shipment: Any) -> bool | None:
    """Build and register the chosen chain, or return ``None`` to delegate."""
    planned = _plan(context, shipment)
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
            return _assign(context, shipment)
        except _DATA_ERRORS:
            return None

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Delegate in-transit booking changes to the organizer fallback."""
        return None
