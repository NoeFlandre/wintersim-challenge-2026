"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. Returning ``None`` from any method
signals "not handled; use the organizer fallback", leaving the maritime data
context, routes, bookings, and vessel state exactly as the framework built
them.

This module deliberately delegates ``select_vessel_for_berth``,
``assign_associated_bookings``, and ``adjust_bookings_before_cargo_handling``
to the organizer fallback. ``create_alternative_service_routes`` is also a
no-op when no disruption is active (returning ``None`` so the fallback can
clean up and restore). While at least one disruption is active, however, it
returns ``False`` to tell the caller "handled, do not run the organizer
fallback", suppressing the alternative-route policy for the duration of the
disruption. The active call makes no mutation whatsoever on the context,
routes, vessels, legs, or the supplied vessel sentinel.

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Iterable
from typing import Any


def _has_active_disruption(context: Any, now: Any) -> bool:
    """Return True if any disruption plan is currently active.

    A plan is usable only when ``start_offset_days`` and ``duration_days`` are
    both not ``None``. Its active window is
    ``datetime.min + timedelta(days=start_offset_days)`` inclusive through
    ``start + timedelta(days=duration_days)`` exclusive. The check uses only
    the supplied ``context`` and ``now``; it caches nothing, mutates nothing,
    and never accesses wall-clock time. For an unsupported/non-datetime
    sentinel used by some unit tests, it safely reports no active disruption.
    """
    if not isinstance(now, _dt.datetime):
        return False
    plans: Iterable[Any] | None = getattr(context, "disruption_plans", None)
    if not plans:
        return False
    for plan in plans:
        start_offset = getattr(plan, "start_offset_days", None)
        duration = getattr(plan, "duration_days", None)
        if start_offset is None or duration is None:
            continue
        start = _dt.datetime.min + _dt.timedelta(days=start_offset)
        end = start + _dt.timedelta(days=duration)
        if start <= now < end:
            return True
    return False


class UserStrategy:
    """Behavior-neutral participant adapter, except for active-disruption
    suppression of alternative-route creation (returns ``False`` while a
    disruption is active so the organizer fallback does not run; returns
    ``None`` otherwise so cleanup/restoration may proceed).
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

        Returns ``None`` to use the organizer fallback; no input is mutated.
        """
        return None

    @staticmethod
    def create_alternative_service_routes(context: Any, now: Any, vessel: Any = None) -> Any:
        """Build alternative service routes for a vessel.

        Returns ``False`` ("handled, do not run the organizer alternative-route
        fallback") while at least one disruption is active. The active call
        makes no mutation; it simply signals suppression. Returns ``None``
        ("not handled; use the organizer fallback") outside active
        disruptions so the fallback may perform cleanup and restoration.
        """
        if _has_active_disruption(context, now):
            return False
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
