"""RED/GREEN contract tests for the recovery-aware origin-hold policy."""

from __future__ import annotations

import datetime as dt
import math
from types import SimpleNamespace

import pytest
from response_strategies import user_strategy as strategy
from response_strategies.user_strategy import UserStrategy


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(route_id: str, legs: list[tuple[SimpleNamespace, SimpleNamespace, float]]):
    route = SimpleNamespace(
        id=route_id,
        segments=[],
        deployed_vessels=[],
        source_service_route=None,
        disruption_key=None,
        associated_bookings=[],
    )
    for sequence, (departure, arrival, distance) in enumerate(legs, start=1):
        leg = SimpleNamespace(
            departure_port=departure,
            arrival_port=arrival,
            sailing_distance=distance,
            segments=[],
        )
        segment = SimpleNamespace(
            sequence_index=sequence,
            associated_leg=leg,
            associated_service_route=route,
            current_vessels=[],
        )
        leg.segments.append(segment)
        route.segments.append(segment)
    vessel = SimpleNamespace(
        assigned_service_route=route,
        vessel_class=SimpleNamespace(sailing_speed=20.0),
    )
    route.deployed_vessels.append(vessel)
    return route


def _fixture(*, safe_distance: float = 1_000.0):
    origin = _port("Origin")
    destination = _port("Destination")
    detour = _port("Detour")
    nominal = _route(
        "NOMINAL",
        [(origin, destination, 100.0), (destination, origin, 100.0)],
    )
    safe = _route(
        "SAFE",
        [
            (origin, detour, safe_distance / 2.0),
            (detour, destination, safe_distance / 2.0),
            (destination, origin, 20.0),
        ],
    )
    target_leg = nominal.segments[0].associated_leg
    plan = SimpleNamespace(
        start_offset_days=10.0,
        duration_days=5.0,
        target_leg=target_leg,
        target_berth=None,
        multiplier=2.0,
        close_berth=False,
    )
    context = SimpleNamespace(
        ports=[origin, destination, detour],
        service_routes=[nominal, safe],
        disruption_plans=[plan],
    )
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        associated_bookings=[],
        current_booking_index=None,
    )
    return context, shipment, plan, nominal, safe


def _now(day: float) -> dt.datetime:
    return dt.datetime.min + dt.timedelta(days=day)


def test_returns_false_when_waiting_for_recovery_beats_safe_detour() -> None:
    context, shipment, _plan, _nominal, _safe = _fixture(safe_distance=1_000.0)
    before = (
        tuple(context.service_routes),
        tuple(context.ports),
        list(shipment.associated_bookings),
        shipment.current_booking_index,
    )

    result = UserStrategy.assign_associated_bookings(context, _now(14.5), shipment)

    assert result is False
    assert (
        tuple(context.service_routes),
        tuple(context.ports),
        shipment.associated_bookings,
        shipment.current_booking_index,
    ) == before


def test_delegates_when_safe_detour_is_faster() -> None:
    context, shipment, _plan, _nominal, _safe = _fixture(safe_distance=20.0)

    result = UserStrategy.assign_associated_bookings(context, _now(14.5), shipment)

    assert result is None
    assert shipment.associated_bookings == []
    assert shipment.current_booking_index is None


def test_active_window_start_is_inclusive() -> None:
    context, shipment, _plan, _nominal, _safe = _fixture(safe_distance=3_000.0)

    assert UserStrategy.assign_associated_bookings(context, _now(10.0), shipment) is False


def test_active_window_end_is_exclusive() -> None:
    context, shipment, plan, _nominal, _safe = _fixture(safe_distance=1_000.0)
    at_end = _now(plan.start_offset_days + plan.duration_days)

    assert UserStrategy.assign_associated_bookings(context, at_end, shipment) is None


def test_delegates_when_active_plan_does_not_touch_nominal_path() -> None:
    context, shipment, plan, _nominal, _safe = _fixture(safe_distance=1_000.0)
    other_origin = _port("Other origin")
    other_destination = _port("Other destination")
    plan.target_leg = SimpleNamespace(
        departure_port=other_origin,
        arrival_port=other_destination,
        sailing_distance=10.0,
        segments=[],
    )

    assert UserStrategy.assign_associated_bookings(context, _now(14.5), shipment) is None


def test_delegates_when_no_complete_safe_path_exists() -> None:
    context, shipment, _plan, nominal, safe = _fixture(safe_distance=1_000.0)
    context.service_routes = [nominal]

    assert UserStrategy.assign_associated_bookings(context, _now(14.5), shipment) is None


def test_delegates_without_active_disruption() -> None:
    context, shipment, plan, _nominal, _safe = _fixture(safe_distance=1_000.0)
    plan.start_offset_days = 100.0

    assert UserStrategy.assign_associated_bookings(context, _now(14.5), shipment) is None


def test_malformed_context_fails_closed_without_mutation() -> None:
    shipment = SimpleNamespace(
        demand=SimpleNamespace(origin_port=_port("A"), destination_port=_port("B")),
        associated_bookings=[],
        current_booking_index=None,
    )
    context = SimpleNamespace(
        ports=[],
        service_routes=[],
        disruption_plans=[object()],
    )

    assert UserStrategy.assign_associated_bookings(context, _now(14.5), shipment) is None
    assert shipment.associated_bookings == []
    assert shipment.current_booking_index is None


