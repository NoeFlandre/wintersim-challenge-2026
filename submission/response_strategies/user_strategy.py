"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. Three methods return ``None`` and
delegate to the organizer fallback. The in-transit hook may return ``False``
only when every active disruption is downstream of the vessel's current
segment; that skips a premature fallback re-plan without mutating state.

The policy is intentionally narrow: direct disruptions remain governed by the
organizer fallback, while future-only impacts are deferred until the vessel is
closer to the affected resource.

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

from typing import Any

from .deferred_rebooking import should_defer_future_only_rebooking


class UserStrategy:
    """Participant adapter with one fail-closed in-transit policy."""

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

        Returns ``None`` to use the organizer fallback.
        """
        return None

    @staticmethod
    def adjust_bookings_before_cargo_handling(context: Any, now: Any, vessel: Any) -> Any:
        """Adjust booking chains before a vessel handles cargo.

        Return ``False`` only to defer a future-only disruption re-plan. Return
        ``None`` for direct impacts, inactive disruptions, invalid state, or
        no relevant shipment so the organizer fallback remains authoritative.
        """
        return should_defer_future_only_rebooking(context, now, vessel)
