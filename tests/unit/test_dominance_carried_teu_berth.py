"""RED/GREEN contract for the carried-TEU berth-priority experiment."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from response_strategies.user_strategy import UserStrategy

_ORIGIN = dt.datetime.min


def _plan(*, start: float = 10.0, duration: float = 5.0) -> SimpleNamespace:
    return SimpleNamespace(
        start_offset_days=start,
        duration_days=duration,
        multiplier=2.0,
        target_leg=object(),
        close_berth=False,
        target_berth=None,
    )


def _vessel(
    *,
    carried_teu: int,
    loa: float = 110.0,
    capacity: int = 1000,
    handled_teu: int = 0,
) -> SimpleNamespace:
    class Vessel:
        pass

    vessel = Vessel()
    vessel.vessel_class = SimpleNamespace(loa=loa, teu_capacity=capacity)
    vessel.assigned_service_route = object()
    vessel.current_segment = None
    vessel.carried_shipments = (
        [SimpleNamespace(teu_size=carried_teu, get_current_booking=lambda: object())]
        if carried_teu
        else []
    )
    vessel.get_discharging_shipments_at_current_segment = lambda: (
        [SimpleNamespace(teu_size=handled_teu)] if handled_teu else []
    )
    vessel.get_loading_shipments_at_next_segment = lambda: []
    return vessel


def test_active_disruption_uses_carried_teu_wspt_when_fallback_differs() -> None:
    now = _ORIGIN + dt.timedelta(days=12)
    older_light = _vessel(carried_teu=1, handled_teu=1)
    newer_heavy = _vessel(carried_teu=1000, handled_teu=1)
    waiting_since = {
        older_light: now - dt.timedelta(hours=2),
        newer_heavy: now - dt.timedelta(hours=1),
    }

    selected = UserStrategy.select_vessel_for_berth(
        SimpleNamespace(disruption_plans=[_plan()]),
        object(),
        [older_light, newer_heavy],
        [object()],
        now,
        waiting_since,
    )

    assert selected is newer_heavy


def test_inactive_and_end_boundary_delegate() -> None:
    start = _ORIGIN + dt.timedelta(days=10)
    plan = _plan(start=10.0, duration=5.0)
    vessel = _vessel(carried_teu=100)
    kwargs = {
        "maritime_data_context": SimpleNamespace(disruption_plans=[plan]),
        "port": object(),
        "waiting_vessels": [vessel],
        "available_berths": [object()],
        "waiting_since_by_vessel": {vessel: start},
    }

    assert (
        UserStrategy.select_vessel_for_berth(current_time=start - dt.timedelta(seconds=1), **kwargs)
        is None
    )
    assert (
        UserStrategy.select_vessel_for_berth(current_time=start + dt.timedelta(days=5), **kwargs)
        is None
    )


def test_exact_start_boundary_is_active() -> None:
    start = _ORIGIN + dt.timedelta(days=10)
    older_light = _vessel(carried_teu=1)
    newer_heavy = _vessel(carried_teu=1000)
    selected = UserStrategy.select_vessel_for_berth(
        SimpleNamespace(disruption_plans=[_plan(start=10.0)]),
        object(),
        [older_light, newer_heavy],
        [object()],
        start,
        {
            older_light: start - dt.timedelta(hours=2),
            newer_heavy: start - dt.timedelta(hours=1),
        },
    )

    assert selected is newer_heavy


def test_equal_w_spt_ratios_keep_queue_order() -> None:
    now = _ORIGIN + dt.timedelta(days=12)
    first = _vessel(carried_teu=100)
    second = _vessel(carried_teu=100)
    waiting_since = {
        first: now - dt.timedelta(hours=1),
        second: now - dt.timedelta(hours=2),
    }

    selected = UserStrategy.select_vessel_for_berth(
        SimpleNamespace(disruption_plans=[_plan()]),
        object(),
        [first, second],
        [object()],
        now,
        waiting_since,
    )

    # The fallback prefers the older second vessel; the candidate's exact ratio
    # is tied and must therefore choose the first queue member.
    assert selected is first


def test_malformed_state_fails_closed_without_mutation() -> None:
    now = _ORIGIN + dt.timedelta(days=12)
    vessel = _vessel(carried_teu=100)
    waiting = [vessel]
    plans = [SimpleNamespace(start_offset_days=float("nan"), duration_days=5.0)]

    assert (
        UserStrategy.select_vessel_for_berth(
            SimpleNamespace(disruption_plans=plans),
            object(),
            waiting,
            [object()],
            now,
            {vessel: now},
        )
        is None
    )
    assert waiting == [vessel]


def test_other_hooks_remain_delegates() -> None:
    assert UserStrategy.create_alternative_service_routes({}, 1, None) is None
    assert UserStrategy.assign_associated_bookings({}, 1, object()) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling({}, 1, object()) is None
