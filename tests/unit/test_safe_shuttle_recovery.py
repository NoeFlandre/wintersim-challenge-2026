"""Synthetic contract tests for the disruption recovery-shuttle candidate."""

from __future__ import annotations

import ast
import datetime as dt
import inspect
import pathlib
import sys
from types import ModuleType

import pytest
from response_strategies.user_strategy import (
    UserStrategy,
    _active_disruption_state,
    _build_recovery_plan,
    _find_shortest_leg_path,
)

USER_STRATEGY_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "submission"
    / "response_strategies"
    / "user_strategy.py"
)


class Port:
    def __init__(self, name: str) -> None:
        self.name = name
        self.berths = [Berth(self)]


class Berth:
    def __init__(self, port: Port) -> None:
        self.port = port
        self.is_available = True
        self.occupying_vessel = None


class Leg:
    def __init__(self, departure: Port, arrival: Port, distance: float = 1.0) -> None:
        self.departure_port = departure
        self.arrival_port = arrival
        self.sailing_distance = distance
        self.segments: list[Segment] = []


class Segment:
    def __init__(self, sequence_index: int, leg: Leg, route: ServiceRoute) -> None:
        self.sequence_index = sequence_index
        self.associated_leg = leg
        self.associated_service_route = route
        self.current_vessels: list[Vessel] = []


class ServiceRoute:
    def __init__(self, id: str, name: str, start_day_of_week: float) -> None:
        self.id = id
        self.name = name
        self.start_day_of_week = start_day_of_week
        self.segments: list[Segment] = []
        self.deployed_vessels: list[Vessel] = []
        self.associated_bookings: list = []
        self.source_service_route = None
        self.disruption_key = None


class Vessel:
    def __init__(self, index: int, route: ServiceRoute) -> None:
        self.index = index
        self.assigned_service_route = route
        self.pending_assigned_service_route = None
        self.current_segment = None
        self.current_berth = None
        self.carried_shipments: list = []


class Plan:
    def __init__(
        self,
        *,
        start: float,
        duration: float,
        berth: Berth | None = None,
        leg: Leg | None = None,
        multiplier: float = 1.0,
    ) -> None:
        self.start_offset_days = start
        self.duration_days = duration
        self.target_berth = berth
        self.target_leg = leg
        self.close_berth = berth is not None
        self.multiplier = multiplier


class Context:
    def __init__(
        self,
        ports: list[Port],
        legs: list[Leg],
        routes: list[ServiceRoute],
        plans: list[Plan],
    ) -> None:
        self.ports = ports
        self.legs = legs
        self.service_routes = list(routes)
        self.initial_service_routes = list(routes)
        self.partial_service_routes = [segment for route in routes for segment in route.segments]
        self.disruption_plans = plans
        self.vessels: list[Vessel] = []


def make_route(route_id: str, legs: list[Leg]) -> ServiceRoute:
    route = ServiceRoute(route_id, route_id, 0.0)
    for index, leg in enumerate(legs, start=1):
        segment = Segment(index, leg, route)
        route.segments.append(segment)
        leg.segments.append(segment)
    return route


@pytest.fixture
def network():
    a, b, c, blocked, remote = [Port(name) for name in ("A", "B", "C", "X", "R")]
    ab = Leg(a, b)
    bx = Leg(b, blocked)
    xr = Leg(blocked, remote)
    ra = Leg(remote, a)
    bc = Leg(b, c)
    ca = Leg(c, a)
    source = make_route("SOURCE", [ab, bx, xr, ra])
    plans = [Plan(start=10, duration=5, berth=blocked.berths[0])]
    context = Context(
        [a, b, c, blocked, remote],
        [ab, bx, xr, ra, bc, ca],
        [source],
        plans,
    )
    return context, source, (a, b, c, blocked, remote), (ab, bx, xr, ra, bc, ca)


def now(day: float) -> dt.datetime:
    return dt.datetime.min + dt.timedelta(days=day)


def install_fake_maritime_module(monkeypatch) -> None:
    maritime = ModuleType("maritime_data_context")
    maritime.Segment = Segment
    maritime.ServiceRoute = ServiceRoute
    monkeypatch.setitem(sys.modules, "maritime_data_context", maritime)


