"""Targeted coverage tests for the recovery-hold-vs-detour candidate.

These tests cover narrow branches in the implementation that the contract
tests do not exercise directly: invalid numeric inputs, edge-case vessel
selection, edge enumeration short-circuits, pathfind no-result paths, and
plan intersection branches.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import math
from pathlib import Path

import pytest

from tests.unit._helpers_recovery_hold import (  # type: ignore[import-not-found]
    FakeContext,
    make_demand,
    make_disruption_plan,
    make_leg,
    make_port,
    make_route,
    make_segment,
    make_shipment,
    make_vessel,
    make_vessel_class,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
USER_STRATEGY_FILE = REPO_ROOT / "submission" / "response_strategies" / "user_strategy.py"


def _load_strategy() -> object:
    spec = importlib.util.spec_from_file_location(
        "wsc_participant_user_strategy_cov", str(USER_STRATEGY_FILE)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def strategy_module() -> object:
    return _load_strategy()


# --- _is_finite_positive / _as_finite_positive branches -------------------


def test_is_finite_positive_rejects_bool(strategy_module: object) -> None:
    assert strategy_module._is_finite_positive(True) is False
    assert strategy_module._is_finite_positive(False) is False


def test_is_finite_positive_rejects_non_numeric(strategy_module: object) -> None:
    assert strategy_module._is_finite_positive(None) is False
    assert strategy_module._is_finite_positive("1.0") is False
    assert strategy_module._is_finite_positive([1.0]) is False
    assert strategy_module._is_finite_positive(math.inf) is False
    assert strategy_module._is_finite_positive(-1.0) is False
    assert strategy_module._is_finite_positive(0.0) is False
    assert strategy_module._is_finite_positive(float("nan")) is False


def test_is_finite_nonnegative_rejects_bool(strategy_module: object) -> None:
    assert strategy_module._is_finite_nonnegative(True) is False


def test_as_finite_positive_returns_none_on_invalid(strategy_module: object) -> None:
    assert strategy_module._as_finite_positive(None) is None
    assert strategy_module._as_finite_positive("a") is None
    assert strategy_module._as_finite_positive(-1.0) is None


def test_as_finite_nonnegative_returns_none_on_invalid(strategy_module: object) -> None:
    assert strategy_module._as_finite_nonnegative(None) is None


# --- Route speed fallback to current_vessels ------------------------------


def test_route_speed_falls_back_to_current_vessels(strategy_module: object) -> None:
    """If no deployed vessels, current_vessels on segments are used."""
    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    leg_ba = make_leg(b, a, 100.0)
    route = make_route("R1")
    seg1 = make_segment(1, leg_ab, route)
    make_segment(2, leg_ba, route)
    # Vessel not in deployed_vessels but in segment current_vessels.
    vc = make_vessel_class("VC", teu_capacity=1000, sailing_speed=12.5)
    vessel = make_vessel(99, vc, make_route("OTHER"))
    seg1.current_vessels.append(vessel)
    speeds = strategy_module._route_eligible_speeds(route)
    assert speeds == [12.5]


# --- Cycle distance and headway error branches -----------------------------


def test_cycle_distance_invalid_segment(strategy_module: object) -> None:
    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    route = make_route("R1")
    make_segment(1, leg_ab, route)
    # Set distance to invalid
    leg_ab.sailing_distance = -1.0
    assert strategy_module._route_cycle_distance(route) == math.inf


def test_cycle_distance_no_segments(strategy_module: object) -> None:
    route = make_route("R1")
    assert strategy_module._route_cycle_distance(route) == 0.0


def test_headway_invalid_cycle_distance(strategy_module: object) -> None:
    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    route = make_route("R1")
    make_segment(1, leg_ab, route)
    vc = make_vessel_class("VC", teu_capacity=1000, sailing_speed=10.0)
    make_vessel(1, vc, route)
    assert strategy_module._route_headway_hours(route, 0.0) == math.inf
    assert strategy_module._route_headway_hours(route, -1.0) == math.inf


def test_headway_invalid_speed_sum(strategy_module: object) -> None:
    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    route = make_route("R1")
    make_segment(1, leg_ab, route)
    vc = make_vessel_class("VC", teu_capacity=1000, sailing_speed=0.0)
    make_vessel(1, vc, route)
    assert strategy_module._route_headway_hours(route, 100.0) == math.inf


def test_mean_speed_empty(strategy_module: object) -> None:
    route = make_route("R1")
    assert strategy_module._route_mean_speed(route) == math.inf


# --- Route availability predicate branches --------------------------------


def test_route_is_available_no_deployed(strategy_module: object) -> None:
    """An alternative route without deployed vessels is unavailable."""
    route = make_route("R2")
    route.source_service_route = make_route("R1")
    route.disruption_key = (("a",), ())
    assert strategy_module._route_is_available_for_booking(route, (("a",), ())) is False


def test_route_is_available_mismatched_key(strategy_module: object) -> None:
    route = make_route("R2")
    route.source_service_route = make_route("R1")
    route.disruption_key = (("a",), ())
    vc = make_vessel_class("VC", teu_capacity=1000, sailing_speed=10.0)
    make_vessel(1, vc, route)
    assert strategy_module._route_is_available_for_booking(route, (("b",), ())) is False


def test_route_is_available_matching(strategy_module: object) -> None:
    route = make_route("R2")
    route.source_service_route = make_route("R1")
    route.disruption_key = (("a",), ())
    vc = make_vessel_class("VC", teu_capacity=1000, sailing_speed=10.0)
    make_vessel(1, vc, route)
    assert strategy_module._route_is_available_for_booking(route, (("a",), ())) is True


# --- Edge enumeration branches -------------------------------------------


def test_route_edges_nominal_no_segments(strategy_module: object) -> None:
    route = make_route("R1")
    assert strategy_module._route_edges_for_nominal(route) == []


def test_route_edges_nominal_skip_alternative(strategy_module: object) -> None:
    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    leg_ba = make_leg(b, a, 100.0)
    route = make_route("R1")
    route.source_service_route = make_route("SOURCE")
    make_segment(1, leg_ab, route)
    make_segment(2, leg_ba, route)
    assert strategy_module._route_edges_for_nominal(route) == []


def test_route_edges_safe_unavailable(strategy_module: object) -> None:
    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    leg_ba = make_leg(b, a, 100.0)
    route = make_route("R1")
    make_segment(1, leg_ab, route)
    make_segment(2, leg_ba, route)
    # No source_service_route -> original. Returns edges.
    # Empty avoid/congested sets.
    edges = strategy_module._route_edges_for_safe(route, set(), set(), ((), ()))
    assert len(edges) > 0


def test_route_edges_safe_no_segments(strategy_module: object) -> None:
    route = make_route("R1")
    assert strategy_module._route_edges_for_safe(route, set(), set(), ((), ())) == []


# --- _pathfind no-result / edge cases ------------------------------------


def test_pathfind_no_edges(strategy_module: object) -> None:
    a = make_port("A")
    b = make_port("B")
    context = FakeContext(ports=[a, b], service_routes=[], legs=[], vessels=[])
    assert strategy_module._pathfind(context, [], a, b) == []


def test_pathfind_origin_eq_destination(strategy_module: object) -> None:
    a = make_port("A")
    context = FakeContext(ports=[a], service_routes=[], legs=[], vessels=[])
    assert strategy_module._pathfind(context, [], a, a) == []


def test_pathfind_no_ports(strategy_module: object) -> None:
    a = make_port("A")
    b = make_port("B")
    context = FakeContext(ports=[], service_routes=[], legs=[], vessels=[])
    assert strategy_module._pathfind(context, [], a, b) == []


def test_pathfind_no_predecessor(strategy_module: object) -> None:
    """When no path exists, returns empty list."""
    a = make_port("A")
    b = make_port("B")
    c = make_port("C")
    context = FakeContext(ports=[a, b, c], service_routes=[], legs=[], vessels=[])
    # No edges, so no predecessor -> empty path.
    assert strategy_module._pathfind(context, [], a, c) == []


# --- Plan intersection branches ------------------------------------------


def test_plan_intersects_no_berth_no_leg(strategy_module: object) -> None:
    plan = make_disruption_plan(start_offset_days=60.0, duration_days=1.0)
    assert strategy_module._plan_intersects_path(plan, []) is False


def test_plan_intersects_no_target_berth(strategy_module: object) -> None:
    plan = make_disruption_plan(start_offset_days=60.0, duration_days=1.0, close_berth=True)
    assert strategy_module._plan_intersects_path(plan, []) is False


def test_plan_intersects_no_target_leg(strategy_module: object) -> None:
    plan = make_disruption_plan(start_offset_days=60.0, duration_days=1.0, multiplier=5.0)
    assert strategy_module._plan_intersects_path(plan, []) is False


def test_plan_active_window_invalid(strategy_module: object) -> None:
    bad = make_disruption_plan(start_offset_days=-1.0, duration_days=1.0)
    assert strategy_module._plan_active_window(bad, dt.datetime.min) is None
    bad = make_disruption_plan(start_offset_days=60.0, duration_days=0.0)
    assert strategy_module._plan_active_window(bad, dt.datetime.min) is None
    bad = make_disruption_plan(start_offset_days=None, duration_days=1.0)
    assert strategy_module._plan_active_window(bad, dt.datetime.min) is None


# --- Duration estimation branches ----------------------------------------


def test_path_duration_invalid_distance(strategy_module: object) -> None:
    a = make_port("A")
    b = make_port("B")
    c = make_port("C")
    leg_ab = make_leg(a, b, 100.0)
    leg_bc = make_leg(b, c, 100.0)
    route = make_route("R1")
    make_segment(1, leg_ab, route)
    make_segment(2, leg_bc, route)
    vc = make_vessel_class("VC", teu_capacity=1000, sailing_speed=10.0)
    make_vessel(1, vc, route)
    # Use the edge class directly with invalid distance.
    edge = strategy_module._NominalBookingEdge(
        service_route=route,
        departure_port=a,
        arrival_port=b,
        departure_segment_index=1,
        arrival_segment_index=2,
        candidate_segments=[],
    )
    edge.total_distance = math.inf
    assert strategy_module._path_duration_hours([edge]) == math.inf


def test_path_duration_no_route(strategy_module: object) -> None:
    a = make_port("A")
    edge = strategy_module._NominalBookingEdge(
        service_route=None,
        departure_port=a,
        arrival_port=a,
        departure_segment_index=1,
        arrival_segment_index=2,
        candidate_segments=[],
    )
    edge.total_distance = 100.0
    assert strategy_module._path_duration_hours([edge]) == math.inf


# --- Main impl early-exit branches ---------------------------------------


def test_main_impl_returns_none_when_now_not_datetime(strategy_module: object) -> None:
    a = make_port("A")
    demand = make_demand(a, a)
    shipment = make_shipment(1, 1, demand, a)
    context = FakeContext(ports=[a], service_routes=[], legs=[], vessels=[])
    result = strategy_module._assign_associated_bookings_impl(context, "not-a-datetime", shipment)
    assert result is None


def test_main_impl_returns_none_when_origin_eq_destination(strategy_module: object) -> None:
    a = make_port("A")
    demand = make_demand(a, a)
    shipment = make_shipment(1, 1, demand, a)
    context = FakeContext(ports=[a], service_routes=[], legs=[], vessels=[])
    result = strategy_module._assign_associated_bookings_impl(context, dt.datetime.min, shipment)
    assert result is None


def test_main_impl_returns_none_when_shipment_has_no_demand(strategy_module: object) -> None:
    a = make_port("A")
    shipment = make_shipment(1, 1, demand=None, origin=a)  # type: ignore[arg-type]
    context = FakeContext(ports=[a], service_routes=[], legs=[], vessels=[])
    result = strategy_module._assign_associated_bookings_impl(context, dt.datetime.min, shipment)
    assert result is None


# --- Public hook signature sanity ----------------------------------------


def test_public_method_signatures(strategy_module: object) -> None:
    """The public surface keeps its original names and signatures."""
    import inspect

    cls = strategy_module.UserStrategy
    sig = inspect.signature(cls.select_vessel_for_berth)
    assert list(sig.parameters) == [
        "maritime_data_context",
        "port",
        "waiting_vessels",
        "available_berths",
        "current_time",
        "waiting_since_by_vessel",
    ]
    sig = inspect.signature(cls.create_alternative_service_routes)
    assert list(sig.parameters) == ["context", "now", "vessel"]
    sig = inspect.signature(cls.assign_associated_bookings)
    assert list(sig.parameters) == ["context", "now", "shipment"]
    sig = inspect.signature(cls.adjust_bookings_before_cargo_handling)
    assert list(sig.parameters) == ["context", "now", "vessel"]


# --- Narrow exception delegation ----------------------------------------


def test_narrow_exception_in_public_hook(strategy_module: object) -> None:
    """The public hook must catch narrow exceptions only."""
    sentinel = object()
    # Passing a string for `now` raises TypeError inside _impl; the outer
    # hook must catch it and return None.
    cls = strategy_module.UserStrategy
    result = cls.assign_associated_bookings(sentinel, "garbage", sentinel)
    assert result is None
    # Build a context-like object that raises an unexpected exception type
    # on attribute access; the public hook should propagate (we exercise
    # this via mocking the impl).
    orig = strategy_module._assign_associated_bookings_impl

    def boom(_context, _now, _shipment):  # noqa: ANN001, ANN202
        raise RuntimeError("unexpected")

    strategy_module._assign_associated_bookings_impl = boom
    try:
        try:
            cls.assign_associated_bookings(sentinel, dt.datetime.min, sentinel)
        except RuntimeError:
            pass
        else:
            pytest.fail("non-narrow exception must propagate")
    finally:
        strategy_module._assign_associated_bookings_impl = orig
