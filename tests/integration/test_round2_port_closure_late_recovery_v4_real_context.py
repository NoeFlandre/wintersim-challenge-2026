"""Real Round 2 contract for the late-recovery refinement."""

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


def _source_or_skip() -> Path:
    source = round_source_dir("round2")
    if not source.is_dir():
        pytest.skip("Round 2 organizer source is not bootstrapped")
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
    path = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_round2_late_recovery_v4", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _midpoints(context: Any) -> tuple[dt.datetime, ...]:
    values: list[dt.datetime] = []
    for plan in context.disruption_plans:
        if (
            getattr(plan, "close_berth", None) is not True
            or getattr(plan, "target_berth", None) is None
            or getattr(plan, "target_leg", None) is not None
        ):
            continue
        start_days = getattr(plan, "start_offset_days", None)
        duration_days = getattr(plan, "duration_days", None)
        if (
            isinstance(start_days, bool)
            or not isinstance(start_days, (int, float))
            or not math.isfinite(float(start_days))
            or isinstance(duration_days, bool)
            or not isinstance(duration_days, (int, float))
            or not math.isfinite(float(duration_days))
            or duration_days <= 0
        ):
            continue
        start = dt.datetime.min + dt.timedelta(days=float(start_days))
        end = start + dt.timedelta(days=float(duration_days))
        for day in range(
            math.floor(float(start_days)), math.ceil(float(start_days + duration_days))
        ):
            midpoint = dt.datetime.min + dt.timedelta(days=day + 0.5)
            if start <= midpoint < end:
                values.append(midpoint)
    return tuple(dict.fromkeys(values))


def _identity(value: Any) -> int | None:
    return None if value is None else id(value)


def _signature(context: Any, shipment: Any) -> tuple[Any, ...]:
    routes = tuple(
        (
            id(route),
            _identity(getattr(route, "source_service_route", None)),
            repr(getattr(route, "disruption_key", None)),
            tuple(map(id, getattr(route, "segments", ()))),
            tuple(map(id, getattr(route, "deployed_vessels", ()))),
            tuple(map(id, getattr(route, "associated_bookings", ()))),
        )
        for route in context.service_routes
    )
    vessels = tuple(
        (
            id(vessel),
            _identity(getattr(vessel, "assigned_service_route", None)),
            _identity(getattr(vessel, "pending_assigned_service_route", None)),
            _identity(getattr(vessel, "current_segment", None)),
            _identity(getattr(vessel, "current_berth", None)),
            tuple(map(id, getattr(vessel, "carried_shipments", ()))),
        )
        for vessel in context.vessels
    )
    plans = tuple(
        (
            id(plan),
            _identity(getattr(plan, "target_leg", None)),
            _identity(getattr(plan, "target_berth", None)),
            getattr(plan, "start_offset_days", None),
            getattr(plan, "duration_days", None),
            getattr(plan, "multiplier", None),
            getattr(plan, "close_berth", None),
        )
        for plan in context.disruption_plans
    )
    shipment_state = (
        id(shipment),
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
        tuple(map(id, context.service_routes)),
        tuple(map(id, context.legs)),
        tuple(map(id, context.vessels)),
        tuple(map(id, context.disruption_plans)),
        routes,
        vessels,
        plans,
        shipment_state,
    )


def _output_signature(path: Path) -> tuple[bool, int, str | None, int | None]:
    if not path.exists():
        return False, 0, None, None
    data = path.read_bytes()
    return True, len(data), hashlib.sha256(data).hexdigest(), path.stat().st_mtime_ns


def _control_details(
    participant: Any, context: Any, now: Any, shipment: Any
) -> tuple[bool, float, float]:
    demand = shipment.demand
    state = participant._active_state(context, now)
    if state is None:
        return False, 0.0, 0.0
    graphs = participant._graphs(context, state)
    if graphs is None:
        return False, 0.0, 0.0
    nominal = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[0]
    )
    safe = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[1]
    )
    if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
        return False, 0.0, 0.0
    changes = sum(
        left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
    )
    matching = participant._matching_constraints(nominal[0], state)
    if changes != 1 or {item.kind for item in matching} != {"port"}:
        return False, 0.0, 0.0
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    headway = participant._max_path_headway(safe)
    if recovery is None or nominal_hours is None or detour_hours is None or headway is None:
        return False, 0.0, 0.0
    wait_hours = max(0.0, (recovery - now).total_seconds() / 3600.0)
    margin = detour_hours - (wait_hours + nominal_hours)
    if not math.isfinite(margin) or margin <= headway:
        return False, wait_hours, headway
    return True, wait_hours, headway


def test_real_round2_late_recovery_guard_diverges_without_mutation() -> None:
    source = _source_or_skip()
    _prepare_imports(source)

    import main  # type: ignore[import-not-found]  # noqa: F401, PLC0415
    import scenario_builders  # type: ignore[import-not-found]  # noqa: PLC0415
    from maritime_data_context.shipment import Shipment  # type: ignore[import-not-found]
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )

    participant = _load_participant()
    template = scenario_builders.create_with_disruption()
    times = _midpoints(template)
    assert times, "the real Round 2 scenario must expose port-closure windows"
    output = source / "Output" / "ATT_By_Statistics_Interval.csv"
    output_before = _output_signature(output)
    found_early = False
    found_late = False

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
            before = _signature(context, shipment)
            control, wait_hours, headway = _control_details(participant, context, now, shipment)
            if not control:
                continue
            decision = participant.UserStrategy.assign_associated_bookings(context, now, shipment)
            assert _signature(context, shipment) == before
            if wait_hours < headway:
                assert decision is False
                found_late = True
            else:
                assert decision is None
                found_early = True
            if found_early and found_late:
                break
        if found_early and found_late:
            break

    assert found_early, "real context must exercise a control-only early recovery case"
    assert found_late, "real context must retain a late-recovery control hold"
    assert _output_signature(output) == output_before
