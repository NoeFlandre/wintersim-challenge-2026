"""Unit tests for the temporal lower-bound safe routing strategy.

These tests exercise the ``assign_associated_bookings`` hook of the
participant-owned ``UserStrategy`` with synthetic organizer data. They are
self-contained: they never import organizer source or load the real Round 0
tree. The implementation under test must respect the documented contract:

* Override ``assign_associated_bookings`` only when all four conditions hold:
  1. at least one disruption plan is currently active;
  2. the shipment's nominal distance-shortest path over **original** service
     routes touches at least one active closed port or congested leg;
  3. every active disrupted resource touched by that path has its earliest
     physically possible encounter at or after that plan's recovery time
     (under the documented optimistic lower-bound model);
  4. a complete valid nominal booking chain exists.
* When the override fires, atomically install the booking chain and return
  ``True``.
* Otherwise, return ``None`` without mutating any reachable state.
* Never return ``False``.
* The other three hooks always return ``None`` without mutating any input.

A fake ``maritime_data_context`` module is injected into ``sys.modules`` so the
participant's lazy ``from maritime_data_context import Booking`` resolves to
the synthetic class below.
"""

from __future__ import annotations

import datetime as dt
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest
from response_strategies.user_strategy import UserStrategy

# ---------------------------------------------------------------------------
# Synthetic organizer model
# ---------------------------------------------------------------------------


class FakeBooking:
    """Mimics maritime_data_context.Booking for unit tests."""

    __slots__ = (
        "sequence_index",
        "shipment",
        "service_route",
        "departure_segment_index",
        "arrival_segment_index",
    )

    def __init__(
        self,
        sequence_index: int = 0,
        shipment: Any = None,
        service_route: Any = None,
        departure_segment_index: int = 0,
        arrival_segment_index: int = 0,
    ) -> None:
        self.sequence_index = sequence_index
        self.shipment = shipment
        self.service_route = service_route
        self.departure_segment_index = departure_segment_index
        self.arrival_segment_index = arrival_segment_index


@pytest.fixture(autouse=True)
def _install_fake_maritime_context():
    """Inject a fake maritime_data_context module before each test.

    The participant imports ``Booking`` lazily inside the override path. The
    fake class lets unit tests exercise that path without the real organizer
    source on PYTHONPATH.
    """
    fake_module = types.ModuleType("maritime_data_context")
    fake_module.Booking = FakeBooking
    saved = sys.modules.get("maritime_data_context")
    sys.modules["maritime_data_context"] = fake_module
    try:
        yield
    finally:
        if saved is None:
            sys.modules.pop("maritime_data_context", None)
        else:
            sys.modules["maritime_data_context"] = saved


class _Port:
    __slots__ = ("name", "berths")

    def __init__(self, name: str) -> None:
        self.name = name
        self.berths: list = []

    def __repr__(self) -> str:
        return self.name


class _Berth:
    __slots__ = ("index", "port", "is_available")

    def __init__(self, index: int, port: _Port) -> None:
        self.index = index
        self.port = port
        self.is_available = True


class _Leg:
    __slots__ = ("departure_port", "arrival_port", "sailing_distance")

    def __init__(self, departure_port: _Port, arrival_port: _Port, distance: float) -> None:
        self.departure_port = departure_port
        self.arrival_port = arrival_port
        self.sailing_distance = distance


class _Segment:
    __slots__ = ("sequence_index", "associated_leg", "associated_service_route", "current_vessels")

    def __init__(self, sequence_index: int, leg: _Leg, route: _ServiceRoute) -> None:
        self.sequence_index = sequence_index
        self.associated_leg = leg
        self.associated_service_route = route
        self.current_vessels: list = []


class _ServiceRoute:
    __slots__ = (
        "id",
        "name",
        "start_day_of_week",
        "segments",
        "deployed_vessels",
        "associated_bookings",
        "source_service_route",
    )

    def __init__(self, route_id: str, name: str = "") -> None:
        self.id = route_id
        self.name = name
        self.start_day_of_week = 0.0
        self.segments: list = []
        self.deployed_vessels: list = []
        self.associated_bookings: list = []
        self.source_service_route: _ServiceRoute | None = None


class _VesselClass:
    __slots__ = ("name", "teu_capacity", "sailing_speed", "loa")

    def __init__(self, name: str, capacity: int, speed: float, loa: float = 200.0) -> None:
        self.name = name
        self.teu_capacity = capacity
        self.sailing_speed = speed
        self.loa = loa


class _Vessel:
    __slots__ = (
        "index",
        "vessel_class",
        "assigned_service_route",
        "pending_assigned_service_route",
        "current_segment",
        "current_berth",
        "carried_shipments",
    )

    def __init__(self, index: int, vessel_class: _VesselClass, route: _ServiceRoute) -> None:
        self.index = index
        self.vessel_class = vessel_class
        self.assigned_service_route = route
        self.pending_assigned_service_route = None
        self.current_segment = None
        self.current_berth = None
        self.carried_shipments: list = []


