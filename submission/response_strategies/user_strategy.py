"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

This module is the complete submission surface. Only files inside this
``response_strategies`` directory may enter a submission archive.

The ``UserStrategy`` class exposes the four static methods that the organizer
simulation calls during event handling. Returning ``None`` from any method
signals "not handled; use the organizer fallback", leaving the maritime data
context, routes, bookings, and vessel state exactly as the framework built
them.

Three hooks delegate unconditionally:
  * ``create_alternative_service_routes``
  * ``assign_associated_bookings``
  * ``adjust_bookings_before_cargo_handling``

``select_vessel_for_berth`` ranks waiting vessels by a Smith-style
TEU-delay-per-berth-hour priority that includes the fixed 3-hour berthing
overhead defined in ``simulation_model/berth_berthing.py``. Selection is
purely observational; no input is mutated.

Runtime constraints (enforced by the challenge rules):
- Standard-library imports only.
- No network, subprocess, filesystem, environment, cwd, wall-clock, unseeded
  randomness, or mutable cross-run global state.

Supported Python: 3.11+ (kept compatible with the organizer framework).
"""

from __future__ import annotations

import math
from typing import Any


def _read_positive_teu(shipment: Any) -> int:
    """Read shipment.teu_size as a positive integer or raise.

    A strict positive TEU value is required for scheduling decisions.
    Missing, non-numeric, non-finite, zero, or negative values raise a
    narrow expected exception that the public selector catches and uses
    to delegate with ``None``.
    """
    value = getattr(shipment, "teu_size", None)
    if value is None:
        raise TypeError("shipment.teu_size is None")
    if isinstance(value, bool):
        raise TypeError("shipment.teu_size is a bool")
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"shipment.teu_size is non-numeric: {value!r}") from exc
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"shipment.teu_size is non-finite: {value!r}")
    if numeric <= 0:
        raise ValueError(f"shipment.teu_size must be positive: {numeric}")
    return numeric


def _calc_occupied_teu(vessel: Any, route: Any, current_seg_index: int | None) -> int:
    """Mirror the organizer ``VesselBeingServed._calc_occupied_teu`` rule.

    Counts TEU of carried shipments whose current booking belongs to the
    vessel's assigned route, excluding cargo discharging at the current
    segment. When ``current_seg_index`` is ``None``, the discharge
    exclusion is skipped (mirroring organizer's ``curr_seq is None``
    branch) but the route-exclusion still applies.
    """
    total = 0
    for shipment in vessel.carried_shipments:
        booking = shipment.get_current_booking()
        if booking is None:
            continue
        if booking.service_route != route:
            continue
        if current_seg_index is not None and booking.arrival_segment_index == current_seg_index:
            continue
        total += _read_positive_teu(shipment)
    return total


def _predict_projected_load_teu(
    port: Any, vessel: Any, route: Any, next_seg_index: int, occupied: int
) -> int:
    """Greedy predicted load in TEU without mutation or reordering."""
    remaining = vessel.vessel_class.teu_capacity - occupied
    if remaining <= 0:
        return 0
    loaded = 0
    for shipment in port.shipments_in_storage:
        if shipment.carrying_vessel is not None:
            continue
        booking = shipment.get_current_booking()
        if booking is None or booking.service_route is not route:
            continue
        if booking.departure_segment_index != next_seg_index:
            continue
        teu = _read_positive_teu(shipment)
        if loaded + teu > remaining:
            continue
        loaded += teu
    return loaded


def _validate_vessel_inputs(vessel: Any) -> None:
    """Raise on missing or non-finite/nonpositive vessel inputs.

    Explicit checks ensure that a malformed but integer-coercible value
    (e.g. ``loa = -1`` would otherwise pass through ``max(1, int(-1/55))``)
    is detected and surfaced as a delegating failure.
    """
    vc = getattr(vessel, "vessel_class", None)
    if vc is None:
        raise AttributeError("vessel.vessel_class is None")
    loa = getattr(vc, "loa", None)
    if not isinstance(loa, (int, float)) or isinstance(loa, bool):
        raise TypeError(f"vessel_class.loa is non-numeric: {loa!r}")
    if not math.isfinite(loa) or loa <= 0:
        raise ValueError(f"vessel_class.loa must be positive finite: {loa!r}")
    capacity = getattr(vc, "teu_capacity", None)
    if not isinstance(capacity, (int, float)) or isinstance(capacity, bool):
        raise TypeError(f"vessel_class.teu_capacity is non-numeric: {capacity!r}")
    if not math.isfinite(capacity) or capacity <= 0:
        raise ValueError(f"vessel_class.teu_capacity must be positive finite: {capacity!r}")
    route = getattr(vessel, "assigned_service_route", None)
    if route is None:
        raise AttributeError("vessel.assigned_service_route is None")


def _candidate_metrics(port: Any, vessel: Any) -> tuple[int, int, int, int]:
    """Return ``(handled_teu, affected_teu, qc_count, carried_teu)``."""
    _validate_vessel_inputs(vessel)
    route = vessel.assigned_service_route
    current_seg = vessel.current_segment
    next_seg = vessel.get_next_segment()
    current_seg_index = current_seg.sequence_index if current_seg is not None else None
    next_seg_index = next_seg.sequence_index

    carried_teu = sum(_read_positive_teu(s) for s in vessel.carried_shipments)
    occupied = _calc_occupied_teu(vessel, route, current_seg_index)
    projected_load = _predict_projected_load_teu(port, vessel, route, next_seg_index, occupied)

    discharge_teu = carried_teu - occupied
    handled_teu = discharge_teu + projected_load
    affected_teu = carried_teu + projected_load
    qc_count = max(1, int(vessel.vessel_class.loa / 55))
    return handled_teu, affected_teu, qc_count, carried_teu


def _safe_metrics(port: Any, vessel: Any):
    """Compute metrics, returning None on any narrow expected failure."""
    try:
        return _candidate_metrics(port, vessel)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


class UserStrategy:
    """Behavior-neutral participant adapter with one berth-priority override."""

    @staticmethod
    def select_vessel_for_berth(
        maritime_data_context: Any,
        port: Any,
        waiting_vessels: Any,
        available_berths: Any,
        current_time: Any,
        waiting_since_by_vessel: Any = None,
    ) -> Any:
        """Choose a waiting vessel by TEU-delay-per-berth-hour Smith ratio.

        Returns one of ``waiting_vessels`` or ``None`` to delegate to the
        organizer fallback. Inputs are never mutated.
        """
        if not waiting_vessels:
            return None
        candidates: list[tuple[int, int, Any]] = []
        for vessel in waiting_vessels:
            metrics = _safe_metrics(port, vessel)
            if metrics is None:
                return None
            handled, affected, qc, _ = metrics
            candidates.append((affected * qc, 135 * qc + handled, vessel))

        best_index = 0
        best_num, best_den = candidates[0][0], candidates[0][1]
        for i in range(1, len(candidates)):
            num, den, _ = candidates[i]
            if num * best_den > best_num * den:
                best_index = i
                best_num, best_den = num, den
        return candidates[best_index][2]

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
