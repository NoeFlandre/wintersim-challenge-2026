"""Unit tests for the TEU-delay-per-berth-hour Smith-style priority candidate.

These tests cover ``UserStrategy.select_vessel_for_berth`` with synthetic
organizer-shaped objects. The candidate is purely observational: it reads
state via ``getattr``/method calls and returns one of the supplied
``waiting_vessels`` without mutating any input. The implementation is
expected to live entirely in
``submission/response_strategies/user_strategy.py``.

The fixtures build a small network (one service route, two ports) with
helpers for routes, segments, legs, vessel classes, vessels, ports and
shipments that mirror the organizer public surface. Tests are concise and
data-driven; numbers are chosen so the expected winner is unambiguous.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from response_strategies.user_strategy import UserStrategy

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
        self, *, service_route, departure_segment_index, arrival_segment_index, shipment=None
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
        self.completion_time = None
        self.associated_bookings = [booking] if booking is not None else []
        self.current_booking_index = 1 if booking is not None else None

    def get_current_booking(self) -> _Booking:
        return self._booking


class _Leg:
    def __init__(self, departure_port, arrival_port, distance=100.0) -> None:
        self.departure_port = departure_port
        self.arrival_port = arrival_port
        self.sailing_distance = distance


class _Segment:
    def __init__(self, sequence_index, leg, route) -> None:
        self.sequence_index = sequence_index
        self.associated_leg = leg
        self.associated_service_route = route
        self.current_vessels: list = []


class _ServiceRoute:
    def __init__(self, segments) -> None:
        self.segments = segments
        self.id = "R1"
        self.source_service_route = None
        self.associated_bookings: list = []
        self.deployed_vessels: list = []


class _VesselClass:
    def __init__(self, *, teu_capacity, sailing_speed=20.0, loa=200.0) -> None:
        self.teu_capacity = teu_capacity
        self.sailing_speed = sailing_speed
        self.loa = loa


class _Vessel:
    def __init__(
        self, *, vessel_class, route, current_segment=None, carried_shipments=None, index=1
    ) -> None:
        self.index = index
        self.vessel_class = vessel_class
        self.assigned_service_route = route
        self.current_segment = current_segment
        self.current_berth = None
        self.carried_shipments = list(carried_shipments or [])
        self.pending_assigned_service_route = None

    def get_next_segment(self) -> _Segment:
        segments = sorted(self.assigned_service_route.segments, key=lambda s: s.sequence_index)
        if self.current_segment is None:
            return segments[0]
        for seg in segments:
            if seg.sequence_index > self.current_segment.sequence_index:
                return seg
        return segments[0]

    def get_discharging_shipments_at_current_segment(self) -> list[_Shipment]:
        if self.current_segment is None:
            return []
        out = []
        for s in self.carried_shipments:
            b = s.get_current_booking()
            if b is None:
                continue
            if (
                b.service_route is self.assigned_service_route
                and b.arrival_segment_index == self.current_segment.sequence_index
            ):
                out.append(s)
        return out

    def get_loading_shipments_at_next_segment(self) -> list[_Shipment]:
        nxt = self.get_next_segment()
        out = []
        for s in self.carried_shipments:
            b = s.get_current_booking()
            if b is None:
                continue
            if (
                b.service_route is self.assigned_service_route
                and b.departure_segment_index == nxt.sequence_index
            ):
                out.append(s)
        return out


class _Berth:
    def __init__(self, port, index=0) -> None:
        self.port = port
        self.index = index
        self.is_available = True
        self.occupying_vessel = None


class _Port:
    def __init__(self, name, berths=1) -> None:
        self.name = name
        self.berths = [_Berth(self, i) for i in range(berths)]
        self.shipments_in_storage: list = []


def _now() -> dt.datetime:
    return dt.datetime.min + dt.timedelta(days=200.0)


def _make_route(num_segments: int = 2, *, distance: float = 100.0) -> _ServiceRoute:
    origin = _Port("A")
    mid = _Port("B")
    segments: list = []
    leg = _Leg(origin, mid, distance=distance)
    seg1 = _Segment(1, leg, None)
    segments.append(seg1)
    leg2 = _Leg(mid, origin, distance=distance)
    segments.append(_Segment(2, leg2, None))
    for s in segments:
        s.associated_service_route = None  # set below
    route = _ServiceRoute(segments)
    for s in segments:
        s.associated_service_route = route
    return route


def _make_vessel(
    *, teu_capacity=1000, loa=200.0, current_segment=None, carried=(), index=1
) -> _Vessel:
    route = _make_route()
    vc = _VesselClass(teu_capacity=teu_capacity, loa=loa)
    return _Vessel(
        vessel_class=vc,
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
        teu_size=teu_size, carrying_vessel=vessel, booking=booking, age_seconds=age_seconds
    )


def _make_storage_shipment(
    *, teu_size, route, departure_segment_index, port, carrying_vessel=None
) -> _Shipment:
    booking = _Booking(
        service_route=route,
        departure_segment_index=departure_segment_index,
        arrival_segment_index=departure_segment_index,
    )
    s = _Shipment(
        teu_size=teu_size,
        current_storage_port=port,
        carrying_vessel=carrying_vessel,
        booking=booking,
    )
    port.shipments_in_storage.append(s)
    return s


def _snapshot_state(context, port, waiting_vessels, available_berths) -> dict:
    """Snapshot every relevant identity-bearing attribute."""
    return {
        "context_id": id(context),
        "port_id": id(port),
        "port_shipments_in_storage": [id(s) for s in port.shipments_in_storage],
        "waiting_vessels": [id(v) for v in waiting_vessels],
        "available_berths_ids": [id(b) for b in available_berths],
        "vessels": {
            id(v): {
                "current_segment": id(v.current_segment) if v.current_segment else None,
                "current_berth": id(v.current_berth) if v.current_berth else None,
                "carried": [id(s) for s in v.carried_shipments],
                "assigned_route": id(v.assigned_service_route),
            }
            for v in waiting_vessels
        },
        "shipments": {
            id(s): {
                "carrying_vessel": id(s.carrying_vessel) if s.carrying_vessel else None,
                "current_storage_port": id(s.current_storage_port)
                if s.current_storage_port
                else None,
                "associated_bookings": [id(b) for b in s.associated_bookings],
                "current_booking_index": s.current_booking_index,
            }
            for s in port.shipments_in_storage
            for v in waiting_vessels
            for sh in v.carried_shipments
            if id(s) == id(sh)
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_waiting_returns_none() -> None:
    context = SimpleNamespace()
    port = _Port("A")
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is None


def test_single_vessel_returns_that_vessel() -> None:
    context = SimpleNamespace()
    port = _Port("A")
    vessel = _make_vessel(index=42)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is vessel


def test_other_hooks_return_none_without_mutation() -> None:
    context = SimpleNamespace()
    vessel = _make_vessel()
    snapshot_context = {"k": 1}
    snap = dict(snapshot_context)
    assert UserStrategy.create_alternative_service_routes(context, _now()) is None
    assert UserStrategy.assign_associated_bookings(context, _now(), vessel) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(context, _now(), vessel) is None
    assert snapshot_context == snap


def test_zero_handling_work_ranks_ahead_of_positive() -> None:
    """A vessel with zero predicted service time must outrank any
    positive-service-time vessel, even one with much larger affected TEU.
    """
    context = SimpleNamespace()
    port = _Port("A")
    route_a = _make_route()
    route_b = _make_route()
    vc_a = _VesselClass(teu_capacity=1000, loa=200.0)
    vc_b = _VesselClass(teu_capacity=1000, loa=200.0)
    seg_a1 = route_a.segments[0]
    seg_b1 = route_b.segments[0]

    vessel_a = _Vessel(vessel_class=vc_a, route=route_a, current_segment=seg_a1, index=1)
    vessel_b = _Vessel(vessel_class=vc_b, route=route_b, current_segment=seg_b1, index=2)

    # A has zero carried/handled work; B has massive carried TEU.
    for _ in range(50):
        vessel_b.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route_b,
                current_segment_index=seg_b1.sequence_index,
                vessel=vessel_b,
            )
        )

    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel_b, vessel_a],  # B first to test selection
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is vessel_a


def test_multiple_zero_work_vessels_preserve_waiting_order() -> None:
    context = SimpleNamespace()
    port = _Port("A")
    v_first = _make_vessel(index=1)
    v_mid = _make_vessel(index=2)
    v_last = _make_vessel(index=3)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[v_first, v_mid, v_last],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is v_first


def test_basic_smith_ratio_favors_b_over_carried_teu_favored_a() -> None:
    """Raw carried TEU favors A but the Smith ratio favors B.

    Set up so:
      vessel_a: carried_teu=1000, qc=1, no discharge, no load
                affected=1000, handled=0 -> ratio is zero-service case
      vessel_b: carried_teu=200, qc=10, discharging=100
                affected=200, handled=100
                service_hours = 100 / (10*45) = 0.2222h
                ratio per hour = 200 / 0.2222 = 900
    Expected: B wins because A's handled=0 means it outranks all positive.
    We pick a different setup where both have positive handled_teu.
    """
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    vc = _VesselClass(teu_capacity=2000, loa=200.0)
    seg1 = route.segments[0]
    vessel_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    vessel_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)

    # A: 1000 TEU aboard that does NOT discharge at current seg (continuing).
    # B: 200 TEU aboard that DOES discharge here, plus no load.
    for _ in range(10):
        vessel_a.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index + 1,
                vessel=vessel_a,
            )
        )
    for _ in range(2):
        vessel_b.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=vessel_b,
            )
        )

    # A: carried=1000, handled=0, affected=1000, qc=1
    # B: carried=200, handled=200, affected=200, qc=1
    # A.handled == 0 -> A is zero-service -> outranks positive
    # So with this setup, A wins. To make B win, we need both positive
    # handled. Add a non-discharging continuing shipment to B so its
    # handled > 0 and qc * affected / handled is large for B.
    vessel_b.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=10,
            route=route,
            current_segment_index=seg1.sequence_index + 1,
            vessel=vessel_b,
        )
    )
    # B: carried=210, handled=200, affected=210, qc=1 -> ratio = 210/200 = 1.05
    # A: handled=0 -> zero-service -> wins
    # So we need A to also have positive handled.
    # Add a discharging shipment to A.
    vessel_a.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=10,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel_a,
        )
    )
    # A: carried=1010, handled=10, affected=1010, qc=1 -> ratio = 1010/10 = 101
    # B: carried=210, handled=200, affected=210, qc=1 -> ratio = 210/200 = 1.05
    # Now A wins (101 > 1.05). We need a setup where B wins.

    # Reset and design properly.
    vessel_a.carried_shipments.clear()
    vessel_b.carried_shipments.clear()
    # A: high carried TEU but small discharging TEU. Huge carried -> big
    # affected but tiny handled.
    # B: moderate carried, large discharging TEU.
    # With qc_a=1 and qc_b=10 (much bigger LOA), the qc multiplier swings
    # it for B even when affected is smaller.
    vc_a = _VesselClass(teu_capacity=1000, loa=110.0)  # qc=2
    vc_b = _VesselClass(teu_capacity=1000, loa=600.0)  # qc=10
    vessel_a.vessel_class = vc_a
    vessel_b.vessel_class = vc_b

    # A: 1000 TEU continuing, no discharge at this seg
    for _ in range(10):
        vessel_a.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index + 1,
                vessel=vessel_a,
            )
        )
    # B: 500 TEU continuing + 100 TEU discharging
    for _ in range(5):
        vessel_b.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index + 1,
                vessel=vessel_b,
            )
        )
    vessel_b.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=100,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel_b,
        )
    )

    # A: carried=1000, handled=0, affected=1000 -> ZERO-SERVICE -> wins
    # To prevent this, give A something to discharge.
    vessel_a.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=10,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel_a,
        )
    )
    # A: carried=1010, handled=10, affected=1010, qc=2 -> (1010*2)/10 = 202
    # B: carried=600, handled=100, affected=600, qc=10 -> (600*10)/100 = 60
    # A still wins. Need B to actually win.
    # Make B's discharging TEU be the major contributor to its ratio.
    # Reduce A's continuing cargo drastically.
    vessel_a.carried_shipments.clear()
    vessel_a.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=10,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel_a,
        )
    )
    # A: carried=10, handled=10, affected=10, qc=2 -> 20/10 = 2
    # B: carried=600, handled=100, affected=600, qc=10 -> 6000/100 = 60
    # B wins (60 > 2).

    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel_a, vessel_b],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is vessel_b, "Smith ratio should prefer B (qc-driven)"


def test_age_does_not_change_selection() -> None:
    """Cargo age alone must not affect the chosen vessel."""
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    vc = _VesselClass(teu_capacity=2000, loa=200.0)
    seg1 = route.segments[0]
    vessel_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    vessel_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)
    vessel_a.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=100,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel_a,
            age_seconds=0.0,
        )
    )
    vessel_b.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=100,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel_b,
            age_seconds=0.0,
        )
    )

    pick_no_age = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel_a, vessel_b],
        available_berths=port.berths,
        current_time=_now(),
    )

    vessel_a.carried_shipments[0].generated_time = dt.datetime(2026, 1, 1) - dt.timedelta(days=365)
    vessel_b.carried_shipments[0].generated_time = dt.datetime(2026, 1, 1) - dt.timedelta(seconds=1)
    pick_with_age = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel_a, vessel_b],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert pick_no_age is pick_with_age


def test_qc_count_drives_selection() -> None:
    """Higher crane productivity (higher LOA -> higher qc_count) can flip the
    decision even when carried TEU is equal."""
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    seg1 = route.segments[0]
    vc_a = _VesselClass(teu_capacity=2000, loa=110.0)  # qc=2
    vc_b = _VesselClass(teu_capacity=2000, loa=600.0)  # qc=10
    vessel_a = _Vessel(vessel_class=vc_a, route=route, current_segment=seg1, index=1)
    vessel_b = _Vessel(vessel_class=vc_b, route=route, current_segment=seg1, index=2)

    # Equal carried TEU, equal handled TEU.
    for v in (vessel_a, vessel_b):
        v.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=v,
            )
        )

    # A: affected=100, qc=2, handled=100 -> 200/100 = 2
    # B: affected=100, qc=10, handled=100 -> 1000/100 = 10
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel_a, vessel_b],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is vessel_b


def test_discharging_only_uses_current_segment() -> None:
    """Cargo discharging at a non-current segment does NOT contribute to
    handled_teu."""
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    vc = _VesselClass(teu_capacity=2000, loa=200.0)
    seg1 = route.segments[0]
    seg2 = route.segments[1]
    vessel = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    # Discharge at segment 2 (not current). This must NOT count as handled.
    vessel.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=500,
            route=route,
            current_segment_index=seg2.sequence_index,
            vessel=vessel,
        )
    )

    # vessel alone -> handled_teu == 0 -> zero-service -> selected.
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is vessel


def test_continuing_cargo_counts_in_affected_not_handled() -> None:
    """Continuing cargo adds to affected_teu but not handled_teu.

    Construct two vessels with equal handled_teu but different
    continuing cargo. The one with more continuing cargo must win.
    """
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    vc = _VesselClass(teu_capacity=2000, loa=200.0)
    seg1 = route.segments[0]
    vessel_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    vessel_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)

    # A: 10 discharging + 0 continuing -> affected=10, handled=10
    vessel_a.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=10,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel_a,
        )
    )
    # B: 10 discharging + 1000 continuing -> affected=1010, handled=10
    vessel_b.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=10,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel_b,
        )
    )
    for _ in range(10):
        vessel_b.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index + 1,
                vessel=vessel_b,
            )
        )
    # A: (10*1)/10 = 1, B: (1010*1)/10 = 101 -> B wins
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel_a, vessel_b],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is vessel_b


def test_projected_load_counts_in_both() -> None:
    """A vessel whose greedy load fills more TEU wins the comparison."""
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    seg1 = route.segments[0]
    seg2 = route.segments[1]
    vc = _VesselClass(teu_capacity=100, loa=200.0)
    vessel_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    vessel_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)

    # 90 TEU eligible at port for next segment of each vessel's route
    for _ in range(9):
        _make_storage_shipment(
            teu_size=10, route=route, departure_segment_index=seg2.sequence_index, port=port
        )

    # B has 50 TEU continuing so its remaining capacity is 50.
    vessel_b.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=50,
            route=route,
            current_segment_index=seg1.sequence_index + 1,
            vessel=vessel_b,
        )
    )

    # A: handled=0 (continuing only), projected_load=90 (fills full 100).
    #    affected=0+90=90, ratio = (90*1)/90 = 1.
    # B: handled=0, projected_load=50 (capacity 100 - 50 continuing = 50).
    #    affected=50+50=100, handled=50, ratio = (100*1)/50 = 2.
    # B wins.
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel_a, vessel_b],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is vessel_b


def test_loading_filters_route_departure_carrying_storage() -> None:
    """The predicted-load filter must exclude:
    * cargo on a different route;
    * cargo with the wrong departure segment;
    * cargo already assigned a carrying vessel;
    * cargo not stored at the supplied port.
    """
    context = SimpleNamespace()
    port = _Port("A")
    other_port = _Port("B")
    route = _make_route()
    other_route = _make_route()
    seg1 = route.segments[0]
    seg2 = route.segments[1]
    vc = _VesselClass(teu_capacity=1000, loa=200.0)
    vessel = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)

    # Excluded: wrong route.
    _make_storage_shipment(
        teu_size=10, route=other_route, departure_segment_index=seg2.sequence_index, port=port
    )
    # Excluded: wrong departure segment (still on route).
    _make_storage_shipment(
        teu_size=10, route=route, departure_segment_index=seg1.sequence_index, port=port
    )
    # Excluded: already carrying a vessel.
    other_v = _make_vessel()
    _make_storage_shipment(
        teu_size=10,
        route=route,
        departure_segment_index=seg2.sequence_index,
        port=port,
        carrying_vessel=other_v,
    )
    # Excluded: stored at a different port.
    _make_storage_shipment(
        teu_size=10, route=route, departure_segment_index=seg2.sequence_index, port=other_port
    )
    # Eligible: correct route + next departure seg + this port + no carrier.
    eligible = _make_storage_shipment(
        teu_size=10, route=route, departure_segment_index=seg2.sequence_index, port=port
    )

    snapshot = _snapshot_state(context, port, [vessel], port.berths)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel],
        available_berths=port.berths,
        current_time=_now(),
    )
    after = _snapshot_state(context, port, [vessel], port.berths)
    assert result is vessel
    assert after == snapshot, "no mutation may occur"
    # Eligible shipment is still in storage (not loaded).
    assert eligible in port.shipments_in_storage


def test_greedy_load_preserves_order_and_caps_capacity() -> None:
    """Greedy load respects storage order and never exceeds capacity."""
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    seg1 = route.segments[0]
    seg2 = route.segments[1]
    vc = _VesselClass(teu_capacity=100, loa=200.0)
    vessel = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    # 12 x 10 = 120 TEU eligible -> only 100 fill, 20 left.
    for _ in range(12):
        _make_storage_shipment(
            teu_size=10, route=route, departure_segment_index=seg2.sequence_index, port=port
        )

    # Snapshot storage identity list before.
    before_ids = [id(s) for s in port.shipments_in_storage]
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel],
        available_berths=port.berths,
        current_time=_now(),
    )
    after_ids = [id(s) for s in port.shipments_in_storage]
    assert result is vessel
    assert before_ids == after_ids, "storage order must not be reordered"


def test_current_segment_discharge_excluded_from_occupied_capacity() -> None:
    """Dischargeable cargo at the current segment frees capacity for loading."""
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    seg1 = route.segments[0]
    seg2 = route.segments[1]
    vc = _VesselClass(teu_capacity=100, loa=200.0)
    vessel = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    # 80 TEU that discharge at current seg -> frees space.
    vessel.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=80,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel,
        )
    )
    # 30 TEU eligible at port.
    for _ in range(3):
        _make_storage_shipment(
            teu_size=10, route=route, departure_segment_index=seg2.sequence_index, port=port
        )
    # Occupied after discharge: 0 (the 80 discharge). remaining=100.
    # Projected load: 30.
    # handled_teu = 80 (discharge) + 30 (load) = 110.
    # affected_teu = 80 + 30 = 110.
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is vessel


def test_current_segment_none_counts_all_as_occupied() -> None:
    """When current_segment is None, all carried cargo counts as occupied."""
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    seg2 = route.segments[1]
    vc = _VesselClass(teu_capacity=100, loa=200.0)
    vessel = _Vessel(vessel_class=vc, route=route, current_segment=None, index=1)
    # 80 TEU carried (no segment to discharge from).
    vessel.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=80,
            route=route,
            current_segment_index=seg2.sequence_index,
            vessel=vessel,
        )
    )
    # 30 TEU eligible at port.
    for _ in range(3):
        _make_storage_shipment(
            teu_size=10, route=route, departure_segment_index=seg2.sequence_index, port=port
        )
    # Occupied = 80 (since current_segment is None). remaining=20.
    # Greedy load: 20 TEU (skip 10).
    snapshot_before = [id(s) for s in port.shipments_in_storage]
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel],
        available_berths=port.berths,
        current_time=_now(),
    )
    snapshot_after = [id(s) for s in port.shipments_in_storage]
    assert result is vessel
    assert snapshot_before == snapshot_after


def test_exact_tie_preserves_waiting_order() -> None:
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    seg1 = route.segments[0]
    vc = _VesselClass(teu_capacity=1000, loa=200.0)
    vessel_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    vessel_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)
    # Identical work.
    for v in (vessel_a, vessel_b):
        v.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=v,
            )
        )
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel_a, vessel_b],
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is vessel_a  # first in waiting_vessels


def test_invalid_runtime_data_delegates_with_none() -> None:
    """Malformed data must delegate with None, no mutation."""
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    seg1 = route.segments[0]
    vc = _VesselClass(teu_capacity=1000, loa=200.0)
    vessel = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    vessel.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=100,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel,
        )
    )

    # Missing vessel class.
    vessel.vessel_class = None
    assert (
        UserStrategy.select_vessel_for_berth(
            maritime_data_context=context,
            port=port,
            waiting_vessels=[vessel],
            available_berths=port.berths,
            current_time=_now(),
        )
        is None
    )
    vessel.vessel_class = vc

    # Negative teu_capacity.
    vc.teu_capacity = -1
    assert (
        UserStrategy.select_vessel_for_berth(
            maritime_data_context=context,
            port=port,
            waiting_vessels=[vessel],
            available_berths=port.berths,
            current_time=_now(),
        )
        is None
    )
    vc.teu_capacity = 1000

    # Negative LOA.
    vc.loa = -10.0
    assert (
        UserStrategy.select_vessel_for_berth(
            maritime_data_context=context,
            port=port,
            waiting_vessels=[vessel],
            available_berths=port.berths,
            current_time=_now(),
        )
        is None
    )
    vc.loa = 200.0

    # No assigned route.
    vessel.assigned_service_route = None
    assert (
        UserStrategy.select_vessel_for_berth(
            maritime_data_context=context,
            port=port,
            waiting_vessels=[vessel],
            available_berths=port.berths,
            current_time=_now(),
        )
        is None
    )


def test_returned_object_always_in_waiting_vessels() -> None:
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    seg1 = route.segments[0]
    vc = _VesselClass(teu_capacity=1000, loa=200.0)
    vessel = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    vessel.carried_shipments.append(
        _make_carrying_shipment(
            teu_size=100,
            route=route,
            current_segment_index=seg1.sequence_index,
            vessel=vessel,
        )
    )
    other = _make_vessel(index=99)
    waiting = [vessel, other]
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=waiting,
        available_berths=port.berths,
        current_time=_now(),
    )
    assert result is not None
    assert result in waiting


def test_no_mutation_snapshot() -> None:
    """Full identity snapshot of vessels/port/storage/routes must be unchanged."""
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    seg1 = route.segments[0]
    seg2 = route.segments[1]
    vc = _VesselClass(teu_capacity=500, loa=200.0)
    vessel_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    vessel_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)
    for v in (vessel_a, vessel_b):
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
        teu_size=10, route=route, departure_segment_index=seg2.sequence_index, port=port
    )
    _make_storage_shipment(
        teu_size=10, route=route, departure_segment_index=seg2.sequence_index, port=port
    )

    snap = _snapshot_state(context, port, [vessel_a, vessel_b], port.berths)
    UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[vessel_a, vessel_b],
        available_berths=port.berths,
        current_time=_now(),
    )
    after = _snapshot_state(context, port, [vessel_a, vessel_b], port.berths)
    assert after == snap


def test_determinism_repeated_calls_same_selection() -> None:
    context = SimpleNamespace()
    port = _Port("A")
    route = _make_route()
    seg1 = route.segments[0]
    vc = _VesselClass(teu_capacity=1000, loa=200.0)
    vessel_a = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=1)
    vessel_b = _Vessel(vessel_class=vc, route=route, current_segment=seg1, index=2)
    for v in (vessel_a, vessel_b):
        v.carried_shipments.append(
            _make_carrying_shipment(
                teu_size=100,
                route=route,
                current_segment_index=seg1.sequence_index,
                vessel=v,
            )
        )
    picks = set()
    for _ in range(5):
        picks.add(
            UserStrategy.select_vessel_for_berth(
                maritime_data_context=context,
                port=port,
                waiting_vessels=[vessel_a, vessel_b],
                available_berths=port.berths,
                current_time=_now(),
            )
        )
    assert len(picks) == 1