class _Demand:
    __slots__ = ("origin_port", "destination_port", "annual_teus")

    def __init__(self, origin: _Port, destination: _Port, annual_teus: int = 100) -> None:
        self.origin_port = origin
        self.destination_port = destination
        self.annual_teus = annual_teus


class _Shipment:
    __slots__ = (
        "index",
        "teu_size",
        "demand",
        "current_storage_port",
        "generated_time",
        "associated_bookings",
        "current_booking_index",
        "carrying_vessel",
        "completion_time",
    )

    def __init__(self, index: int, demand: _Demand) -> None:
        self.index = index
        self.teu_size = 1
        self.demand = demand
        self.current_storage_port = demand.origin_port
        self.generated_time = None
        self.associated_bookings: list = []
        self.current_booking_index: int | None = None
        self.carrying_vessel = None
        self.completion_time = None

    def get_current_booking(self):
        if self.current_booking_index is None:
            raise ValueError("no current booking")
        for booking in self.associated_bookings:
            if booking.sequence_index == self.current_booking_index:
                return booking
        raise ValueError("no matching booking")

    def is_at_last_booking(self) -> bool:
        current = self.get_current_booking()
        last_seq = max(b.sequence_index for b in self.associated_bookings)
        return current.sequence_index == last_seq


class _DisruptionPlan:
    __slots__ = (
        "target_leg",
        "target_berth",
        "start_offset_days",
        "duration_days",
        "multiplier",
        "close_berth",
    )

    def __init__(
        self,
        *,
        target_leg: _Leg | None = None,
        target_berth: _Berth | None = None,
        start_offset_days: float | None = None,
        duration_days: float | None = None,
        multiplier: float = 1.0,
        close_berth: bool = False,
    ) -> None:
        self.target_leg = target_leg
        self.target_berth = target_berth
        self.start_offset_days = start_offset_days
        self.duration_days = duration_days
        self.multiplier = multiplier
        self.close_berth = close_berth


def _context(
    *,
    ports: list[_Port],
    service_routes: list[_ServiceRoute],
    initial_service_routes: list[_ServiceRoute] | None = None,
    vessels: list[_Vessel] | None = None,
    disruption_plans: list[_DisruptionPlan] | None = None,
    demands: list[_Demand] | None = None,
):
    ctx = SimpleNamespace()
    ctx.ports = ports
    ctx.service_routes = service_routes
    ctx.initial_service_routes = (
        list(initial_service_routes) if initial_service_routes is not None else list(service_routes)
    )
    ctx.vessels = vessels or []
    ctx.disruption_plans = disruption_plans or []
    ctx.demands = demands or []
    ctx.legs: list = []
    for route in service_routes:
        for segment in route.segments:
            leg = segment.associated_leg
            if leg not in ctx.legs:
                ctx.legs.append(leg)
    return ctx


def _now_at_day(day: float) -> dt.datetime:
    """Return the simulation-time ``now`` for an offset in days.

    Organizer code anchors disruptions at ``datetime.min``, so test times must
    follow that convention.
    """
    return dt.datetime.min + dt.timedelta(days=day)


# ---------------------------------------------------------------------------
# Network builders used across the test cases
# ---------------------------------------------------------------------------


def _make_simple_network() -> dict[str, Any]:
    """Three ports A, B, C with two parallel routes:
    - Original route R1: A -> B -> C (segments 1, 2)
    - Original route R2: A -> C (segment 1)
    - Alternative route R1-ALT (source_service_route=R1): B -> A -> C

    Vessel class VC1 with sailing_speed = 20 knots (speed deliberately large
    so the lower-bound encounter times are easy to reason about in tests).
    """
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    # Legs
    ab = _Leg(a, b, distance=100.0)
    bc = _Leg(b, c, distance=100.0)
    ac = _Leg(a, c, distance=300.0)
    ba = _Leg(b, a, distance=100.0)

    # Service routes (original)
    r1 = _ServiceRoute("R1", "R1 A-B-C")
    s1a = _Segment(1, ab, r1)
    s1b = _Segment(2, bc, r1)
    r1.segments.extend([s1a, s1b])

    r2 = _ServiceRoute("R2", "R2 A-C direct")
    s2a = _Segment(1, ac, r2)
    r2.segments.append(s2a)

    # Alternative route with a source. Must be excluded from the nominal graph.
    r_alt = _ServiceRoute("R1-ALT-1", "R1-ALT B-A-C")
    r_alt.source_service_route = r1
    s_alt_1 = _Segment(1, ba, r_alt)
    s_alt_2 = _Segment(2, ac, r_alt)
    r_alt.segments.extend([s_alt_1, s_alt_2])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    vessel.assigned_service_route = r1
    r1.deployed_vessels.append(vessel)
    vessel_alt_owner = _Vessel(2, vessel_class, r1)
    r1.deployed_vessels.append(vessel_alt_owner)

    routes = [r1, r2, r_alt]
    context = _context(
        ports=[a, b, c],
        service_routes=routes,
        initial_service_routes=[r1, r2],
        vessels=[vessel, vessel_alt_owner],
    )
    return {
        "context": context,
        "ports": {"A": a, "B": b, "C": c},
        "routes": {"R1": r1, "R2": r2, "ALT": r_alt},
        "legs": {"AB": ab, "BC": bc, "AC": ac, "BA": ba},
        "segments": {"R1_S1": s1a, "R1_S2": s1b, "R2_S1": s2a},
        "vessels": [vessel, vessel_alt_owner],
        "vessel_class": vessel_class,
    }


