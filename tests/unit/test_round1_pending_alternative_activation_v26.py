"""RED/green contract for the v26 pending-alternative berth selector."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from response_strategies.user_strategy import UserStrategy

ANCHOR = datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _leg(departure: SimpleNamespace, arrival: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(departure_port=departure, arrival_port=arrival)


def _plan(*, start: float = 10.0, duration: float = 5.0) -> SimpleNamespace:
    departure = _port("alpha")
    arrival = _port("bravo")
    return SimpleNamespace(
        close_berth=False,
        multiplier=2.0,
        start_offset_days=start,
        duration_days=duration,
        target_leg=_leg(departure, arrival),
        target_berth=None,
    )


def _context(plan: object) -> SimpleNamespace:
    return SimpleNamespace(disruption_plans=[plan])


def _vessel(
    *,
    port: SimpleNamespace,
    key: object,
    carried: object = None,
    source_present: bool = True,
    sequence: int = 1,
) -> SimpleNamespace:
    leg = SimpleNamespace(departure_port=port, arrival_port=_port("charlie"))
    segment = SimpleNamespace(sequence_index=sequence, associated_leg=leg)
    route = SimpleNamespace(
        source_service_route=object() if source_present else None,
        disruption_key=key,
        segments=[segment],
    )
    return SimpleNamespace(
        carried_shipments=[] if carried is None else carried,
        pending_assigned_service_route=route,
    )


def _matching_key(plan: SimpleNamespace) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    leg = plan.target_leg
    return ((), ((leg.departure_port.name.casefold(), leg.arrival_port.name.casefold()),))


def _select(context: object, port: object, waiting: object, day: float) -> object:
    return UserStrategy.select_vessel_for_berth(
        context,
        port,
        waiting,
        [],
        ANCHOR + timedelta(days=day),
        {},
    )


def test_matching_pending_vessel_is_returned_by_identity() -> None:
    plan = _plan()
    port = _port("departure")
    vessel = _vessel(port=port, key=_matching_key(plan))

    assert _select(_context(plan), port, [vessel], 12.0) is vessel


def test_queue_order_selects_first_matching_vessel() -> None:
    plan = _plan()
    port = _port("departure")
    first = _vessel(port=port, key=_matching_key(plan))
    second = _vessel(port=port, key=_matching_key(plan))

    assert _select(_context(plan), port, [first, second], 12.0) is first


@pytest.mark.parametrize(
    ("day", "expected"),
    [(10.0, True), (14.999999, True), (15.0, False), (9.999999, False)],
)
def test_active_window_is_start_inclusive_and_end_exclusive(day: float, expected: bool) -> None:
    plan = _plan()
    port = _port("departure")
    vessel = _vessel(port=port, key=_matching_key(plan))

    assert (_select(_context(plan), port, [vessel], day) is vessel) is expected


def test_mismatched_disruption_key_delegates() -> None:
    plan = _plan()
    port = _port("departure")
    vessel = _vessel(port=port, key=((), (("other", "leg"),)))

    assert _select(_context(plan), port, [vessel], 12.0) is None


@pytest.mark.parametrize(
    "vessel",
    [
        _vessel(port=_port("departure"), key=_matching_key(_plan()), carried=[object()]),
        _vessel(port=_port("departure"), key=_matching_key(_plan()), source_present=False),
        SimpleNamespace(carried_shipments=[], pending_assigned_service_route=None),
        SimpleNamespace(
            carried_shipments=[],
            pending_assigned_service_route=SimpleNamespace(
                source_service_route=object(), disruption_key=((), ()), segments=[]
            ),
        ),
        SimpleNamespace(
            carried_shipments=[],
            pending_assigned_service_route=SimpleNamespace(
                source_service_route=object(),
                disruption_key=((), ()),
                segments=[SimpleNamespace(sequence_index=True, associated_leg=object())],
            ),
        ),
    ],
)
def test_carried_or_malformed_vessels_fail_closed(vessel: object) -> None:
    plan = _plan()
    port = _port("departure")

    assert _select(_context(plan), port, [vessel], 12.0) is None


def test_wrong_port_and_inactive_window_delegate() -> None:
    plan = _plan()
    vessel = _vessel(port=_port("departure"), key=_matching_key(plan))

    assert _select(_context(plan), _port("other"), [vessel], 12.0) is None
    assert _select(_context(plan), _port("departure"), [vessel], 15.0) is None
    assert _select(SimpleNamespace(disruption_plans=[]), _port("departure"), [vessel], 12.0) is None


@pytest.mark.parametrize(
    "plan",
    [
        SimpleNamespace(
            close_berth=False,
            multiplier=2.0,
            start_offset_days=None,
            duration_days=5.0,
            target_leg=object(),
            target_berth=None,
        ),
        SimpleNamespace(
            close_berth=False,
            multiplier=float("nan"),
            start_offset_days=10.0,
            duration_days=5.0,
            target_leg=object(),
            target_berth=None,
        ),
        object(),
    ],
)
def test_malformed_plans_delegate(plan: object) -> None:
    assert _select(_context(plan), object(), [object()], 12.0) is None


class _BrokenQueue:
    def __iter__(self):
        raise TypeError("queue unavailable")


def test_broken_queue_delegates() -> None:
    assert _select(_context(_plan()), object(), _BrokenQueue(), 12.0) is None


def test_selection_does_not_mutate_inputs() -> None:
    plan = _plan()
    port = _port("departure")
    vessel = _vessel(port=port, key=_matching_key(plan))
    context = _context(plan)
    waiting = [vessel]
    route = vessel.pending_assigned_service_route
    before = (
        list(context.disruption_plans),
        list(waiting),
        list(route.segments),
        vessel.carried_shipments,
    )

    assert _select(context, port, waiting, 12.0) is vessel
    assert (
        context.disruption_plans,
        waiting,
        route.segments,
        vessel.carried_shipments,
    ) == before


def test_other_hooks_preserve_v3_delegation_contract() -> None:
    assert UserStrategy.create_alternative_service_routes({}, ANCHOR, object()) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling({}, ANCHOR, object()) is None
