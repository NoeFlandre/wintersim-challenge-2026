"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. Returning ``None`` from any method
signals "not handled; use the organizer fallback", leaving the maritime data
context, routes, bookings, and vessel state exactly as the framework built
them.

This baseline intentionally delegates every decision to the organizer fallback
so the repository starts from a known, unmodified baseline. No optimization is
performed here; future strategy work will be added only as approved, tested
modules.

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

from typing import Any

from .progress_first_berth import choose_progress_capable_vessel


class UserStrategy:
    """Participant adapter with one narrow berth-priority policy.

    The berth hook may return an original progress-capable vessel during a
    mixed active disruption queue. All other cases delegate to the organizer
    fallback without mutating any argument.
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

        Returns an original waiting vessel only for the approved mixed-queue
        policy; ``None`` delegates to the organizer fallback.
        """
        return choose_progress_capable_vessel(
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
