"""Real Round 1 contract for the safe-departure opportunity gate v4 policy."""

from __future__ import annotations

import datetime as dt
import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _bootstrap_or_skip() -> Path:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip(
            "Round 1 source is unavailable; bootstrap the organizer archive "
            "to run this integration contract."
        )
    return source


def _prepare_imports(source: Path) -> None:
    for path in (str(source), str(source / "o2despy")):
        if path not in sys.path:
            sys.path.insert(0, path)
    prefixes = (
        "config",
        "main",
        "maritime_data_context",
        "o2des",
        "o2despy",
        "response_strategies",
        "scenario_builders",
        "simulation_model",
    )
    for module_name in list(sys.modules):
        if any(
            module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes
        ):
            sys.modules.pop(module_name, None)


def _load_participant_module() -> Any:
    participant_file = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location(
        "wsc_round1_safe_departure_opportunity_gate_v4_participant", participant_file
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(value: Any) -> int | None:
    return None if value is None else id(value)


def _snapshot(context: Any, shipment: Any) -> tuple[Any, ...]:
    port_state = tuple(
        (
            id(port),
            getattr(port, "name", None),
            tuple(map(id, getattr(port, "berths", ()))),
            tuple(map(id, getattr(port, "outgoing_legs", ()))),
            tuple(map(id, getattr(port, "incoming_legs", ()))),
            tuple(map(id, getattr(port, "outgoing_demands", ()))),
            tuple(map(id, getattr(port, "incoming_demands", ()))),
            tuple(map(id, getattr(port, "shipments_in_storage", ()))),
        )
        for port in context.ports
    )
    route_state = tuple(
        (
            id(route),
            getattr(route, "id", None),
            getattr(route, "name", None),
            _identity(getattr(route, "source_service_route", None)),
            repr(getattr(route, "disruption_key", None)),
            tuple(map(id, route.segments)),
            tuple(
                (
                    id(segment),
                    segment.sequence_index,
                    id(segment.associated_leg),
                    _identity(getattr(segment, "associated_service_route", None)),
                    tuple(map(id, getattr(segment, "current_vessels", ()))),
                    id(segment.associated_leg.departure_port),
                    id(segment.associated_leg.arrival_port),
                    segment.associated_leg.sailing_distance,
                    getattr(segment.associated_leg, "sailing_time_multiplier", None),
                )
                for segment in route.segments
            ),
            tuple(map(id, route.deployed_vessels)),
            tuple(map(id, route.associated_bookings)),
        )
        for route in context.service_routes
    )
    vessel_state = tuple(
        (
            id(vessel),
            _identity(vessel.vessel_class),
            _identity(vessel.assigned_service_route),
            _identity(vessel.pending_assigned_service_route),
            _identity(vessel.current_segment),
            _identity(vessel.current_berth),
            tuple(map(id, vessel.carried_shipments)),
        )
        for vessel in context.vessels
    )
    plan_state = tuple(
        (
            id(plan),
            _identity(plan.target_leg),
            _identity(plan.target_berth),
            plan.start_offset_days,
            plan.duration_days,
            plan.multiplier,
            plan.close_berth,
        )
        for plan in context.disruption_plans
    )
    shipment_state = (
        id(shipment),
        getattr(shipment, "index", None),
        getattr(shipment, "teu_size", None),
        _identity(getattr(shipment, "demand", None)),
        _identity(getattr(shipment, "current_storage_port", None)),
        getattr(shipment, "generated_time", None),
        getattr(shipment, "completion_time", None),
        tuple(map(id, getattr(shipment, "associated_bookings", ()))),
        getattr(shipment, "current_booking_index", None),
        _identity(getattr(shipment, "carrying_vessel", None)),
    )
    return (
        tuple(map(id, context.ports)),
        tuple(map(id, context.demands)),
        tuple(map(id, context.service_routes)),
        tuple(map(id, context.initial_service_routes)),
        tuple(map(id, context.legs)),
        tuple(map(id, context.vessels)),
        tuple(map(id, context.disruption_plans)),
        port_state,
        route_state,
        vessel_state,
        plan_state,
        shipment_state,
    )


def _candidate_times(context: Any) -> tuple[dt.datetime, ...]:
    times: set[dt.datetime] = set()
    for plan in context.disruption_plans:
        start_days = getattr(plan, "start_offset_days", None)
        duration_days = getattr(plan, "duration_days", None)
        if (
            isinstance(start_days, (int, float))
            and not isinstance(start_days, bool)
            and math.isfinite(start_days)
            and isinstance(duration_days, (int, float))
            and not isinstance(duration_days, bool)
            and math.isfinite(duration_days)
            and duration_days > 0
        ):
            for offset in range(math.ceil(duration_days)):
                midpoint = start_days + offset + 0.5
                if midpoint < start_days + duration_days:
                    times.add(dt.datetime.min + dt.timedelta(days=midpoint))
    return tuple(sorted(set(times)))


def _outside_time(context: Any) -> dt.datetime:
    starts = [
        dt.datetime.min + dt.timedelta(days=plan.start_offset_days)
        for plan in context.disruption_plans
        if isinstance(getattr(plan, "start_offset_days", None), (int, float))
        and not isinstance(plan.start_offset_days, bool)
        and math.isfinite(plan.start_offset_days)
    ]
    assert starts, "real Round 1 context must expose a valid disruption start"
    earliest = min(starts)
    assert earliest > dt.datetime.min
    return earliest - dt.timedelta(microseconds=1)


def _v3_eligible_metrics(
    participant: Any,
    context: Any,
    now: dt.datetime,
    demand: Any,
) -> tuple[float, float] | None:
    state = participant._active_state(context, now)
    if state is None:
        return None
    graphs = participant._graphs(context, state)
    if graphs is None:
        return None
    nominal = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[0]
    )
    safe = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[1]
    )
    if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
        return None
    route_changes = sum(
        left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
    )
    if route_changes < 2:
        return None
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    safe_first_profile = participant._route_profile(safe[0].route)
    if (
        recovery is None
        or nominal_hours is None
        or detour_hours is None
        or safe_first_profile is None
    ):
        return None
    wait_hours = max(0.0, (recovery - now).total_seconds() / 3600.0)
    hold_hours = wait_hours + nominal_hours
    if not all(
        math.isfinite(value) and value > 0.0
        for value in (hold_hours, detour_hours, safe_first_profile.headway_hours)
    ):
        return None
    if hold_hours >= detour_hours:
        return None
    return wait_hours, safe_first_profile.headway_hours


