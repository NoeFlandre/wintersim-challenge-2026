"""RED/contract tests for the exposed-cargo berth experiment."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from response_strategies.user_strategy import UserStrategy


@dataclass
class Port:
    name: str


@dataclass
class Leg:
    departure_port: Port
    arrival_port: Port


@dataclass
class Segment:
    associated_leg: Leg


@dataclass
class Route:
    segments: list[Segment]


@dataclass
class Booking:
    service_route: Route


@dataclass
class Shipment:
    teu_size: int
    associated_bookings: list[Booking]


@dataclass(eq=False)
class Vessel:
    carried_shipments: list[Shipment] = field(default_factory=list)


@dataclass
class Berth:
    port: Port


@dataclass
class Plan:
    start_offset_days: float
    duration_days: float
    target_leg: Leg | None = None
    target_berth: Berth | None = None


@dataclass
class Context:
    disruption_plans: list[Plan]


def _clock(day: float) -> datetime:
    return datetime.min + timedelta(days=day)


def _network() -> tuple[Port, Port, Port, Leg, Leg]:
    origin = Port("origin")
    exposed = Port("exposed")
    safe = Port("safe")
    exposed_leg = Leg(origin, exposed)
    safe_leg = Leg(origin, safe)
    return origin, exposed, safe, exposed_leg, safe_leg


def _vessel(teu: int, leg: Leg) -> Vessel:
    route = Route([Segment(leg)])
    return Vessel([Shipment(teu, [Booking(route)])])


def _call(context: Context, waiting: list[Vessel], now: datetime, since: dict) -> object:
    return UserStrategy.select_vessel_for_berth(
        context,
        object(),
        waiting,
        [object()],
        now,
        since,
    )


def test_active_congestion_prioritizes_oldest_exposed_teu() -> None:
    _, _, _, exposed_leg, safe_leg = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    exposed_vessel = _vessel(20, exposed_leg)
    safe_vessel = _vessel(100, safe_leg)
    now = _clock(11.0)

    result = _call(
        context,
        [safe_vessel, exposed_vessel],
        now,
        {safe_vessel: _clock(10.5), exposed_vessel: _clock(10.0)},
    )

    assert result is exposed_vessel


def test_closed_port_exposure_is_detected() -> None:
    _, exposed, _, _, safe_leg = _network()
    context = Context(
        [Plan(10.0, 3.0, target_berth=Berth(exposed))],
    )
    exposed_vessel = _vessel(5, Leg(Port("elsewhere"), exposed))
    safe_vessel = _vessel(80, safe_leg)
    now = _clock(11.0)

    assert (
        _call(
            context,
            [safe_vessel, exposed_vessel],
            now,
            {safe_vessel: _clock(10.5), exposed_vessel: _clock(10.0)},
        )
        is exposed_vessel
    )


def test_inactive_or_unexposed_queue_delegates() -> None:
    _, _, _, exposed_leg, safe_leg = _network()
    context = Context([Plan(10.0, 1.0, target_leg=exposed_leg)])
    waiting = [_vessel(20, exposed_leg), _vessel(100, safe_leg)]
    now = _clock(12.0)

    assert _call(context, waiting, now, {}) is None


def test_exact_score_tie_delegates_to_fallback() -> None:
    _, _, _, exposed_leg, safe_leg = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    first = _vessel(20, exposed_leg)
    second = _vessel(10, exposed_leg)
    now = _clock(11.0)

    assert (
        _call(
            context,
            [first, second],
            now,
            {first: _clock(10.0), second: _clock(9.0)},
        )
        is None
    )


def test_missing_wait_entries_use_current_time_and_delegate_when_zero() -> None:
    _, _, _, exposed_leg, safe_leg = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    waiting = [_vessel(20, exposed_leg), _vessel(100, safe_leg)]
    now = _clock(11.0)

    assert _call(context, waiting, now, {}) is None


def test_malformed_disruption_fails_closed_without_mutation() -> None:
    _, _, _, exposed_leg, _ = _network()
    context = Context([Plan(10.0, 3.0, target_leg=None)])
    waiting = [_vessel(20, exposed_leg)]
    snapshot = list(waiting)

    assert _call(context, waiting, _clock(11.0), {}) is None
    assert waiting == snapshot


def test_malformed_waiting_timestamp_delegates() -> None:
    _, _, _, exposed_leg, _ = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    waiting = [_vessel(20, exposed_leg)]

    assert _call(context, waiting, _clock(11.0), {waiting[0]: "not-a-time"}) is None


def test_malformed_booking_sequence_delegates() -> None:
    _, _, _, exposed_leg, _ = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    vessel = _vessel(20, exposed_leg)
    vessel.carried_shipments[0].current_booking_index = 1
    vessel.carried_shipments[0].associated_bookings[0].sequence_index = "bad"

    assert _call(context, [vessel], _clock(11.0), {}) is None


def test_exposure_inspection_does_not_mutate_runtime_objects() -> None:
    _, _, _, exposed_leg, safe_leg = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    waiting = [_vessel(20, exposed_leg), _vessel(10, safe_leg)]
    before = [list(vessel.carried_shipments) for vessel in waiting]

    _call(context, waiting, _clock(11.0), {waiting[0]: _clock(10.0)})

    assert [vessel.carried_shipments for vessel in waiting] == before


@pytest.mark.parametrize(
    ("start", "duration"),
    [
        (True, 1.0),
        (-1.0, 1.0),
        (float("nan"), 1.0),
        (10.0, False),
        (10.0, 0.0),
        (10.0, float("nan")),
    ],
)
def test_invalid_plan_timing_fails_closed(start: object, duration: object) -> None:
    _, _, _, exposed_leg, _ = _network()
    plan = Plan(start, duration, target_leg=exposed_leg)  # type: ignore[arg-type]
    assert _call(Context([plan]), [_vessel(1, exposed_leg)], _clock(11.0), {}) is None


def test_invalid_plan_shape_and_targets_fail_closed() -> None:
    _, _, _, exposed_leg, _ = _network()
    waiting = [_vessel(1, exposed_leg)]
    malformed = [
        SimpleNamespace(start_offset_days=10.0, duration_days=1.0),
        SimpleNamespace(
            start_offset_days=10.0,
            duration_days=1.0,
            target_leg=exposed_leg,
            target_berth=Berth(Port("both")),
        ),
        SimpleNamespace(
            start_offset_days=10.0,
            duration_days=1.0,
            target_leg=SimpleNamespace(departure_port=None, arrival_port=Port("x")),
        ),
        SimpleNamespace(
            start_offset_days=10.0,
            duration_days=1.0,
            target_berth=SimpleNamespace(port=None),
        ),
    ]
    for plan in malformed:
        assert _call(Context([plan]), waiting, _clock(11.0), {}) is None


def test_missing_context_plan_container_and_bad_waiting_input_delegate() -> None:
    _, _, _, exposed_leg, _ = _network()
    vessel = _vessel(1, exposed_leg)
    assert _call(SimpleNamespace(), [vessel], _clock(11.0), {}) is None
    assert _call(SimpleNamespace(disruption_plans=1), [vessel], _clock(11.0), {}) is None
    assert (
        UserStrategy.select_vessel_for_berth(Context([]), object(), None, [], _clock(11.0), {})
        is None
    )
    assert (
        UserStrategy.select_vessel_for_berth(Context([]), object(), [], [], _clock(11.0), {})
        is None
    )
    assert UserStrategy.select_vessel_for_berth(Context([]), object(), [vessel], [], 0, {}) is None


def test_plan_overflow_and_target_deduplication_delegate_or_continue() -> None:
    _, _, _, exposed_leg, _ = _network()
    waiting = [_vessel(1, exposed_leg), _vessel(2, exposed_leg)]
    overflow = Plan(1e300, 1.0, target_leg=exposed_leg)
    assert _call(Context([overflow]), waiting, _clock(11.0), {}) is None
    duplicate_plans = [
        Plan(10.0, 3.0, target_leg=exposed_leg),
        Plan(10.0, 3.0, target_leg=exposed_leg),
    ]
    result = _call(
        Context(duplicate_plans),
        waiting,
        _clock(11.0),
        {waiting[0]: _clock(10.0)},
    )
    assert result is waiting[0]


def test_route_and_booking_shape_errors_delegate() -> None:
    _, _, _, exposed_leg, _ = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    malformed_routes = [
        None,
        SimpleNamespace(segments=None),
        SimpleNamespace(segments=[]),
        SimpleNamespace(segments=1),
        SimpleNamespace(segments=[SimpleNamespace(sequence_index="bad")]),
    ]
    for route in malformed_routes:
        shipment = SimpleNamespace(
            teu_size=1,
            associated_bookings=[SimpleNamespace(service_route=route)],
        )
        vessel = SimpleNamespace(carried_shipments=[shipment])
        assert _call(context, [vessel], _clock(11.0), {}) is None


def test_missing_segment_indices_use_full_route_and_bad_indices_delegate() -> None:
    _, _, _, exposed_leg, safe_leg = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    route = Route([Segment(exposed_leg), Segment(safe_leg)])
    full_route_booking = SimpleNamespace(service_route=route)
    full_route_shipment = SimpleNamespace(
        teu_size=5,
        associated_bookings=[full_route_booking],
    )
    full_route_vessel = SimpleNamespace(carried_shipments=[full_route_shipment])
    assert _call(context, [full_route_vessel], _clock(11.0), {}) is None

    bad_indices = SimpleNamespace(
        service_route=route,
        departure_segment_index=99,
        arrival_segment_index=1,
    )
    bad_shipment = SimpleNamespace(teu_size=5, associated_bookings=[bad_indices])
    assert (
        _call(context, [SimpleNamespace(carried_shipments=[bad_shipment])], _clock(11.0), {})
        is None
    )


def test_cyclic_booking_slice_and_past_booking_are_safe() -> None:
    _, _, _, exposed_leg, safe_leg = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    route = Route([Segment(safe_leg), Segment(exposed_leg)])
    past = SimpleNamespace(
        sequence_index=1,
        service_route=route,
        departure_segment_index=1,
        arrival_segment_index=1,
    )
    current = SimpleNamespace(
        sequence_index=2,
        service_route=route,
        departure_segment_index=2,
        arrival_segment_index=1,
    )
    shipment = SimpleNamespace(
        teu_size=5,
        current_booking_index=2,
        associated_bookings=[past, current],
    )
    vessel = SimpleNamespace(carried_shipments=[shipment])
    assert _call(context, [vessel], _clock(11.0), {}) is None


@pytest.mark.parametrize("teu", [True, -1, float("nan"), "10"])
def test_invalid_teu_fails_closed(teu: object) -> None:
    _, _, _, exposed_leg, _ = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    shipment = SimpleNamespace(teu_size=teu, associated_bookings=[])
    vessel = SimpleNamespace(carried_shipments=[shipment])
    assert _call(context, [vessel], _clock(11.0), {}) is None


def test_malformed_shipment_collection_and_segment_ports_delegate() -> None:
    _, _, _, exposed_leg, _ = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    for shipments in (None, 1):
        assert (
            _call(context, [SimpleNamespace(carried_shipments=shipments)], _clock(11.0), {}) is None
        )
    for bookings in (None, 1):
        shipment = SimpleNamespace(teu_size=1, associated_bookings=bookings)
        assert (
            _call(context, [SimpleNamespace(carried_shipments=[shipment])], _clock(11.0), {})
            is None
        )
    for leg in (None, SimpleNamespace(departure_port=None, arrival_port=Port("x"))):
        segment = SimpleNamespace(sequence_index=1, associated_leg=leg)
        booking = SimpleNamespace(
            service_route=SimpleNamespace(segments=[segment]),
        )
        shipment = SimpleNamespace(teu_size=1, associated_bookings=[booking])
        assert (
            _call(context, [SimpleNamespace(carried_shipments=[shipment])], _clock(11.0), {})
            is None
        )


def test_waiting_map_and_datetime_arithmetic_fail_closed() -> None:
    _, _, _, exposed_leg, _ = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    vessel = _vessel(1, exposed_leg)
    for waiting_map in (object(), {vessel: None}):
        assert _call(context, [vessel], _clock(11.0), waiting_map) is None
    aware_time = datetime(2026, 1, 1, tzinfo=UTC)
    assert _call(context, [vessel], _clock(11.0), {vessel: aware_time}) is None
