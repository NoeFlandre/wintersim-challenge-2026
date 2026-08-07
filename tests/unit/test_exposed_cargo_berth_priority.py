"""RED/contract tests for the exposed-cargo berth experiment."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

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

    assert _call(
        context,
        [safe_vessel, exposed_vessel],
        now,
        {safe_vessel: _clock(10.5), exposed_vessel: _clock(10.0)},
    ) is exposed_vessel


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

    assert _call(
        context,
        [first, second],
        now,
        {first: _clock(10.0), second: _clock(9.0)},
    ) is None


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


def test_exposure_inspection_does_not_mutate_runtime_objects() -> None:
    _, _, _, exposed_leg, safe_leg = _network()
    context = Context([Plan(10.0, 3.0, target_leg=exposed_leg)])
    waiting = [_vessel(20, exposed_leg), _vessel(10, safe_leg)]
    before = [list(vessel.carried_shipments) for vessel in waiting]

    _call(context, waiting, _clock(11.0), {waiting[0]: _clock(10.0)})

    assert [vessel.carried_shipments for vessel in waiting] == before
