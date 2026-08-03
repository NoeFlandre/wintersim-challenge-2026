"""RED contract tests for deferred in-transit rebooking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

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
class Route:
    segments: list[Segment] = field(default_factory=list)


@dataclass
class Segment:
    sequence_index: int
    associated_leg: Leg
    associated_service_route: Route


@dataclass
class Berth:
    port: Port


@dataclass
class Plan:
    target_leg: Leg | None = None
    target_berth: Berth | None = None
    start_offset_days: float | None = 10.0
    duration_days: float | None = 5.0
    multiplier: float = 1.0
    close_berth: bool = False


@dataclass
class Booking:
    sequence_index: int
    service_route: Route
    departure_segment_index: int
    arrival_segment_index: int


@dataclass
class Shipment:
    associated_bookings: list[Booking]
    current_booking_index: int = 1

    def get_current_booking(self) -> Booking:
        return next(
            booking
            for booking in self.associated_bookings
            if booking.sequence_index == self.current_booking_index
        )


@dataclass
class Vessel:
    current_segment: Segment | None
    carried_shipments: list[Shipment]


@dataclass
class Context:
    disruption_plans: list[Plan]


def _context() -> tuple[Context, Vessel, dict[str, object]]:
    ports = [Port(name) for name in ("A", "B", "C", "D")]
    legs = [
        Leg(ports[0], ports[1]),
        Leg(ports[1], ports[2]),
        Leg(ports[2], ports[3]),
        Leg(ports[3], ports[0]),
    ]
    route = Route()
    route.segments = [Segment(i + 1, leg, route) for i, leg in enumerate(legs)]
    shipment = Shipment([Booking(1, route, 1, 3)])
    vessel = Vessel(route.segments[0], [shipment])
    plan = Plan(target_leg=legs[2], multiplier=3.0)
    context = Context([plan])
    snapshot = {
        "segments": tuple(route.segments),
        "bookings": tuple(shipment.associated_bookings),
        "current_segment": vessel.current_segment,
        "carried": tuple(vessel.carried_shipments),
        "plans": tuple(context.disruption_plans),
    }
    return context, vessel, snapshot


def _active_time() -> datetime:
    return datetime.min + timedelta(days=12)


def _assert_unchanged(vessel: Vessel, context: Context, snapshot: dict[str, object]) -> None:
    shipment = vessel.carried_shipments[0]
    assert tuple(vessel.current_segment.associated_service_route.segments) == snapshot[
        "segments"
    ]
    assert tuple(shipment.associated_bookings) == snapshot["bookings"]
    assert vessel.current_segment is snapshot["current_segment"]
    assert tuple(vessel.carried_shipments) == snapshot["carried"]
    assert tuple(context.disruption_plans) == snapshot["plans"]


def test_future_only_active_impact_is_deferred_without_mutation() -> None:
    context, vessel, snapshot = _context()

    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context, _active_time(), vessel
    )

    assert result is False
    _assert_unchanged(vessel, context, snapshot)


def test_directly_affected_current_segment_delegates_to_fallback() -> None:
    context, vessel, snapshot = _context()
    context.disruption_plans[0].target_leg = vessel.current_segment.associated_leg

    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context, _active_time(), vessel
    )

    assert result is None
    _assert_unchanged(vessel, context, snapshot)


def test_future_only_later_booking_is_deferred() -> None:
    context, vessel, snapshot = _context()
    route = vessel.current_segment.associated_service_route
    shipment = vessel.carried_shipments[0]
    shipment.associated_bookings = [
        Booking(1, route, 1, 1),
        Booking(2, route, 2, 3),
    ]
    context.disruption_plans[0].target_leg = route.segments[2].associated_leg

    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context, _active_time(), vessel
    )

    assert result is False
    assert shipment.current_booking_index == 1
    assert tuple(vessel.current_segment.associated_service_route.segments) == snapshot[
        "segments"
    ]


def test_inactive_impact_delegates() -> None:
    context, vessel, snapshot = _context()

    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context, datetime.min + timedelta(days=20), vessel
    )

    assert result is None
    _assert_unchanged(vessel, context, snapshot)


def test_no_impact_delegates() -> None:
    context, vessel, snapshot = _context()
    context.disruption_plans[0].target_leg = vessel.current_segment.associated_leg
    context.disruption_plans[0].start_offset_days = 100.0

    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context, _active_time(), vessel
    )

    assert result is None
    _assert_unchanged(vessel, context, snapshot)


def test_closed_current_port_delegates() -> None:
    context, vessel, snapshot = _context()
    context.disruption_plans = [
        Plan(target_berth=Berth(vessel.current_segment.associated_leg.arrival_port), close_berth=True)
    ]
    snapshot["plans"] = tuple(context.disruption_plans)

    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context, _active_time(), vessel
    )

    assert result is None
    _assert_unchanged(vessel, context, snapshot)


def test_mixed_direct_and_future_impact_delegates() -> None:
    context, vessel, snapshot = _context()
    route = vessel.current_segment.associated_service_route
    second = Shipment([Booking(1, route, 1, 3)])
    second.current_booking_index = 1
    vessel.carried_shipments.append(second)
    context.disruption_plans.append(Plan(target_leg=vessel.current_segment.associated_leg, multiplier=2.0))
    snapshot["carried"] = tuple(vessel.carried_shipments)
    snapshot["plans"] = tuple(context.disruption_plans)

    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context, _active_time(), vessel
    )

    assert result is None
    _assert_unchanged(vessel, context, snapshot)


@pytest.mark.parametrize("bad_now", [None, "not-a-datetime"])
def test_invalid_clock_delegates(bad_now: object) -> None:
    context, vessel, snapshot = _context()

    result = UserStrategy.adjust_bookings_before_cargo_handling(context, bad_now, vessel)

    assert result is None
    _assert_unchanged(vessel, context, snapshot)


def test_missing_current_segment_delegates() -> None:
    context, vessel, _ = _context()
    vessel.current_segment = None

    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context, _active_time(), vessel
    )

    assert result is None
