"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. Three methods delegate to the
organizer fallback. The route hook contains one deliberately narrow policy:
when an existing disruption alternative is reserved for a carrying vessel, it
may move that pending reservation to the first empty vessel on the same source
route. The policy never creates routes or changes an assigned route.

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

import datetime as dt
import math
from numbers import Real
from typing import Any


def _active_disruption_key(context: Any, now: Any) -> tuple[Any, Any] | None:
    """Return the organizer-compatible key for the currently active plans.

    The organizer builds keys from lower-case closed-port names and congested
    leg endpoint names. A malformed context is deliberately treated as
    non-actionable so the organizer fallback remains in control.
    """
    if not isinstance(now, dt.datetime):
        return None
    plans = getattr(context, "disruption_plans", None)
    if plans is None:
        return None
    try:
        plans = tuple(plans)
    except (AttributeError, TypeError, ValueError):
        return None

    closed_ports: set[str] = set()
    congested_legs: set[tuple[str, str]] = set()
    try:
        for plan in plans:
            start_offset = getattr(plan, "start_offset_days", None)
            duration = getattr(plan, "duration_days", None)
            if not isinstance(start_offset, Real) or not isinstance(duration, Real):
                return None
            if not math.isfinite(float(start_offset)) or not math.isfinite(float(duration)):
                return None
            if float(duration) <= 0:
                return None
            start = dt.datetime.min + dt.timedelta(days=float(start_offset))
            end = start + dt.timedelta(days=float(duration))
            if not start <= now < end:
                continue

            if bool(getattr(plan, "close_berth", False)):
                berth = getattr(plan, "target_berth", None)
                port = getattr(berth, "port", None)
                name = getattr(port, "name", None)
                if not isinstance(name, str) or not name:
                    return None
                closed_ports.add(name.casefold())

            multiplier = getattr(plan, "multiplier", None)
            if not isinstance(multiplier, Real) or not math.isfinite(float(multiplier)):
                return None
            if float(multiplier) > 1.0:
                leg = getattr(plan, "target_leg", None)
                departure = getattr(getattr(leg, "departure_port", None), "name", None)
                arrival = getattr(getattr(leg, "arrival_port", None), "name", None)
                if not isinstance(departure, str) or not departure:
                    return None
                if not isinstance(arrival, str) or not arrival:
                    return None
                congested_legs.add((departure.casefold(), arrival.casefold()))
    except (AttributeError, OverflowError, TypeError, ValueError):
        return None

    if not closed_ports and not congested_legs:
        return None
    return tuple(sorted(closed_ports)), tuple(sorted(congested_legs))


def _has_shipments(vessel: Any) -> bool | None:
    """Return cargo presence, or ``None`` when vessel state is malformed."""
    try:
        shipments = vessel.carried_shipments
        if shipments is None:
            return None
        return bool(shipments)
    except (AttributeError, TypeError, ValueError):
        return None


def _swap_pending_reservation(old_vessel: Any, empty_vessel: Any, alternative: Any) -> bool:
    """Swap only pending pointers, rolling back if either write fails."""
    old_pending = getattr(old_vessel, "pending_assigned_service_route", None)
    empty_pending = getattr(empty_vessel, "pending_assigned_service_route", None)
    try:
        old_vessel.pending_assigned_service_route = None
        empty_vessel.pending_assigned_service_route = alternative
        if (
            old_vessel.pending_assigned_service_route is not None
            or empty_vessel.pending_assigned_service_route is not alternative
        ):
            raise RuntimeError("pending reservation write did not stick")
        return True
    except (AttributeError, TypeError, ValueError, RuntimeError):
        try:
            old_vessel.pending_assigned_service_route = old_pending
            empty_vessel.pending_assigned_service_route = empty_pending
        except (AttributeError, TypeError, ValueError, RuntimeError):
            pass
        return False


def _replace_carrying_reservation(context: Any, disruption_key: tuple[Any, Any]) -> bool:
    """Move one carried pending reservation to a deterministic empty vessel."""
    routes = getattr(context, "service_routes", None)
    vessels = getattr(context, "vessels", None)
    if routes is None or vessels is None:
        return False
    try:
        routes = tuple(routes)
        vessels = tuple(vessels)
    except (AttributeError, TypeError, ValueError):
        return False

    for vessel in vessels:
        pending_route = getattr(vessel, "pending_assigned_service_route", None)
        if (
            pending_route is not None
            and getattr(pending_route, "disruption_key", None) != disruption_key
        ):
            return False

    changed = False
    for alternative in routes:
        if getattr(alternative, "disruption_key", None) != disruption_key:
            continue
        source_route = getattr(alternative, "source_service_route", None)
        if source_route is None:
            continue
        try:
            pending = [
                vessel
                for vessel in vessels
                if getattr(vessel, "pending_assigned_service_route", None) is alternative
            ]
            deployed = tuple(source_route.deployed_vessels)
        except (AttributeError, TypeError, ValueError):
            return False
        if len(pending) != 1:
            continue

        old_vessel = pending[0]
        if getattr(old_vessel, "assigned_service_route", None) is not source_route:
            continue
        if _has_shipments(old_vessel) is not True:
            continue

        for empty_vessel in deployed:
            if empty_vessel is old_vessel:
                continue
            if getattr(empty_vessel, "assigned_service_route", None) is not source_route:
                continue
            if getattr(empty_vessel, "pending_assigned_service_route", None) is not None:
                continue
            if _has_shipments(empty_vessel) is not False:
                continue
            if _swap_pending_reservation(old_vessel, empty_vessel, alternative):
                changed = True
                break
    return changed


class UserStrategy:
    """Participant adapter with one narrowly scoped route-reservation policy."""

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
        """Prefer an empty source-route vessel for an existing alternative.

        Returning ``True`` only suppresses the organizer route hook after a
        pending pointer swap succeeds. With no safe swap, ``None`` delegates
        unchanged to the organizer fallback.
        """
        disruption_key = _active_disruption_key(context, now)
        if disruption_key is None:
            return None
        return True if _replace_carrying_reservation(context, disruption_key) else None

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
