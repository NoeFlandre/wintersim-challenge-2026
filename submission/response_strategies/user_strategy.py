"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. Returning ``None`` from any method
signals "not handled; use the organizer fallback", leaving the maritime data
context, routes, bookings, and vessel state exactly as the framework built
them.

The current experiment overrides only berth selection when an active
disruption exposes carried cargo; all other decisions delegate to the
organizer fallback. The policy is intentionally small and fail-closed.

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

import datetime as dt
import math
import numbers
from typing import Any


def _active_disruption_targets(
    context: Any, now: dt.datetime
) -> tuple[list[Any], list[Any]] | None:
    """Return active target legs and closed-berth ports, or fail closed."""
    plans = getattr(context, "disruption_plans", None)
    if plans is None:
        return None
    try:
        plans = list(plans)
    except (TypeError, ValueError):
        return None

    active_legs: list[Any] = []
    active_ports: list[Any] = []
    for plan in plans:
        start = getattr(plan, "start_offset_days", None)
        duration = getattr(plan, "duration_days", None)
        if (
            isinstance(start, bool)
            or not isinstance(start, numbers.Real)
            or not math.isfinite(float(start))
            or float(start) < 0.0
            or isinstance(duration, bool)
            or not isinstance(duration, numbers.Real)
            or not math.isfinite(float(duration))
            or float(duration) <= 0.0
        ):
            return None
        target_leg = getattr(plan, "target_leg", None)
        target_berth = getattr(plan, "target_berth", None)
        if (target_leg is None) == (target_berth is None):
            return None
        try:
            start_time = dt.datetime.min + dt.timedelta(days=float(start))
            end_time = start_time + dt.timedelta(days=float(duration))
        except (OverflowError, TypeError, ValueError):
            return None

        if target_leg is not None:
            departure_port = getattr(target_leg, "departure_port", None)
            arrival_port = getattr(target_leg, "arrival_port", None)
            if departure_port is None or arrival_port is None:
                return None
            if start_time <= now < end_time and not any(
                target is target_leg for target in active_legs
            ):
                active_legs.append(target_leg)
            continue

        port = getattr(target_berth, "port", None)
        if port is None:
            return None
        if start_time <= now < end_time and not any(target is port for target in active_ports):
            active_ports.append(port)

    if not active_legs and not active_ports:
        return None
    return active_legs, active_ports


def _segment_slice(booking: Any) -> list[Any] | None:
    """Return the cyclic segment slice represented by one booking."""
    route = getattr(booking, "service_route", None)
    if route is None:
        return None
    raw_segments = getattr(route, "segments", None)
    if raw_segments is None:
        return None
    try:
        segments = sorted(
            raw_segments,
            key=lambda segment: getattr(segment, "sequence_index", 0),
        )
    except (TypeError, ValueError):
        return None
    if not segments:
        return None

    departure_index = getattr(booking, "departure_segment_index", None)
    arrival_index = getattr(booking, "arrival_segment_index", None)
    if departure_index is None or arrival_index is None:
        return segments
    departure_position = next(
        (
            index
            for index, segment in enumerate(segments)
            if getattr(segment, "sequence_index", None) == departure_index
        ),
        None,
    )
    arrival_position = next(
        (
            index
            for index, segment in enumerate(segments)
            if getattr(segment, "sequence_index", None) == arrival_index
        ),
        None,
    )
    if departure_position is None or arrival_position is None:
        return None
    selected: list[Any] = []
    position = departure_position
    while True:
        selected.append(segments[position])
        if position == arrival_position:
            return selected
        position = (position + 1) % len(segments)
        if len(selected) > len(segments):
            return None


