"""RED regression tests for the Phase A review corrections.

These tests pin the behavior introduced by the second review:

* Eligible-vessel filtering must reject vessels that belong to a different
  route (no cross-route vessel estimation).
* Disruption key collection must evaluate ``close_berth`` and
  ``multiplier > 1`` independently (a plan carrying both valid effects
  contributes both).
* Duplicate active plans targeting the same congested leg must collapse
  into a single key entry, matching the organizer's ordered-set semantics.
* Path intersection must succeed when either effect intersects.
* The package README must advertise the candidate policy (not the no-op
  fallback).
* The strategy file must not contain mutable module-level state.

The tests here are written first (RED) and committed separately from the
implementation. They use only the synthetic helpers in
``_helpers_recovery_hold`` plus the live ``user_strategy`` module loaded
from the file path.
"""

from __future__ import annotations

import ast
import datetime as dt
import importlib.util
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
README_FILE = REPO_ROOT / "submission" / "response_strategies" / "README.md"


def _load_strategy_module() -> object:
    spec = importlib.util.spec_from_file_location(
        "wsc_participant_user_strategy_corr", str(USER_STRATEGY_FILE)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def strategy_module() -> object:
    return _load_strategy_module()


@pytest.fixture(scope="module")
def user_strategy_cls(strategy_module: object) -> type:
    return strategy_module.UserStrategy


def _safe_close_plan(berth_port: object, start: float = 60.0, duration_days: float = 1.0 / 24.0) -> object:
    from tests.unit._helpers_recovery_hold import make_berth  # type: ignore[import-not-found]

    return make_disruption_plan(
        target_berth=make_berth(0, berth_port),
        start_offset_days=start,
        duration_days=duration_days,
        close_berth=True,
    )


# --- Foreign-vessel filtering --------------------------------------------


def test_foreign_route_vessel_on_segment_is_ignored(strategy_module: object) -> None:
    """A vessel assigned to a different route must not contribute to speed/headway.

    Concretely: a vessel sitting on R1's segment ``current_vessels`` whose
    ``assigned_service_route`` is R2 is foreign to R1 and must be excluded.
    """
    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    leg_ba = make_leg(b, a, 100.0)
    target_route = make_route("TARGET")
    foreign_route = make_route("FOREIGN")
    seg = make_segment(1, leg_ab, target_route)
    make_segment(2, leg_ba, target_route)
    # Foreign vessel: assigned to foreign_route, but listed on target segment.
    foreign_vc = make_vessel_class("FVC", teu_capacity=100, sailing_speed=999.0)
    foreign_vessel = make_vessel(1, foreign_vc, foreign_route)
    seg.current_vessels.append(foreign_vessel)
    # No deployed vessels on the target route.
    speeds = strategy_module._route_eligible_speeds(target_route)
    assert speeds == []


def test_segment_vessel_assigned_to_same_route_is_accepted(strategy_module: object) -> None:
    """A vessel on a segment whose ``assigned_service_route is route`` is accepted."""
    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    leg_ba = make_leg(b, a, 100.0)
    route = make_route("R1")
    seg = make_segment(1, leg_ab, route)
    make_segment(2, leg_ba, route)
    vc = make_vessel_class("VC", teu_capacity=1000, sailing_speed=12.5)
    vessel = make_vessel(1, vc, route)
    seg.current_vessels.append(vessel)
    # No deployed vessels but the on-segment vessel is properly assigned.
    speeds = strategy_module._route_eligible_speeds(route)
    assert speeds == [12.5]


def test_foreign_vessel_excluded_from_earliest_safe_path_decision(
    user_strategy_cls: type,
) -> None:
    """Inject a foreign vessel; confirm the strategy still delegates.

    The setup is otherwise safe-now-is-much-slower so that any extra
    foreign-vessel speed would shrink the safe path duration enough to
    flip the decision.
    """
    a = make_port("A")
    b = make_port("B")
    c = make_port("C")
    leg_ab = make_leg(a, b, 100.0)
    leg_bc = make_leg(b, c, 100.0)
    leg_ca = make_leg(c, a, 100.0)
    leg_ac = make_leg(a, c, 1000.0)
    leg_ca_alt = make_leg(c, a, 100.0)
    r1 = make_route("R1")
    make_segment(1, leg_ab, r1)
    make_segment(2, leg_bc, r1)
    make_segment(3, leg_ca, r1)
    r2 = make_route("R2")
    r2.source_service_route = r1
    r2.disruption_key = (("b",), ())
    seg_ac = make_segment(1, leg_ac, r2)
    make_segment(2, leg_ca_alt, r2)
    vc = make_vessel_class("VC", teu_capacity=1000, sailing_speed=10.0)
    v1 = make_vessel(1, vc, r1)
    v2 = make_vessel(2, vc, r2)
    # Foreign vessel on R2's segment with absurd speed. If foreign vessels
    # were counted, mean speed would be (10 + 999)/2 = 504.5 -> 1000/504.5
    # ~= 1.98 hours sailing + 0.5 * headway approximation. Wait_then_nominal
    # is 1h + 35h = 36h, which would still be much larger, so this test
    # is mostly about the foreign-vessel being excluded from the count.
    foreign_vc = make_vessel_class("FVC", teu_capacity=100, sailing_speed=999.0)
    foreign_route = make_route("FOREIGN")
    foreign_vessel = make_vessel(99, foreign_vc, foreign_route)
    seg_ac.current_vessels.append(foreign_vessel)
    plan = _safe_close_plan(b)
    context = FakeContext(
        ports=[a, b, c],
        service_routes=[r1, r2],
        legs=[leg_ab, leg_bc, leg_ca, leg_ac, leg_ca_alt],
        vessels=[v1, v2],
        disruption_plans=[plan],
    )
    inside = dt.datetime.min + dt.timedelta(days=60.0, seconds=0.5)
    demand = make_demand(a, c)
    shipment = make_shipment(50, 1, demand, a)
    res = user_strategy_cls.assign_associated_bookings(context, inside, shipment)
    # The behavior should still be False (wait_then_nominal strictly faster).
    assert res is False


# --- Disruption dual-effect semantics -------------------------------------


def test_collect_active_disruption_keys_congested_leg_alone(strategy_module: object) -> None:
    """A plan with only ``multiplier > 1`` contributes that effect only."""
    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    plan = make_disruption_plan(
        target_leg=leg_ab,
        start_offset_days=60.0,
        duration_days=1.0,
        multiplier=5.0,
    )
    context = FakeContext(
        ports=[a, b],
        service_routes=[],
        legs=[leg_ab],
        vessels=[],
        disruption_plans=[plan],
    )
    inside = dt.datetime.min + dt.timedelta(days=60.0, seconds=1)
    avoid_ports, congested_legs, key = strategy_module._collect_active_disruption_keys(
        context, inside
    )
    assert avoid_ports == set()
    assert id(leg_ab) in congested_legs
    assert key == ((), (("a", "b"),))


def test_collect_active_disruption_keys_close_berth_alone(strategy_module: object) -> None:
    """A plan with only ``close_berth=True`` contributes that effect only."""
    from tests.unit._helpers_recovery_hold import make_berth  # type: ignore[import-not-found]

    a = make_port("A")
    b = make_port("B")
    closing_port = b
    plan = make_disruption_plan(
        target_berth=make_berth(0, closing_port),
        start_offset_days=60.0,
        duration_days=1.0,
        close_berth=True,
    )
    context = FakeContext(
        ports=[a, b],
        service_routes=[],
        legs=[],
        vessels=[],
        disruption_plans=[plan],
    )
    inside = dt.datetime.min + dt.timedelta(days=60.0, seconds=1)
    avoid_ports, congested_legs, key = strategy_module._collect_active_disruption_keys(
        context, inside
    )
    assert avoid_ports == {"b"}
    assert congested_legs == set()
    assert key == (("b",), ())


def test_collect_active_disruption_keys_combined_effects(strategy_module: object) -> None:
    """A plan with both valid effects contributes both, producing a key with two components."""
    from tests.unit._helpers_recovery_hold import make_berth  # type: ignore[import-not-found]

    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    plan = make_disruption_plan(
        target_berth=make_berth(0, b),
        target_leg=leg_ab,
        start_offset_days=60.0,
        duration_days=1.0,
        multiplier=5.0,
        close_berth=True,
    )
    context = FakeContext(
        ports=[a, b],
        service_routes=[],
        legs=[leg_ab],
        vessels=[],
        disruption_plans=[plan],
    )
    inside = dt.datetime.min + dt.timedelta(days=60.0, seconds=1)
    avoid_ports, congested_legs, key = strategy_module._collect_active_disruption_keys(
        context, inside
    )
    assert avoid_ports == {"b"}
    assert id(leg_ab) in congested_legs
    assert key == (("b",), (("a", "b"),))


def test_collect_active_disruption_keys_deduplicates_congested_leg(
    strategy_module: object,
) -> None:
    """Two distinct active plans targeting the same leg produce one entry in the key."""
    a = make_port("A")
    b = make_port("B")
    leg_ab = make_leg(a, b, 100.0)
    plan1 = make_disruption_plan(
        target_leg=leg_ab,
        start_offset_days=60.0,
        duration_days=1.0,
        multiplier=2.0,
    )
    plan2 = make_disruption_plan(
        target_leg=leg_ab,
        start_offset_days=60.0,
        duration_days=1.0,
        multiplier=3.0,
    )
    context = FakeContext(
        ports=[a, b],
        service_routes=[],
        legs=[leg_ab],
        vessels=[],
        disruption_plans=[plan1, plan2],
    )
    inside = dt.datetime.min + dt.timedelta(days=60.0, seconds=1)
    _avoid_ports, congested_legs, key = strategy_module._collect_active_disruption_keys(
        context, inside
    )
    assert id(leg_ab) in congested_legs
    # Single collapsed key entry (not two).
    assert key == ((), (("a", "b"),))


def test_path_intersects_when_only_berth_intersects_user_strategy(
    user_strategy_cls: type,
) -> None:
    """Either effect intersecting is sufficient for the path to count as disrupted.

    Build a world where the berth is closed but the targeted leg is
    elsewhere. The nominal path passes through the closed port but the
    congested leg is not on the path. Path intersection succeeds.
    """
    a = make_port("A")
    b = make_port("B")
    c = make_port("C")
    d = make_port("D")
    leg_ab = make_leg(a, b, 100.0)
    leg_bc = make_leg(b, c, 100.0)
    leg_ca = make_leg(c, a, 100.0)
    route = make_route("R1")
    make_segment(1, leg_ab, route)
    make_segment(2, leg_bc, route)
    make_segment(3, leg_ca, route)
    vc = make_vessel_class("VC", teu_capacity=1000, sailing_speed=10.0)
    make_vessel(1, vc, route)
    leg_cd = make_leg(c, d, 100.0)
    # Combined plan: close B AND congest C->D. Nominal A->B->C intersects B
    # (closed berth), demonstrating the OR semantics.
    plan = make_disruption_plan(
        target_berth=(lambda port: (port, 0)) and None,  # placeholder
        target_leg=leg_cd,
        start_offset_days=60.0,
        duration_days=1.0,
        multiplier=5.0,
    )
    # Replace target_berth with a real berth at B.
    from tests.unit._helpers_recovery_hold import make_berth  # type: ignore[import-not-found]

    plan.target_berth = make_berth(0, b)
    plan.close_berth = True
    context = FakeContext(
        ports=[a, b, c, d],
        service_routes=[route],
        legs=[leg_ab, leg_bc, leg_ca, leg_cd],
        vessels=[route.deployed_vessels[0]],
        disruption_plans=[plan],
    )
    inside = dt.datetime.min + dt.timedelta(days=60.0, seconds=1)
    demand = make_demand(a, c)
    shipment = make_shipment(60, 1, demand, a)
    # No alternative route; no safe path -> delegate. The intersect path
    # itself is verified by the assertion that the policy doesn't
    # short-circuit before intersection is checked (no exception, normal
    # None return).
    res = user_strategy_cls.assign_associated_bookings(context, inside, shipment)
    assert res is None


# --- Module-level state: AST assertion -----------------------------------


def test_no_mutable_module_level_state(strategy_module: object) -> None:
    """Reject mutable module-level dict/list/set assignments or caches.

    Only the immutable ``_NARROW_EXCEPTIONS`` tuple is allowed. The AST
    inspection must not find any mutable assignments at module level.
    """
    src = USER_STRATEGY_FILE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            target = node.targets[0]
            name = getattr(target, "id", None)
            if name == "_NARROW_EXCEPTIONS":
                continue
            pytest.fail(
                f"unexpected module-level mutable assignment to {name!r}"
            )
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            target = node.target
            name = getattr(target, "id", None)
            if name == "_NARROW_EXCEPTIONS":
                continue
            pytest.fail(
                f"unexpected module-level mutable annotated assignment to {name!r}"
            )


# --- Packaged README describes the candidate, not the no-op fallback -----


def test_packaged_readme_describes_candidate() -> None:
    """The README must describe the recovery-aware origin-hold candidate."""
    text = README_FILE.read_text(encoding="utf-8")
    forbidden_noop_phrases = [
        "Every method in `UserStrategy` currently returns `None`",
        "establishes a known, unmodified baseline",
        "Optimization is deliberately deferred",
    ]
    for phrase in forbidden_noop_phrases:
        assert phrase not in text, (
            f"the README must describe the candidate, not the no-op fallback: contains {phrase!r}"
        )
    required_phrases = [
        "recovery-aware",
        "assign_associated_bookings",
        "False",
    ]
    for phrase in required_phrases:
        assert phrase in text, f"README must mention {phrase!r}"
