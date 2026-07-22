"""Unit tests for the TEU-delay-per-berth-hour Smith-style priority candidate.

These tests cover ``UserStrategy.select_vessel_for_berth`` with synthetic
organizer-shaped objects. The candidate is purely observational: it reads
state via ``getattr``/method calls and returns one of the supplied
``waiting_vessels`` without mutating any input.

The fixture builds a small two-port network. Helpers expose only the
public surface the candidate reads; they do not copy organizer source.

The candidate's exact selection formula is:

  service_hours = 3.0 + handled_teu / (qc_count * 45.0)
  ratio = affected_teu / service_hours

For exact integer comparison, multiply through by 45:

  numerator   = affected_teu * qc_count
  denominator = 135 * qc_count + handled_teu

A outranks B iff ``A.numerator * B.denominator > B.numerator * A.denominator``.
Exact ties preserve waiting_vessels order. Zero cargo handling still consumes
the fixed three-hour berthing window, so it is compared via the same ratio.
"""

from __future__ import annotations

import ast
import datetime as dt
import math
import pathlib
from types import SimpleNamespace

import pytest
from response_strategies.user_strategy import UserStrategy

USER_STRATEGY_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "submission"
    / "response_strategies"
    / "user_strategy.py"
)


# ---------------------------------------------------------------------------
# Synthetic organizer-shaped objects
# ---------------------------------------------------------------------------


class _Booking:
    __slots__ = (
        "sequence_index",
        "shipment",
        "service_route",
        "departure_segment_index",
        "arrival_segment_index",
    )

    def __init__(
        self,
        *,
        service_route,
        departure_segment_index,
        arrival_segment_index,
        shipment=None,
    ) -> None:
        self.sequence_index = departure_segment_index
        self.shipment = shipment
        self.service_route = service_route
        self.departure_segment_index = departure_segment_index
        self.arrival_segment_index = arrival_segment_index


class _Shipment:
    def __init__(
        self,
        *,
        teu_size=1,
        current_storage_port=None,
        carrying_vessel=None,
        booking=None,
        age_seconds=0.0,
    ) -> None:
        self.teu_size = teu_size
        self.current_storage_port = current_storage_port
        self.carrying_vessel = carrying_vessel
        self._booking = booking
        self.generated_time = (
            dt.datetime(2026, 1, 1) - dt.timedelta(seconds=age_seconds)
            if age_seconds
            else dt.datetime(2026, 1, 1)
        )
        self.associated_bookings = [booking] if booking is not None else []
        self.current_booking_index = 1 if booking is not None else None

    def get_current_booking(self) -> _Booking | None:
        return self._booking


class _Leg:
    def __init__(self, departure_port, arrival_port) -> None:
        self.departure_port = departure_port
        self.arrival_port = arrival_port
        self.sailing_distance = 100.0


class _Segment:
    def __init__(self, sequence_index, leg) -> None:
        self.sequence_index = sequence_index
        self.associated_leg = leg
        self.associated_service_route = None
        self.current_vessels: list = []


class _ServiceRoute:
    def __init__(self, segments) -> None:
        self.segments = segments
        self.id = "R1"
        self.source_service_route = None
        self.associated_bookings: list = []
        self.deployed_vessels: list = []


class _VesselClass:
    def __init__(self, *, teu_capacity, loa) -> None:
        self.teu_capacity = teu_capacity
        self.sailing_speed = 20.0
        self.loa = loa


class _Vessel:
    def __init__(
        self,
        *,
        vessel_class,
        route,
        current_segment=None,
        carried_shipments=(),
        index=1,
    ) -> None:
        self.index = index
        self.vessel_class = vessel_class
        self.assigned_service_route = route
        self.current_segment = current_segment
        self.current_berth = None
        self.carried_shipments = list(carried_shipments)
        self.pending_assigned_service_route = None

    def get_next_segment(self) -> _Segment:
        segments = sorted(self.assigned_service_route.segments, key=lambda s: s.sequence_index)
        if self.current_segment is None:
            return segments[0]
        for seg in segments:
            if seg.sequence_index > self.current_segment.sequence_index:
                return seg
        return segments[0]