def _shipment_is_exposed(
    shipment: Any,
    active_legs: list[Any],
    active_ports: list[Any],
) -> bool | None:
    """Classify one carried shipment without mutating its booking chain."""
    bookings = getattr(shipment, "associated_bookings", None)
    if bookings is None:
        return None
    try:
        booking_values = list(bookings)
    except (TypeError, ValueError):
        return None
    current_index = getattr(shipment, "current_booking_index", None)
    for booking in booking_values:
        sequence_index = getattr(booking, "sequence_index", None)
        if current_index is not None and sequence_index is not None:
            try:
                if sequence_index < current_index:
                    continue
            except TypeError:
                return None
        segments = _segment_slice(booking)
        if segments is None:
            return None
        for segment in segments:
            leg = getattr(segment, "associated_leg", None)
            if leg is None:
                return None
            departure_port = getattr(leg, "departure_port", None)
            arrival_port = getattr(leg, "arrival_port", None)
            if departure_port is None or arrival_port is None:
                return None
            if any(target is leg for target in active_legs) or any(
                target is departure_port or target is arrival_port for target in active_ports
            ):
                return True
    return False


def _exposed_cargo_berth_choice(
    context: Any,
    waiting_vessels: Any,
    current_time: Any,
    waiting_since_by_vessel: Any,
) -> Any:
    """Choose the vessel carrying the oldest exposed TEU backlog."""
    if not isinstance(current_time, dt.datetime):
        return None
    try:
        waiting = list(waiting_vessels)
    except (TypeError, ValueError):
        return None
    if not waiting:
        return None

    targets = _active_disruption_targets(context, current_time)
    if targets is None:
        return None
    active_legs, active_ports = targets
    scores: list[float] = []
    for vessel in waiting:
        shipments = getattr(vessel, "carried_shipments", None)
        if shipments is None:
            return None
        try:
            shipment_values = list(shipments)
        except (TypeError, ValueError):
            return None
        exposed_teu = 0.0
        for shipment in shipment_values:
            teu = getattr(shipment, "teu_size", None)
            if (
                isinstance(teu, bool)
                or not isinstance(teu, numbers.Real)
                or not math.isfinite(float(teu))
                or float(teu) < 0.0
            ):
                return None
            exposed = _shipment_is_exposed(shipment, active_legs, active_ports)
            if exposed is None:
                return None
            if exposed:
                exposed_teu += float(teu)

        waiting_since = current_time
        if waiting_since_by_vessel is not None:
            get = getattr(waiting_since_by_vessel, "get", None)
            if get is None:
                return None
            try:
                waiting_since = get(vessel, current_time)
            except (TypeError, ValueError, KeyError):
                return None
        if not isinstance(waiting_since, dt.datetime):
            return None
        try:
            waiting_hours = max(
                0.0,
                (current_time - waiting_since).total_seconds() / 3600.0,
            )
        except (OverflowError, TypeError, ValueError):
            return None
        scores.append(exposed_teu * waiting_hours)

    maximum = max(scores)
    if maximum <= 0.0 or all(score == maximum for score in scores):
        return None
    return max(
        enumerate(waiting),
        key=lambda item: (scores[item[0]], -item[0]),
    )[1]


class UserStrategy:
    """Participant adapter with a narrowly scoped berth policy.

    The berth hook may return a waiting vessel for an active exposed-cargo
    queue; the other hooks always return ``None``. No hook mutates its inputs.
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

        Prioritizes the oldest exposed TEU backlog only during an active
        disruption; all other states delegate to the organizer fallback.
        """
        return _exposed_cargo_berth_choice(
            maritime_data_context,
            waiting_vessels,
            current_time,
            waiting_since_by_vessel,
        )

    @staticmethod
    def create_alternative_service_routes(context: Any, now: Any, vessel: Any = None) -> Any:
        """Build alternative service routes for a vessel.

        Returns ``None`` ("not handled") which must leave ``context`` unchanged.
        """
        return None

    @staticmethod
    def assign_associated_bookings(context: Any, now: Any, shipment: Any) -> Any:
        """Assign a complete booking chain for a shipment.

        Returns ``None`` to use the organizer fallback.
        """
        return None

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Adjust booking chains before a vessel handles cargo.

        Returns ``None`` to use the organizer fallback.
        """
        return None