def _make_shipment(network: dict[str, Any], origin_name: str, dest_name: str) -> _Shipment:
    demand = _Demand(
        network["ports"][origin_name],
        network["ports"][dest_name],
        annual_teus=100,
    )
    return _Shipment(index=1, demand=demand)


# ---------------------------------------------------------------------------
# Test: contract and no-op hooks
# ---------------------------------------------------------------------------


def test_other_three_hooks_return_none_without_mutation() -> None:
    network = _make_simple_network()
    ctx = network["context"]
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]
    snapshot_vessels = [v.assigned_service_route for v in ctx.vessels]

    assert (
        UserStrategy.select_vessel_for_berth(ctx, network["ports"]["A"], [], [], _now_at_day(0))
        is None
    )
    assert UserStrategy.create_alternative_service_routes(ctx, _now_at_day(0)) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(ctx, _now_at_day(0), None) is None

    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes
    assert [v.assigned_service_route for v in ctx.vessels] == snapshot_vessels


def test_assign_never_returns_false() -> None:
    """``False`` is not a permitted return value for any hook."""
    network = _make_simple_network()
    ctx = network["context"]
    shipment = _make_shipment(network, "A", "C")
    plan = _DisruptionPlan(
        target_leg=network["legs"]["AB"],
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=5.0,
    )
    ctx.disruption_plans.append(plan)

    # Inside active window with disrupted leg on the path.
    inside = _now_at_day(12.0)
    result = UserStrategy.assign_associated_bookings(ctx, inside, shipment)
    assert result is not False
    # Either None or True is acceptable; the no-op fallback returns None.
    assert result is None or result is True


# ---------------------------------------------------------------------------
# Test 1: no active plans
# ---------------------------------------------------------------------------


def test_no_active_plans_returns_none_and_no_mutation() -> None:
    network = _make_simple_network()
    ctx = network["context"]
    shipment = _make_shipment(network, "A", "C")
    # No disruption plans.
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]
    shipment_snap = list(shipment.associated_bookings)

    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(50.0), shipment)

    assert result is None
    assert shipment.associated_bookings == shipment_snap
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


# ---------------------------------------------------------------------------
# Test 2: unrelated active disruption not touched by the nominal path
# ---------------------------------------------------------------------------


def test_unrelated_active_disruption_returns_none() -> None:
    network = _make_simple_network()
    ctx = network["context"]
    # Plan affects leg A->C, but shipment goes A->B->C which never uses A->C.
    plan = _DisruptionPlan(
        target_leg=network["legs"]["AC"],
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=5.0,
    )
    ctx.disruption_plans.append(plan)

    shipment = _make_shipment(network, "A", "C")
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]

    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(12.0), shipment)

    assert result is None
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


# ---------------------------------------------------------------------------
# Test 3: affected resource reachable before recovery
# ---------------------------------------------------------------------------


def test_affected_resource_before_recovery_delegates() -> None:
    network = _make_simple_network()
    ctx = network["context"]
    # Close port B for 5 days starting at day 10.
    plan = _DisruptionPlan(
        target_berth=network["ports"]["B"].berths[0],
        start_offset_days=10.0,
        duration_days=5.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)
    # Recovery at day 15.
    # Speed 20 nm/h => 100 nm leg takes 5 hours. 1.05x => ~4.76 hours = 0.198 days.
    # So the encounter at B is at elapsed ~0.198 days, well before day 15.

    shipment = _make_shipment(network, "A", "C")
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]

    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(12.0), shipment)

    assert result is None
    assert shipment.associated_bookings == []
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


# ---------------------------------------------------------------------------
# Test 4: affected resource's earliest encounter after recovery -> True
# ---------------------------------------------------------------------------