class _Berth:
    def __init__(self, port, index=0) -> None:
        self.port = port
        self.index = index
        self.is_available = True
        self.occupying_vessel = None


class _Port:
    def __init__(self, name="A", berths=1) -> None:
        self.name = name
        self.berths = [_Berth(self, i) for i in range(berths)]
        self.shipments_in_storage: list = []


def _now() -> dt.datetime:
    return dt.datetime.min + dt.timedelta(days=200.0)


def _make_route() -> _ServiceRoute:
    origin = _Port("A")
    mid = _Port("B")
    leg1 = _Leg(origin, mid)
    leg2 = _Leg(mid, origin)
    seg1 = _Segment(1, leg1)
    seg2 = _Segment(2, leg2)
    route = _ServiceRoute([seg1, seg2])
    for s in route.segments:
        s.associated_service_route = route
    return route


def _make_vessel(
    *,
    teu_capacity=1000,
    loa=200.0,
    current_segment=None,
    carried=(),
    index=1,
    route=None,
) -> _Vessel:
    route = route if route is not None else _make_route()
    return _Vessel(
        vessel_class=_VesselClass(teu_capacity=teu_capacity, loa=loa),
        route=route,
        current_segment=current_segment,
        carried_shipments=list(carried),
        index=index,
    )


def _make_carrying_shipment(
    *, teu_size, route, current_segment_index, vessel, age_seconds=0.0
) -> _Shipment:
    booking = _Booking(
        service_route=route,
        departure_segment_index=current_segment_index,
        arrival_segment_index=current_segment_index,
    )
    return _Shipment(
        teu_size=teu_size,
        carrying_vessel=vessel,
        booking=booking,
        age_seconds=age_seconds,
    )


def _make_storage_shipment(
    *,
    teu_size,
    route,
    departure_segment_index,
    port,
    carrying_vessel=None,
) -> _Shipment:
    booking = _Booking(
        service_route=route,
        departure_segment_index=departure_segment_index,
        arrival_segment_index=departure_segment_index,
    )
    shipment = _Shipment(
        teu_size=teu_size,
        current_storage_port=port,
        carrying_vessel=carrying_vessel,
        booking=booking,
    )
    port.shipments_in_storage.append(shipment)
    return shipment


def _select(*, port, waiting_vessels, context=None):
    if context is None:
        context = SimpleNamespace()
    return UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=waiting_vessels,
        available_berths=port.berths,
        current_time=_now(),
    )


# ---------------------------------------------------------------------------
# Selection rule and lifecycle
# ---------------------------------------------------------------------------


def test_empty_waiting_returns_none() -> None:
    assert _select(port=_Port(), waiting_vessels=[]) is None


def test_single_vessel_returns_that_vessel() -> None:
    vessel = _make_vessel(index=42)
    assert _select(port=_Port(), waiting_vessels=[vessel]) is vessel


def test_other_hooks_return_none() -> None:
    ctx = SimpleNamespace()
    vessel = _make_vessel()
    shipment = _make_vessel(index=7)
    snap = dict(ctx.__dict__)
    assert UserStrategy.create_alternative_service_routes(ctx, _now(), vessel) is None
    assert UserStrategy.assign_associated_bookings(ctx, _now(), shipment) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(ctx, _now(), vessel) is None
    assert ctx.__dict__ == snap


def test_returned_object_always_in_waiting_vessels() -> None:
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    vessel = _make_vessel(
        route=route,
        current_segment=seg1,
        carried=[
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=None,
            )
        ],
    )
    other = _make_vessel(index=99)
    result = _select(port=port, waiting_vessels=[vessel, other])
    assert result in (vessel, other)


def test_exact_tie_preserves_waiting_order() -> None:
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    vc = _VesselClass(teu_capacity=1000, loa=200.0)
    v_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    v_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)
    for v in (v_a, v_b):
        v.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=v,
            )
        )
    assert _select(port=port, waiting_vessels=[v_a, v_b]) is v_a


# ---------------------------------------------------------------------------
# Smith-ratio math with the three-hour fixed berthing overhead
# ---------------------------------------------------------------------------


