"""Contract tests for the participant-owned UserStrategy adapter.

These tests pin the public surface that the organizer framework calls:

* The class is exactly named ``UserStrategy``.
* The four required static methods exist with the exact names and a compatible
  argument signature (the organizer's documented parameter names must be
  accepted positionally or by keyword).
* Each method is static and callable without instantiation.
* For this baseline milestone every method returns ``None`` (delegating to the
  organizer fallback) and never mutates any of its arguments, even sentinel
  mutable inputs.

The tests use only sentinel objects defined here; they never import organizer
source.
"""

from __future__ import annotations

import datetime as dt
import inspect
import sys
import types

import pytest
from response_strategies.user_strategy import UserStrategy

REQUIRED_METHODS: dict[str, list[str]] = {
    "select_vessel_for_berth": [
        "maritime_data_context",
        "port",
        "waiting_vessels",
        "available_berths",
        "current_time",
        "waiting_since_by_vessel",
    ],
    "create_alternative_service_routes": ["context", "now", "vessel"],
    "assign_associated_bookings": ["context", "now", "shipment"],
    "adjust_bookings_before_cargo_handling": ["context", "now", "vessel"],
}


def test_class_is_named_user_strategy() -> None:
    assert UserStrategy.__name__ == "UserStrategy"


@pytest.mark.parametrize("method_name,expected_params", list(REQUIRED_METHODS.items()))
def test_required_static_methods_have_compatible_signature(
    method_name: str, expected_params: list[str]
) -> None:
    method = getattr(UserStrategy, method_name, None)
    assert method is not None, f"UserStrategy missing required method {method_name}"
    assert isinstance(inspect.getattr_static(UserStrategy, method_name), staticmethod), (
        f"UserStrategy.{method_name} must be a staticmethod"
    )

    sig = inspect.signature(method)
    params = list(sig.parameters)
    # The organizer call sites pass these positionally; the participant method
    # must accept at least the documented parameter names in order.
    assert params == expected_params, (
        f"UserStrategy.{method_name} signature {params} != expected {expected_params}"
    )


def test_select_vessel_for_berth_returns_none_and_does_not_mutate() -> None:
    waiting = ["vessel_a", "vessel_b"]
    berths = ["berth_1"]
    snapshot = list(waiting)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=berths,
        current_time=0,
        waiting_since_by_vessel={"vessel_a": 0},
    )
    assert result is None
    assert waiting == snapshot, "must not mutate waiting_vessels"
    assert berths == ["berth_1"], "must not mutate available_berths"


def test_create_alternative_service_routes_returns_none_and_leaves_context_unchanged() -> None:
    context = {"routes": [1, 2, 3], "vessels": ["x"]}
    snapshot = {"routes": list(context["routes"]), "vessels": list(context["vessels"])}
    result = UserStrategy.create_alternative_service_routes(context, now=5, vessel="x")
    assert result is None
    assert context == snapshot, "None result must leave context unchanged"


def test_assign_associated_bookings_returns_none() -> None:
    result = UserStrategy.assign_associated_bookings(context={"k": 1}, now=10, shipment=object())
    assert result is None


class _Port:
    def __init__(self, name: str) -> None:
        self.name = name


class _Leg:
    def __init__(self, departure_port: _Port, arrival_port: _Port, distance: float) -> None:
        self.departure_port = departure_port
        self.arrival_port = arrival_port
        self.sailing_distance = distance
        self.sailing_time_multiplier = 1.0


class _Segment:
    def __init__(self, sequence_index: int, leg: _Leg) -> None:
        self.sequence_index = sequence_index
        self.associated_leg = leg


class _VesselClass:
    def __init__(self, sailing_speed: float = 20.0) -> None:
        self.sailing_speed = sailing_speed


class _Vessel:
    def __init__(self, sailing_speed: float = 20.0) -> None:
        self.vessel_class = _VesselClass(sailing_speed)


class _Route:
    def __init__(
        self,
        route_id: str,
        ports_and_distances: list[tuple[_Port, _Port, float]],
        sailing_speed: float = 20.0,
    ) -> None:
        self.id = route_id
        self.source_service_route = None
        self.segments = [
            _Segment(index, _Leg(departure, arrival, distance))
            for index, (departure, arrival, distance) in enumerate(ports_and_distances, start=1)
        ]
        self.deployed_vessels = [_Vessel(sailing_speed)]
        self.associated_bookings: list[object] = []


class _Booking:
    def __init__(
        self,
        sequence_index: int,
        shipment: object,
        service_route: _Route,
        departure_segment_index: int,
        arrival_segment_index: int,
    ) -> None:
        self.sequence_index = sequence_index
        self.shipment = shipment
        self.service_route = service_route
        self.departure_segment_index = departure_segment_index
        self.arrival_segment_index = arrival_segment_index