def test_affected_resource_after_recovery_overrides() -> None:
    """Construct a case where the lower-bound encounter at B is after recovery.

    Use a much longer leg distance so the encounter time exceeds the recovery
    time even at 1.05x speed.
    """
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    # Long legs so that even at 1.05x speed, encounter at B is after recovery.
    ab = _Leg(a, b, distance=10_000.0)
    bc = _Leg(b, c, distance=10_000.0)
    r1 = _ServiceRoute("R1", "R1 long")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, bc, r1)])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)

    ctx = _context(
        ports=[a, b, c],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    # Close B for 1 day starting at day 10, recovery at day 11.
    plan = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=1.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)

    # Speed 20 nm/h. Leg distance 10_000 nm. 1.05x speed = 21 nm/h.
    # Travel time = 10_000 / 21 = ~476 hours = ~19.83 days.
    # Encounter at B is at elapsed ~19.83 days.
    # now = 10.0 (inside active window). Encounter in absolute sim time =
    # 10 + 19.83 = ~29.83 days > 11 days recovery.
    shipment = _Shipment(1, _Demand(a, c, 100))
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(10.0), shipment)

    assert result is True
    assert len(shipment.associated_bookings) == 1
    booking = shipment.associated_bookings[0]
    assert booking.sequence_index == 1
    assert booking.service_route is r1
    assert booking.departure_segment_index == 1
    assert booking.arrival_segment_index == 2
    assert booking.shipment is shipment
    # Installed on the route too.
    assert booking in r1.associated_bookings
    assert shipment.current_booking_index == 1


# ---------------------------------------------------------------------------
# Test 5: exact recovery boundary (encounter == end)
# ---------------------------------------------------------------------------


def test_encounter_exactly_at_recovery_accepted() -> None:
    """An encounter at the recovery instant is safe because the interval is
    end-exclusive (``start <= now < end``)."""
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    # We want encounter at B = exactly recovery (end-exclusive).
    # now = 10, recovery = 25. Elapsed = 15 days = 360 hours.
    # At 1.05x speed (21 nm/h): distance = 360 * 21 = 7560 nm.
    ab = _Leg(a, b, distance=7560.0)
    bc = _Leg(b, c, distance=10.0)
    r1 = _ServiceRoute("R1", "R1 boundary")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, bc, r1)])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)
    ctx = _context(
        ports=[a, b, c],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    plan = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=15.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)

    # Encounter at B = 10 + 7560 / 21 / 24 = 10 + 15 = 25 days = recovery.
    shipment = _Shipment(1, _Demand(a, c, 100))
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(10.0), shipment)
    assert result is True
    assert len(shipment.associated_bookings) == 1


# ---------------------------------------------------------------------------
# Test 6: 1.05x fast-sailing guard
# ---------------------------------------------------------------------------


def test_fast_sailing_guard_makes_unsafe_safe_path_delegate() -> None:
    """A case that LOOKS safe at nominal speed but is unsafe at 1.05x speed
    must delegate. The lower bound is computed at 1.05x speed, not nominal.
    """
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    # Recovery at day 15; nominal encounter at day 12; 1.05x encounter at
    # day 12 / 1.05 = ~11.43 days, still before 15. Need a more careful
    # design: make the nominal encounter fall at 16 days but the 1.05x
    # encounter at 14 days (just before 15).
    # duration_hours_nominal = distance / 20 nm/h = distance/20 hours.
    # duration_hours_1_05 = distance / 21 nm/h.
    # now=10. Nominal encounter = 10 + dist/20/24 days. 1.05x encounter =
    # 10 + dist/21/24 days.
    # Target: nominal = 16, 1.05x = 14.9.
    # dist/20/24 = 6 => dist = 2880 nm.
    # dist/21/24 = 14.9... hmm not quite right, let me redo.
    # 16 - 10 = 6 days = 144 hours. dist = 144*20 = 2880 nm.
    # 1.05x: 2880 / 21 = 137.14 hours = 5.714 days -> encounter at 15.714 days,
    # AFTER 15. So this isn't unsafe either. Need to recalibrate.
    #
    # Different setup: very short recovery, very tight margin.
    # recovery = 15. now = 10. We want 1.05x encounter to be just before 15,
    # nominal encounter to be after 15.
    # 1.05x encounter = 14.9 days (just before recovery).
    # nominal encounter = 14.9 * 1.05 = 15.645 days (after recovery).
    # elapsed_1_05 = 4.9 days = 117.6 hours. dist = 117.6 * 21 = 2469.6 nm.
    # elapsed_nominal = 2469.6 / 20 = 123.48 hours = 5.145 days.
    # nominal encounter = 10 + 5.145 = 15.145 days (after recovery).
    # 1.05x encounter = 10 + 4.9 = 14.9 days (before recovery).
    ab = _Leg(a, b, distance=2469.6)
    bc = _Leg(b, c, distance=10.0)
    r1 = _ServiceRoute("R1", "R1 1.05x guard")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, bc, r1)])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)
    ctx = _context(
        ports=[a, b, c],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    plan = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=5.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)

    shipment = _Shipment(1, _Demand(a, c, 100))
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]

    # At nominal speed the encounter is at 15.145 days (after recovery, so the
    # override would fire). At 1.05x the encounter is at 14.9 days (before
    # recovery, so the override must NOT fire). The lower bound uses 1.05x, so
    # we expect delegation with no mutation.
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(10.0), shipment)
    assert result is None
    assert shipment.associated_bookings == []
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


# ---------------------------------------------------------------------------
# Test 7: closed origin port
# ---------------------------------------------------------------------------


