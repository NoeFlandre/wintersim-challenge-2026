"""Participant-owned Round 1 congestion-only direct-booking policy.

Only an exact origin-to-destination shipment whose endpoints match an active
congested leg may receive a direct booking, and only while no berth closure is
active. Every other decision delegates to the organizer fallback.
"""

from __future__ import annotations

import datetime as dt
import importlib
import math
from typing import Any


def _active_congested_legs(context: Any, now: dt.datetime) -> tuple[tuple[Any, ...], bool] | None:
    """Return active congested legs and whether an active berth is closed."""
    plans = getattr(context, "disruption_plans", None)
    if plans is None:
        return None
    try:
        plan_values = tuple(plans)
    except (TypeError, ValueError):
        return None

    congested: list[Any] = []
    closure_active = False
    for plan in plan_values:
        start_raw = getattr(plan, "start_offset_days", None)
        duration_raw = getattr(plan, "duration_days", None)
        multiplier_raw = getattr(plan, "multiplier", 1.0)
        if start_raw is None or duration_raw is None or multiplier_raw is None:
            return None
        try:
            start_offset = float(start_raw)
            duration = float(duration_raw)
            multiplier = float(multiplier_raw)
        except (TypeError, ValueError, OverflowError):
            return None
        if not all(math.isfinite(value) for value in (start_offset, duration, multiplier)):
            return None
        if duration <= 0.0 or multiplier <= 0.0:
            return None
        try:
            start = dt.datetime.min + dt.timedelta(days=start_offset)
            end = start + dt.timedelta(days=duration)
        except (OverflowError, ValueError):
            return None
        if not start <= now < end:
            continue

        if bool(getattr(plan, "close_berth", False)):
            berth = getattr(plan, "target_berth", None)
            if berth is None or getattr(berth, "port", None) is None:
                return None
            closure_active = True

        if multiplier > 1.0:
            leg = getattr(plan, "target_leg", None)
            if leg is None:
                return None
            if (
                getattr(leg, "departure_port", None) is None
                or getattr(leg, "arrival_port", None) is None
            ):
                return None
            if not any(existing is leg for existing in congested):
                congested.append(leg)

    return tuple(congested), closure_active


def _find_direct_segment(context: Any, target_leg: Any) -> tuple[Any, int] | None:
    """Find a deterministic original-route segment with a deployed vessel."""
    routes = getattr(context, "service_routes", None)
    if routes is None:
        return None
    try:
        route_values = tuple(routes)
    except (TypeError, ValueError):
        return None

    for route in route_values:
        if getattr(route, "source_service_route", None) is not None:
            continue
        deployed = getattr(route, "deployed_vessels", None)
        try:
            if not deployed:
                continue
            segments = sorted(
                getattr(route, "segments", ()),
                key=lambda segment: segment.sequence_index,
            )
        except (AttributeError, TypeError, ValueError):
            return None
        for segment in segments:
            if getattr(segment, "associated_leg", None) is not target_leg:
                continue
            sequence_index = getattr(segment, "sequence_index", None)
            if isinstance(sequence_index, bool) or not isinstance(sequence_index, int):
                return None
            if sequence_index <= 0:
                return None
            if not isinstance(getattr(route, "associated_bookings", None), list):
                return None
            return route, sequence_index
    return None


def _install_direct_booking(shipment: Any, route: Any, sequence_index: int) -> bool | None:
    """Install one booking atomically, restoring every touched list on failure."""
    old_bookings = getattr(shipment, "associated_bookings", None)
    route_bookings = getattr(route, "associated_bookings", None)
    if not isinstance(old_bookings, list) or not isinstance(route_bookings, list):
        return None
    old_index = getattr(shipment, "current_booking_index", None)

    try:
        booking_module = importlib.import_module("maritime_data_context")
        booking_type = booking_module.Booking
        booking = booking_type(
            sequence_index=1,
            shipment=shipment,
            service_route=route,
            departure_segment_index=sequence_index,
            arrival_segment_index=sequence_index,
        )
    except (ImportError, AttributeError, TypeError, ValueError):
        return None

    touched_routes: list[tuple[Any, list[Any]]] = [(route, list(route_bookings))]
    try:
        for old_booking in old_bookings:
            old_route = getattr(old_booking, "service_route", None)
            old_route_bookings = getattr(old_route, "associated_bookings", None)
            if old_route is None or not isinstance(old_route_bookings, list):
                return None
            if not any(existing is old_route for existing, _ in touched_routes):
                touched_routes.append((old_route, list(old_route_bookings)))
    except (AttributeError, TypeError, ValueError):
        return None

    try:
        for old_booking in old_bookings:
            old_route = old_booking.service_route
            while old_booking in old_route.associated_bookings:
                old_route.associated_bookings.remove(old_booking)
        shipment.associated_bookings = [booking]
        shipment.current_booking_index = 1
        route_bookings.append(booking)
    except (AttributeError, TypeError, ValueError, IndexError, RuntimeError):
        for touched_route, snapshot in touched_routes:
            touched_route.associated_bookings[:] = snapshot
        shipment.associated_bookings = old_bookings
        shipment.current_booking_index = old_index
        return None
    return True


def _direct_booking_decision(context: Any, now: Any, shipment: Any) -> bool | None:
    if context is None or shipment is None or not isinstance(now, dt.datetime):
        return None
    demand = getattr(shipment, "demand", None)
    origin = getattr(demand, "origin_port", None)
    destination = getattr(demand, "destination_port", None)
    if origin is None or destination is None or origin is destination:
        return None

    active = _active_congested_legs(context, now)
    if active is None:
        return None
    congested_legs, closure_active = active
    if closure_active or not congested_legs:
        return None

    for target_leg in congested_legs:
        departure = getattr(target_leg, "departure_port", None)
        arrival = getattr(target_leg, "arrival_port", None)
        if origin is not departure or destination is not arrival:
            continue
        match = _find_direct_segment(context, target_leg)
        if match is None:
            return None
        route, sequence_index = match
        return _install_direct_booking(shipment, route, sequence_index)
    return None


class UserStrategy:
    """Participant adapter with one narrow cargo-routing override."""

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

        A congestion-only exact endpoint match receives one validated direct
        booking; every other case returns ``None`` for the organizer fallback.
        """
        return _direct_booking_decision(context, now, shipment)

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Adjust booking chains before a vessel handles cargo.

        Returns ``None`` to use the organizer fallback.
        """
        return None