def test_three_hour_overhead_changes_decision() -> None:
    """Vessel A (10 affected, 0 handled, qc=1) must lose to vessel B
    (100 affected, 100 handled, qc=1) once the 3-hour berthing is included:

      A: numerator=10*1=10,  denominator=135*1+0=135    -> 10/135
      B: numerator=100*1=100, denominator=135*1+100=235 -> 100/235

    A.numerator * B.denominator = 10 * 235 = 2350
    B.numerator * A.denominator = 100 * 135 = 13500
    B wins."""
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    v_a = _Vessel(
        vessel_class=_VesselClass(teu_capacity=100, loa=200.0),
        route=route,
        current_segment=seg1,
        index=1,
    )
    v_b = _Vessel(
        vessel_class=_VesselClass(teu_capacity=1000, loa=200.0),
        route=route,
        current_segment=seg1,
        index=2,
    )
    # v_b carries 100 TEU that discharge here -> handled=100, affected=100.
    v_b.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=100,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=v_b,
        )
    )
    assert _select(port=port, waiting_vessels=[v_a, v_b]) is v_b


def test_empty_zero_work_vessel_loses_to_positive_ratio() -> None:
    """affected=0, handled=0 -> numerator=0. Any positive numerator wins."""
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    empty = _make_vessel(route=route, current_segment=seg1, index=1)
    positive = _make_vessel(
        route=route,
        current_segment=seg1,
        index=2,
        carried=[
            _make_carrying_shipment(
                teu_size=10,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=None,
            )
        ],
    )
    assert _select(port=port, waiting_vessels=[empty, positive]) is positive


def test_zero_handling_can_still_win_with_high_affected() -> None:
    """A vessel with zero handled TEU but high continuing cargo can win
    against a low-positive competitor via the 3-hour floor:

      A: affected=1000, handled=0, qc=1 -> 1000*1 / 135*1
      B: affected=10,   handled=10, qc=1 -> 10*1 / (135+10)

      A.num * B.den = 1000 * 145 = 145000
      B.num * A.den = 10   * 135 =  1350
      A wins."""
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    v_a = _make_vessel(route=route, current_segment=seg1, index=1)
    v_b = _make_vessel(route=route, current_segment=seg1, index=2)
    for _ in range(10):
        v_a.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index + 1,
                vessel=None,
            )
        )
    v_b.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=10,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=None,
        )
    )
    assert _select(port=port, waiting_vessels=[v_b, v_a]) is v_a


def test_qc_count_drives_selection() -> None:
    """qc_count appears in both numerator and denominator."""
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    v_a = _Vessel(
        vessel_class=_VesselClass(teu_capacity=2000, loa=110.0),  # qc=2
        route=route,
        current_segment=seg1,
        index=1,
    )
    v_b = _Vessel(
        vessel_class=_VesselClass(teu_capacity=2000, loa=600.0),  # qc=10
        route=route,
        current_segment=seg1,
        index=2,
    )
    for v, teu in ((v_a, 100), (v_b, 100)):
        v.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=teu,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=v,
            )
        )
    # A: (100*2)/(135*2+100) = 200/370
    # B: (100*10)/(135*10+100) = 1000/1450
    # B wins.
    assert _select(port=port, waiting_vessels=[v_a, v_b]) is v_b


def test_exact_total_duration_cross_multiplication() -> None:
    """Verify exact cross multiplication across mixed qc/handled values."""
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    v_a = _Vessel(
        vessel_class=_VesselClass(teu_capacity=2000, loa=275.0),  # qc=5
        route=route,
        current_segment=seg1,
        index=1,
    )
    v_b = _Vessel(
        vessel_class=_VesselClass(teu_capacity=2000, loa=385.0),  # qc=7
        route=route,
        current_segment=seg1,
        index=2,
    )
    # A: carried=300, qc=5, affected=300, handled=300
    #    num=1500, den=675+300=975 -> 1500/975
    # B: carried=100, qc=7, affected=100, handled=100
    #    num=700,  den=945+100=1045 -> 700/1045
    # A.num * B.den = 1500*1045 = 1567500
    # B.num * A.den = 700 * 975  =  682500
    # A wins.
    for _ in range(3):
        v_a.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=v_a,
            )
        )
    v_b.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=100,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=v_b,
        )
    )
    assert _select(port=port, waiting_vessels=[v_b, v_a]) is v_a