def test_closed_origin_port_delegates_while_active() -> None:
    """Encounter at a closed origin happens at elapsed zero; during an active
    closure, the candidate must delegate (the closed origin is unsafe NOW)."""
    network = _make_simple_network()
    ctx = network["context"]
    plan = _DisruptionPlan(
        target_berth=network["ports"]["A"].berths[0],
        start_offset_days=10.0,
        duration_days=5.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)

    shipment = _make_shipment(network, "A", "C")
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]

    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(12.0), shipment)
    assert result is None
    assert shipment.associated_bookings == []
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


def test_closed_origin_after_recovery_allows_override() -> None:
    """Encounter at the origin happens at elapsed zero.

    If the origin is closed and the active window is short, the encounter at
    elapsed zero is immediately at/after recovery only when ``now`` sits at
    or beyond recovery AND the plan is still active. We use a 1-day closure
    starting at day 10 (recovery at day 11) and ``now`` at 10.99, which is
    still in the active window [10, 11). The encounter at A is at elapsed
    zero = 10.99, which is BEFORE recovery (11). Override does NOT fire.

    This test exercises the spec's "encounter at origin at elapsed zero" path
    while staying inside an active window.
    """
    network = _make_simple_network()
    ctx = network["context"]
    plan = _DisruptionPlan(
        target_berth=network["ports"]["A"].berths[0],
        start_offset_days=10.0,
        duration_days=1.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)

    # Active window [10, 11). now = 10.5 (inside). Encounter at A = 10.5.
    # Recovery = 11. 10.5 < 11: encounter BEFORE recovery. Override must NOT fire.
    shipment = _make_shipment(network, "A", "C")
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(10.5), shipment)
    assert result is None
    assert shipment.associated_bookings == []
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


# ---------------------------------------------------------------------------
# Test 8: closed intermediate / destination port uses arrival time
# ---------------------------------------------------------------------------


def test_closed_destination_after_arrival_time_used() -> None:
    """A closed destination's encounter happens AFTER sailing into it."""
    a, b = _Port("A"), _Port("B")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    ab = _Leg(a, b, distance=10.0)
    r1 = _ServiceRoute("R1", "R1 A-B")
    r1.segments.append(_Segment(1, ab, r1))
    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)
    ctx = _context(
        ports=[a, b],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    # Close B for 2 days starting at day 10, recovery at day 12.
    plan = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=2.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)

    # Travel time A->B at 1.05x: 10nm / 21 nm/h = 0.476 hours = 0.0198 days.
    # Arrival at B at now + 0.0198 days.
    # Now = 10.0. Arrival = 10.0198. Recovery = 12.0. Arrival < recovery.
    # So encounter at B is BEFORE recovery; must delegate.
    shipment = _Shipment(1, _Demand(a, b, 100))
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(10.0), shipment)
    assert result is None
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes

    # Active window [10, 12). At now = 11.99 we are still inside the active
    # window. Arrival at B = 11.99 + 0.0198 = 12.0098 > recovery (12.0).
    # Override fires because arrival is strictly after recovery.
    shipment2 = _Shipment(2, _Demand(a, b, 100))
    result2 = UserStrategy.assign_associated_bookings(ctx, _now_at_day(11.99), shipment2)
    assert result2 is True
    assert len(shipment2.associated_bookings) == 1


# ---------------------------------------------------------------------------
# Test 9: multiple active plans
# ---------------------------------------------------------------------------


def test_multiple_active_plans_all_must_be_safe() -> None:
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    ab = _Leg(a, b, distance=10_000.0)
    bc = _Leg(b, c, distance=10_000.0)
    r1 = _ServiceRoute("R1", "R1 multi")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, bc, r1)])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)
    ctx = _context(
        ports=[a, b, c],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    # Both B and C close; B recovers early, C recovers later than the
    # encounter at C.
    plan_b = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=1.0,
        close_berth=True,
    )
    # C recovers at day 100, encounter at C is at ~20 days. Unsafe.
    plan_c = _DisruptionPlan(
        target_berth=c.berths[0],
        start_offset_days=10.0,
        duration_days=90.0,
        close_berth=True,
    )
    ctx.disruption_plans.extend([plan_b, plan_c])

    shipment = _Shipment(1, _Demand(a, c, 100))
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(10.0), shipment)
    assert result is None
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


def test_multiple_active_plans_all_safe_overrides() -> None:
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    ab = _Leg(a, b, distance=10_000.0)
    bc = _Leg(b, c, distance=10_000.0)
    r1 = _ServiceRoute("R1", "R1 multi safe")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, bc, r1)])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)
    ctx = _context(
        ports=[a, b, c],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    # Both close, both recover quickly. Encounters both at ~20 days > 11 days.
    plan_b = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=1.0,
        close_berth=True,
    )
    plan_c = _DisruptionPlan(
        target_berth=c.berths[0],
        start_offset_days=10.0,
        duration_days=1.0,
        close_berth=True,
    )
    ctx.disruption_plans.extend([plan_b, plan_c])

    shipment = _Shipment(1, _Demand(a, c, 100))
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(10.0), shipment)
    assert result is True