def test_active_interval_is_start_inclusive_end_exclusive(network) -> None:
    context, _, _, _ = network
    assert _active_disruption_state(context, now(10)) is not None
    assert _active_disruption_state(context, now(14.999)) is not None
    assert _active_disruption_state(context, now(15)) is None


def test_safe_state_excludes_closed_port_incident_legs(network) -> None:
    context, _, (_, _, _, blocked, _), (_, bx, xr, _, _, _) = network
    state = _active_disruption_state(context, now(12))
    assert state is not None
    assert blocked in state.closed_ports
    assert bx not in state.safe_legs
    assert xr not in state.safe_legs


def test_safe_state_excludes_congested_leg_by_identity(network) -> None:
    context, _, _, (ab, _, _, _, _, _) = network
    context.disruption_plans.append(Plan(start=10, duration=5, leg=ab, multiplier=3))
    state = _active_disruption_state(context, now(12))
    assert state is not None
    assert ab in state.congested_legs
    assert ab not in state.safe_legs


def test_shortest_path_tie_preserves_context_leg_order() -> None:
    a, b, c, d = [Port(name) for name in ("A", "B", "C", "D")]
    ab, ac, bd, cd = Leg(a, b), Leg(a, c), Leg(b, d), Leg(c, d)
    context = Context([a, b, c, d], [ab, ac, bd, cd], [], [])
    assert _find_shortest_leg_path(context, a, d, tuple(context.legs)) == (ab, bd)


def test_plan_uses_largest_component_and_starts_upstream(network) -> None:
    context, source, (a, b, c, _, _), (ab, _, _, _, bc, ca) = network
    state = _active_disruption_state(context, now(12))
    assert state is not None
    plan = _build_recovery_plan(context, source, state.closed_ports, state.congested_legs)
    assert plan is not None
    assert plan.start_port is b
    assert plan.legs == (bc, ca, ab)
    assert [leg.departure_port for leg in plan.legs] == [b, c, a]


def test_plan_returns_none_without_two_mutually_reachable_anchors(network) -> None:
    context, source, _, (_, _, _, _, bc, ca) = network
    context.legs.remove(bc)
    context.legs.remove(ca)
    state = _active_disruption_state(context, now(12))
    assert state is not None
    assert _build_recovery_plan(context, source, state.closed_ports, state.congested_legs) is None


def test_hook_creates_recovery_idempotently_and_does_not_reserve(network, monkeypatch) -> None:
    context, source, _, original_legs = network
    install_fake_maritime_module(monkeypatch)

    assert UserStrategy.create_alternative_service_routes(context, now(12)) is True
    shuttles = [
        route
        for route in context.service_routes
        if getattr(route, "is_participant_recovery_shuttle", False)
    ]
    assert len(shuttles) == 1
    shuttle = shuttles[0]
    assert shuttle.source_service_route is source
    assert [segment.sequence_index for segment in shuttle.segments] == [1, 2, 3]
    assert all(segment.associated_leg in original_legs for segment in shuttle.segments)
    assert not shuttle.deployed_vessels
    assert not context.vessels

    assert UserStrategy.create_alternative_service_routes(context, now(12)) is True
    assert [
        route
        for route in context.service_routes
        if getattr(route, "is_participant_recovery_shuttle", False)
    ] == [shuttle]


def test_hook_handles_inactive_state(network, monkeypatch) -> None:
    context, _, _, _ = network
    install_fake_maritime_module(monkeypatch)

    assert UserStrategy.create_alternative_service_routes(context, now(15)) is True
    assert not [
        route
        for route in context.service_routes
        if getattr(route, "is_participant_recovery_shuttle", False)
    ]


def test_hook_preserves_existing_organizer_alternative(network, monkeypatch) -> None:
    context, source, _, _ = network
    install_fake_maritime_module(monkeypatch)
    state = _active_disruption_state(context, now(12))
    assert state is not None
    alternative = ServiceRoute("SOURCE-ALT-1", "organizer alternative", 0.0)
    alternative.source_service_route = source
    alternative.disruption_key = state.key
    context.service_routes.append(alternative)

    assert UserStrategy.create_alternative_service_routes(context, now(12)) is True
    assert context.service_routes == [source, alternative]


