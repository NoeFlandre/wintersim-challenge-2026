"""Real Round 1 RED contract for the v12 candidate-only activation."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _source_or_fail() -> Path:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.fail(f"Round 1 source is required for this contract: {source}")
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


def _load_participant() -> Any:
    participant_file = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_v12_real_participant", participant_file)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _timestamps(context: Any) -> tuple[dt.datetime, ...]:
    values: list[dt.datetime] = []
    for plan in context.disruption_plans:
        start_days = _finite(getattr(plan, "start_offset_days", None))
        duration_days = _finite(getattr(plan, "duration_days", None))
        if start_days is None or duration_days is None or duration_days <= 0.0:
            continue
        start = dt.datetime.min + dt.timedelta(days=start_days)
        end = start + dt.timedelta(days=duration_days)
        for integer_day in range(math.floor(start_days), math.ceil(start_days + duration_days)):
            midpoint = dt.datetime.min + dt.timedelta(days=integer_day + 0.5)
            if start <= midpoint < end:
                values.append(midpoint)
    return tuple(dict.fromkeys(values))


def _shipment(Shipment: Any, index: int, demand: Any, now: dt.datetime) -> Any:
    return Shipment(
        index=index,
        teu_size=1,
        demand=demand,
        current_storage_port=demand.origin_port,
        generated_time=now,
    )


def _matching(participant: Any, edge: Any, state: Any) -> tuple[Any, ...]:
    leg_ids = {id(leg) for leg in edge.legs}
    arrival_names = {
        participant._port_name(port) for port in (*edge.intermediate_ports, edge.arrival)
    }
    return tuple(
        constraint
        for constraint in state.constraints
        if (constraint.kind == "leg" and constraint.target_identity in leg_ids)
        or (constraint.kind == "port" and constraint.arrival_name in arrival_names)
    )


def _candidate_only_shape(
    participant: Any, context: Any, now: dt.datetime, demand: Any
) -> dict[str, Any] | None:
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
    changes = sum(
        left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
    )
    matches = _matching(participant, nominal[0], state)
    kinds = frozenset(match.kind for match in matches)
    if changes != 1 or kinds != frozenset({"leg", "port"}):
        return None
    recovery = max((match.recovery for match in matches), default=None)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    if recovery is None or nominal_hours is None or detour_hours is None:
        return None
    hold_hours = max(0.0, (recovery - now).total_seconds() / 3600.0) + nominal_hours
    margin = detour_hours - hold_hours
    if not all(
        math.isfinite(value) and value > 0.0 for value in (hold_hours, detour_hours, margin)
    ):
        return None
    if margin <= 0.0:
        return None
    return {
        "nominal_edges": len(nominal),
        "safe_edges": len(safe),
        "route_changes": changes,
        "kinds": sorted(kinds),
        "timing_margin_hours": margin,
    }


def _v3_should_hold(participant: Any, context: Any, now: dt.datetime, shipment: Any) -> bool:
    """Frozen control oracle: the pre-v12 v3 route-change gate only."""
    state = participant._active_state(context, now)
    if state is None:
        return False
    graphs = participant._graphs(context, state)
    if graphs is None:
        return False
    origin = shipment.demand.origin_port
    destination = shipment.demand.destination_port
    nominal = participant._shortest_path(context, origin, destination, graphs[0])
    safe = participant._shortest_path(context, origin, destination, graphs[1])
    if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
        return False
    changes = sum(
        left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
    )
    if changes < 2:
        return False
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    if recovery is None or nominal_hours is None or detour_hours is None:
        return False
    hold_hours = max(0.0, (recovery - now).total_seconds() / 3600.0) + nominal_hours
    return hold_hours < detour_hours


def _snapshot(context: Any, shipment: Any) -> tuple[Any, ...]:
    ports = tuple(
        (
            id(port),
            tuple(
                (
                    id(berth),
                    getattr(berth, "index", None),
                    id(getattr(berth, "occupying_vessel", None))
                    if getattr(berth, "occupying_vessel", None) is not None
                    else None,
                    getattr(berth, "is_available", None),
                )
                for berth in port.berths
            ),
            tuple(id(leg) for leg in port.outgoing_legs),
            tuple(id(leg) for leg in port.incoming_legs),
            tuple(id(demand) for demand in port.outgoing_demands),
            tuple(id(demand) for demand in port.incoming_demands),
            tuple(id(item) for item in port.shipments_in_storage),
        )
        for port in context.ports
    )
    routes = tuple(
        (
            id(route),
            id(getattr(route, "source_service_route", None))
            if getattr(route, "source_service_route", None) is not None
            else None,
            repr(getattr(route, "disruption_key", None)),
            tuple(
                (
                    id(segment),
                    segment.sequence_index,
                    id(segment.associated_leg),
                    id(getattr(segment, "associated_service_route", None))
                    if getattr(segment, "associated_service_route", None) is not None
                    else None,
                    tuple(id(vessel) for vessel in segment.current_vessels),
                )
                for segment in route.segments
            ),
            tuple(id(vessel) for vessel in route.deployed_vessels),
            tuple(id(booking) for booking in route.associated_bookings),
        )
        for route in context.service_routes
    )
    vessels = tuple(
        (
            id(vessel),
            id(getattr(vessel, "assigned_service_route", None))
            if getattr(vessel, "assigned_service_route", None) is not None
            else None,
            id(getattr(vessel, "pending_assigned_service_route", None))
            if getattr(vessel, "pending_assigned_service_route", None) is not None
            else None,
            id(getattr(vessel, "current_segment", None))
            if getattr(vessel, "current_segment", None) is not None
            else None,
            id(getattr(vessel, "current_berth", None))
            if getattr(vessel, "current_berth", None) is not None
            else None,
            tuple(id(item) for item in vessel.carried_shipments),
        )
        for vessel in context.vessels
    )
    plans = tuple(
        (
            id(plan),
            id(getattr(plan, "target_leg", None)) if plan.target_leg is not None else None,
            id(getattr(plan, "target_berth", None)) if plan.target_berth is not None else None,
            plan.start_offset_days,
            plan.duration_days,
            plan.multiplier,
            plan.close_berth,
        )
        for plan in context.disruption_plans
    )
    shipment_state = (
        id(shipment),
        id(shipment.demand),
        id(getattr(shipment, "current_storage_port", None))
        if getattr(shipment, "current_storage_port", None) is not None
        else None,
        shipment.generated_time,
        shipment.completion_time,
        tuple(id(booking) for booking in shipment.associated_bookings),
        shipment.current_booking_index,
        id(getattr(shipment, "carrying_vessel", None))
        if getattr(shipment, "carrying_vessel", None) is not None
        else None,
    )
    return (
        tuple(id(port) for port in context.ports),
        tuple(id(demand) for demand in context.demands),
        tuple(id(route) for route in context.service_routes),
        tuple(id(route) for route in context.initial_service_routes),
        tuple(id(leg) for leg in context.legs),
        tuple(id(vessel) for vessel in context.vessels),
        tuple(id(plan) for plan in context.disruption_plans),
        ports,
        routes,
        vessels,
        plans,
        shipment_state,
    )


def _output_signature(path: Path) -> tuple[Any, ...]:
    data = path.read_bytes()
    stat = path.stat()
    return (hashlib.sha256(data).hexdigest(), stat.st_size, stat.st_mtime_ns)


def test_real_round1_finds_identity_free_mixed_one_transfer_candidate_only() -> None:
    source = _source_or_fail()
    _prepare_imports(source)
    import main  # type: ignore[import-not-found]  # noqa: F401, PLC0415
    import scenario_builders  # type: ignore[import-not-found]  # noqa: PLC0415
    from maritime_data_context.shipment import (
        Shipment,  # type: ignore[import-not-found]  # noqa: PLC0415
    )
    from response_strategies.default_strategy import (
        DefaultStrategy,  # type: ignore[import-not-found]  # noqa: PLC0415
    )

    participant = _load_participant()
    template = scenario_builders.create_with_disruption()
    times = _timestamps(template)
    assert len(times) == 50
    output_path = source / "Output" / "ATT_By_Statistics_Interval.csv"
    output_before = _output_signature(output_path)
    found = False

    for now in times:
        context = scenario_builders.create_with_disruption()
        DefaultStrategy.create_alternative_service_routes(context, now)
        for index, demand in enumerate(context.demands):
            shape = _candidate_only_shape(participant, context, now, demand)
            if shape is None:
                continue
            control_shipment = _shipment(Shipment, index, demand, now)
            control_before = _snapshot(context, control_shipment)
            assert _v3_should_hold(participant, context, now, control_shipment) is False
            assert _snapshot(context, control_shipment) == control_before

            candidate_shipment = _shipment(Shipment, index, demand, now)
            candidate_before = _snapshot(context, candidate_shipment)
            # RED: untouched v3 delegates; v12 must return exact False.
            assert (
                participant.UserStrategy.assign_associated_bookings(
                    context, now, candidate_shipment
                )
                is False
            )
            assert _snapshot(context, candidate_shipment) == candidate_before
            assert shape["nominal_edges"] == 1
            assert shape["safe_edges"] >= 2
            assert shape["route_changes"] == 1
            assert shape["kinds"] == ["leg", "port"]
            assert shape["timing_margin_hours"] > 0.0
            found = True
            break
        if found:
            break

    assert found, "no identity-free mixed one-transfer candidate-only case was derived"
    assert _output_signature(output_path) == output_before
