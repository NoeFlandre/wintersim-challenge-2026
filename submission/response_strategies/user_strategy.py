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
    """Read shipment.teu_size as a strict positive integer or raise.

    Accepts positive ``int`` only (excluding ``bool``). Strings, ``None``,
    non-finite or fractional floats, ``bool``, zero, and negative values
    all raise a narrow expected exception that the public selector
    catches and uses to delegate with ``None``.
    """
    value = getattr(shipment, "teu_size", None)
    if value is None:
        raise TypeError("shipment.teu_size is None")
    if isinstance(value, bool):
        raise TypeError("shipment.teu_size is a bool")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(f"shipment.teu_size must be positive: {value}")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"shipment.teu_size is non-finite: {value!r}")
        if not value.is_integer():
            raise ValueError(f"shipment.teu_size must be integer: {value!r}")
        if value <= 0:
            raise ValueError(f"shipment.teu_size must be positive: {value}")
        return int(value)
    raise TypeError(f"shipment.teu_size is non-numeric: {value!r}")


def _classify_carried_cargo(
    vessel: Any, route: Any, current_seg_index: int | None
) -> tuple[int, int, int]:
    """One-pass classification of carried shipments.

    Returns ``(carried_teu, occupied_teu, discharge_teu)``. Foreign-route
    cargo contributes to carried_teu, contributes to neither occupied nor
    discharge, and propagates a ``TypeError`` if TEU is malformed. A None
    booking is treated as malformed and propagates ``AttributeError``.

    Rules mirror ``VesselBeingServed._calc_occupied_teu`` for the occupied
    count, plus an explicit discharge rule: when ``current_seg_index`` is
    not None, assigned-route cargo whose ``arrival_segment_index`` equals
    the current segment counts as discharge; all other assigned-route
    cargo is occupied.
    """
    carried_teu = 0
    occupied_teu = 0
    discharge_teu = 0
    for shipment in vessel.carried_shipments:
        teu = _read_positive_teu(shipment)
        carried_teu += teu
        booking = shipment.get_current_booking()
        if booking is None:
            raise AttributeError(f"shipment {getattr(shipment, 'id', '?')} has no current booking")
        if booking.service_route is not route:
            continue
        if current_seg_index is not None and booking.arrival_segment_index == current_seg_index:
            discharge_teu += teu
            continue
        occupied_teu += teu
    return carried_teu, occupied_teu, discharge_teu


def _predict_projected_load_teu(
    port: Any, vessel: Any, route: Any, next_seg_index: int, occupied: int
) -> int:
    """Greedy predicted load in TEU without mutation or reordering.

    A stored shipment with ``get_current_booking()`` returning ``None`` is
    malformed and raises so the public selector delegates.
    """
    remaining = vessel.vessel_class.teu_capacity - occupied
    if remaining <= 0:
        return 0
    loaded = 0
    for shipment in port.shipments_in_storage:
        if shipment.carrying_vessel is not None:
            continue
        booking = shipment.get_current_booking()
        if booking is None:
            raise AttributeError(
                f"stored shipment {getattr(shipment, 'id', '?')} has no current booking"
            )
        if booking.service_route is not route:
            continue
        if booking.departure_segment_index != next_seg_index:
            continue
        teu = _read_positive_teu(shipment)
        if loaded + teu > remaining:
            continue
        loaded += teu
    return loaded


def _validate_vessel_inputs(vessel: Any) -> None:
    """Raise on missing or non-finite/nonpositive vessel inputs."""
    vc = getattr(vessel, "vessel_class", None)
    if vc is None:
        raise AttributeError("vessel.vessel_class is None")
    loa = getattr(vc, "loa", None)
    if isinstance(loa, bool) or not isinstance(loa, (int, float)):
        raise TypeError(f"vessel_class.loa is non-numeric: {loa!r}")
    if not math.isfinite(loa) or loa <= 0:
        raise ValueError(f"vessel_class.loa must be positive finite: {loa!r}")
    capacity = getattr(vc, "teu_capacity", None)
    if isinstance(capacity, bool) or not isinstance(capacity, (int, float)):
        raise TypeError(f"vessel_class.teu_capacity is non-numeric: {capacity!r}")
    if not math.isfinite(capacity) or capacity <= 0:
        raise ValueError(f"vessel_class.teu_capacity must be positive finite: {capacity!r}")
    route = getattr(vessel, "assigned_service_route", None)
    if route is None:
        raise AttributeError("vessel.assigned_service_route is None")


def _candidate_metrics(port: Any, vessel: Any) -> tuple[int, int, int, int, int]:
    """Return ``(handled_teu, affected_teu, qc_count, carried_teu, occupied_teu)``."""
    _validate_vessel_inputs(vessel)
    route = vessel.assigned_service_route
    current_seg = vessel.current_segment
    next_seg = vessel.get_next_segment()
    current_seg_index = current_seg.sequence_index if current_seg is not None else None
    next_seg_index = next_seg.sequence_index

    carried_teu, occupied_teu, discharge_teu = _classify_carried_cargo(
        vessel, route, current_seg_index
    )
    projected_load = _predict_projected_load_teu(port, vessel, route, next_seg_index, occupied_teu)

    handled_teu = discharge_teu + projected_load
    affected_teu = carried_teu + projected_load
    qc_count = max(1, int(vessel.vessel_class.loa / 55))
    return handled_teu, affected_teu, qc_count, carried_teu, occupied_teu


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
            handled, affected, qc, _, _ = metrics
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
