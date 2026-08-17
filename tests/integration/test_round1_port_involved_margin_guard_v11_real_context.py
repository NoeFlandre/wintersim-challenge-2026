"""Real-context activation contract for the Round 1 v11 margin guard."""

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
        "wsc_round1_port_involved_margin_guard_v11_participant", participant_file
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(value: Any) -> int | None:
    return None if value is None else id(value)


def _snapshot(context: Any, shipment: Any) -> tuple[Any, ...]:
    return (
        tuple(map(id, context.ports)),
        tuple(map(id, context.demands)),
        tuple(map(id, context.service_routes)),
        tuple(map(id, context.initial_service_routes)),
        tuple(map(id, context.legs)),
        tuple(map(id, context.vessels)),
        tuple(map(id, context.disruption_plans)),
        tuple(
            (
                id(route),
                _identity(getattr(route, "source_service_route", None)),
                repr(getattr(route, "disruption_key", None)),
                tuple(map(id, route.segments)),
                tuple(map(id, route.deployed_vessels)),
                tuple(map(id, route.associated_bookings)),
            )
            for route in context.service_routes
        ),
        tuple(
            (
                id(plan),
                _identity(getattr(plan, "target_leg", None)),
                _identity(getattr(plan, "target_berth", None)),
                plan.start_offset_days,
                plan.duration_days,
                plan.multiplier,
                plan.close_berth,
            )
            for plan in context.disruption_plans
        ),
        (
            id(shipment),
            tuple(map(id, getattr(shipment, "associated_bookings", ()))),
            getattr(shipment, "current_booking_index", None),
        ),
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


def _matches_port_constraint(edge: Any, state: Any) -> bool:
    arrival_names = {
        getattr(port, "name", "").casefold()
        for port in (*edge.intermediate_ports, edge.arrival)
        if isinstance(getattr(port, "name", None), str)
    }
    return any(
        constraint.kind == "port" and constraint.arrival_name in arrival_names
        for constraint in state.constraints
    )


def test_real_round1_v11_delegates_only_low_margin_port_holds() -> None:
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
    assert times, "real Round 1 context must expose active disruption windows"

    found_low_margin = False
    found_retained = False
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
            state = participant._active_state(context, now)
            graphs = None if state is None else participant._graphs(context, state)
            if state is None or graphs is None:
                continue
            nominal = participant._shortest_path(
                context, demand.origin_port, demand.destination_port, graphs[0]
            )
            safe = participant._shortest_path(
                context, demand.origin_port, demand.destination_port, graphs[1]
            )
            if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
                continue
            route_changes = sum(
                left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
            )
            if route_changes < 2 or not _matches_port_constraint(nominal[0], state):
                continue
            recovery = participant._edge_constraint_recovery(nominal[0], state)
            nominal_hours = participant._path_service_hours(nominal)
            detour_hours = participant._path_service_hours(safe)
            first_profile = participant._route_profile(safe[0].route)
            if recovery is None or nominal_hours is None or detour_hours is None:
                continue
            if first_profile is None:
                continue
            hold_hours = max(0.0, (recovery - now).total_seconds() / 3600.0) + nominal_hours
            if not hold_hours < detour_hours:
                continue
            before = _snapshot(context, shipment)
            decision = participant.UserStrategy.assign_associated_bookings(context, now, shipment)
            after = _snapshot(context, shipment)
            assert after == before, "v11 decision mutated the real Round 1 state"
            if detour_hours - hold_hours < first_profile.headway_hours:
                assert decision is None
                found_low_margin = True
            else:
                assert decision is False
                found_retained = True
            if found_low_margin and found_retained:
                return

    assert found_low_margin, "no real low-margin port-involved v3 hold was activated"
    assert found_retained, "no real high-margin port-involved v3 hold was retained"