# ---------------------------------------------------------------------------
# Cargo semantics
# ---------------------------------------------------------------------------


def test_age_does_not_change_selection() -> None:
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    vc = _VesselClass(teu_capacity=2000, loa=200.0)
    v_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    v_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)
    for v in (v_a, v_b):
        v.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=v,
            )
        )
    pick_no_age = _select(port=port, waiting_vessels=[v_a, v_b])
    v_a.carried_shipments[0].generated_time = dt.datetime(2026, 1, 1) - dt.timedelta(days=365)
    v_b.carried_shipments[0].generated_time = dt.datetime(2026, 1, 1) - dt.timedelta(seconds=1)
    pick_with_age = _select(port=port, waiting_vessels=[v_a, v_b])
    assert pick_no_age is pick_with_age


def test_discharging_uses_only_current_segment() -> None:
    """Cargo discharging at a future segment is continuing, not handled."""
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    seg2 = route.segments[1]
    v_a = _make_vessel(
        route=route,
        current_segment=seg1,
        index=1,
        carried=[
            _make_carrying_shipment(
                teu_size=10,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=None,
            )
        ],
    )
    v_b = _make_vessel(
        route=route,
        current_segment=seg1,
        index=2,
        carried=[
            _make_carrying_shipment(
                teu_size=500,
                route=route,
                current_segment_index=seg2.sequence_index,
                vessel=None,
            )
        ],
    )
    # A: handled=10, affected=10, qc=1
    #    num=10, den=145
    # B: handled=0 (500 is continuing, not current discharge), affected=500
    #    num=500, den=135
    # A.num*B.den = 10*135  = 1350
    # B.num*A.den = 500*145 = 72500
    # B wins.
    assert _select(port=port, waiting_vessels=[v_a, v_b]) is v_b


def test_continuing_cargo_counts_in_affected_not_handled() -> None:
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    v_a = _Vessel(
        vessel_class=_VesselClass(teu_capacity=2000, loa=200.0),
        route=route,
        current_segment=seg1,
        index=1,
    )
    v_b = _Vessel(
        vessel_class=_VesselClass(teu_capacity=2000, loa=200.0),
        route=route,
        current_segment=seg1,
        index=2,
    )
    v_a.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=10,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=v_a,
        )
    )
    v_b.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=10,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=v_b,
        )
    )
    for _ in range(10):
        v_b.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index + 1,
                vessel=v_b,
            )
        )
    assert _select(port=port, waiting_vessels=[v_a, v_b]) is v_b


def test_different_route_carried_cargo_excluded_from_occupied() -> None:
    """Mirror organizer _calc_occupied_teu: different-route carried cargo
    does not occupy capacity; it should not artificially reduce projected
    loading."""
    port = _Port()
    main_route = _make_route()
    foreign_route = _make_route()
    seg1 = main_route.segments[0]
    seg2 = main_route.segments[1]
    vc = _VesselClass(teu_capacity=100, loa=200.0)
    v = _Vessel(
        vessel_class=vc,
        route=main_route,
        current_segment=seg1,
        index=1,
    )
    # Carry cargo whose booking belongs to a different route -> must be
    # excluded from occupied capacity (organizer rule).
    foreign_booking = _Booking(
        service_route=foreign_route,
        departure_segment_index=seg1.sequence_index,
        arrival_segment_index=seg1.sequence_index,
    )
    foreign = _Shipment(teu_size=80, carrying_vessel=v, booking=foreign_booking)
    v.carried_shipments.append(foreign)
    # Eligible storage cargo: 100 TEU.
    for _ in range(10):
        _make_storage_shipment(
            teu_size=10,
            route=main_route,
            departure_segment_index=seg2.sequence_index,
            port=port,
        )
    # Occupied = 0 (foreign-route cargo is excluded).
    # Projected load = 100.
    # handled = 100, affected = 100.
    result = _select(port=port, waiting_vessels=[v])
    assert result is v