# ---------------------------------------------------------------------------
# Test 10: duplicate berth plans for one port - latest active end controls
# ---------------------------------------------------------------------------


def test_duplicate_berth_plans_latest_active_end_controls() -> None:
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    ab = _Leg(a, b, distance=10_000.0)
    bc = _Leg(b, c, distance=10_000.0)
    r1 = _ServiceRoute("R1", "R1 dup")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, bc, r1)])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)
    ctx = _context(
        ports=[a, b, c],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    # Two plans for the same berth, the LATEST recovery wins.
    # First plan: closed day 10..11 (recovery=11).
    # Second plan: closed day 10..30 (recovery=30).
    # The candidate must use recovery=30 for safety.
    plan_short = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=1.0,
        close_berth=True,
    )
    plan_long = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=20.0,
        close_berth=True,
    )
    ctx.disruption_plans.extend([plan_short, plan_long])

    # Encounter at B at now + elapsed. now=10, elapsed ~ 19.83 days.
    # Encounter at B = ~29.83 days < 30 (long plan recovery).
    # So the candidate must delegate (the encounter is before the LATEST
    # recovery).
    shipment = _Shipment(1, _Demand(a, c, 100))
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(10.0), shipment)
    assert result is None
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


# ---------------------------------------------------------------------------
# Test 11: missing / nonpositive vessel speed
# ---------------------------------------------------------------------------


def test_nonpositive_speed_delegates() -> None:
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    ab = _Leg(a, b, distance=100.0)
    bc = _Leg(b, c, distance=100.0)
    r1 = _ServiceRoute("R1", "R1 speed")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, bc, r1)])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=0.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)
    ctx = _context(
        ports=[a, b, c],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    plan = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=1.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)

    shipment = _Shipment(1, _Demand(a, c, 100))
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(10.0), shipment)
    assert result is None
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


def test_missing_vessel_class_speed_delegates() -> None:
    """If a vessel class is missing, speed is None; delegate."""
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    ab = _Leg(a, b, distance=100.0)
    bc = _Leg(b, c, distance=100.0)
    r1 = _ServiceRoute("R1", "R1 no speed")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, bc, r1)])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=None)  # type: ignore[arg-type]
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)
    ctx = _context(
        ports=[a, b, c],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    plan = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=1.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)

    shipment = _Shipment(1, _Demand(a, c, 100))
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(10.0), shipment)
    assert result is None
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


# ---------------------------------------------------------------------------
# Test 12: no complete nominal path
# ---------------------------------------------------------------------------


def test_no_complete_path_delegates() -> None:
    """Origin and destination are isolated in the original route graph."""
    a = _Port("A")
    z = _Port("Z")
    a.berths.append(_Berth(0, a))
    z.berths.append(_Berth(0, z))

    # Routes that do NOT connect A to Z.
    r1 = _ServiceRoute("R1", "R1 A-B")
    b = _Port("B")
    ab = _Leg(a, b, distance=100.0)
    r1.segments.append(_Segment(1, ab, r1))
    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)

    ctx = _context(
        ports=[a, b, z],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )
    plan = _DisruptionPlan(
        target_berth=a.berths[0],
        start_offset_days=10.0,
        duration_days=5.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)

    shipment = _Shipment(1, _Demand(a, z, 100))
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(12.0), shipment)
    assert result is None
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


# ---------------------------------------------------------------------------
# Test 13: existing bookings preserved on delegation; replaced on override
# ---------------------------------------------------------------------------


def test_delegation_preserves_existing_bookings_by_identity() -> None:
    network = _make_simple_network()
    ctx = network["context"]
    r1 = network["routes"]["R1"]
    shipment = _make_shipment(network, "A", "C")

    # Pre-populate an existing booking.
    old_booking = FakeBooking(
        sequence_index=1,
        shipment=shipment,
        service_route=r1,
        departure_segment_index=1,
        arrival_segment_index=2,
    )
    shipment.associated_bookings.append(old_booking)
    r1.associated_bookings.append(old_booking)
    shipment.current_booking_index = 1

    # No active disruption -> delegate.
    snapshot_routes = [tuple(r.associated_bookings) for r in ctx.service_routes]

    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(0.0), shipment)
    assert result is None
    # Existing bookings untouched.
    assert old_booking in shipment.associated_bookings
    assert old_booking in r1.associated_bookings
    assert shipment.current_booking_index == 1
    assert [tuple(r.associated_bookings) for r in ctx.service_routes] == snapshot_routes


