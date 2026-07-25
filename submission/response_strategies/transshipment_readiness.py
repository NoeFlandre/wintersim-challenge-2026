from __future__ import annotations

from datetime import datetime, timedelta
from math import floor, isfinite
from typing import Any, NamedTuple


class BarrierDecision(NamedTuple):
    receiver: Any
    buffer: Any
    guaranteed_transitional_teu: float
    next_opportunity_hours: float
    buffer_service_hours: float
    affected_receiver_teu: float
    net_teu_hours: float


class _ReceiverCargo(NamedTuple):
    mature_shipments: tuple[Any, ...]
    transitional_shipments: tuple[Any, ...]
    mature_teu: float
    transitional_teu: float


class _BookingChain(NamedTuple):
    current: Any
    next_booking: Any | None


def _number(value: Any, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("numeric value required")
    number = float(value)
    if not isfinite(number):
        raise ValueError("finite value required")
    if positive and number <= 0:
        raise ValueError("positive value required")
    if nonnegative and number < 0:
        raise ValueError("nonnegative value required")
    return number


def _index(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("integer sequence index required")
    return value


def _identity_contains(values: Any, target: Any) -> bool:
    return any(value is target for value in values)


def _identity_unique(values: tuple[Any, ...]) -> bool:
    return all(not _identity_contains(values[:index], value) for index, value in enumerate(values))


def _teu_sum(shipments: Any, *, positive: bool = False) -> float:
    items = tuple(shipments)
    if not _identity_unique(items):
        raise ValueError("duplicate shipment identity")
    total = 0.0
    for shipment in items:
        total += _number(shipment.teu_size, positive=positive, nonnegative=not positive)
    if not isfinite(total):
        raise ValueError("non-finite TEU total")
    return total


def _route_segments(route: Any) -> tuple[Any, ...]:
    if route is None:
        raise ValueError("route required")
    if route.source_service_route is not None or route.disruption_key is not None:
        raise ValueError("alternative route")
    segments = tuple(route.segments)
    if not segments or not _identity_unique(segments):
        raise ValueError("nonempty unique route segments required")
    indexes = tuple(_index(segment.sequence_index) for segment in segments)
    if indexes != tuple(sorted(indexes)) or len(set(indexes)) != len(indexes):
        raise ValueError("route segments must be uniquely ordered")
    if indexes != tuple(range(indexes[0], indexes[0] + len(indexes))):
        raise ValueError("route segment indexes must be complete")
    for position, segment in enumerate(segments):
        if segment.associated_service_route is not route:
            raise ValueError("segment route membership mismatch")
        leg = segment.associated_leg
        if leg is None or leg.departure_port is None or leg.arrival_port is None:
            raise ValueError("complete route leg required")
        _number(leg.sailing_distance, nonnegative=True)
        if _number(leg.sailing_time_multiplier) != 1.0:
            raise ValueError("unstable sailing multiplier")
        next_leg = segments[(position + 1) % len(segments)].associated_leg
        if leg.arrival_port is not next_leg.departure_port:
            raise ValueError("route must be connected and cyclic")
    return segments


def _segment_position(segments: tuple[Any, ...], target: Any) -> int:
    positions = [index for index, segment in enumerate(segments) if segment is target]
    if len(positions) != 1:
        raise ValueError("segment must belong uniquely to route")
    return positions[0]


def _next_segment(vessel: Any, segments: tuple[Any, ...]) -> Any:
    current_position = _segment_position(segments, vessel.current_segment)
    expected = segments[(current_position + 1) % len(segments)]
    actual = vessel.get_next_segment()
    if actual is not expected:
        raise ValueError("invalid next segment")
    return expected


def _validate_route_fleet(route: Any, expected_vessel: Any) -> tuple[Any, ...]:
    segments = _route_segments(route)
    deployed = tuple(route.deployed_vessels)
    if not deployed or not _identity_unique(deployed):
        raise ValueError("valid deployed fleet required")
    if not _identity_contains(deployed, expected_vessel):
        raise ValueError("vessel not deployed on assigned route")
    for vessel in deployed:
        if vessel.assigned_service_route is not route:
            raise ValueError("deployed route mismatch")
        if vessel.pending_assigned_service_route is not None:
            raise ValueError("pending route assignment")
        vessel_class = vessel.vessel_class
        if vessel_class is None:
            raise ValueError("vessel class required")
        _number(vessel_class.sailing_speed, positive=True)
        _segment_position(segments, vessel.current_segment)
    return segments


def _waiting_hours(current_time: Any, waiting_start: Any) -> float:
    if not isinstance(current_time, datetime) or not isinstance(waiting_start, datetime):
        raise TypeError("valid datetime arithmetic required")
    hours = (current_time - waiting_start).total_seconds() / 3600.0
    return max(0.0, _number(hours))


def _normalized(values: tuple[float, ...]) -> tuple[float, ...]:
    if not values:
        raise ValueError("values required")
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return (0.0,) * len(values)
    span = maximum - minimum
    normalized = tuple((value - minimum) / span for value in values)
    if not all(isfinite(value) for value in normalized):
        raise ValueError("finite normalization required")
    return normalized


def _fallback_ranking(
    waiting_vessels: Any,
    current_time: Any,
    waiting_since_by_vessel: Any,
) -> tuple[Any | None, bool]:
    vessels = tuple(waiting_vessels)
    if not vessels or not _identity_unique(vessels):
        return None, False
    waiting_map = {} if waiting_since_by_vessel is None else waiting_since_by_vessel
    waits: list[float] = []
    carried: list[float] = []
    capacities: list[float] = []
    handling: list[float] = []
    for vessel in vessels:
        waiting_start = waiting_map.get(vessel, current_time)
        waits.append(_waiting_hours(current_time, waiting_start))
        carried.append(_teu_sum(vessel.carried_shipments))
        vessel_class = vessel.vessel_class
        if vessel_class is None:
            return None, False
        capacities.append(_number(vessel_class.teu_capacity, positive=True))
        discharging = vessel.get_discharging_shipments_at_current_segment()
        loading = vessel.get_loading_shipments_at_next_segment()
        handling.append(_teu_sum(discharging) + _teu_sum(loading))

    normalized_waits = _normalized(tuple(waits))
    normalized_carried = _normalized(tuple(carried))
    normalized_capacities = _normalized(tuple(capacities))
    normalized_handling = _normalized(tuple(handling))
    scores = tuple(
        0.4 * wait_score + 0.3 * carried_score + 0.2 * capacity_score - 0.1 * handling_score
        for wait_score, carried_score, capacity_score, handling_score in zip(
            normalized_waits,
            normalized_carried,
            normalized_capacities,
            normalized_handling,
            strict=True,
        )
    )
    if not all(isfinite(score) for score in scores):
        return None, False
    maximum = max(scores)
    winner_index = next(index for index, score in enumerate(scores) if score == maximum)
    is_strict = sum(score == maximum for score in scores) == 1
    return vessels[winner_index], is_strict


def _strict_fallback_winner(
    waiting_vessels: Any,
    current_time: Any,
    waiting_since_by_vessel: Any,
) -> Any | None:
    winner, is_strict = _fallback_ranking(
        waiting_vessels,
        current_time,
        waiting_since_by_vessel,
    )
    return winner if is_strict else None


def _segment_by_index(route: Any, sequence_index: Any) -> Any:
    wanted = _index(sequence_index)
    segments = _route_segments(route)
    matches = [segment for segment in segments if segment.sequence_index == wanted]
    if len(matches) != 1:
        raise ValueError("booking segment index must resolve uniquely")
    return matches[0]


def _booking_chain(shipment: Any) -> _BookingChain:
    bookings = tuple(shipment.associated_bookings)
    if not bookings or not _identity_unique(bookings):
        raise ValueError("nonempty unique booking chain required")
    indexes: list[int] = []
    for booking in bookings:
        if booking.shipment is not shipment:
            raise ValueError("booking shipment mismatch")
        indexes.append(_index(booking.sequence_index))
        route = booking.service_route
        departure = _segment_by_index(route, booking.departure_segment_index)
        arrival = _segment_by_index(route, booking.arrival_segment_index)
        if departure.associated_leg.departure_port is None:
            raise ValueError("booking departure port required")
        if arrival.associated_leg.arrival_port is None:
            raise ValueError("booking arrival port required")
        departure_port = departure.associated_leg.departure_port
        arrival_port = arrival.associated_leg.arrival_port
        if departure_port is arrival_port:
            raise ValueError("booking must not be a full cycle")
    if len(set(indexes)) != len(indexes):
        raise ValueError("duplicate booking indexes")
    current_matches = [
        booking for booking in bookings if booking.sequence_index == shipment.current_booking_index
    ]
    if len(current_matches) != 1:
        raise ValueError("current booking must resolve uniquely")
    current = current_matches[0]
    later = [booking for booking in bookings if booking.sequence_index > current.sequence_index]
    next_booking = min(later, key=lambda booking: booking.sequence_index) if later else None
    return _BookingChain(current=current, next_booking=next_booking)


def _classify_receiver_cargo(port: Any, receiver_route: Any, target: Any) -> _ReceiverCargo:
    mature: list[Any] = []
    transitional: list[Any] = []
    for shipment in tuple(port.shipments_in_storage):
        if shipment.current_storage_port is not port or shipment.carrying_vessel is not None:
            raise ValueError("shipment storage state mismatch")
        _number(shipment.teu_size, positive=True)
        chain = _booking_chain(shipment)
        current = chain.current
        current_departure = _segment_by_index(
            current.service_route, current.departure_segment_index
        )
        if (
            current.service_route is receiver_route
            and current_departure is target
            and current_departure.associated_leg.departure_port is port
        ):
            mature.append(shipment)
            continue

        next_booking = chain.next_booking
        if next_booking is None:
            continue
        current_arrival = _segment_by_index(current.service_route, current.arrival_segment_index)
        next_departure = _segment_by_index(
            next_booking.service_route, next_booking.departure_segment_index
        )
        if (
            current_arrival.associated_leg.arrival_port is port
            and next_booking.service_route is receiver_route
            and next_departure is target
            and next_departure.associated_leg.departure_port is port
            and current.service_route is not next_booking.service_route
        ):
            transitional.append(shipment)

    mature_items = tuple(mature)
    transitional_items = tuple(transitional)
    return _ReceiverCargo(
        mature_shipments=mature_items,
        transitional_shipments=transitional_items,
        mature_teu=_teu_sum(mature_items, positive=True),
        transitional_teu=_teu_sum(transitional_items, positive=True),
    )


def _receiver_teu(receiver: Any, cargo: _ReceiverCargo) -> tuple[float, float]:
    carried = tuple(receiver.carried_shipments)
    total_carried = _teu_sum(carried)
    discharging = tuple(receiver.get_discharging_shipments_at_current_segment())
    if not _identity_unique(discharging):
        raise ValueError("duplicate receiver discharge cargo")
    if any(not _identity_contains(carried, shipment) for shipment in discharging):
        raise ValueError("receiver discharge cargo not carried")
    discharging_teu = _teu_sum(discharging)
    onboard_after_discharge = total_carried - discharging_teu
    if onboard_after_discharge < 0 or not isfinite(onboard_after_discharge):
        raise ValueError("invalid receiver onboard TEU")
    capacity = _number(receiver.vessel_class.teu_capacity, positive=True)
    if onboard_after_discharge + cargo.mature_teu + cargo.transitional_teu > capacity:
        raise ValueError("whole receiver cargo set does not fit")
    affected = total_carried + cargo.mature_teu
    if affected < 0 or not isfinite(affected):
        raise ValueError("invalid affected receiver TEU")
    return onboard_after_discharge, affected


def _route_ports_and_berths(
    segments: tuple[Any, ...],
) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    ports: list[Any] = []
    for segment in segments:
        leg = segment.associated_leg
        for port in (leg.departure_port, leg.arrival_port):
            if not any(existing is port for existing in ports):
                ports.append(port)
    berths: list[Any] = []
    for port in ports:
        for berth in tuple(port.berths):
            if berth.port is not port:
                raise ValueError("berth port mismatch")
            if not any(existing is berth for existing in berths):
                berths.append(berth)
    return tuple(ports), tuple(berths)


def _active_disruption_affects(
    context: Any,
    current_time: Any,
    segments: tuple[Any, ...],
) -> bool:
    if not isinstance(current_time, datetime):
        raise TypeError("current time must be datetime")
    legs = tuple(segment.associated_leg for segment in segments)
    _, berths = _route_ports_and_berths(segments)
    for plan in tuple(context.disruption_plans):
        start_offset = _number(plan.start_offset_days, nonnegative=True)
        duration = _number(plan.duration_days, nonnegative=True)
        start = datetime.min + timedelta(days=start_offset)
        end = start + timedelta(days=duration)
        if start <= current_time < end and (
            _identity_contains(legs, plan.target_leg)
            or _identity_contains(berths, plan.target_berth)
        ):
            return True
    return False


def _next_opportunity_hours(receiver: Any, route: Any, target: Any) -> float:
    segments = _validate_route_fleet(route, receiver)
    target_position = _segment_position(segments, target)
    receiver_speed = _number(receiver.vessel_class.sailing_speed, positive=True)
    receiver_return = float(
        sum(
            0.95
            * _number(segment.associated_leg.sailing_distance, nonnegative=True)
            / receiver_speed
            for segment in segments
        )
    )
    opportunities: list[float] = [receiver_return]
    for vessel in tuple(route.deployed_vessels):
        if vessel is receiver:
            continue
        speed = _number(vessel.vessel_class.sailing_speed, positive=True)
        current_position = _segment_position(segments, vessel.current_segment)
        position = (current_position + 1) % len(segments)
        hours = 0.0
        for _ in range(len(segments)):
            if position == target_position:
                break
            segment = segments[position]
            hours += (
                0.95 * _number(segment.associated_leg.sailing_distance, nonnegative=True) / speed
            )
            position = (position + 1) % len(segments)
        else:
            raise ValueError("compatible departure is unreachable")
        opportunities.append(hours)
    result = min(opportunities)
    if not isfinite(result) or result <= 0:
        raise ValueError("positive finite next opportunity required")
    return result


def _has_stored_transition_for_buffer(port: Any, route: Any, target: Any) -> bool:
    for shipment in tuple(port.shipments_in_storage):
        chain = _booking_chain(shipment)
        if chain.next_booking is None:
            continue
        current_arrival = _segment_by_index(
            chain.current.service_route, chain.current.arrival_segment_index
        )
        next_departure = _segment_by_index(
            chain.next_booking.service_route,
            chain.next_booking.departure_segment_index,
        )
        if (
            current_arrival.associated_leg.arrival_port is port
            and chain.next_booking.service_route is route
            and next_departure is target
            and chain.current.service_route is not chain.next_booking.service_route
        ):
            return True
    return False


def _buffer_connects_discharge_to_receiver(
    buffer: Any,
    port: Any,
    receiver_route: Any,
    receiver_target: Any,
) -> bool:
    for shipment in tuple(buffer.get_discharging_shipments_at_current_segment()):
        chain = _booking_chain(shipment)
        if chain.next_booking is None:
            continue
        current_arrival = _segment_by_index(
            chain.current.service_route, chain.current.arrival_segment_index
        )
        next_departure = _segment_by_index(
            chain.next_booking.service_route,
            chain.next_booking.departure_segment_index,
        )
        if (
            current_arrival.associated_leg.arrival_port is port
            and chain.next_booking.service_route is receiver_route
            and next_departure is receiver_target
        ):
            return True
    return False


def _buffer_service_hours(buffer: Any) -> float:
    vessel_class = buffer.vessel_class
    if vessel_class is None:
        raise ValueError("buffer vessel class required")
    capacity = _number(vessel_class.teu_capacity, positive=True)
    _number(vessel_class.sailing_speed, positive=True)
    loa = _number(vessel_class.loa, positive=True)
    carried = tuple(buffer.carried_shipments)
    total_carried = _teu_sum(carried)
    discharging = tuple(buffer.get_discharging_shipments_at_current_segment())
    if not _identity_unique(discharging):
        raise ValueError("duplicate buffer discharge cargo")
    if any(not _identity_contains(carried, shipment) for shipment in discharging):
        raise ValueError("buffer discharge cargo not carried")
    discharge_teu = _teu_sum(discharging)
    onboard_after_discharge = total_carried - discharge_teu
    if onboard_after_discharge < 0 or not isfinite(onboard_after_discharge):
        raise ValueError("invalid buffer onboard TEU")
    loading_teu = _teu_sum(buffer.get_loading_shipments_at_next_segment())
    crane_count = max(1, floor(loa / 55.0))
    service = 3.0 + (discharge_teu + loading_teu + max(0.0, capacity - onboard_after_discharge)) / (
        45.0 * crane_count
    )
    if not isfinite(service) or service <= 0:
        raise ValueError("positive finite buffer service required")
    return service


def _receiver_is_guaranteed_next(
    waiting_vessels: tuple[Any, ...],
    buffer: Any,
    receiver: Any,
    current_time: Any,
    waiting_since_by_vessel: Any,
) -> bool:
    remaining = tuple(vessel for vessel in waiting_vessels if vessel is not buffer)
    if len(remaining) != len(waiting_vessels) - 1 or not remaining:
        return False
    strict_winner = _strict_fallback_winner(remaining, current_time, waiting_since_by_vessel)
    if strict_winner is not receiver:
        return False
    if len(remaining) >= 3:
        return True
    return remaining[0] is receiver


def _evaluate(
    maritime_data_context: Any,
    port: Any,
    waiting_vessels: Any,
    available_berths: Any,
    current_time: Any,
    waiting_since_by_vessel: Any,
) -> BarrierDecision | None:
    vessels = tuple(waiting_vessels)
    berths = tuple(available_berths)
    port_berths = tuple(port.berths)
    if len(berths) != 1 or len(port_berths) != 1:
        return None
    if berths[0].port is not port or port_berths[0] is not berths[0]:
        return None
    receiver = _strict_fallback_winner(vessels, current_time, waiting_since_by_vessel)
    if receiver is None or not _identity_contains(vessels, receiver):
        return None
    if receiver.vessel_class is None or receiver.pending_assigned_service_route is not None:
        return None
    receiver_route = receiver.assigned_service_route
    receiver_segments = _validate_route_fleet(receiver_route, receiver)
    receiver_target = _next_segment(receiver, receiver_segments)
    if receiver_target.associated_leg.departure_port is not port:
        return None
    if _active_disruption_affects(maritime_data_context, current_time, receiver_segments):
        return None

    cargo = _classify_receiver_cargo(port, receiver_route, receiver_target)
    if cargo.transitional_teu <= 0:
        return None
    _, affected_receiver_teu = _receiver_teu(receiver, cargo)
    next_opportunity = _next_opportunity_hours(receiver, receiver_route, receiver_target)

    best: BarrierDecision | None = None
    for buffer in vessels:
        if buffer is receiver or buffer.pending_assigned_service_route is not None:
            continue
        if buffer.vessel_class is None:
            continue
        buffer_route = buffer.assigned_service_route
        try:
            buffer_segments = _validate_route_fleet(buffer_route, buffer)
            buffer_target = _next_segment(buffer, buffer_segments)
            if buffer_target.associated_leg.departure_port is not port:
                continue
            if buffer_route is receiver_route and buffer_target is receiver_target:
                continue
            if _active_disruption_affects(maritime_data_context, current_time, buffer_segments):
                continue
            if _has_stored_transition_for_buffer(port, buffer_route, buffer_target):
                continue
            if _buffer_connects_discharge_to_receiver(
                buffer, port, receiver_route, receiver_target
            ):
                continue
            if not _receiver_is_guaranteed_next(
                vessels,
                buffer,
                receiver,
                current_time,
                waiting_since_by_vessel,
            ):
                continue
            service = _buffer_service_hours(buffer)
        except (AttributeError, TypeError, ValueError, KeyError, IndexError, OverflowError):
            continue
        if not isfinite(next_opportunity) or next_opportunity <= service:
            continue
        net = cargo.transitional_teu * (next_opportunity - service) - (
            affected_receiver_teu * service
        )
        if not isfinite(net) or net <= 0:
            continue
        decision = BarrierDecision(
            receiver=receiver,
            buffer=buffer,
            guaranteed_transitional_teu=cargo.transitional_teu,
            next_opportunity_hours=next_opportunity,
            buffer_service_hours=service,
            affected_receiver_teu=affected_receiver_teu,
            net_teu_hours=net,
        )
        if best is None or decision.net_teu_hours > best.net_teu_hours:
            best = decision
    return best


def evaluate_transshipment_readiness_barrier(
    maritime_data_context: Any,
    port: Any,
    waiting_vessels: Any,
    available_berths: Any,
    current_time: Any,
    waiting_since_by_vessel: Any = None,
) -> BarrierDecision | None:
    try:
        return _evaluate(
            maritime_data_context=maritime_data_context,
            port=port,
            waiting_vessels=waiting_vessels,
            available_berths=available_berths,
            current_time=current_time,
            waiting_since_by_vessel=waiting_since_by_vessel,
        )
    except (AttributeError, TypeError, ValueError, KeyError, IndexError, OverflowError):
        return None


def choose_buffer_vessel(
    maritime_data_context: Any,
    port: Any,
    waiting_vessels: Any,
    available_berths: Any,
    current_time: Any,
    waiting_since_by_vessel: Any = None,
) -> object | None:
    decision = evaluate_transshipment_readiness_barrier(
        maritime_data_context=maritime_data_context,
        port=port,
        waiting_vessels=waiting_vessels,
        available_berths=available_berths,
        current_time=current_time,
        waiting_since_by_vessel=waiting_since_by_vessel,
    )
    return None if decision is None else decision.buffer