def test_loading_filters_route_departure_carrying_storage() -> None:
    """Predicted-load filter excludes wrong route, wrong departure,
    carrying vessel, and other-port storage."""
    port = _Port()
    other_port = _Port("B")
    route = _make_route()
    other_route = _make_route()
    seg1 = route.segments[0]
    seg2 = route.segments[1]
    vessel = _make_vessel(route=route, current_segment=seg1, index=1)
    _make_storage_shipment(
        teu_size=10,
        route=other_route,
        departure_segment_index=seg2.sequence_index,
        port=port,
    )
    _make_storage_shipment(
        teu_size=10,
        route=route,
        departure_segment_index=seg1.sequence_index,
        port=port,
    )
    other_v = _make_vessel(index=99)
    _make_storage_shipment(
        teu_size=10,
        route=route,
        departure_segment_index=seg2.sequence_index,
        port=port,
        carrying_vessel=other_v,
    )
    _make_storage_shipment(
        teu_size=10,
        route=route,
        departure_segment_index=seg2.sequence_index,
        port=other_port,
    )
    eligible = _make_storage_shipment(
        teu_size=10,
        route=route,
        departure_segment_index=seg2.sequence_index,
        port=port,
    )
    storage_ids = [id(s) for s in port.shipments_in_storage]
    result = _select(port=port, waiting_vessels=[vessel])
    assert result is vessel
    assert [id(s) for s in port.shipments_in_storage] == storage_ids
    assert eligible in port.shipments_in_storage


def test_greedy_load_preserves_order_and_caps_capacity() -> None:
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    seg2 = route.segments[1]
    vessel = _Vessel(
        vessel_class=_VesselClass(teu_capacity=100, loa=200.0),
        route=route,
        current_segment=seg1,
        index=1,
    )
    for _ in range(12):
        _make_storage_shipment(
            teu_size=10,
            route=route,
            departure_segment_index=seg2.sequence_index,
            port=port,
        )
    before = [id(s) for s in port.shipments_in_storage]
    assert _select(port=port, waiting_vessels=[vessel]) is vessel
    assert [id(s) for s in port.shipments_in_storage] == before


def test_current_segment_none_excludes_only_assigned_route_discharge() -> None:
    """Mirror organizer: when current_segment is None, foreign-route
    cargo is excluded, all assigned-route cargo is occupied."""
    port = _Port()
    main_route = _make_route()
    foreign_route = _make_route()
    seg2 = main_route.segments[1]
    vc = _VesselClass(teu_capacity=100, loa=200.0)
    vessel = _Vessel(vessel_class=vc, route=main_route, current_segment=None, index=1)
    vessel.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=80,
            route=main_route,
            current_segment_index=seg2.sequence_index,
            vessel=vessel,
        )
    )
    foreign = _Shipment(
        teu_size=50,
        carrying_vessel=vessel,
        booking=_Booking(
            service_route=foreign_route,
            departure_segment_index=seg2.sequence_index,
            arrival_segment_index=seg2.sequence_index,
        ),
    )
    vessel.carried_shipments.append(foreign)
    for _ in range(3):
        _make_storage_shipment(
            teu_size=10,
            route=main_route,
            departure_segment_index=seg2.sequence_index,
            port=port,
        )
    # Organizer rule (current_segment None, foreign excluded):
    # occupied = 80 (foreign 50 excluded). remaining=20. Load 20 TEU.
    assert _select(port=port, waiting_vessels=[vessel]) is vessel


# ---------------------------------------------------------------------------
# Determinism, no-mutation, and invalid-input delegation
# ---------------------------------------------------------------------------


def test_determinism_repeated_calls_same_selection() -> None:
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    vc = _VesselClass(teu_capacity=1000, loa=200.0)
    v_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    v_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)
    for v in (v_a, v_b):
        v.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=v,
            )
        )
    seen = {_select(port=port, waiting_vessels=[v_a, v_b]) for _ in range(5)}
    assert len(seen) == 1