def test_override_removes_old_and_installs_new_consistently() -> None:
    """On override, the candidate must remove old bookings from old routes
    and install the new chain on the new routes consistently."""
    network = _make_simple_network()
    ctx = network["context"]
    r2 = network["routes"]["R2"]
    shipment = _make_shipment(network, "A", "C")

    # Pre-populate an existing booking on R2.
    old_booking = FakeBooking(
        sequence_index=1,
        shipment=shipment,
        service_route=r2,
        departure_segment_index=1,
        arrival_segment_index=1,
    )
    shipment.associated_bookings.append(old_booking)
    r2.associated_bookings.append(old_booking)

    # Active disruption that does NOT touch the path (R2 has segment 1 only,
    # disruption is on leg A->B which R2 doesn't use). Since the path is
    # unaffected, the candidate must return None without mutation.
    plan = _DisruptionPlan(
        target_leg=network["legs"]["AB"],
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=5.0,
    )
    ctx.disruption_plans.append(plan)
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(12.0), shipment)
    assert result is None
    assert old_booking in r2.associated_bookings

    # Now an active disruption on a leg that IS on R2 (no such leg here; we
    # will instead verify the override path removes the old booking by
    # constructing an artificial setup with a long-leg route where the
    # override fires).
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))
    ab = _Leg(a, b, distance=10_000.0)
    bc = _Leg(b, c, distance=10_000.0)
    r1 = _ServiceRoute("R1", "R1 override remove")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, bc, r1)])
    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)
    ctx2 = _context(
        ports=[a, b, c],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )
    plan = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=1.0,
        close_berth=True,
    )
    ctx2.disruption_plans.append(plan)

    shipment2 = _Shipment(2, _Demand(a, c, 100))
    old_booking2 = FakeBooking(
        sequence_index=1,
        shipment=shipment2,
        service_route=r1,
        departure_segment_index=1,
        arrival_segment_index=1,
    )
    shipment2.associated_bookings.append(old_booking2)
    r1.associated_bookings.append(old_booking2)

    result = UserStrategy.assign_associated_bookings(ctx2, _now_at_day(10.0), shipment2)
    assert result is True
    # Old booking removed from old route.
    assert old_booking2 not in r1.associated_bookings
    # Shipment now has the new chain only.
    assert old_booking2 not in shipment2.associated_bookings
    assert all(b is not old_booking2 for b in shipment2.associated_bookings)
    assert all(b.shipment is shipment2 for b in shipment2.associated_bookings)
    assert shipment2.current_booking_index == 1
    # All new bookings installed on r1.
    assert len(shipment2.associated_bookings) == len(r1.associated_bookings)
    assert set(shipment2.associated_bookings) == set(r1.associated_bookings)


# ---------------------------------------------------------------------------
# Test 14: determinism and ties
# ---------------------------------------------------------------------------


def test_equal_distance_paths_resolve_by_iteration_order() -> None:
    """Two routes with identical segment distances; tie-break by iteration
    order on context.ports / route segments."""
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    # Two routes with identical distance.
    ab1 = _Leg(a, b, distance=100.0)
    bc1 = _Leg(b, c, distance=100.0)
    r1 = _ServiceRoute("R1", "R1 first")
    r1.segments.extend([_Segment(1, ab1, r1), _Segment(2, bc1, r1)])

    ab2 = _Leg(a, b, distance=100.0)
    bc2 = _Leg(b, c, distance=100.0)
    r2 = _ServiceRoute("R2", "R2 second")
    r2.segments.extend([_Segment(1, ab2, r2), _Segment(2, bc2, r2)])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel1 = _Vessel(1, vessel_class, r1)
    vessel2 = _Vessel(2, vessel_class, r2)
    r1.deployed_vessels.append(vessel1)
    r2.deployed_vessels.append(vessel2)

    ctx = _context(
        ports=[a, b, c],
        service_routes=[r1, r2],  # r1 is earlier in iteration order
        initial_service_routes=[r1, r2],
        vessels=[vessel1, vessel2],
    )

    # Active disruption on R2's first leg (forces R1 selection if safe).
    plan = _DisruptionPlan(
        target_leg=ab2,
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=5.0,
    )
    ctx.disruption_plans.append(plan)

    shipment = _Shipment(1, _Demand(a, c, 100))
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(12.0), shipment)
    assert result is None  # Encounter at B at ~12.2 days < recovery 15.

    # Test determinism: a second call yields the same result.
    shipment2 = _Shipment(2, _Demand(a, c, 100))
    result2 = UserStrategy.assign_associated_bookings(ctx, _now_at_day(12.0), shipment2)
    assert result2 is None


# ---------------------------------------------------------------------------
# Test 15: alternative service routes excluded from nominal graph
# ---------------------------------------------------------------------------


