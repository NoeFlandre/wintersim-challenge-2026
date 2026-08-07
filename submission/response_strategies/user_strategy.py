"""Participant strategy for the Round 1 immediate-direct-next-leg experiment.

The participant surface is deliberately conservative.  During an active
disruption it may install one direct booking only when an original service
route has a vessel whose next physical leg is already the shipment's exact
origin-to-destination leg.  Every other decision delegates to the organizer
fallback by returning ``None``.

Runtime constraints:

* standard-library imports only (the organizer ``Booking`` class is resolved
  lazily at the one point where a booking must be constructed);
* no I/O, network, subprocess, environment, wall-clock, or randomness access;
* no mutable module-level state and no mutation before all gates pass.
"""

from __future__ import annotations

import datetime as dt
import math
import numbers
from typing import Any


def _active_disruption_targets(
    context: Any, now: dt.datetime
) -> tuple[list[Any], list[Any]] | None:
    """Return active congested legs and closed ports, or fail closed.

    ``None`` means either no meaningful disruption is active or the runtime
    shape is not trustworthy enough for a participant override.
    """
    plans = getattr(context, "disruption_plans", None)
    if plans is None:
        return None
    try:
        plan_values = list(plans)
    except (TypeError, ValueError):
        return None

    active_legs: list[Any] = []
    active_ports: list[Any] = []
    for plan in plan_values:
        start_value = getattr(plan, "start_offset_days", None)
        duration_value = getattr(plan, "duration_days", None)
        if (
            isinstance(start_value, bool)
            or not isinstance(start_value, numbers.Real)
            or not math.isfinite(float(start_value))
            or float(start_value) < 0.0
            or isinstance(duration_value, bool)
            or not isinstance(duration_value, numbers.Real)
            or not math.isfinite(float(duration_value))
            or float(duration_value) <= 0.0
        ):
            return None

        target_leg = getattr(plan, "target_leg", None)
        target_berth = getattr(plan, "target_berth", None)
        if (target_leg is None) == (target_berth is None):
            return None
        try:
            start = dt.datetime.min + dt.timedelta(days=float(start_value))
            end = start + dt.timedelta(days=float(duration_value))
        except (OverflowError, TypeError, ValueError):
            return None
        if not (start <= now < end):
            continue

        if target_leg is not None:
            multiplier = getattr(plan, "multiplier", None)
            if (
                isinstance(multiplier, bool)
                or not isinstance(multiplier, numbers.Real)
                or not math.isfinite(float(multiplier))
            ):
                return None
            if float(multiplier) > 1.0:
                active_legs.append(target_leg)
            continue

        if bool(getattr(plan, "close_berth", False)):
            port = getattr(target_berth, "port", None)
            if port is None:
                return None
            if not any(existing is port for existing in active_ports):
                active_ports.append(port)

    if not active_legs and not active_ports:
        return None
    return active_legs, active_ports


def _is_original_route(route: Any) -> bool:
    """Return whether ``route`` is an untouched organizer route."""
    return (
        getattr(route, "source_service_route", None) is None
        and getattr(route, "disruption_key", None) is None
    )


def _ordered_segments(route: Any) -> list[Any] | None:
    """Return route segments in sequence order, or ``None`` if malformed."""
    segments = getattr(route, "segments", None)
    if segments is None:
        return None
    try:
        ordered = sorted(segments, key=lambda segment: segment.sequence_index)
    except (AttributeError, TypeError, ValueError):
        return None
    if not ordered:
        return None
    return ordered


def _next_leg_is_ready(route: Any, segment: Any) -> bool:
    """Check for a deployed vessel whose next leg is exactly ``segment``."""
    vessels = getattr(route, "deployed_vessels", None)
    if vessels is None:
        return False
    try:
        vessel_values = list(vessels)
    except (TypeError, ValueError):
        return False

    segment_leg = getattr(segment, "associated_leg", None)
    if segment_leg is None:
        return False
    departure_port = getattr(segment_leg, "departure_port", None)
    if departure_port is None:
        return False

    for vessel in vessel_values:
        if getattr(vessel, "assigned_service_route", None) is not route:
            continue
        if getattr(vessel, "pending_assigned_service_route", None) is not None:
            continue
        get_next_segment = getattr(vessel, "get_next_segment", None)
        if not callable(get_next_segment):
            continue
        try:
            next_segment = get_next_segment()
        except (AttributeError, TypeError, ValueError, RuntimeError):
            continue
        if next_segment is not segment:
            continue

        current_segment = getattr(vessel, "current_segment", None)
        if current_segment is None:
            return True
        current_leg = getattr(current_segment, "associated_leg", None)
        if current_leg is None:
            continue
        if getattr(current_leg, "arrival_port", None) is departure_port:
            return True
    return False