def test_all_other_hooks_delegate() -> None:
    assert UserStrategy.select_vessel_for_berth(None, None, [], [], None) is None
    assert UserStrategy.create_alternative_service_routes(None, None) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(None, None, None) is None


@pytest.mark.parametrize("value", [True, False, "20", -1.0, math.inf, math.nan])
def test_numeric_validators_reject_non_positive_or_non_numeric_values(value) -> None:
    assert strategy._positive_float(value) is None
    assert strategy._nonnegative_float(value) is None


def test_numeric_validators_accept_positive_and_zero_values() -> None:
    assert strategy._positive_float(2) == 2.0
    assert strategy._nonnegative_float(0) == 0.0


def test_plan_window_rejects_invalid_and_overflowing_windows() -> None:
    now = _now(1.0)
    assert (
        strategy._plan_window(SimpleNamespace(start_offset_days=-1, duration_days=2), now) is None
    )
    assert strategy._plan_window(SimpleNamespace(start_offset_days=0, duration_days=0), now) is None
    assert (
        strategy._plan_window(SimpleNamespace(start_offset_days=0, duration_days=1e308), now)
        is None
    )
    assert strategy._plan_window(SimpleNamespace(start_offset_days=0, duration_days=1), now) is None


def test_active_state_handles_closed_berth_and_ignored_plans() -> None:
    context, _shipment, plan, _nominal, _safe = _fixture()
    port = context.ports[0]
    closed = SimpleNamespace(
        start_offset_days=10.0,
        duration_days=5.0,
        target_leg=None,
        target_berth=SimpleNamespace(port=port),
        close_berth=True,
        multiplier=None,
    )
    ignored = SimpleNamespace(
        start_offset_days=10.0,
        duration_days=5.0,
        target_leg=plan.target_leg,
        target_berth=None,
        multiplier=1.0,
    )
    context.disruption_plans = [closed, ignored]
    state = strategy._active_state(context, _now(12.0))
    assert state is not None
    assert state.closed_ports == (port,)
    assert state.closed_names == ("origin",)
    assert state.congested_legs == ()


def test_active_state_fails_closed_for_invalid_active_plan() -> None:
    context, _shipment, plan, _nominal, _safe = _fixture()
    plan.target_berth = SimpleNamespace(port=_port("Other"))
    assert strategy._active_state(context, _now(12.0)) is None


def test_route_availability_and_ordered_segments_fail_closed() -> None:
    context, _shipment, _plan, nominal, _safe = _fixture()
    state = strategy._active_state(context, _now(12.0))
    assert state is not None
    assert strategy._route_available(nominal, state, safe=False)
    assert strategy._ordered_segments(SimpleNamespace(segments=None)) is None
    assert strategy._ordered_segments(SimpleNamespace(segments=[])) is None
    alternative = SimpleNamespace(
        source_service_route=nominal,
        disruption_key=state.disruption_key,
        deployed_vessels=[object()],
        segments=nominal.segments,
    )
    assert strategy._route_available(alternative, state, safe=True)
    alternative.disruption_key = ((), ())
    assert not strategy._route_available(alternative, state, safe=True)


def test_pathfind_handles_empty_invalid_and_unreachable_graphs() -> None:
    context, _shipment, _plan, nominal, safe = _fixture()
    state = strategy._active_state(context, _now(12.0))
    assert state is not None
    edges = strategy._route_edges(nominal, state, safe=False)
    origin, destination, outside = context.ports[0], context.ports[1], _port("Outside")
    assert strategy._pathfind(context, [], origin, destination) is None
    assert strategy._pathfind(context, edges, origin, origin) is None
    assert strategy._pathfind(context, edges, outside, destination) is None
    assert strategy._pathfind(context, edges, destination, outside) is None
    assert strategy._pathfind(
        context, strategy._route_edges(safe, state, safe=True), origin, destination
    )


def test_route_speed_fallback_and_invalid_duration_fail_closed() -> None:
    context, _shipment, state_plan, nominal, _safe = _fixture()
    state = strategy._active_state(context, _now(12.0))
    assert state is not None
    edge = strategy._route_edges(nominal, state, safe=False)[0]
    nominal.deployed_vessels = []
    nominal.segments[0].current_vessels = [
        SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=20.0))
    ]
    assert strategy._route_speeds(nominal) == [20.0]
    assert strategy._path_duration_hours([edge]) is not None
    nominal.segments[0].associated_leg.sailing_distance = 0.0
    assert strategy._route_cycle_distance(nominal) is None
    assert strategy._path_duration_hours([edge]) is None
    assert state_plan is not None


