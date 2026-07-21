"""Unit tests for the in-transit rebooking suppression policy in UserStrategy.

These tests pin the behavior introduced by
``docs/experiments/round0-in-transit-rebooking-suppression-v1``:

* Returns exactly ``False`` while at least one disruption plan is active.
* Makes no mutation whatsoever during that active call (context, routes,
  vessels, legs, segments, bookings, shipments, vessel assignment, vessel
  carried shipments, vessel segment/berth, and nested collection contents
  are all preserved).
* Returns ``None`` outside active disruptions so the organizer fallback may
  perform normal in-transit replanning.
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


def _make_plan(start: float | None, duration: float | None) -> Any:
    return SimpleNamespace(
        start_offset_days=start,
        duration_days=duration,
        close_berth=False,
        multiplier=1.0,
        target_berth=None,
        target_leg=None,
    )


def _make_context(plans: list[Any]) -> Any:
    return SimpleNamespace(
        disruption_plans=tuple(plans),
        vessels=(),
        legs=(),
        service_routes=(),
        initial_service_routes=(),
        partial_service_routes=[],
    )


@pytest.fixture
def active_plan() -> Any:
    """One active plan: 0..10 days, active at now=5."""
    return _make_plan(start=0.0, duration=10.0)


def _make_vessel() -> Any:
    """Construct a vessel-like sentinel with mutable nested state to detect
    any mutation attempts during the active call.

    We do not call any organizer code here; this object is a stand-in. Its
    fields are intentionally mutable so that any incidental mutation would
    be observable.
    """
    carried = []

    class _Leg:
        def __init__(self) -> None:
            self.departure_port = SimpleNamespace(name="Origin")
            self.arrival_port = SimpleNamespace(name="Destination")

    leg = _Leg()

    class _Segment:
        def __init__(self) -> None:
            self.sequence_index = 1
            self.associated_leg = leg
            self.current_vessels = []

    seg = _Segment()

    class _Booking:
        def __init__(self) -> None:
            self.sequence_index = 1
            self.service_route = SimpleNamespace(
                id="R1", segments=[seg], associated_bookings=[]
            )
            self.departure_segment_index = 1
            self.arrival_segment_index = 2
            self.shipment = None

    booking = _Booking()

    class _Route:
        def __init__(self) -> None:
            self.id = "R1"
            self.deployed_vessels = []

    route = _Route()

    class _Shipment:
        def __init__(self) -> None:
            self.teu_size = 1
            self.associated_bookings = [booking]
            self.current_booking_index = 1
            self.current_storage_port = None

    s = _Shipment()
    booking.shipment = s

    class _Vessel:
        def __init__(self) -> None:
            self.index = 0
            self.assigned_service_route = route
            self.pending_assigned_service_route = None
            self.current_segment = seg
            self.current_berth = None
            self.carried_shipments = carried
            self.vessel_class = SimpleNamespace(teu_capacity=10)
            self.get_discharging_shipments_at_current_segment = lambda: []
            self.get_loading_shipments_at_next_segment = lambda: []

    v = _Vessel()
    carried.append(s)
    # Wire deployments and segment membership to the vessel so a mutation
    # attempt would change membership.
    route.deployed_vessels.append(v)
    seg.current_vessels.append(v)

    return v


# ---------------------------------------------------------------------------
# Active disruption: returns exactly False.
# ---------------------------------------------------------------------------


def test_active_disruption_returns_false(active_plan: Any) -> None:
    context = _make_context([active_plan])
    from datetime import datetime, timedelta

    vessel = _make_vessel()
    now = datetime.min + timedelta(days=5)
    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)
    assert result is False


def test_active_disruption_no_mutation(active_plan: Any) -> None:
    from datetime import datetime, timedelta

    context = _make_context([active_plan])
    vessel = _make_vessel()

    # Snapshot the entire reachable mutable state we expect to be preserved.
    snapshot = {
        "vessel.assigned_service_route": vessel.assigned_service_route,
        "vessel.pending_assigned_service_route": vessel.pending_assigned_service_route,
        "vessel.current_segment": vessel.current_segment,
        "vessel.current_berth": vessel.current_berth,
        "carried_ids": [id(s) for s in vessel.carried_shipments],
        "carried_shipments_len": len(vessel.carried_shipments),
        "segment_vessels": tuple(id(v) for v in vessel.current_segment.current_vessels),
        "route_vessels": tuple(id(vv) for vv in vessel.assigned_service_route.deployed_vessels),
        "booking_service_route": vessel.carried_shipments[0]
        .associated_bookings[0]
        .service_route,
        "shipment_associated_bookings_len": len(
            vessel.carried_shipments[0].associated_bookings
        ),
        "shipment_current_booking_index": vessel.carried_shipments[0].current_booking_index,
        "shipment_current_storage_port": vessel.carried_shipments[0].current_storage_port,
    }

    now = datetime.min + timedelta(days=5)
    UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)

    assert vessel.assigned_service_route is snapshot["vessel.assigned_service_route"]
    assert (
        vessel.pending_assigned_service_route
        is snapshot["vessel.pending_assigned_service_route"]
    )
    assert vessel.current_segment is snapshot["vessel.current_segment"]
    assert vessel.current_berth is snapshot["vessel.current_berth"]
    assert [id(s) for s in vessel.carried_shipments] == snapshot["carried_ids"]
    assert len(vessel.carried_shipments) == snapshot["carried_shipments_len"]
    assert tuple(id(v) for v in vessel.current_segment.current_vessels) == snapshot[
        "segment_vessels"
    ]
    assert tuple(id(vv) for vv in vessel.assigned_service_route.deployed_vessels) == snapshot[
        "route_vessels"
    ]
    assert (
        vessel.carried_shipments[0].associated_bookings[0].service_route
        is snapshot["booking_service_route"]
    )
    assert (
        len(vessel.carried_shipments[0].associated_bookings)
        == snapshot["shipment_associated_bookings_len"]
    )
    assert (
        vessel.carried_shipments[0].current_booking_index
        == snapshot["shipment_current_booking_index"]
    )
    assert (
        vessel.carried_shipments[0].current_storage_port
        is snapshot["shipment_current_storage_port"]
    )


# ---------------------------------------------------------------------------
# Boundary conditions for the active window.
# ---------------------------------------------------------------------------


def test_start_boundary_is_inclusive(active_plan: Any) -> None:
    from datetime import datetime, timedelta

    context = _make_context([active_plan])
    vessel = _make_vessel()
    now_start = datetime.min + timedelta(days=0)
    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now_start, vessel)
    assert result is False


def test_end_boundary_is_exclusive(active_plan: Any) -> None:
    from datetime import datetime, timedelta

    context = _make_context([active_plan])
    vessel = _make_vessel()
    now_end = datetime.min + timedelta(days=10)
    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now_end, vessel)
    assert result is None


def test_before_start_returns_none() -> None:
    from datetime import datetime, timedelta

    # Use plan with start at day 100 so we can stay safely above datetime.min.
    plan = _make_plan(start=100.0, duration=10.0)
    context = _make_context([plan])
    vessel = _make_vessel()
    now_before = datetime.min + timedelta(days=99)
    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now_before, vessel)
    assert result is None


def test_after_end_returns_none() -> None:
    from datetime import datetime, timedelta

    # Use plan with start at day 100 so we can stay safely above datetime.min.
    plan = _make_plan(start=100.0, duration=10.0)
    context = _make_context([plan])
    vessel = _make_vessel()
    now_after = datetime.min + timedelta(days=111)
    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now_after, vessel)
    assert result is None


def test_one_second_inside_active_returns_false(active_plan: Any) -> None:
    from datetime import datetime, timedelta

    context = _make_context([active_plan])
    vessel = _make_vessel()
    now_inside = datetime.min + timedelta(days=10) + timedelta(seconds=-1)
    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now_inside, vessel)
    assert result is False


# ---------------------------------------------------------------------------
# Plans with missing timing fields are ignored.
# ---------------------------------------------------------------------------


def test_plans_with_missing_timing_fields_are_ignored() -> None:
    from datetime import datetime, timedelta

    plans = [
        _make_plan(start=None, duration=10.0),
        _make_plan(start=0.0, duration=None),
        _make_plan(start=None, duration=None),
    ]
    context = _make_context(plans)
    vessel = _make_vessel()
    now = datetime.min + timedelta(days=5)
    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)
    assert result is None


def test_mixed_plans_active_when_any_is_active() -> None:
    from datetime import datetime, timedelta

    inactive = _make_plan(start=None, duration=None)
    active = _make_plan(start=20.0, duration=5.0)
    context = _make_context([inactive, active])
    vessel = _make_vessel()
    now = datetime.min + timedelta(days=22)
    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)
    assert result is False


# ---------------------------------------------------------------------------
# Empty / unsupported now.
# ---------------------------------------------------------------------------


def test_no_plans_returns_none() -> None:
    from datetime import datetime, timedelta

    context = _make_context([])
    vessel = _make_vessel()
    now = datetime.min + timedelta(days=5)
    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)
    assert result is None


def test_unsupported_now_sentinel_returns_none(active_plan: Any) -> None:
    """Non-datetime sentinels used by some unit tests must not crash; the
    helper must safely report no active disruption and the function must
    return ``None``."""
    context = _make_context([active_plan])
    vessel = _make_vessel()
    sentinels = ["string-now", 12345, None, 5.5, [], {}, object()]
    for sentinel in sentinels:
        result = UserStrategy.adjust_bookings_before_cargo_handling(context, sentinel, vessel)
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


def test_create_alternative_service_routes_remains_none_delegate() -> None:
    result = UserStrategy.create_alternative_service_routes(
        context={"k": 1}, now=5, vessel="x"
    )
    assert result is None


def test_assign_associated_bookings_remains_none_delegate() -> None:
    result = UserStrategy.assign_associated_bookings(
        context={"k": 1}, now=10, shipment=object()
    )
    assert result is None