def test_hook_recreates_standard_alternative_reservation_and_switch(monkeypatch) -> None:
    a, b, blocked = [Port(name) for name in ("A", "B", "X")]
    ax, xb, ba, ab = Leg(a, blocked), Leg(blocked, b), Leg(b, a), Leg(a, b)
    source = make_route("SOURCE", [ax, xb, ba])
    context = Context(
        [a, b, blocked],
        [ax, xb, ba, ab],
        [source],
        [Plan(start=10, duration=5, berth=blocked.berths[0])],
    )
    later = Vessel(2, source)
    reserved = Vessel(1, source)
    source.deployed_vessels.extend([later, reserved])
    context.vessels.extend([later, reserved])
    install_fake_maritime_module(monkeypatch)

    assert UserStrategy.create_alternative_service_routes(context, now(12)) is True
    alternative = context.service_routes[-1]
    assert alternative.source_service_route is source
    assert not getattr(alternative, "is_participant_recovery_shuttle", False)
    assert [
        (segment.associated_leg.departure_port, segment.associated_leg.arrival_port)
        for segment in alternative.segments
    ] == [(a, b), (b, a)]
    assert reserved.pending_assigned_service_route is alternative
    assert later.pending_assigned_service_route is None

    reserved.current_segment = source.segments[-1]  # B -> A, the alternative start.
    reserved.current_segment.current_vessels.append(reserved)
    assert UserStrategy.create_alternative_service_routes(context, now(12), reserved) is True
    assert reserved.assigned_service_route is alternative
    assert reserved.pending_assigned_service_route is None
    assert reserved in alternative.deployed_vessels
    assert reserved not in source.deployed_vessels


def test_hook_restores_empty_alternative_vessel_after_recovery(monkeypatch) -> None:
    a, b, blocked = [Port(name) for name in ("A", "B", "X")]
    ax, xb, ba, ab = Leg(a, blocked), Leg(blocked, b), Leg(b, a), Leg(a, b)
    source = make_route("SOURCE", [ax, xb, ba])
    context = Context(
        [a, b, blocked],
        [ax, xb, ba, ab],
        [source],
        [Plan(start=10, duration=5, berth=blocked.berths[0])],
    )
    vessel = Vessel(1, source)
    source.deployed_vessels.append(vessel)
    context.vessels.append(vessel)
    install_fake_maritime_module(monkeypatch)
    UserStrategy.create_alternative_service_routes(context, now(12))
    alternative = context.service_routes[-1]
    vessel.current_segment = source.segments[-1]
    vessel.current_segment.current_vessels.append(vessel)
    UserStrategy.create_alternative_service_routes(context, now(12), vessel)
    vessel.current_segment = alternative.segments[-1]  # B -> A, a source re-entry.
    vessel.current_segment.current_vessels.append(vessel)

    assert UserStrategy.create_alternative_service_routes(context, now(15), vessel) is True
    assert vessel.assigned_service_route is source
    assert vessel.pending_assigned_service_route is None
    assert vessel.current_segment is source.segments[-1]
    assert vessel in source.deployed_vessels
    assert vessel not in alternative.deployed_vessels


def test_hook_skips_route_without_viable_recovery_cycle(network, monkeypatch) -> None:
    context, source, _, (_, _, _, _, bc, ca) = network
    install_fake_maritime_module(monkeypatch)
    context.legs.remove(bc)
    context.legs.remove(ca)

    assert UserStrategy.create_alternative_service_routes(context, now(12)) is True
    assert context.service_routes == [source]


def test_hook_clears_default_pending_assignment_to_custom_shuttle(network, monkeypatch) -> None:
    context, source, _, _ = network
    install_fake_maritime_module(monkeypatch)
    UserStrategy.create_alternative_service_routes(context, now(12))
    shuttle = context.service_routes[-1]
    vessel = Vessel(1, source)
    vessel.pending_assigned_service_route = shuttle
    context.vessels.append(vessel)

    UserStrategy.create_alternative_service_routes(context, now(12))

    assert vessel.pending_assigned_service_route is None
    assert vessel.assigned_service_route is source