def test_constraint_intersection_and_latest_recovery() -> None:
    context, _shipment, _plan, nominal, _safe = _fixture()
    state = strategy._active_state(context, _now(12.0))
    assert state is not None
    edge = strategy._route_edges(nominal, state, safe=False)[0]
    constraint = state.constraints[0]
    assert strategy._edge_intersects_constraint(edge, constraint)
    assert strategy._latest_recovery([edge], state.constraints) == constraint.recovery
    unrelated = strategy._Constraint("leg", object(), constraint.recovery)
    assert not strategy._edge_intersects_constraint(edge, unrelated)
    assert strategy._latest_recovery([edge], (unrelated,)) is None


def test_public_hook_catches_runtime_shape_errors() -> None:
    context, shipment, plan, _nominal, _safe = _fixture()
    context.service_routes = None
    assert UserStrategy.assign_associated_bookings(context, _now(12.0), shipment) is None
    assert plan is not None


def test_edge_and_leg_key_reject_invalid_shape() -> None:
    origin = _port("Origin")
    destination = _port("Destination")
    bad_leg = SimpleNamespace(
        departure_port=origin,
        arrival_port=destination,
        sailing_distance=0.0,
    )
    with pytest.raises(ValueError):
        strategy._Edge(
            SimpleNamespace(), origin, destination, 1, 1, [SimpleNamespace(associated_leg=bad_leg)]
        )
    assert strategy._leg_key(SimpleNamespace(departure_port=origin, arrival_port=None)) is None


def test_active_state_handles_missing_and_malformed_plans() -> None:
    assert strategy._active_state(SimpleNamespace(), _now(1.0)) is None
    context, _shipment, plan, _nominal, _safe = _fixture()
    plan.target_leg = None
    plan.target_berth = SimpleNamespace(port=None)
    plan.close_berth = True
    assert strategy._active_state(context, _now(12.0)) is None
    plan.target_berth = None
    plan.target_leg = SimpleNamespace(departure_port=None, arrival_port=None)
    plan.multiplier = 2.0
    assert strategy._active_state(context, _now(12.0)) is None


def test_route_edges_skips_unavailable_and_malformed_routes() -> None:
    context, _shipment, _plan, nominal, _safe = _fixture()
    state = strategy._active_state(context, _now(12.0))
    assert state is not None
    alternative = SimpleNamespace(
        source_service_route=nominal,
        disruption_key=state.disruption_key,
        deployed_vessels=[],
        segments=nominal.segments,
    )
    assert strategy._route_edges(alternative, state, safe=True) == []
    malformed = SimpleNamespace(
        source_service_route=None,
        segments=[SimpleNamespace(sequence_index=1, associated_leg=object())],
    )
    assert strategy._route_edges(malformed, state, safe=False) == []


def test_route_speeds_ignores_duplicates_and_invalid_vessels() -> None:
    route = SimpleNamespace(
        deployed_vessels=[],
        segments=[],
    )
    vessel = SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=20.0))
    route.segments = [SimpleNamespace(current_vessels=[vessel, vessel])]
    route.segments.append(
        SimpleNamespace(
            current_vessels=[SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=0.0))]
        )
    )
    assert strategy._route_speeds(route) == [20.0]


def test_path_duration_fails_closed_for_invalid_speed_and_headway(monkeypatch) -> None:
    context, _shipment, _plan, nominal, _safe = _fixture()
    state = strategy._active_state(context, _now(12.0))
    assert state is not None
    edge = strategy._route_edges(nominal, state, safe=False)[0]
    monkeypatch.setattr(strategy, "_route_speeds", lambda _route: [20.0])
    monkeypatch.setattr(strategy, "_route_cycle_distance", lambda _route: math.inf)
    assert strategy._path_duration_hours([edge]) is None


def test_should_hold_fails_closed_for_invalid_inputs_and_missing_nominal_path() -> None:
    context, shipment, _plan, _nominal, _safe = _fixture()
    assert strategy._should_hold(context, "not-a-time", shipment) is False
    shipment.demand.origin_port = shipment.demand.destination_port
    assert strategy._should_hold(context, _now(12.0), shipment) is False
    context.service_routes = []
    shipment.demand.origin_port = context.ports[0]
    shipment.demand.destination_port = context.ports[1]
    assert strategy._should_hold(context, _now(12.0), shipment) is False


def test_should_hold_rejects_unusable_duration_and_recovery(monkeypatch) -> None:
    context, shipment, _plan, nominal, safe = _fixture()
    nominal.deployed_vessels = []
    safe.deployed_vessels = []
    assert strategy._should_hold(context, _now(12.0), shipment) is False

    context, shipment, _plan, _nominal, _safe = _fixture()
    monkeypatch.setattr(strategy, "_latest_recovery", lambda _path, _constraints: _now(11.0))
    assert strategy._should_hold(context, _now(12.0), shipment) is False


def test_port_constraint_matches_intermediate_segment() -> None:
    origin, middle, destination = _port("Origin"), _port("Middle"), _port("Destination")
    route = _route(
        "MULTI",
        [(origin, middle, 10.0), (middle, destination, 10.0), (destination, origin, 10.0)],
    )
    state = strategy._ActiveState((middle,), ("middle",), (), frozenset(), ((), ()), ())
    edge = strategy._route_edges(route, state, safe=False)[0]
    constraint = strategy._Constraint("port", middle, _now(5.0))
    assert strategy._edge_intersects_constraint(edge, constraint)
