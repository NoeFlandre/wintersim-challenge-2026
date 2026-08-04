"""Read-only progress-aware berth selection for Round 1."""

from __future__ import annotations

import datetime as dt
import math
from typing import Any


def choose_progress_capable_vessel(
    context: Any,
    waiting_vessels: Any,
    current_time: Any,
    waiting_since_by_vessel: Any,
) -> Any:
    """Select a progress-capable vessel only for a mixed active queue.

    The normal organizer ranking is retained for every numeric component.  A
    ``None`` result delegates the complete decision back to the organizer.
    """
    try:
        vessels = tuple(waiting_vessels)
    except (AttributeError, TypeError, ValueError):
        return None
    if not vessels or not isinstance(current_time, dt.datetime):
        return None

    active = _active_disruptions(context, current_time)
    if active is None:
        return None
    congested_legs, closed_ports = active
    if not congested_legs and not closed_ports:
        return None

    classifications: list[bool] = []
    for vessel in vessels:
        try:
            next_segment = vessel.get_next_segment()
            next_leg = next_segment.associated_leg
            arrival_port = next_leg.arrival_port
        except (AttributeError, KeyError, IndexError, TypeError, ValueError):
            return None
        if next_leg is None or arrival_port is None:
            return None
        blocked = any(next_leg is leg for leg in congested_legs) or any(
            arrival_port is port for port in closed_ports
        )
        classifications.append(not blocked)

    if all(classifications) or not any(classifications):
        return None

    scores = _fallback_scores(vessels, current_time, waiting_since_by_vessel)
    if scores is None:
        return None
    return max(
        (
            (score, -index, vessels[index])
            for index, (score, progress_capable) in enumerate(
                zip(scores, classifications, strict=True)
            )
            if progress_capable
        ),
        key=lambda candidate: (candidate[0], candidate[1]),
    )[2]


def _active_disruptions(
    context: Any, now: dt.datetime
) -> tuple[tuple[Any, ...], tuple[Any, ...]] | None:
    """Return active congested legs and closed arrival ports by identity."""
    try:
        plans = tuple(context.disruption_plans)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None

    congested: list[Any] = []
    closed: list[Any] = []
    for plan in plans:
        try:
            start_days = plan.start_offset_days
            duration_days = plan.duration_days
            multiplier = plan.multiplier
            close_berth = plan.close_berth
            target_leg = plan.target_leg
            target_berth = plan.target_berth
            if not _finite_nonnegative(start_days) or not _finite_positive(duration_days):
                return None
            if not _finite_number(multiplier) or not isinstance(close_berth, bool):
                return None
            start = dt.datetime.min + dt.timedelta(days=float(start_days))
            end = start + dt.timedelta(days=float(duration_days))
            active = start <= now < end
            if close_berth:
                if target_berth is None or target_berth.port is None:
                    return None
                if active:
                    closed.append(target_berth.port)
            if float(multiplier) > 1.0:
                if target_leg is None:
                    return None
                if active:
                    congested.append(target_leg)
        except (AttributeError, KeyError, IndexError, TypeError, ValueError, OverflowError):
            return None
    return tuple(congested), tuple(closed)


def _fallback_scores(
    vessels: tuple[Any, ...], now: dt.datetime, waiting_since_by_vessel: Any
) -> list[float] | None:
    try:
        waiting = []
        carried = []
        capacities = []
        handling = []
        lookup = {} if waiting_since_by_vessel is None else waiting_since_by_vessel
        get_waiting_since = lookup.get
        for vessel in vessels:
            since = get_waiting_since(vessel, now)
            if not isinstance(since, dt.datetime):
                return None
            wait_hours = max(0.0, (now - since).total_seconds() / 3600.0)
            waiting.append(_checked_nonnegative(wait_hours))
            carried.append(_shipments_teu(vessel.carried_shipments))
            capacities.append(_checked_nonnegative(vessel.vessel_class.teu_capacity))
            handling.append(
                _shipments_teu(vessel.get_discharging_shipments_at_current_segment())
                + _shipments_teu(vessel.get_loading_shipments_at_next_segment())
            )
    except (AttributeError, KeyError, IndexError, TypeError, ValueError, OverflowError):
        return None

    waiting_scores = _normalize(waiting)
    carried_scores = _normalize(carried)
    capacity_scores = _normalize(capacities)
    handling_scores = _normalize(handling)
    return [
        0.4 * wait + 0.3 * teu + 0.2 * capacity - 0.1 * workload
        for wait, teu, capacity, workload in zip(
            waiting_scores, carried_scores, capacity_scores, handling_scores, strict=True
        )
    ]


def _shipments_teu(shipments: Any) -> float:
    total = 0.0
    for shipment in shipments:
        total += _checked_nonnegative(shipment.teu_size)
    return _checked_nonnegative(total)


def _normalize(values: list[float]) -> list[float]:
    minimum = min(values)
    maximum = max(values)
    if maximum == minimum:
        return [0.0] * len(values)
    span = maximum - minimum
    return [(value - minimum) / span for value in values]


def _finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and math.isfinite(float(value))


def _finite_nonnegative(value: Any) -> bool:
    return _finite_number(value) and float(value) >= 0.0


def _finite_positive(value: Any) -> bool:
    return _finite_number(value) and float(value) > 0.0


def _checked_nonnegative(value: Any) -> float:
    if not _finite_nonnegative(value):
        raise ValueError("numeric strategy input must be finite and non-negative")
    return float(value)
