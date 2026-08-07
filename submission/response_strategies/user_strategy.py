"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. This candidate changes only berth
selection during an active disruption: it gives priority to an empty vessel
whose already-reserved alternative route starts at the current port. Returning
``None`` in every other case signals "not handled; use the organizer
fallback".

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

import datetime as dt
from typing import Any


def _has_active_disruption(context: Any, now: Any) -> bool:
    """Return whether ``now`` is inside a well-formed disruption plan."""
    try:
        plans = getattr(context, "disruption_plans", None)
        if plans is None:
            return False
        for plan in plans:
            start_offset = getattr(plan, "start_offset_days", None)
            duration = getattr(plan, "duration_days", None)
            if start_offset is None or duration is None:
                continue
            start = dt.datetime.min + dt.timedelta(days=float(start_offset))
            end = start + dt.timedelta(days=float(duration))
            if start <= now < end:
                return True
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False
    return False


def _pending_route_starts_at_port(vessel: Any, port: Any) -> bool:
    """Check an empty vessel's pending route without changing it."""
    try:
        if getattr(vessel, "carried_shipments", None):
            return False
        route = getattr(vessel, "pending_assigned_service_route", None)
        segments = list(getattr(route, "segments", ()) or ())
        if not segments:
            return False
        first_segment = min(segments, key=lambda segment: segment.sequence_index)
        leg = first_segment.associated_leg
        return leg.departure_port is port
    except (AttributeError, TypeError, ValueError):
        return False


class UserStrategy:
    """Participant policy with a narrow pending-route berth preference."""

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

        During an active disruption, return the first empty waiting vessel
        whose pending alternative route starts at this port. Otherwise return
        ``None`` to use the organizer fallback; no input is mutated.
        """
        if not _has_active_disruption(maritime_data_context, current_time):
            return None
        try:
            candidates = list(waiting_vessels)
        except (TypeError, ValueError):
            return None
        for vessel in candidates:
            if _pending_route_starts_at_port(vessel, port):
                return vessel
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

        Returns ``None`` to use the organizer fallback.
        """
        return None

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Adjust booking chains before a vessel handles cargo.

        Returns ``None`` to use the organizer fallback.
        """
        return None
