"""Participant-owned response strategy for the WSC 2026 Simulation Challenge.

Only the berth selector is overridden.  During an active disruption it uses a
carried-TEU weighted-shortest-processing-time order, and otherwise delegates
to the organizer fallback.  All reads are deterministic and side-effect free;
the three route/booking hooks remain no-op delegates.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any


def _finite_number(value: Any, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("expected a numeric value")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError("expected a finite positive value")
    return result


def _disruption_is_active(context: Any, now: Any) -> bool | None:
    """Return active/inactive, or ``None`` for malformed runtime state."""
    if not isinstance(now, dt.datetime):
        return None
    try:
        plans = context.disruption_plans
        iterator = iter(plans)
    except (AttributeError, TypeError):
        return None

    active = False
    for plan in iterator:
        try:
            start_days = _finite_number(plan.start_offset_days)
            duration_days = _finite_number(plan.duration_days, positive=True)
            if start_days < 0:
                return None
            start = dt.datetime.min + dt.timedelta(days=start_days)
            end = start + dt.timedelta(days=duration_days)
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None
        try:
            active = active or start <= now < end
        except TypeError:
            return None
    return active


def _teu(shipment: Any) -> float:
    value = _finite_number(shipment.teu_size)
    if value < 0:
        raise ValueError("TEU must be non-negative")
    return value


def _sum_shipments(shipments: Any) -> float:
    return sum(_teu(shipment) for shipment in shipments)


def _metrics(vessel: Any) -> tuple[float, float, float, int]:
    """Return carried TEU, handled TEU, capacity, and crane count."""
    vessel_class = vessel.vessel_class
    loa = _finite_number(vessel_class.loa, positive=True)
    capacity = _finite_number(vessel_class.teu_capacity, positive=True)
    cranes = max(1, int(loa / 55.0))
    carried = _sum_shipments(vessel.carried_shipments)
    discharged = _sum_shipments(vessel.get_discharging_shipments_at_current_segment())
    loaded = _sum_shipments(vessel.get_loading_shipments_at_next_segment())
    return carried, discharged + loaded, capacity, cranes


def _waiting_hours(vessel: Any, current_time: dt.datetime, waiting_since_by_vessel: Any) -> float:
    if waiting_since_by_vessel is None:
        waiting_since = current_time
    else:
        waiting_since = waiting_since_by_vessel.get(vessel, current_time)
    if not isinstance(waiting_since, dt.datetime):
        raise TypeError("waiting_since must be datetime")
    return max(0.0, (current_time - waiting_since).total_seconds() / 3600.0)


def _normalize(values: list[float]) -> list[float]:
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return [0.0] * len(values)
    span = maximum - minimum
    return [(value - minimum) / span for value in values]


def _fallback_index(
    vessels: list[Any],
    metrics: list[tuple[float, float, float, int]],
    current_time: dt.datetime,
    waiting_since_by_vessel: Any,
) -> int:
    waiting = _normalize(
        [_waiting_hours(vessel, current_time, waiting_since_by_vessel) for vessel in vessels]
    )
    carried = _normalize([item[0] for item in metrics])
    capacity = _normalize([item[2] for item in metrics])
    workload = _normalize([item[1] for item in metrics])
    scores = [
        0.4 * wait + 0.3 * cargo + 0.2 * cap - 0.1 * work
        for wait, cargo, cap, work in zip(waiting, carried, capacity, workload, strict=True)
    ]
    return max(range(len(vessels)), key=lambda index: (scores[index], -index))


def _wspt_index(metrics: list[tuple[float, float, float, int]]) -> int:
    """Choose max carried-TEU per actual berth service-time ratio."""
    best = 0
    best_carried, best_handled, _, best_cranes = metrics[0]
    for index, (carried, handled, _, cranes) in enumerate(metrics[1:], start=1):
        # The common positive factor 45 is omitted.  Cross multiplication keeps
        # exact queue-order ties deterministic and avoids division by zero.
        left = carried * (135.0 * best_cranes + best_handled)
        right = best_carried * (135.0 * cranes + handled)
        if left > right:
            best = index
            best_carried, best_handled, _, best_cranes = metrics[index]
    return best


class UserStrategy:
    """Participant adapter with one disruption-only berth-priority override."""

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

        Returns a queue member only when the carried-TEU WSPT order differs
        from the fallback-compatible order during an active disruption.
        """
        if not waiting_vessels:
            return None
        active = _disruption_is_active(maritime_data_context, current_time)
        if active is not True:
            return None
        try:
            vessels = list(waiting_vessels)
            if not vessels:
                return None
            metrics = [_metrics(vessel) for vessel in vessels]
            fallback = _fallback_index(
                vessels,
                metrics,
                current_time,
                waiting_since_by_vessel,
            )
            candidate = _wspt_index(metrics)
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None
        if candidate == fallback:
            return None
        return vessels[candidate]

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