def _install_fake_booking_module(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("maritime_data_context")
    module.Booking = _Booking  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "maritime_data_context", module)


def _routing_fixture() -> tuple[object, object, _Route, _Route, _Route]:
    a, b, c = _Port("A"), _Port("B"), _Port("C")
    first = _Route("first", [(a, b, 1_000.0), (b, a, 1_000.0)])
    second = _Route("second", [(b, c, 1_000.0), (c, b, 1_000.0)])
    direct = _Route("direct", [(a, c, 2_500.0), (c, a, 2_500.0)])
    context = types.SimpleNamespace(
        ports=[a, b, c],
        service_routes=[first, second, direct],
        disruption_plans=[],
    )
    shipment = types.SimpleNamespace(
        demand=types.SimpleNamespace(origin_port=a, destination_port=c),
        associated_bookings=[],
        current_booking_index=None,
    )
    return context, shipment, first, second, direct


def test_booking_strategy_avoids_a_transfer_when_its_expected_wait_exceeds_detour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_booking_module(monkeypatch)
    context, shipment, first, second, direct = _routing_fixture()

    result = UserStrategy.assign_associated_bookings(
        context,
        now=dt.datetime.min + dt.timedelta(days=10),
        shipment=shipment,
    )

    assert result is True
    assert [booking.service_route for booking in shipment.associated_bookings] == [direct]
    assert shipment.current_booking_index == 1
    assert direct.associated_bookings == shipment.associated_bookings
    assert first.associated_bookings == []
    assert second.associated_bookings == []


def test_booking_strategy_delegates_during_active_disruption_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_booking_module(monkeypatch)
    context, shipment, _first, _second, _direct = _routing_fixture()
    context.disruption_plans = [types.SimpleNamespace(start_offset_days=5.0, duration_days=10.0)]
    original_bookings = list(shipment.associated_bookings)

    result = UserStrategy.assign_associated_bookings(
        context,
        now=dt.datetime.min + dt.timedelta(days=10),
        shipment=shipment,
    )

    assert result is None
    assert shipment.associated_bookings == original_bookings


def test_booking_strategy_accounts_for_route_speed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_booking_module(monkeypatch)
    context, shipment, first, second, direct = _routing_fixture()
    direct.deployed_vessels[0].vessel_class.sailing_speed = 10.0

    result = UserStrategy.assign_associated_bookings(
        context,
        now=dt.datetime.min + dt.timedelta(days=10),
        shipment=shipment,
    )

    assert result is True
    assert [booking.service_route for booking in shipment.associated_bookings] == [
        first,
        second,
    ]


def test_booking_strategy_completes_same_port_demand_and_removes_stale_booking() -> None:
    context, shipment, _first, _second, direct = _routing_fixture()
    stale_booking = types.SimpleNamespace(service_route=direct)
    direct.associated_bookings.append(stale_booking)
    shipment.associated_bookings.append(stale_booking)
    shipment.current_booking_index = 1
    shipment.demand.destination_port = shipment.demand.origin_port

    result = UserStrategy.assign_associated_bookings(
        context,
        now=dt.datetime.min + dt.timedelta(days=10),
        shipment=shipment,
    )

    assert result is True
    assert shipment.associated_bookings == []
    assert shipment.current_booking_index is None
    assert direct.associated_bookings == []


def test_booking_strategy_delegates_when_no_route_is_available() -> None:
    context, shipment, first, second, direct = _routing_fixture()
    for route in (first, second, direct):
        route.deployed_vessels = []

    result = UserStrategy.assign_associated_bookings(
        context,
        now=dt.datetime.min + dt.timedelta(days=10),
        shipment=shipment,
    )

    assert result is None
    assert shipment.associated_bookings == []


def test_adjust_bookings_before_cargo_handling_returns_none() -> None:
    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context={"k": 1}, now=10, vessel=object()
    )
    assert result is None


def test_all_methods_static_callable_via_class() -> None:
    # Every required method must be callable on the class without an instance.
    for name in REQUIRED_METHODS:
        method = getattr(UserStrategy, name)
        assert callable(method)
        # Binding check: a staticmethod accessed on the class must not require
        # a 'self' argument (it has no 'self' parameter).
        sig = inspect.signature(method)
        assert "self" not in sig.parameters, f"{name} must not be an instance method"


def test_module_does_not_import_development_tooling() -> None:
    # The submission must not depend on our dev CLI package.
    import response_strategies.user_strategy as mod

    src = inspect.getsource(mod)
    assert "wsc2026_tools" not in src