def test_no_mutation_snapshot() -> None:
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    seg2 = route.segments[1]
    vc = _VesselClass(teu_capacity=500, loa=200.0)
    v_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    v_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)
    for v in (v_a, v_b):
        v.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=50,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=v,
            )
        )
        v.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=50,
                route=route,
                current_segment_index=seg1.sequence_index + 1,
                vessel=v,
            )
        )
    _make_storage_shipment(
        teu_size=10,
        route=route,
        departure_segment_index=seg2.sequence_index,
        port=port,
    )
    storage_before = [id(s) for s in port.shipments_in_storage]
    carried_before = (
        [id(s) for s in v_a.carried_shipments],
        [id(s) for s in v_b.carried_shipments],
    )
    _select(port=port, waiting_vessels=[v_a, v_b])
    assert [id(s) for s in port.shipments_in_storage] == storage_before
    assert [id(s) for s in v_a.carried_shipments] == carried_before[0]
    assert [id(s) for s in v_b.carried_shipments] == carried_before[1]


@pytest.mark.parametrize(
    "invalid_value",
    ["missing", None, "abc", math.nan, math.inf, 0, -5],
    ids=["missing_attr", "none", "nonnumeric", "nan", "inf", "zero", "negative"],
)
def test_invalid_teu_delegates_and_preserves_state(invalid_value) -> None:
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    vessel = _Vessel(
        vessel_class=_VesselClass(teu_capacity=1000, loa=200.0),
        route=route,
        current_segment=seg1,
        index=1,
    )
    booking = _Booking(
        service_route=route,
        departure_segment_index=seg1.sequence_index,
        arrival_segment_index=seg1.sequence_index,
    )
    if invalid_value == "missing":

        class _MissingTeuShipment:
            def __init__(self, *, carrying_vessel, booking):
                self.carrying_vessel = carrying_vessel
                self._booking = booking

            def get_current_booking(self):
                return self._booking

        shipment = _MissingTeuShipment(carrying_vessel=vessel, booking=booking)
    else:
        shipment = _Shipment(
            teu_size=invalid_value,
            carrying_vessel=vessel,
            booking=booking,
        )
    vessel.carried_shipments.append(shipment)

    storage_before = [id(s) for s in port.shipments_in_storage]
    carried_before = [id(s) for s in vessel.carried_shipments]
    other_vessel = _make_vessel(index=2)

    assert _select(port=port, waiting_vessels=[vessel, other_vessel]) is None
    assert [id(s) for s in port.shipments_in_storage] == storage_before
    assert [id(s) for s in vessel.carried_shipments] == carried_before


@pytest.mark.parametrize(
    "mutator",
    [
        lambda v: setattr(v, "vessel_class", None),
        lambda v: setattr(v.vessel_class, "loa", -1.0),
        lambda v: setattr(v.vessel_class, "loa", math.inf),
        lambda v: setattr(v.vessel_class, "teu_capacity", -1),
        lambda v: setattr(v, "assigned_service_route", None),
    ],
    ids=[
        "missing_vessel_class",
        "negative_loa",
        "nonfinite_loa",
        "nonpositive_capacity",
        "missing_route",
    ],
)
def test_invalid_vessel_inputs_delegate(mutator) -> None:
    port = _Port()
    route = _make_route()
    seg1 = route.segments[0]
    vessel = _Vessel(
        vessel_class=_VesselClass(teu_capacity=1000, loa=200.0),
        route=route,
        current_segment=seg1,
        index=1,
    )
    vessel.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=100,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel,
        )
    )
    mutator(vessel)
    assert _select(port=port, waiting_vessels=[vessel]) is None


# ---------------------------------------------------------------------------
# Static guard: no broad exception handlers in submission code
# ---------------------------------------------------------------------------


def test_no_broad_exception_handlers_in_user_strategy() -> None:
    """AST guard: the candidate must not contain bare except, ``except:``,
    or handlers catching ``Exception`` / ``BaseException``. Only narrow
    expected exceptions are permitted."""
    source = USER_STRATEGY_PATH.read_text()
    tree = ast.parse(source)
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            offenders.append((node.lineno, "bare except"))
            continue
        target = node.type
        names: list[str] = []
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Tuple):
            for elt in target.elts:
                if isinstance(elt, ast.Name):
                    names.append(elt.id)
                elif isinstance(elt, ast.Attribute):
                    names.append(elt.attr)
        for name in names:
            if name in {"Exception", "BaseException"}:
                offenders.append((node.lineno, f"broad handler for {name}"))
    assert not offenders, f"submission must not contain broad exception handlers: {offenders}"