def _install_direct_booking(shipment: Any, route: Any, segment: Any) -> Any:
    """Install one direct booking transactionally, returning ``True``/``None``."""
    try:
        from maritime_data_context import Booking
    except (ImportError, AttributeError):
        return None

    shipment_bookings = getattr(shipment, "associated_bookings", None)
    route_bookings = getattr(route, "associated_bookings", None)
    if not isinstance(shipment_bookings, list) or not isinstance(route_bookings, list):
        return None

    old_bookings = list(shipment_bookings)
    old_index = getattr(shipment, "current_booking_index", None)
    reverse_snapshots: dict[Any, list[Any]] = {}
    for booking in old_bookings:
        old_route = getattr(booking, "service_route", None)
        if old_route is None:
            continue
        old_reverse = getattr(old_route, "associated_bookings", None)
        if not isinstance(old_reverse, list):
            return None
        if old_route not in reverse_snapshots:
            reverse_snapshots[old_route] = list(old_reverse)

    try:
        for booking in old_bookings:
            old_route = getattr(booking, "service_route", None)
            if old_route is None:
                continue
            old_reverse = old_route.associated_bookings
            while booking in old_reverse:
                old_reverse.remove(booking)

        shipment_bookings.clear()
        booking = Booking(
            sequence_index=1,
            shipment=shipment,
            service_route=route,
            departure_segment_index=segment.sequence_index,
            arrival_segment_index=segment.sequence_index,
        )
        shipment_bookings.append(booking)
        route_bookings.append(booking)
        shipment.current_booking_index = 1
        return True
    except Exception:
        shipment_bookings.clear()
        shipment_bookings.extend(old_bookings)
        shipment.current_booking_index = old_index
        for old_route, old_reverse in reverse_snapshots.items():
            old_route.associated_bookings.clear()
            old_route.associated_bookings.extend(old_reverse)
        return None


def _assign_immediate_direct_next_leg(context: Any, now: Any, shipment: Any) -> Any:
    """Apply the narrow direct-next-leg policy, otherwise delegate."""
    if not isinstance(now, dt.datetime):
        return None
    demand = getattr(shipment, "demand", None)
    if demand is None:
        return None
    origin_port = getattr(demand, "origin_port", None)
    destination_port = getattr(demand, "destination_port", None)
    if origin_port is None or destination_port is None or origin_port is destination_port:
        return None

    targets = _active_disruption_targets(context, now)
    if targets is None:
        return None
    active_legs, active_ports = targets

    routes = getattr(context, "service_routes", None)
    if routes is None:
        return None
    try:
        route_values = list(routes)
    except (TypeError, ValueError):
        return None

    for route in route_values:
        if not _is_original_route(route):
            continue
        segments = _ordered_segments(route)
        if segments is None:
            continue
        for segment in segments:
            leg = getattr(segment, "associated_leg", None)
            if leg is None:
                continue
            if (
                getattr(leg, "departure_port", None) is not origin_port
                or getattr(leg, "arrival_port", None) is not destination_port
            ):
                continue
            if any(target is leg for target in active_legs):
                continue
            if any(target is origin_port or target is destination_port for target in active_ports):
                continue
            try:
                multiplier = float(getattr(leg, "sailing_time_multiplier", 1.0))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(multiplier) or multiplier != 1.0:
                continue
            if _next_leg_is_ready(route, segment):
                return _install_direct_booking(shipment, route, segment)
    return None


class UserStrategy:
    """Participant adapter with one conservative Round 1 cargo override."""

    @staticmethod
    def select_vessel_for_berth(
        maritime_data_context: Any,
        port: Any,
        waiting_vessels: Any,
        available_berths: Any,
        current_time: Any,
        waiting_since_by_vessel: Any = None,
    ) -> Any:
        """Delegate berth selection to the organizer fallback."""
        return None

    @staticmethod
    def create_alternative_service_routes(context: Any, now: Any, vessel: Any = None) -> Any:
        """Delegate route creation to the organizer fallback."""
        return None

    @staticmethod
    def assign_associated_bookings(context: Any, now: Any, shipment: Any) -> Any:
        """Use a ready direct next leg, or delegate initial booking assignment."""
        return _assign_immediate_direct_next_leg(context, now, shipment)

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Delegate in-transit rebooking to the organizer fallback."""
        return None
