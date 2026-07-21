"""Unit tests for the alternative-route suppression policy in UserStrategy.

These tests pin the behavior introduced by
``docs/experiments/round0-alternative-route-suppression-v1``:

* Returns exactly ``False`` while at least one disruption plan is active.
* Makes no mutation whatsoever during that active call (context, routes,
  vessels, legs, and the supplied vessel sentinel are all preserved).
* Returns ``None`` outside active disruptions so the organizer fallback may
  perform normal cleanup/restoration.
* The other three strategy methods remain unconditional ``None`` delegates.
* Boundary rules: ``start <= now < end``.
* Plans with missing timing fields are ignored.
* A context with no plans returns ``None``.
* An unsupported sentinel ``now`` does not crash and returns ``None``.

These tests use only sentinel objects defined here; they must not import the
organizer source.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from response_strategies.user_strategy import UserStrategy


class _VesselSentinel:
    """A trivial vessel-like sentinel.

    Verifying that no mutation occurs requires a mutable object whose identity
    we can compare. Strings and tuples cannot be mutated; a custom class
    exposes a ``marker`` attribute the implementation must not change.
    """

    def __init__(self, marker: str = "sentinel") -> None:
        self.marker = marker
        self.calls: list[str] = []


def _make_plan(start: float | None, duration: float | None) -> Any:
    return SimpleNamespace(
        start_offset_days=start,
        duration_days=duration,
        close_berth=False,
        multiplier=1.0,
        target_berth=None,
        target_leg=None,
    )


def _make_context(plans: list[Any], *, vessels: tuple = (), routes: tuple = ()) -> Any:
    return SimpleNamespace(
        disruption_plans=tuple(plans),
        vessels=tuple(vessels),
        legs=(),
        service_routes=tuple(routes),
        initial_service_routes=tuple(routes),
        partial_service_routes=[],
    )


@pytest.fixture
def active_plan() -> Any:
    """One active plan: 0..10 days, active at now=5."""
    return _make_plan(start=0.0, duration=10.0)


@pytest.fixture
def vessel_sentinel() -> _VesselSentinel:
    return _VesselSentinel()


# ---------------------------------------------------------------------------
# Active disruption: returns exactly False and never mutates.
# ---------------------------------------------------------------------------


def test_active_disruption_returns_false(
    active_plan: Any, vessel_sentinel: _VesselSentinel
) -> None:
    context = _make_context([active_plan])
    from datetime import datetime, timedelta

    now = datetime.min + timedelta(days=5)
    result = UserStrategy.create_alternative_service_routes(context, now, vessel_sentinel)
    assert result is False


def test_active_disruption_no_mutation(active_plan: Any, vessel_sentinel: _VesselSentinel) -> None:
    from datetime import datetime, timedelta

    vessel_a = SimpleNamespace(index=0, name="V0", marker="untouched")
    vessel_b = SimpleNamespace(index=1, name="V1", marker="untouched")
    route = SimpleNamespace(id="R1", source_service_route=None, disruption_key=())
    context = _make_context(
        [active_plan],
        vessels=(vessel_a, vessel_b),
        routes=(route,),
    )

    snapshot_context = {
        "disruption_plans": tuple(context.disruption_plans),
        "vessels": tuple(context.vessels),
        "legs": tuple(context.legs),
        "service_routes": tuple(context.service_routes),
        "initial_service_routes": tuple(context.initial_service_routes),
        "partial_service_routes": list(context.partial_service_routes),
    }

    vessel_marker_before = vessel_sentinel.marker
    vessel_a_marker_before = vessel_a.marker
    vessel_b_marker_before = vessel_b.marker

    now = datetime.min + timedelta(days=5)
    UserStrategy.create_alternative_service_routes(context, now, vessel_sentinel)

    assert context.disruption_plans == snapshot_context["disruption_plans"]
    assert context.vessels == snapshot_context["vessels"]
    assert context.legs == snapshot_context["legs"]
    assert context.service_routes == snapshot_context["service_routes"]
    assert context.initial_service_routes == snapshot_context["initial_service_routes"]
    assert context.partial_service_routes == snapshot_context["partial_service_routes"]
    assert vessel_sentinel.marker == vessel_marker_before
    assert vessel_a.marker == vessel_a_marker_before
    assert vessel_b.marker == vessel_b_marker_before


def test_active_disruption_with_vessel_none_still_returns_false(active_plan: Any) -> None:
    from datetime import datetime, timedelta

    context = _make_context([active_plan])
    now = datetime.min + timedelta(days=5)
    result = UserStrategy.create_alternative_service_routes(context, now, vessel=None)
    assert result is False


# ---------------------------------------------------------------------------
# Boundary conditions for the active window.
# ---------------------------------------------------------------------------


def test_start_boundary_is_inclusive(active_plan: Any, vessel_sentinel: _VesselSentinel) -> None:
    from datetime import datetime, timedelta

    # active_plan: start=0, duration=10 -> start=datetime.min, end=datetime.min+10d
    context = _make_context([active_plan])
    # exactly at start (inclusive): must still be active -> False
    now_start = datetime.min + timedelta(days=0)
    result = UserStrategy.create_alternative_service_routes(context, now_start, vessel_sentinel)
    assert result is False


def test_end_boundary_is_exclusive(active_plan: Any, vessel_sentinel: _VesselSentinel) -> None:
    from datetime import datetime, timedelta

    context = _make_context([active_plan])
    # exactly at end (exclusive): must NOT be active -> None
    now_end = datetime.min + timedelta(days=10)
    result = UserStrategy.create_alternative_service_routes(context, now_end, vessel_sentinel)
    assert result is None


def test_before_start_returns_none(
    vessel_sentinel: _VesselSentinel,
) -> None:
    from datetime import datetime, timedelta

    # Plan starts at day 100 so we can subtract 1 day safely above datetime.min.
    plan = _make_plan(start=100.0, duration=10.0)
    context = _make_context([plan])
    # 1 day before plan start
    now_before = datetime.min + timedelta(days=99)
    result = UserStrategy.create_alternative_service_routes(context, now_before, vessel_sentinel)
    assert result is None


def test_after_end_returns_none(active_plan: Any, vessel_sentinel: _VesselSentinel) -> None:
    from datetime import datetime, timedelta

    context = _make_context([active_plan])
    now_after = datetime.min + timedelta(days=11)
    result = UserStrategy.create_alternative_service_routes(context, now_after, vessel_sentinel)
    assert result is None


def test_one_second_inside_active_returns_false(
    active_plan: Any, vessel_sentinel: _VesselSentinel
) -> None:
    from datetime import datetime, timedelta

    context = _make_context([active_plan])
    now_one_sec_before_end = datetime.min + timedelta(days=10) + timedelta(seconds=-1)
    result = UserStrategy.create_alternative_service_routes(
        context, now_one_sec_before_end, vessel_sentinel
    )
    assert result is False


# ---------------------------------------------------------------------------
# Plans with missing timing fields are ignored.
# ---------------------------------------------------------------------------


def test_plans_with_missing_timing_fields_are_ignored(vessel_sentinel: _VesselSentinel) -> None:
    from datetime import datetime, timedelta

    # Three plans, all missing timing fields -> never active -> None
    plans = [
        _make_plan(start=None, duration=10.0),
        _make_plan(start=0.0, duration=None),
        _make_plan(start=None, duration=None),
    ]
    context = _make_context(plans)
    now = datetime.min + timedelta(days=5)
    result = UserStrategy.create_alternative_service_routes(context, now, vessel_sentinel)
    assert result is None


def test_mixed_plans_active_when_any_is_active(vessel_sentinel: _VesselSentinel) -> None:
    from datetime import datetime, timedelta

    # One ignored plan, then an active one at start=20
    inactive = _make_plan(start=None, duration=None)
    active = _make_plan(start=20.0, duration=5.0)
    context = _make_context([inactive, active])
    now = datetime.min + timedelta(days=22)
    result = UserStrategy.create_alternative_service_routes(context, now, vessel_sentinel)
    assert result is False


# ---------------------------------------------------------------------------
# Empty / unsupported now.
# ---------------------------------------------------------------------------


def test_no_plans_returns_none(vessel_sentinel: _VesselSentinel) -> None:
    from datetime import datetime, timedelta

    context = _make_context([])
    now = datetime.min + timedelta(days=5)
    result = UserStrategy.create_alternative_service_routes(context, now, vessel_sentinel)
    assert result is None


def test_unsupported_now_sentinel_returns_none(active_plan: Any) -> None:
    """A non-datetime sentinel used by some unit tests must not crash; the
    helper must safely report no active disruption."""
    context = _make_context([active_plan])
    sentinels = ["string-now", 12345, None, 5.5, [], {}, object()]
    for sentinel in sentinels:
        result = UserStrategy.create_alternative_service_routes(context, sentinel, vessel=None)
        assert result is None, f"non-datetime sentinel {sentinel!r} must return None"


# ---------------------------------------------------------------------------
# Other three strategy hooks: unconditionally None.
# ---------------------------------------------------------------------------


def test_select_vessel_for_berth_remains_none_delegate() -> None:
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=[object()],
        available_berths=[object()],
        current_time=0,
        waiting_since_by_vessel={},
    )
    assert result is None


def test_assign_associated_bookings_remains_none_delegate() -> None:
    result = UserStrategy.assign_associated_bookings(context={"k": 1}, now="any", shipment=object())
    assert result is None


def test_adjust_bookings_before_cargo_handling_remains_none_delegate() -> None:
    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context={"k": 1}, now="any", vessel=object()
    )
    assert result is None
