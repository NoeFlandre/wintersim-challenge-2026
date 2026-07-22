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


def _safe_teu_size(shipment: Any) -> int:
    """Read shipment.teu_size defensively, returning 0 on missing/negative."""
    try:
        value = int(shipment.teu_size)
    except (AttributeError, TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _iter_carrying_for_discharge(
    vessel: Any, route: Any, current_seg_index: int
) -> tuple[int, int]:
    """Return (discharge_teu, continuing_teu) for a vessel at the current
    segment. ``discharge_teu`` is the TEU scheduled to discharge here;
    ``continuing_teu`` is the TEU continuing onto a later segment (still
    counted as carried / affected)."""
    discharge = 0
    continuing = 0
    for shipment in vessel.carried_shipments:
        booking = shipment.get_current_booking()
        if booking is None:
            continue
        if booking.service_route is not route:
            continue
        teu = _safe_teu_size(shipment)
        if booking.arrival_segment_index == current_seg_index:
            discharge += teu
        else:
            continuing += teu
    return discharge, continuing


def _compute_occupied_after_discharge(vessel: Any, route: Any, discharge_at_current: int) -> int:
    """Return occupied TEU after expected discharge at current segment.

    Mirrors the organizer's ``VesselBeingServed.attempt_start`` rule:
    when ``vessel.current_segment`` is ``None`` every carried shipment
    counts as occupied; otherwise only shipments that do NOT discharge
    at the current segment occupy capacity.
    """
    current_seg = vessel.current_segment
    if current_seg is None:
        return sum(_safe_teu_size(s) for s in vessel.carried_shipments)
    occupied = 0
    for shipment in vessel.carried_shipments:
        booking = shipment.get_current_booking()
        if booking is None:
            occupied += _safe_teu_size(shipment)
            continue
        if booking.service_route is not route:
            occupied += _safe_teu_size(shipment)
            continue
        if booking.arrival_segment_index != current_seg.sequence_index:
            occupied += _safe_teu_size(shipment)
    return occupied


def _iter_eligible_loads(port: Any, vessel: Any, next_seg_index: int, route: Any) -> list[Any]:
    """Return the eligible loading candidates in storage order.

    A stored shipment is eligible iff:
      * it has no carrying vessel;
      * it has a valid current booking;
      * the booking's service route is ``vessel.assigned_service_route``;
      * the booking's departure segment is the vessel's next segment;
      * it is stored at ``port`` (implied by iterating
        ``port.shipments_in_storage``).
    """
    out: list[Any] = []
    for shipment in port.shipments_in_storage:
        if shipment.carrying_vessel is not None:
            continue
        booking = shipment.get_current_booking()
        if booking is None:
            continue
        if booking.service_route is not route:
            continue
        if booking.departure_segment_index != next_seg_index:
            continue
        out.append(shipment)
    return out


def _predict_projected_load_teu(
    port: Any, vessel: Any, route: Any, next_seg: Any, occupied: int
) -> int:
    """Greedy predicted load in TEU; never exceeds remaining capacity and
    preserves storage order without reordering or mutation."""
    remaining = vessel.vessel_class.teu_capacity - occupied
    if remaining <= 0:
        return 0
    loaded = 0
    for shipment in _iter_eligible_loads(port, vessel, next_seg.sequence_index, route):
        teu = _safe_teu_size(shipment)
        if loaded + teu > remaining:
            continue
        loaded += teu
    return loaded


def _candidate_metrics(port: Any, vessel: Any) -> tuple[int, int, int, int] | None:
    """Return ``(handled_teu, affected_teu, qc_count, carried_teu)`` or
    ``None`` if inputs are malformed enough that delegation is safer than
    guessing.

    Mirrors the organizer's berth-handling formula:
        qc_count = max(1, int(loa / 55))
        service_hours = handled_teu / (qc_count * 45)
    """
    vc = getattr(vessel, "vessel_class", None)
    if vc is None:
        return None
    try:
        loa = float(vc.loa)
        teu_capacity = int(vc.teu_capacity)
    except (AttributeError, TypeError, ValueError):
        return None
    if loa <= 0 or teu_capacity < 0:
        return None

    route = getattr(vessel, "assigned_service_route", None)
    if route is None:
        return None

    current_seg = vessel.current_segment
    next_seg = vessel.get_next_segment()
    if next_seg is None:
        return None

    carried_teu = sum(_safe_teu_size(s) for s in vessel.carried_shipments)

    if current_seg is None:
        discharge_teu = 0
        occupied_after = carried_teu
    else:
        discharge_teu, _ = _iter_carrying_for_discharge(vessel, route, current_seg.sequence_index)
        occupied_after = _compute_occupied_after_discharge(vessel, route, discharge_teu)

    projected_load = _predict_projected_load_teu(port, vessel, route, next_seg, occupied_after)

    handled = discharge_teu + projected_load
    affected = carried_teu + projected_load
    qc_count = max(1, int(loa / 55))
    return handled, affected, qc_count, carried_teu


def _select_vessel_for_berth_teu_delay_smith(
    maritime_data_context: Any,
    port: Any,
    waiting_vessels: Any,
    available_berths: Any,
    current_time: Any,
) -> Any:
    """Choose a waiting vessel that maximises TEU-delay relieved per
    berth-service hour (Smith-style ratio).

    Returns one element of ``waiting_vessels`` or ``None``. Never mutates
    inputs. Delegates with ``None`` if inputs are not the expected shape.
    """
    if not waiting_vessels:
        return None
    candidates: list[tuple[int, int, int, Any]] = []
    for vessel in waiting_vessels:
        try:
            metrics = _candidate_metrics(port, vessel)
        except Exception:  # defensive: never crash the simulation
            metrics = None
        if metrics is None:
            return None  # delegate on malformed data
        handled, affected, qc, _ = metrics
        if handled <= 0:
            priority_class = 0  # zero-service, outranks all positive
            score_num = 0
            score_den = 0
        else:
            priority_class = 1
            score_num = affected * qc
            score_den = handled
        candidates.append((priority_class, score_num, score_den, vessel))

    # Sort: priority_class ascending (0 < 1), then best ratio first.
    # For positive class: (handled_b, affected_a * qc_a) compared with
    # (handled_a, affected_b * qc_b). For zero-class: stable original order.
    best_index = 0
    best_priority = candidates[0][0]
    best_num = candidates[0][1]
    best_den = candidates[0][2]
    for i in range(1, len(candidates)):
        prio, num, den, _ = candidates[i]
        if prio < best_priority:
            best_index = i
            best_priority = prio
            best_num = num
            best_den = den
            continue
        if prio > best_priority:
            continue
        if prio == 0:
            continue  # both zero-service -> preserve order
        # Cross multiplication: num_a / den_a  vs  num_b / den_b.
        # a better iff num_a * den_b > num_b * den_a.
        try:
            if num * best_den > best_num * den:
                best_index = i
                best_num = num
                best_den = den
        except Exception:
            continue
    return candidates[best_index][3]


class UserStrategy:
    """Behavior-neutral participant adapter.

    Every method except ``select_vessel_for_berth`` returns ``None`` to
    delegate to the organizer fallback without mutating any argument.
    ``select_vessel_for_berth`` implements a Smith-style
    TEU-delay-per-berth-hour priority that ranks vessels by predicted
    affected TEU per predicted berth-service hour.
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

        Returns one of ``waiting_vessels`` chosen by the Smith-style
        TEU-delay-per-berth-hour ratio, or ``None`` to delegate to the
        organizer fallback. Inputs are never mutated.
        """
        return _select_vessel_for_berth_teu_delay_smith(
            maritime_data_context,
            port,
            waiting_vessels,
            available_berths,
            current_time,
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
