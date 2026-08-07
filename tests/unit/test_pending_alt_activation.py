"""RED/green contract tests for pending alternative-route activation.

The fakes intentionally expose only the attributes used by the participant
policy.  They verify that the hook returns an existing queue object and never
mutates the context or route graph.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from response_strategies.user_strategy import UserStrategy


def _context(*plans: object) -> SimpleNamespace:
    return SimpleNamespace(disruption_plans=list(plans))


def _plan(start: float = 10.0, duration: float = 5.0) -> SimpleNamespace:
    return SimpleNamespace(start_offset_days=start, duration_days=duration)


def _vessel(*, port: object, carried: object = None, sequence: int = 0) -> SimpleNamespace:
    leg = SimpleNamespace(departure_port=port)
    segment = SimpleNamespace(sequence_index=sequence, associated_leg=leg)
    route = SimpleNamespace(segments=[segment])
    return SimpleNamespace(
        carried_shipments=[] if carried is None else carried,
        pending_assigned_service_route=route,
    )


def _now(day: float) -> datetime:
    return datetime.min + timedelta(days=day)


def _select(context: object, port: object, waiting: object, now: datetime) -> object:
    return UserStrategy.select_vessel_for_berth(
        context,
        port,
        waiting,
        [],
        now,
        {},
    )


def test_active_matching_vessel_returns_original_object() -> None:
    port = object()
    vessel = _vessel(port=port)

    result = _select(_context(_plan()), port, [vessel], _now(12))

    assert result is vessel


def test_queue_order_wins_for_multiple_matching_vessels() -> None:
    port = object()
    first = _vessel(port=port)
    second = _vessel(port=port)

    assert _select(_context(_plan()), port, [first, second], _now(12)) is first


@pytest.mark.parametrize(
    ("day", "expected"),
    [(10.0, True), (14.999999, True), (15.0, False), (9.999999, False)],
)
def test_disruption_window_is_start_inclusive_end_exclusive(day: float, expected: bool) -> None:
    port = object()
    vessel = _vessel(port=port)

    assert (_select(_context(_plan()), port, [vessel], _now(day)) is vessel) is expected


def test_inactive_or_empty_plan_delegates() -> None:
    port = object()
    vessel = _vessel(port=port)

    assert _select(_context(), port, [vessel], _now(12)) is None
    assert _select(_context(_plan()), port, [vessel], _now(20)) is None


@pytest.mark.parametrize(
    "vessel",
    [
        _vessel(port=object(), carried=[object()]),
        SimpleNamespace(carried_shipments=[], pending_assigned_service_route=None),
        SimpleNamespace(
            carried_shipments=[], pending_assigned_service_route=SimpleNamespace(segments=[])
        ),
    ],
)
def test_ineligible_vessels_delegate(vessel: object) -> None:
    port = object()

    assert _select(_context(_plan()), port, [vessel], _now(12)) is None


def test_wrong_port_and_later_segment_do_not_match() -> None:
    port = object()
    other_port = object()
    first = SimpleNamespace(
        sequence_index=2,
        associated_leg=SimpleNamespace(departure_port=other_port),
    )
    later = SimpleNamespace(
        sequence_index=3,
        associated_leg=SimpleNamespace(departure_port=port),
    )
    vessel = SimpleNamespace(
        carried_shipments=[],
        pending_assigned_service_route=SimpleNamespace(segments=[later, first]),
    )

    assert _select(_context(_plan()), port, [vessel], _now(12)) is None


@pytest.mark.parametrize(
    "vessel",
    [
        SimpleNamespace(
            carried_shipments=[],
            pending_assigned_service_route=SimpleNamespace(segments=[SimpleNamespace()]),
        ),
        SimpleNamespace(
            carried_shipments=[], pending_assigned_service_route=SimpleNamespace(segments=None)
        ),
        object(),
    ],
)
def test_malformed_vessels_fail_closed(vessel: object) -> None:
    assert _select(_context(_plan()), object(), [vessel], _now(12)) is None


@pytest.mark.parametrize(
    "plan",
    [
        SimpleNamespace(start_offset_days=None, duration_days=5),
        SimpleNamespace(start_offset_days=float("nan"), duration_days=5),
        SimpleNamespace(start_offset_days=10, duration_days=float("inf")),
        object(),
    ],
)
def test_malformed_plans_fail_closed(plan: object) -> None:
    port = object()
    vessel = _vessel(port=port)

    assert _select(_context(plan), port, [vessel], _now(12)) is None


class _BrokenQueue:
    def __iter__(self):
        raise TypeError("queue unavailable")


def test_broken_queue_fails_closed() -> None:
    assert _select(_context(_plan()), object(), _BrokenQueue(), _now(12)) is None


def test_selection_does_not_mutate_context_queue_or_route() -> None:
    port = object()
    vessel = _vessel(port=port)
    context = _context(_plan())
    waiting = [vessel]
    route = vessel.pending_assigned_service_route
    plans_before = list(context.disruption_plans)
    waiting_before = list(waiting)
    segments_before = list(route.segments)

    assert _select(context, port, waiting, _now(12)) is vessel
    assert context.disruption_plans == plans_before
    assert waiting == waiting_before
    assert route.segments == segments_before
    assert vessel.carried_shipments == []


def test_other_hooks_remain_fallback_delegates() -> None:
    assert UserStrategy.create_alternative_service_routes({}, 1, object()) is None
    assert UserStrategy.assign_associated_bookings({}, 1, object()) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling({}, 1, object()) is None