def test_real_round1_context_contains_qualifying_and_delegated_calls() -> None:
    source = _bootstrap_or_skip()
    _prepare_imports(source)

    import main  # type: ignore[import-not-found]  # noqa: F401, PLC0415
    import scenario_builders  # type: ignore[import-not-found]  # noqa: PLC0415
    from maritime_data_context.shipment import (  # type: ignore[import-not-found]  # noqa: PLC0415
        Shipment,
    )
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]  # noqa: PLC0415
        DefaultStrategy,
    )

    participant = _load_participant_module()
    template = scenario_builders.create_with_disruption()
    times = _candidate_times(template)
    assert times, "real Round 1 context must expose at least one valid disruption window"

    found_retained_hold = False
    found_long_wait_delegation = False
    for now in times:
        context = scenario_builders.create_with_disruption()
        DefaultStrategy.create_alternative_service_routes(context, now)
        for index, demand in enumerate(context.demands):
            metrics = _v3_eligible_metrics(participant, context, now, demand)
            if metrics is None:
                continue
            shipment = Shipment(
                index=index,
                teu_size=1,
                demand=demand,
                current_storage_port=demand.origin_port,
                generated_time=now,
            )
            before = _snapshot(context, shipment)
            decision = participant.UserStrategy.assign_associated_bookings(context, now, shipment)
            after = _snapshot(context, shipment)
            assert after == before, "participant decision mutated real Round 1 state"
            wait_hours, safe_first_headway = metrics
            if wait_hours <= safe_first_headway:
                assert decision is False
                found_retained_hold = True
            else:
                assert decision is None
                found_long_wait_delegation = True
            if found_retained_hold and found_long_wait_delegation:
                break
        if found_retained_hold and found_long_wait_delegation:
            break

    assert found_retained_hold, "v4 has no retained short-wait hold in the real context"
    assert found_long_wait_delegation, "v4 has no long-wait delegation in the real context"

    context = scenario_builders.create_with_disruption()
    earliest = _outside_time(context)
    demand = context.demands[0]
    delegated = Shipment(
        index=0,
        teu_size=1,
        demand=demand,
        current_storage_port=demand.origin_port,
        generated_time=earliest,
    )
    before = _snapshot(context, delegated)
    assert participant.UserStrategy.assign_associated_bookings(context, earliest, delegated) is None
    assert _snapshot(context, delegated) == before
