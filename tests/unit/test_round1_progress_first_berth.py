"""RED/GREEN contract for the Round 1 progress-first berth policy."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from response_strategies.user_strategy import UserStrategy

DAY_ZERO = dt.datetime.min


class FakeVessel:
    def __init__(
        self,
        name: str,
        next_leg: object,
        *,
        carried_teu: float = 0.0,
        capacity: float = 100.0,
        discharging_teu: float = 0.0,
        loading_teu: float = 0.0,
    ) -> None:
        self.name = name
        self.next_leg = next_leg
        self.carried_shipments = [SimpleNamespace(teu_size=carried_teu)]
        self.vessel_class = SimpleNamespace(teu_capacity=capacity)
        self._discharging = [SimpleNamespace(teu_size=discharging_teu)]
        self._loading = [SimpleNamespace(teu_size=loading_teu)]

    def get_next_segment(self) -> object:
        return SimpleNamespace(associated_leg=self.next_leg)

    def get_discharging_shipments_at_current_segment(self) -> list[object]:
        return self._discharging

    def get_loading_shipments_at_next_segment(self) -> list[object]:
        return self._loading


def _plan(
    *,
    target_leg: object | None = None,
    target_berth: object | None = None,
    multiplier: float = 1.0,
    close_berth: bool = False,
    start_offset_days: float = 10.0,
    duration_days: float = 5.0,
) -> object:
    return SimpleNamespace(
        target_leg=target_leg,
        target_berth=target_berth,
        multiplier=multiplier,
        close_berth=close_berth,
        start_offset_days=start_offset_days,
        duration_days=duration_days,
    )


def _world(
    *,
    blocked: FakeVessel,
    progress: list[FakeVessel],
    plans: list[object],
    now: dt.datetime,
) -> tuple[object, object, list[object], dt.datetime, dict[object, dt.datetime]]:
    queue_port = SimpleNamespace(name="queue")
    waiting = [blocked, *progress]
    waits = {vessel: now - dt.timedelta(hours=index + 1) for index, vessel in enumerate(waiting)}
    context = SimpleNamespace(disruption_plans=plans)
    return context, queue_port, waiting, now, waits


def _mixed_case() -> tuple[
    object, object, list[object], list[object], dt.datetime, dict[object, dt.datetime]
]:
    blocked_leg = SimpleNamespace(arrival_port=SimpleNamespace(name="blocked-arrival"))
    progress_leg = SimpleNamespace(arrival_port=SimpleNamespace(name="open-arrival"))
    blocked = FakeVessel("blocked", blocked_leg, carried_teu=100.0, capacity=500.0)
    progress = FakeVessel("progress", progress_leg, carried_teu=10.0, capacity=100.0)
    disruption = _plan(target_leg=blocked_leg, multiplier=3.0)
    context, port, waiting, now, waits = _world(
        blocked=blocked,
        progress=[progress],
        plans=[disruption],
        now=DAY_ZERO + dt.timedelta(days=10),
    )
    return context, port, waiting, [SimpleNamespace(port=port)], now, waits


def test_mixed_active_queue_returns_original_progress_vessel_by_fallback_rank() -> None:
    context, port, waiting, berths, now, waits = _mixed_case()
    result = UserStrategy.select_vessel_for_berth(context, port, waiting, berths, now, waits)
    assert result is waiting[1]


def test_mixed_active_queue_preserves_fallback_rank_among_progress_vessels() -> None:
    blocked_leg = SimpleNamespace(arrival_port=SimpleNamespace(name="blocked"))
    open_leg = SimpleNamespace(arrival_port=SimpleNamespace(name="open"))
    blocked = FakeVessel("blocked", blocked_leg)
    low = FakeVessel("low", open_leg, carried_teu=1.0, capacity=50.0)
    high = FakeVessel("high", open_leg, carried_teu=10.0, capacity=200.0)
    now = DAY_ZERO + dt.timedelta(days=10)
    context, port, waiting, now, waits = _world(
        blocked=blocked,
        progress=[low, high],
        plans=[_plan(target_leg=blocked_leg, multiplier=3.0)],
        now=now,
    )
    result = UserStrategy.select_vessel_for_berth(
        context, port, waiting, [SimpleNamespace(port=port)], now, waits
    )
    assert result is high


def test_inactive_all_progress_and_all_blocked_queues_delegate() -> None:
    context, port, waiting, berths, now, waits = _mixed_case()
    inactive = now + dt.timedelta(days=5)
    assert (
        UserStrategy.select_vessel_for_berth(context, port, waiting, berths, inactive, waits)
        is None
    )

    open_leg = SimpleNamespace(arrival_port=SimpleNamespace(name="open"))
    all_progress = FakeVessel("open", open_leg)
    progress_context, progress_port, progress_waiting, progress_now, progress_waits = _world(
        blocked=all_progress,
        progress=[],
        plans=[_plan(target_leg=SimpleNamespace(), multiplier=3.0)],
        now=now,
    )
    assert (
        UserStrategy.select_vessel_for_berth(
            progress_context,
            progress_port,
            progress_waiting,
            berths,
            progress_now,
            progress_waits,
        )
        is None
    )

    blocked_leg = SimpleNamespace(arrival_port=SimpleNamespace(name="blocked"))
    all_blocked_a = FakeVessel("a", blocked_leg)
    all_blocked_b = FakeVessel("b", blocked_leg)
    blocked_context, blocked_port, blocked_waiting, blocked_now, blocked_waits = _world(
        blocked=all_blocked_a,
        progress=[all_blocked_b],
        plans=[_plan(target_leg=blocked_leg, multiplier=3.0)],
        now=now,
    )
    assert (
        UserStrategy.select_vessel_for_berth(
            blocked_context,
            blocked_port,
            blocked_waiting,
            berths,
            blocked_now,
            blocked_waits,
        )
        is None
    )


def test_disruption_start_is_inclusive_and_end_is_exclusive() -> None:
    context, port, waiting, berths, now, waits = _mixed_case()
    assert (
        UserStrategy.select_vessel_for_berth(context, port, waiting, berths, now, waits)
        is waiting[1]
    )
    at_end = now + dt.timedelta(days=5)
    assert (
        UserStrategy.select_vessel_for_berth(context, port, waiting, berths, at_end, waits) is None
    )


def test_closed_arrival_berth_is_blocked_alongside_congested_leg() -> None:
    open_leg = SimpleNamespace(arrival_port=SimpleNamespace(name="open"))
    closed_port = SimpleNamespace(name="closed")
    closed_leg = SimpleNamespace(arrival_port=closed_port)
    closed_berth = SimpleNamespace(port=closed_port)
    blocked_by_leg = FakeVessel("leg", closed_leg)
    blocked_by_port = FakeVessel("port", open_leg)
    progress = FakeVessel("progress", open_leg, carried_teu=20.0, capacity=200.0)
    now = DAY_ZERO + dt.timedelta(days=10)
    context, port, waiting, now, waits = _world(
        blocked=blocked_by_leg,
        progress=[blocked_by_port, progress],
        plans=[
            _plan(target_leg=closed_leg, multiplier=3.0),
            _plan(target_berth=closed_berth, close_berth=True),
        ],
        now=now,
    )
    result = UserStrategy.select_vessel_for_berth(
        context, port, waiting, [SimpleNamespace(port=port)], now, waits
    )
    assert result is progress


def test_exact_tie_preserves_queue_order_and_identity() -> None:
    blocked_leg = SimpleNamespace(arrival_port=SimpleNamespace(name="blocked"))
    open_leg = SimpleNamespace(arrival_port=SimpleNamespace(name="open"))
    blocked = FakeVessel("blocked", blocked_leg)
    first = FakeVessel("first", open_leg)
    second = FakeVessel("second", open_leg)
    now = DAY_ZERO + dt.timedelta(days=10)
    context, port, waiting, now, waits = _world(
        blocked=blocked,
        progress=[first, second],
        plans=[_plan(target_leg=blocked_leg, multiplier=3.0)],
        now=now,
    )
    result = UserStrategy.select_vessel_for_berth(
        context, port, waiting, [SimpleNamespace(port=port)], now, waits
    )
    assert result is first


def test_malformed_plan_delegates_and_does_not_mutate_inputs() -> None:
    context, port, waiting, berths, now, waits = _mixed_case()
    context.disruption_plans = [
        _plan(target_leg=waiting[0].next_leg, multiplier=3.0, start_offset_days="bad")
    ]
    before = (
        [(plan.start_offset_days, plan.duration_days) for plan in context.disruption_plans],
        list(waiting),
        list(berths),
        dict(waits),
    )
    assert UserStrategy.select_vessel_for_berth(context, port, waiting, berths, now, waits) is None
    assert [
        (plan.start_offset_days, plan.duration_days) for plan in context.disruption_plans
    ] == before[0]
    assert waiting == before[1]
    assert berths == before[2]
    assert waits == before[3]


def test_missing_next_segment_delegates() -> None:
    blocked_leg = SimpleNamespace(arrival_port=SimpleNamespace(name="blocked"))
    blocked = FakeVessel("blocked", blocked_leg)
    broken = FakeVessel("broken", blocked_leg)
    broken.get_next_segment = lambda: (_ for _ in ()).throw(AttributeError("missing"))  # type: ignore[method-assign]
    now = DAY_ZERO + dt.timedelta(days=10)
    context, port, waiting, now, waits = _world(
        blocked=blocked,
        progress=[broken],
        plans=[_plan(target_leg=blocked_leg, multiplier=3.0)],
        now=now,
    )
    assert (
        UserStrategy.select_vessel_for_berth(
            context, port, waiting, [SimpleNamespace(port=port)], now, waits
        )
        is None
    )