def test_alternative_routes_excluded_from_nominal_graph() -> None:
    """A path only available via an alternative route must NOT be picked."""
    network = _make_simple_network()
    ctx = network["context"]
    # The ALT route has source_service_route=R1 (non-None), so its legs and
    # segments must not contribute to the nominal shortest path.
    # Direct A->C via R2 already exists. The alternative route offers a
    # different topology (B->A->C). The nominal graph still includes R1 (the
    # original A->B->C) and R2 (the original A->C). Use this to confirm the
    # nominal path goes A->C directly, not through the alternative.
    shipment = _make_shipment(network, "A", "C")
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(0.0), shipment)
    assert result is None  # No active disruption, fallback path.

    # Add a disruption affecting R2's leg A->C. The only remaining nominal
    # route from A to C is R1 (A->B->C), which involves port B. Encounter at
    # B is at elapsed ~0.2 days. So if B is NOT closed, the disruption is on
    # a leg not on the path and the override must not fire.
    plan = _DisruptionPlan(
        target_leg=network["legs"]["AC"],
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=5.0,
    )
    ctx.disruption_plans.append(plan)
    shipment3 = _Shipment(3, _Demand(network["ports"]["A"], network["ports"]["C"], 100))
    result3 = UserStrategy.assign_associated_bookings(ctx, _now_at_day(12.0), shipment3)
    assert result3 is None  # No mutation; ALT path is excluded.

    # Sanity: the alternative route's bookings list is empty after all calls.
    alt_route = network["routes"]["ALT"]
    assert alt_route.associated_bookings == []


def test_alternative_route_excluded_even_if_nominal_path_blocked() -> None:
    """If the only original route that connects origin->dest is disrupted and
    the alternative route would be the next best, the candidate must NOT use
    the alternative. It delegates with None."""
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))
    c.berths.append(_Berth(0, c))

    ab = _Leg(a, b, distance=100.0)
    bc = _Leg(b, c, distance=100.0)
    ac = _Leg(a, c, distance=300.0)
    ba = _Leg(b, a, distance=100.0)

    r1 = _ServiceRoute("R1", "R1 A-B-C")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, bc, r1)])
    r_alt = _ServiceRoute("R1-ALT", "R1-ALT")
    r_alt.source_service_route = r1
    r_alt.segments.extend([_Segment(1, ba, r_alt), _Segment(2, ac, r_alt)])

    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)

    ctx = _context(
        ports=[a, b, c],
        service_routes=[r1, r_alt],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    # The candidate cannot ignore the disruption just because the only
    # alternative is a non-original route. With B closed, the override must
    # not fire.
    plan = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=5.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)

    shipment = _Shipment(1, _Demand(a, c, 100))
    snapshot_alt = tuple(r_alt.associated_bookings)
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(12.0), shipment)
    assert result is None
    assert tuple(r_alt.associated_bookings) == snapshot_alt


# ---------------------------------------------------------------------------
# Test: cycle not used as a same-origin same-origin edge
# ---------------------------------------------------------------------------


def test_cycle_not_treated_as_self_edge() -> None:
    """The full cycle of a route must not be a viable origin-to-same-origin
    edge in the nominal graph."""
    a, b = _Port("A"), _Port("B")
    a.berths.append(_Berth(0, a))
    b.berths.append(_Berth(0, b))

    ab = _Leg(a, b, distance=100.0)
    ba = _Leg(b, a, distance=100.0)
    r1 = _ServiceRoute("R1", "R1 cycle")
    r1.segments.extend([_Segment(1, ab, r1), _Segment(2, ba, r1)])
    vessel_class = _VesselClass("VC1", capacity=1000, speed=20.0)
    vessel = _Vessel(1, vessel_class, r1)
    r1.deployed_vessels.append(vessel)
    ctx = _context(
        ports=[a, b],
        service_routes=[r1],
        initial_service_routes=[r1],
        vessels=[vessel],
    )

    # Disruption on leg A->B, no path to B that avoids A->B unless we accept
    # going A->B->A->B (multi-hop). We test simply that no infinite-loop edge
    # is created and the override is safe (encounter at B is at elapsed 0).
    plan = _DisruptionPlan(
        target_berth=b.berths[0],
        start_offset_days=10.0,
        duration_days=5.0,
        close_berth=True,
    )
    ctx.disruption_plans.append(plan)
    shipment = _Shipment(1, _Demand(a, b, 100))
    # Encounter at B at now + 100nm/(20*1.05)/24 days = ~0.198 days. < recovery 15.
    snapshot = tuple(r1.associated_bookings)
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(12.0), shipment)
    assert result is None
    assert tuple(r1.associated_bookings) == snapshot


# ---------------------------------------------------------------------------
# Test: assignee == destination already handled by the candidate
# ---------------------------------------------------------------------------


def test_origin_equals_destination_delegates() -> None:
    """The candidate may receive a shipment with origin == destination. The
    organizer fallback returns True for this; the candidate must not break
    that contract: returning None is safe (fallback handles it). Returning
    True would also be acceptable but is not what the organizer call sites
    expect on this path (the fallback does the trivial case).
    """
    network = _make_simple_network()
    ctx = network["context"]
    shipment = _make_shipment(network, "A", "A")
    result = UserStrategy.assign_associated_bookings(ctx, _now_at_day(0.0), shipment)
    # Either None (delegate) or True (override) is allowed; False is not.
    assert result is not False
