"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. Returning ``None`` signals "not
handled; use the organizer fallback", leaving the maritime data context,
routes, bookings, and vessel state exactly as the framework built them. The
berth hook delegates to the reviewed Transshipment Readiness Barrier v1 helper;
the other hooks remain unconditional fallback delegations.

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

from typing import Any

from .transshipment_readiness import choose_buffer_vessel


class UserStrategy:
    """Participant adapter with one reviewed berth-selection candidate.

    Non-berth hooks return ``None`` without mutating any argument.
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
        """Choose a conservative transshipment-readiness buffer or delegate."""
        return choose_buffer_vessel(
            maritime_data_context=maritime_data_context,
            port=port,
            waiting_vessels=waiting_vessels,
            available_berths=available_berths,
            current_time=current_time,
            waiting_since_by_vessel=waiting_since_by_vessel,
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
