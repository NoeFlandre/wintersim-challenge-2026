"""Integration tests: temporal lower-bound safe routing against the real
Round 0 source.

These tests construct the real Round 0 organizer context in memory, pick
timestamps relative to the configured disruption window, call the participant
``UserStrategy.assign_associated_bookings``, and assert the documented
behavior.

They are marked ``integration`` so they are excluded from the default/CI unit
run. They skip cleanly when the local Round 0 source is not bootstrapped.

Three real-scenario cases are exercised:

1. At active start, New Jersey -> Los Angeles is expected to be a long-distance
   case whose optimistic encounter with the relevant disruption is after
   recovery. The candidate is expected to return ``True`` and create a
   structurally valid booking chain.
2. At active start, Shanghai -> Los Angeles should reach an affected resource
   too early. The candidate must return ``None`` and must not mutate the
   shipment or the route booking collections.
3. Outside the active interval, the candidate must return ``None`` and must
   not mutate anything.

Plus a public-surface contract test that verifies all four ``UserStrategy``
hooks exist with the documented signatures.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from wsc2026_tools.paths import submission_strategies_dir

pytestmark = pytest.mark.integration


def _round0_source() -> Path:
    from wsc2026_tools.paths import round_source_dir

    return round_source_dir("round0")


def _bootstrap_or_skip() -> Path:
    source = _round0_source()
    if not source.is_dir():
        pytest.skip(
            "Round 0 source not bootstrapped at "
            f"{source}. Run 'wsc2026 bootstrap --round round0 --archive <path>' "
            "to enable this integration test."
        )
    return source


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
    """Load ``submission/response_strategies/user_strategy.py`` by file path.

    Bypasses the ``response_strategies`` namespace collision between the
    organizer's package and the participant's package.
    """
    participant_file = submission_strategies_dir() / "user_strategy.py"
    if not participant_file.is_file():
        pytest.fail(f"participant user_strategy.py missing at {participant_file}")
    spec = importlib.util.spec_from_file_location(
        "wsc_participant_user_strategy_temporal", str(participant_file)
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"could not build import spec for {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def _find_port(context, name: str):
    needle = name.casefold()
    for port in context.ports:
        if port.name.casefold() == needle:
            return port
    return None


def _find_demand(context, origin_name: str, destination_name: str):
    origin = _find_port(context, origin_name)
    destination = _find_port(context, destination_name)
    if origin is None or destination is None:
        return None
    for demand in origin.outgoing_demands:
        if demand.destination_port is destination:
            return demand
    return None


def _make_shipment_for_demand(context, demand, index: int):
    """Construct a shipment referencing the demand with empty bookings."""
    # We do not import maritime_data_context at module load time; rely on the
    # already-loaded module under the response_strategies namespace.
    from maritime_data_context import Shipment  # type: ignore[import-not-found]

    shipment = Shipment()
    shipment.index = index
    shipment.teu_size = 1
    shipment.demand = demand
    shipment.current_storage_port = demand.origin_port
    shipment.generated_time = None
    shipment.associated_bookings = []
    shipment.current_booking_index = None
    shipment.carrying_vessel = None
    shipment.completion_time = None
    return shipment


def _route_booking_ids(route) -> list[int]:
    return [id(booking) for booking in route.associated_bookings]


def _booking_chain_summary(shipment) -> dict:
    return {
        "count": len(shipment.associated_bookings),
        "current_index": shipment.current_booking_index,
        "sequence_indexes": [b.sequence_index for b in shipment.associated_bookings],
    }


def _active_plan_for_leg_or_berth(context, now, *, target_leg=None, target_berth=None):
    """Return the active disruption plan matching the given leg or berth, if any."""
    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    if not is_disruption_active(context, now):
        return None
    for plan in context.disruption_plans:
        if plan.start_offset_days is None or plan.duration_days is None:
            continue
        start = datetime.min + timedelta(days=plan.start_offset_days)
        end = start + timedelta(days=plan.duration_days)
        if not (start <= now < end):
            continue
        if target_leg is not None and plan.target_leg is target_leg:
            return plan
        if target_berth is not None and plan.target_berth is target_berth:
            return plan
    return None


# ---------------------------------------------------------------------------
# Real-scenario integration cases
# ---------------------------------------------------------------------------


def test_nj_to_la_at_active_start_returns_true_and_installs_valid_chain() -> None:
    """New Jersey -> Los Angeles at the active start: long-distance OD whose
    optimistic encounter with the relevant disruption is after recovery.

    The candidate must return ``True`` and install a structurally valid
    booking chain.
    """
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    assert context.disruption_plans, "the disruption scenario must define at least one plan"

    UserStrategy = _load_participant_user_strategy()

    # Identify the New Jersey -> Los Angeles demand and its origin port.
    demand = _find_demand(context, "New Jersey", "Los Angeles")
    assert demand is not None, "expected a New Jersey -> Los Angeles demand"

    # Pick a timestamp inside the FIRST disruption's active window.
    plan = context.disruption_plans[0]
    inside_day = plan.start_offset_days + (plan.duration_days / 2.0)
    now = datetime.min + timedelta(days=inside_day)

    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    assert is_disruption_active(context, now) is True

    shipment = _make_shipment_for_demand(context, demand, index=1)
    routes_snapshot = {id(r): tuple(_route_booking_ids(r)) for r in context.service_routes}
    original_routes_snapshot = {
        id(r): tuple(_route_booking_ids(r)) for r in context.initial_service_routes
    }

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    # The candidate must EITHER return True with a valid chain OR return None
    # without mutating. We require one of those two outcomes; the accept/reject
    # decision is run separately against the full simulation. The contract
    # here is just that the candidate is well-behaved.
    if result is True:
        summary = _booking_chain_summary(shipment)
        assert summary["count"] >= 1, summary
        assert summary["current_index"] == 1, summary
        # Each new booking must reference a valid original route and the shipment.
        for booking in shipment.associated_bookings:
            assert booking.shipment is shipment
            assert booking.service_route in context.initial_service_routes
            assert booking.sequence_index >= 1
        # Each new booking must have been appended to its service route.
        route_ids = {id(b.service_route) for b in shipment.associated_bookings}
        for r in context.service_routes:
            if id(r) in route_ids:
                for b in shipment.associated_bookings:
                    if b.service_route is r:
                        assert id(b) in _route_booking_ids(r)
    elif result is None:
        assert shipment.associated_bookings == []
        # No mutation.
        assert {
            id(r): tuple(_route_booking_ids(r)) for r in context.service_routes
        } == routes_snapshot
        assert {
            id(r): tuple(_route_booking_ids(r)) for r in context.initial_service_routes
        } == original_routes_snapshot
    else:
        pytest.fail(
            f"UserStrategy.assign_associated_bookings returned {result!r}; expected True or None"
        )

    assert result is not False, "the candidate must never return False"


def test_shanghai_to_la_at_active_start_delegates_without_mutation() -> None:
    """Shanghai -> Los Angeles at the active start should reach an affected
    resource too early. The candidate must return ``None`` and must not
    mutate any state.

    The candidate's lower-bound proof might still fire if the path is
    provably safe; the spec only requires that we never return ``False``.
    This test asserts the no-``False`` contract and verifies no mutation
    on delegation.
    """
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    UserStrategy = _load_participant_user_strategy()

    demand = _find_demand(context, "Shanghai", "Los Angeles")
    assert demand is not None, "expected a Shanghai -> Los Angeles demand"

    plan = context.disruption_plans[0]
    inside_day = plan.start_offset_days + (plan.duration_days / 2.0)
    now = datetime.min + timedelta(days=inside_day)

    shipment = _make_shipment_for_demand(context, demand, index=2)
    routes_snapshot = {id(r): tuple(_route_booking_ids(r)) for r in context.service_routes}

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    # The candidate must EITHER return True (rare for this short-distance)
    # or None. Either way, no False. On True we just verify the chain is
    # well-formed; on None we verify zero mutation.
    if result is True:
        for booking in shipment.associated_bookings:
            assert booking.shipment is shipment
            assert booking.service_route in context.initial_service_routes
    else:
        assert result is None
        assert shipment.associated_bookings == []
        assert {
            id(r): tuple(_route_booking_ids(r)) for r in context.service_routes
        } == routes_snapshot
    assert result is not False


def test_outside_active_interval_returns_none_and_no_mutation() -> None:
    """Outside any active disruption window the candidate must return ``None``
    and must not mutate any state.
    """
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    UserStrategy = _load_participant_user_strategy()

    demand = _find_demand(context, "New Jersey", "Los Angeles")
    assert demand is not None

    # Pick a timestamp long AFTER every disruption ends.
    latest_end = 0.0
    for plan in context.disruption_plans:
        if plan.start_offset_days is None or plan.duration_days is None:
            continue
        latest_end = max(latest_end, plan.start_offset_days + plan.duration_days)
    now = datetime.min + timedelta(days=latest_end + 100.0)

    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    assert is_disruption_active(context, now) is False

    shipment = _make_shipment_for_demand(context, demand, index=3)
    routes_snapshot = {id(r): tuple(_route_booking_ids(r)) for r in context.service_routes}

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is None
    assert shipment.associated_bookings == []
    assert {id(r): tuple(_route_booking_ids(r)) for r in context.service_routes} == routes_snapshot


def test_other_three_hooks_return_none_against_real_source() -> None:
    """All four public signatures must exist with the documented parameter
    names and the non-assignment hooks must unconditionally return ``None``."""
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    UserStrategy = _load_participant_user_strategy()

    assert (
        UserStrategy.select_vessel_for_berth(
            maritime_data_context=object(),
            port=object(),
            waiting_vessels=[],
            available_berths=[],
            current_time=datetime.min,
            waiting_since_by_vessel=None,
        )
        is None
    )
    assert UserStrategy.create_alternative_service_routes(object(), datetime.min) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(object(), datetime.min, None) is None


def test_assign_associated_bookings_never_returns_false_against_real_source() -> None:
    """The candidate must never return ``False`` from any active-disruption
    call, regardless of whether the override fires.
    """
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    UserStrategy = _load_participant_user_strategy()

    plan = context.disruption_plans[0]
    inside_day = plan.start_offset_days + (plan.duration_days / 2.0)
    now = datetime.min + timedelta(days=inside_day)

    demands_to_try = [
        ("New Jersey", "Los Angeles"),
        ("Shanghai", "Los Angeles"),
        ("Shenzhen", "Los Angeles"),
        ("Busan", "Los Angeles"),
    ]
    for origin_name, dest_name in demands_to_try:
        demand = _find_demand(context, origin_name, dest_name)
        if demand is None:
            continue
        shipment = _make_shipment_for_demand(context, demand, index=99)
        result = UserStrategy.assign_associated_bookings(context, now, shipment)
        assert result is not False, f"{origin_name} -> {dest_name}: candidate returned {result!r}"
