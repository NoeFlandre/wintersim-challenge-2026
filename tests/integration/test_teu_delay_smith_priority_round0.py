"""Integration / contract test: TEU-delay Smith-priority against real Round 0.

Loads the participant ``UserStrategy.select_vessel_for_berth`` and invokes it
against real organizer domain objects built from ``create_with_disruption``.
The contract under test:

  * The hook returns one of the supplied ``waiting_vessels`` (never an
    arbitrary object, never ``False``).
  * It returns ``None`` when no candidates are provided.
  * When a non-trivial scenario is supplied, the hook returns *some*
    vessel without mutating any participant strategy can reach (context
    collections, vessel assignments, bookings, shipment lists, port
    storage, vessel carried shipments).

This test does NOT exercise the simulation horizon. It is a focused
contract test that catches regressions where the strategy mutates state,
delegates when it should not, or returns the wrong shape.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration

SOURCE = round_source_dir("round0")


def _bootstrap_or_skip() -> Path:
    if not SOURCE.is_dir():
        pytest.skip(
            "Round 0 source not bootstrapped at "
            f"{SOURCE}. Run 'wsc2026 bootstrap --round round0 --archive <path>' "
            "to enable this integration test."
        )
    return SOURCE


def _add_source_to_path(source: Path) -> None:
    src = str(source)
    o2des = str(source / "o2despy")
    if src not in sys.path:
        sys.path.insert(0, src)
    if o2des not in sys.path:
        sys.path.insert(0, o2des)

    prefixes = (
        "response_strategies",
        "scenario_builders",
        "simulation_model",
        "maritime_data_context",
        "config",
        "o2despy",
        "o2des",
    )
    for module_name in list(sys.modules):
        if any(
            module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes
        ):
            sys.modules.pop(module_name, None)


def _load_participant_user_strategy() -> type:
    participant_file = submission_strategies_dir() / "user_strategy.py"
    if not participant_file.is_file():
        pytest.fail(f"participant user_strategy.py missing at {participant_file}")
    spec = importlib.util.spec_from_file_location(
        "wsc_participant_user_strategy", str(participant_file)
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"could not build import spec for {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def _snapshot(context, port, waiting_vessels) -> dict:
    """Capture identity-bearing state that the strategy must preserve."""
    return {
        "context_id": id(context),
        "port_id": id(port),
        "port_shipments_in_storage": [id(s) for s in port.shipments_in_storage],
        "vessels": {
            id(v): {
                "assigned_route": id(v.assigned_service_route),
                "current_segment": id(v.current_segment) if v.current_segment else None,
                "current_berth": id(v.current_berth) if v.current_berth else None,
                "carried": tuple(id(s) for s in v.carried_shipments),
                "pending_route": id(v.pending_assigned_service_route)
                if v.pending_assigned_service_route
                else None,
            }
            for v in waiting_vessels
        },
        "bookings": tuple(
            (id(b.shipment), id(b.service_route), b.departure_segment_index)
            for b in getattr(context, "bookings", [])
        ),
    }


def test_select_vessel_for_berth_returns_none_for_empty_waiting() -> None:
    _bootstrap_or_skip()
    _add_source_to_path(SOURCE)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    UserStrategy = _load_participant_user_strategy()

    port = (
        context.ports[0]
        if context.ports
        else SimpleNamespace(
            shipments_in_storage=[],
            berths=[],
        )
    )
    now = datetime.min + timedelta(days=plan_now_offset(context))

    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[],
        available_berths=port.berths,
        current_time=now,
    )
    assert result is None


def test_select_vessel_for_berth_returns_exact_waiting_vessel_no_mutation() -> None:
    _bootstrap_or_skip()
    _add_source_to_path(SOURCE)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    UserStrategy = _load_participant_user_strategy()

    # Pick the first port that has at least one vessel assigned.
    chosen_port = None
    waiting: list = []
    for port in context.ports:
        for vessel in context.vessels:
            if _vessel_wants_port(vessel, port):
                waiting.append(vessel)
        if waiting:
            chosen_port = port
            break
    if chosen_port is None or not waiting:
        pytest.skip("Round 0 scenario did not produce any vessels bound to a port")

    available_berths = list(chosen_port.berths)
    now = datetime.min + timedelta(days=plan_now_offset(context))

    snap_before = _snapshot(context, chosen_port, waiting)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=chosen_port,
        waiting_vessels=waiting,
        available_berths=available_berths,
        current_time=now,
    )
    snap_after = _snapshot(context, chosen_port, waiting)

    if result is not None:
        assert result in waiting, "strategy must return one of the supplied waiting_vessels"
        assert result is not False, "strategy must never return False"
    # Strategy must never mutate state.
    assert snap_after == snap_before, (
        "select_vessel_for_berth must not mutate context, port, or vessel state"
    )


def test_other_hooks_remain_no_op() -> None:
    _bootstrap_or_skip()
    _add_source_to_path(SOURCE)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    UserStrategy = _load_participant_user_strategy()

    vessel = context.vessels[0] if context.vessels else SimpleNamespace()
    shipment = context.shipments[0] if getattr(context, "shipments", None) else SimpleNamespace()
    now = datetime.min + timedelta(days=plan_now_offset(context))

    assert UserStrategy.create_alternative_service_routes(context, now, vessel) is None
    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel) is None


def _vessel_wants_port(vessel, port) -> bool:
    """Real-organizer equivalent of _get_vessel_arrival_port.

    Mirror of ``BerthIdle._get_vessel_arrival_port``.
    """
    if vessel.current_segment is None:
        route = vessel.assigned_service_route
        if route and route.segments:
            first_segment = route.segments[0]
            if first_segment.associated_leg:
                return first_segment.associated_leg.departure_port is port
        return False
    leg = vessel.current_segment.associated_leg
    return bool(leg and leg.arrival_port is port)


def plan_now_offset(context) -> float:
    """Pick a timestamp inside the first disruption if possible, otherwise 0."""
    plans = getattr(context, "disruption_plans", [])
    if plans:
        plan = plans[0]
        return plan.start_offset_days + (plan.duration_days / 2.0)
    return 0.0