def test_hook_switches_exactly_one_empty_source_vessel_at_start(network, monkeypatch) -> None:
    context, source, _, _ = network
    install_fake_maritime_module(monkeypatch)
    UserStrategy.create_alternative_service_routes(context, now(12))
    shuttle = context.service_routes[-1]

    vessel = Vessel(1, source)
    source.deployed_vessels.append(vessel)
    context.vessels.append(vessel)
    vessel.current_segment = source.segments[0]  # A -> B, arrives at shuttle start B.
    vessel.current_segment.current_vessels.append(vessel)

    assert UserStrategy.create_alternative_service_routes(context, now(12), vessel) is True
    assert vessel.assigned_service_route is shuttle
    assert vessel.current_segment is None
    assert vessel in shuttle.deployed_vessels
    assert vessel not in source.deployed_vessels


def test_hook_switches_empty_source_vessel_from_start_port_berth(network, monkeypatch) -> None:
    context, source, (_, start, _, _, _), _ = network
    install_fake_maritime_module(monkeypatch)
    UserStrategy.create_alternative_service_routes(context, now(12))
    shuttle = context.service_routes[-1]
    vessel = Vessel(1, source)
    vessel.current_berth = start.berths[0]
    source.deployed_vessels.append(vessel)
    context.vessels.append(vessel)

    UserStrategy.create_alternative_service_routes(context, now(12), vessel)

    assert vessel.assigned_service_route is shuttle
    assert vessel in shuttle.deployed_vessels


def test_hook_refuses_vessel_with_other_pending_route(network, monkeypatch) -> None:
    context, source, _, _ = network
    install_fake_maritime_module(monkeypatch)
    UserStrategy.create_alternative_service_routes(context, now(12))
    vessel = Vessel(1, source)
    vessel.current_segment = source.segments[0]
    vessel.pending_assigned_service_route = object()
    source.deployed_vessels.append(vessel)
    context.vessels.append(vessel)

    UserStrategy.create_alternative_service_routes(context, now(12), vessel)

    assert vessel.assigned_service_route is source


def test_hook_refuses_second_vessel_when_shuttle_is_already_deployed(network, monkeypatch) -> None:
    context, source, _, _ = network
    install_fake_maritime_module(monkeypatch)
    UserStrategy.create_alternative_service_routes(context, now(12))
    shuttle = context.service_routes[-1]
    deployed = Vessel(1, shuttle)
    shuttle.deployed_vessels.append(deployed)
    candidate = Vessel(2, source)
    candidate.current_segment = source.segments[0]
    source.deployed_vessels.append(candidate)
    context.vessels.extend([deployed, candidate])

    UserStrategy.create_alternative_service_routes(context, now(12), candidate)

    assert candidate.assigned_service_route is source
    assert shuttle.deployed_vessels == [deployed]


@pytest.mark.parametrize(
    "loaded,at_start,foreign", [(True, True, False), (False, False, False), (False, True, True)]
)
def test_hook_refuses_ineligible_vessel(
    network, monkeypatch, loaded: bool, at_start: bool, foreign: bool
) -> None:
    context, source, _, _ = network
    install_fake_maritime_module(monkeypatch)
    UserStrategy.create_alternative_service_routes(context, now(12))
    foreign_route = make_route("FOREIGN", [context.legs[0]])
    vessel = Vessel(2, foreign_route if foreign else source)
    if not foreign:
        source.deployed_vessels.append(vessel)
    vessel.current_segment = source.segments[0 if at_start else 2]
    if loaded:
        vessel.carried_shipments.append(object())
    context.vessels.append(vessel)

    UserStrategy.create_alternative_service_routes(context, now(12), vessel)
    assert vessel.assigned_service_route is (foreign_route if foreign else source)


def test_other_hooks_remain_unconditional_delegates() -> None:
    assert UserStrategy.select_vessel_for_berth(None, None, [], [], now(12)) is None
    assert UserStrategy.assign_associated_bookings(None, now(12), None) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(None, now(12), None) is None


def test_module_has_no_mutable_globals_or_forbidden_runtime_access() -> None:
    tree = ast.parse(USER_STRATEGY_PATH.read_text(encoding="utf-8"))
    assert not [
        node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
    ]
    assert not [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "response_strategies.default_strategy"
    ]
    source = inspect.getsource(sys.modules[UserStrategy.__module__])
    for forbidden in ("subprocess", "socket", "requests", "open(", "os.environ", "Path("):
        assert forbidden not in source
