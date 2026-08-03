"""Pure, fail-closed policy for deferring premature in-transit rebooking."""

from __future__ import annotations

import datetime as dt
from typing import Any

_EXPECTED_RUNTIME_ERRORS = (
    AttributeError,
    IndexError,
    KeyError,
    OverflowError,
    TypeError,
    ValueError,
)


def should_defer_future_only_rebooking(context: Any, now: Any, vessel: Any) -> bool | None:
    """Return ``False`` only when every impact is still downstream.

    ``None`` delegates to the organizer fallback. The function is deliberately
    read-only: it classifies unfinished bookings and never edits runtime state.
    """
    try:
        return _decide(context, now, vessel)
    except _EXPECTED_RUNTIME_ERRORS:
        return None


def _decide(context: Any, now: Any, vessel: Any) -> bool | None:
    if not isinstance(now, dt.datetime) or vessel is None:
        return None

    close_ports, congested_legs = _active_resources(context.disruption_plans, now)
    if not close_ports and not congested_legs:
        return None

    current_segment = vessel.current_segment
    if current_segment is None:
        return None

    route = current_segment.associated_service_route
    segments = _ordered_segments(route)
    current_position = _segment_position(segments, current_segment)
    shipments = tuple(vessel.carried_shipments)
    has_future_only_impact = False

    for shipment in shipments:
        impacted, current_direct = _shipment_impact(
            shipment,
            current_segment,
            route,
            segments,
            current_position,
            close_ports,
            congested_legs,
        )
        if not impacted:
            continue
        if current_direct:
            return None
        has_future_only_impact = True

    return False if has_future_only_impact else None


def _active_resources(plans: Any, now: dt.datetime) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    close_ports: list[Any] = []
    congested_legs: list[Any] = []
    for plan in tuple(plans):
        start_offset = plan.start_offset_days
        duration = plan.duration_days
        if start_offset is None or duration is None:
            continue
        start = dt.datetime.min + dt.timedelta(days=start_offset)
        end = start + dt.timedelta(days=duration)
        if not start <= now < end:
            continue

        if plan.close_berth:
            berth = plan.target_berth
            port = berth.port
            if not _contains_identity(close_ports, port):
                close_ports.append(port)

        multiplier = plan.multiplier
        target_leg = plan.target_leg
        if (
            multiplier > 1.0
            and target_leg is not None
            and not _contains_identity(congested_legs, target_leg)
        ):
            congested_legs.append(target_leg)

    return tuple(close_ports), tuple(congested_legs)


def _shipment_impact(
    shipment: Any,
    current_segment: Any,
    route: Any,
    segments: tuple[Any, ...],
    current_position: int,
    close_ports: tuple[Any, ...],
    congested_legs: tuple[Any, ...],
) -> tuple[bool, bool]:
    bookings = tuple(shipment.associated_bookings)
    current_booking = shipment.get_current_booking()
    if current_booking.service_route is not route:
        raise ValueError("current booking route does not match vessel route")

    current_span = _booking_span(
        segments,
        current_booking.departure_segment_index,
        current_booking.arrival_segment_index,
    )
    if not _contains_identity(current_span, current_segment):
        raise ValueError("current segment is outside current booking")

    current_direct = _segment_is_affected(current_segment, close_ports, congested_legs)
    impacted = current_direct

    arrival_position = _segment_position(segments, current_span[-1])
    if current_position != arrival_position:
        for segment in _segments_after_current_until(segments, current_position, arrival_position):
            impacted = _segment_is_affected(segment, close_ports, congested_legs) or impacted

    current_sequence = current_booking.sequence_index
    for booking in sorted(bookings, key=lambda item: item.sequence_index):
        if booking.sequence_index <= current_sequence:
            continue
        later_route = booking.service_route
        later_segments = _ordered_segments(later_route)
        for segment in _booking_span(
            later_segments,
            booking.departure_segment_index,
            booking.arrival_segment_index,
        ):
            impacted = _segment_is_affected(segment, close_ports, congested_legs) or impacted

    return impacted, current_direct


def _ordered_segments(route: Any) -> tuple[Any, ...]:
    segments = tuple(sorted(route.segments, key=lambda item: item.sequence_index))
    if not segments:
        raise ValueError("route has no segments")
    indexes = [segment.sequence_index for segment in segments]
    if indexes != list(range(1, len(indexes) + 1)):
        raise ValueError("route segment indexes are not consecutive")
    if any(segment.associated_service_route is not route for segment in segments):
        raise ValueError("segment route identity mismatch")
    return segments


def _segment_position(segments: tuple[Any, ...], target: Any) -> int:
    for position, segment in enumerate(segments):
        if segment is target:
            return position
    raise ValueError("segment is not in route")


def _booking_span(segments: tuple[Any, ...], departure: Any, arrival: Any) -> tuple[Any, ...]:
    if not isinstance(departure, int) or isinstance(departure, bool):
        raise ValueError("departure segment index is not an integer")
    if not isinstance(arrival, int) or isinstance(arrival, bool):
        raise ValueError("arrival segment index is not an integer")
    by_index = {segment.sequence_index: position for position, segment in enumerate(segments)}
    try:
        start = by_index[departure]
        end = by_index[arrival]
    except KeyError as exc:
        raise ValueError("booking segment index is outside route") from exc

    result: list[Any] = []
    position = start
    for _ in range(len(segments)):
        result.append(segments[position])
        if position == end:
            return tuple(result)
        position = (position + 1) % len(segments)
    raise ValueError("booking spans a complete route cycle")


def _segments_after_current_until(
    segments: tuple[Any, ...], current_position: int, end_position: int
) -> tuple[Any, ...]:
    result: list[Any] = []
    position = (current_position + 1) % len(segments)
    for _ in range(len(segments)):
        result.append(segments[position])
        if position == end_position:
            return tuple(result)
        position = (position + 1) % len(segments)
    raise ValueError("current segment cannot reach booking arrival")


def _segment_is_affected(
    segment: Any, close_ports: tuple[Any, ...], congested_legs: tuple[Any, ...]
) -> bool:
    leg = segment.associated_leg
    if _contains_identity(congested_legs, leg):
        return True
    departure = leg.departure_port
    arrival = leg.arrival_port
    return _contains_identity(close_ports, departure) or _contains_identity(close_ports, arrival)


def _contains_identity(items: tuple[Any, ...] | list[Any], target: Any) -> bool:
    return any(item is target for item in items)
