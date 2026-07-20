"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. Returning ``None`` from any method
signals "not handled; use the organizer fallback", leaving the maritime data
context, routes, bookings, and vessel state exactly as the framework built
them.

Active experiment (Round 0, seed 2026):

    age_weighted_carried_teu_berth_priority_v1

When port congestion forces a berth-priority decision, ``select_vessel_for_berth``
releases the vessel carrying the greatest accumulated TEU waiting-age:

    score(v) = sum(max(teu, 0) * max(age_hours, 0) for s in carried_shipments)

Tie-breaks (deterministic, in order):

1. greater total carried TEU (after clamping negatives to zero);
2. longer berth waiting time from ``waiting_since_by_vessel``;
3. original order in ``waiting_vessels`` (stable selection).

The other three methods continue to return ``None``. Routes, bookings, legs,
vessels, and organizer state are never mutated.

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

from typing import Any


def _safe_age_hours(generated_time: Any, current_time: Any) -> float:
    """Compute the waiting-age in hours for one shipment.

    Returns ``0.0`` when ``generated_time`` is missing, ``None``, or sits in
    the future relative to ``current_time`` (negative ages are clamped to
    zero; we never produce negative priority contributions).
    """
    if generated_time is None or current_time is None:
        return 0.0
    try:
        delta = current_time - generated_time
    except TypeError:
        return 0.0
    seconds = delta.total_seconds()
    if seconds <= 0:
        return 0.0
    return seconds / 3600.0


def _clamp_teu(value: Any) -> float:
    """Coerce a TEU attribute to a non-negative float."""
    if value is None:
        return 0.0
    try:
        teu = float(value)
    except (TypeError, ValueError):
        return 0.0
    if teu < 0:
        return 0.0
    return teu


def _vessel_priority(
    vessel: Any,
    *,
    current_time: Any,
    waiting_since_by_vessel: Any,
) -> tuple[float, float, float]:
    """Return the priority tuple for one vessel.

    The tuple is ordered to sort correctly with Python's default tuple
    comparison:

        (age_weighted_score, total_teu, waiting_hours)

    The caller appends a ``-original_index`` component at the call site to
    force earlier-in-queue to win on full tie (stable selection).
    """
    age_weighted = 0.0
    total_teu = 0.0
    for shipment in getattr(vessel, "carried_shipments", []) or []:
        teu = _clamp_teu(getattr(shipment, "teu_size", None))
        age = _safe_age_hours(getattr(shipment, "generated_time", None), current_time)
        total_teu += teu
        age_weighted += teu * age
    waiting_hours = 0.0
    if isinstance(waiting_since_by_vessel, dict):
        wait = waiting_since_by_vessel.get(getattr(vessel, "name", None))
        if wait is not None:
            try:
                waiting_hours = float(wait)
            except (TypeError, ValueError):
                waiting_hours = 0.0
            if waiting_hours < 0:
                waiting_hours = 0.0
    # The caller injects the original-index component via the helper below.
    return age_weighted, total_teu, waiting_hours


class UserStrategy:
    """Behavior-neutral participant adapter.

    ``select_vessel_for_berth`` implements the age-weighted carried-TEU
    priority described in the module docstring. The other three methods
    return ``None`` to delegate to the organizer fallback without mutating
    any argument.
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
        """Choose the waiting vessel with the highest age-weighted carried-TEU.

        Returns ``None`` when ``waiting_vessels`` is empty or missing.
        """
        if not waiting_vessels:
            return None
        # Build (priority_tuple, -original_index, vessel) so Python's stable
        # tuple sort yields the lexicographically-largest priority and, on
        # total tie, the earliest vessel in the original queue.
        indexed: list[tuple[tuple[float, float, float], int, Any]] = []
        for idx, vessel in enumerate(waiting_vessels):
            priority = _vessel_priority(
                vessel,
                current_time=current_time,
                waiting_since_by_vessel=waiting_since_by_vessel,
            )
            # Negate index so smaller original index sorts larger.
            indexed.append((priority, -idx, vessel))
        # Sort ascending by tuple but descending by priority: we want the
        # highest priority. Use max() to avoid building a reversed list.
        best = max(indexed)
        return best[2]

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
