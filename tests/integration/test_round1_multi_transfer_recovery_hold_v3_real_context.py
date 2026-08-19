"""Real Round 1 context contract for the v24 service-time refinement."""

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
        "wsc_round1_service_time_safe_path_v24_participant", participant_file
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
    times: list[dt.datetime] = []
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
            for fraction in (0.25, 0.5, 0.75):
                times.append(
                    dt.datetime.min + dt.timedelta(days=start_days + duration_days * fraction)
                )
    return tuple(sorted(set(times)))


def _integer_midpoint_times(context: Any) -> tuple[dt.datetime, ...]:
    times: list[dt.datetime] = []
    for plan in context.disruption_plans:
        start_days = getattr(plan, "start_offset_days", None)
        duration_days = getattr(plan, "duration_days", None)
        if (
            not isinstance(start_days, (int, float))
            or isinstance(start_days, bool)
            or not math.isfinite(start_days)
            or not isinstance(duration_days, (int, float))
            or isinstance(duration_days, bool)
            or not math.isfinite(duration_days)
            or duration_days <= 0
        ):
            continue
        start = dt.datetime.min + dt.timedelta(days=start_days)
        end = start + dt.timedelta(days=duration_days)
        for day in range(math.floor(start_days), math.ceil(start_days + duration_days)):
            midpoint = dt.datetime.min + dt.timedelta(days=day, hours=12)
            if start <= midpoint < end:
                times.append(midpoint)
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


def test_real_round1_context_contains_v3_hold_and_service_time_veto() -> None:
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
    times = tuple(sorted({*_candidate_times(template), *_integer_midpoint_times(template)}))
    assert times, "real Round 1 context must expose at least one valid disruption window"

    qualifying: tuple[Any, Any, Any] | None = None
    service_time_veto: tuple[Any, Any, Any] | None = None
    for now in times:
        context = scenario_builders.create_with_disruption()
        DefaultStrategy.create_alternative_service_routes(context, now)
        for index, demand in enumerate(context.demands):
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
            if decision is False:
                state = participant._active_state(context, now)
                assert state is not None
                graphs = participant._graphs(context, state)
                assert graphs is not None
                safe_path = participant._fastest_path(
                    context,
                    demand.origin_port,
                    demand.destination_port,
                    graphs[1],
                )
                assert safe_path is not None
                route_changes = sum(
                    left.route is not right.route
                    for left, right in zip(safe_path, safe_path[1:], strict=False)
                )
                assert route_changes >= 2
                qualifying = (context, now, shipment)
            elif service_time_veto is None:
                state = participant._active_state(context, now)
                if state is None:
                    continue
                graphs = participant._graphs(context, state)
                if graphs is None:
                    continue
                nominal_path = participant._shortest_path(
                    context,
                    demand.origin_port,
                    demand.destination_port,
                    graphs[0],
                )
                distance_path = participant._shortest_path(
                    context,
                    demand.origin_port,
                    demand.destination_port,
                    graphs[1],
                )
                fastest_path = participant._fastest_path(
                    context,
                    demand.origin_port,
                    demand.destination_port,
                    graphs[1],
                )
                if nominal_path is None or distance_path is None or fastest_path is None:
                    continue
                distance_changes = sum(
                    left.route is not right.route
                    for left, right in zip(distance_path, distance_path[1:], strict=False)
                )
                fastest_changes = sum(
                    left.route is not right.route
                    for left, right in zip(fastest_path, fastest_path[1:], strict=False)
                )
                if (
                    len(nominal_path) == 1
                    and distance_changes >= 2
                    and len(fastest_path) >= 2
                    and fastest_changes < 2
                ):
                    service_time_veto = (context, now, shipment)
            assert decision is None or decision is False
            if qualifying is not None and service_time_veto is not None:
                break
        if qualifying is not None and service_time_veto is not None:
            break

    assert qualifying is not None, (
        "approved policy is dormant in the real Round 1 context at every "
        "derived active-window sample"
    )
    assert service_time_veto is not None, (
        "service-time refinement did not find a distance-only control hold that should delegate"
    )

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
