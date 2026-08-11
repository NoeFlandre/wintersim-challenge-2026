"""Real Round 1 activation contract for the v6 congestion-hold extension."""

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


def _source_or_skip() -> Path:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip("Round 1 organizer source is unavailable")
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
    spec = importlib.util.spec_from_file_location("wsc_round1_v6_participant", participant_file)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _times(context: Any) -> tuple[dt.datetime, ...]:
    values: list[dt.datetime] = []
    for plan in context.disruption_plans:
        start = getattr(plan, "start_offset_days", None)
        duration = getattr(plan, "duration_days", None)
        if (
            isinstance(start, (int, float))
            and not isinstance(start, bool)
            and math.isfinite(start)
            and isinstance(duration, (int, float))
            and not isinstance(duration, bool)
            and math.isfinite(duration)
            and duration > 0
        ):
            first = math.ceil(start)
            last = math.floor(start + duration - 1e-12)
            values.extend(
                dt.datetime.min + dt.timedelta(days=day + 0.5) for day in range(first, last + 1)
            )
    return tuple(sorted(set(values)))


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
                tuple(map(id, route.segments)),
                tuple(map(id, route.deployed_vessels)),
                tuple(map(id, route.associated_bookings)),
            )
            for route in context.service_routes
        ),
        tuple(
            (
                id(vessel),
                id(getattr(vessel, "assigned_service_route", None)),
                id(getattr(vessel, "pending_assigned_service_route", None)),
                id(getattr(vessel, "current_segment", None)),
                id(getattr(vessel, "current_berth", None)),
                tuple(map(id, vessel.carried_shipments)),
            )
            for vessel in context.vessels
        ),
        (
            id(shipment),
            tuple(map(id, shipment.associated_bookings)),
            shipment.current_booking_index,
        ),
    )


def _qualifies(participant: Any, context: Any, now: dt.datetime, demand: Any) -> bool:
    state = participant._active_state(context, now)
    if state is None:
        return False
    graphs = participant._graphs(context, state)
    if graphs is None:
        return False
    nominal = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[0]
    )
    safe = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[1]
    )
    if nominal is None or safe is None or len(nominal) != 1 or len(nominal[0].legs) < 2:
        return False
    route_changes = sum(
        left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
    )
    if route_changes != 1:
        return False
    leg_ids = {id(leg) for leg in nominal[0].legs}
    arrival_names = {
        participant._port_name(port)
        for port in (*nominal[0].intermediate_ports, nominal[0].arrival)
    }
    matching_kinds = {
        constraint.kind
        for constraint in state.constraints
        if constraint.target_identity in leg_ids or constraint.arrival_name in arrival_names
    }
    if matching_kinds != {"leg"}:
        return False
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    if recovery is None or nominal_hours is None or detour_hours is None:
        return False
    hold_hours = max(0.0, (recovery - now).total_seconds() / 3600.0) + nominal_hours
    return hold_hours < detour_hours


def test_real_round1_v6_has_candidate_only_activation_without_mutation() -> None:
    source = _source_or_skip()
    _prepare_imports(source)

    import main  # type: ignore[import-not-found]  # noqa: F401, PLC0415
    import scenario_builders  # type: ignore[import-not-found]  # noqa: PLC0415
    from maritime_data_context.shipment import (
        Shipment,  # type: ignore[import-not-found]  # noqa: PLC0415
    )
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]  # noqa: PLC0415
        DefaultStrategy,
    )

    participant = _load_participant()
    template = scenario_builders.create_with_disruption()
    found = False
    for now in _times(template):
        context = scenario_builders.create_with_disruption()
        DefaultStrategy.create_alternative_service_routes(context, now)
        for index, demand in enumerate(context.demands):
            if not _qualifies(participant, context, now, demand):
                continue
            shipment = Shipment(
                index=index,
                teu_size=1,
                demand=demand,
                current_storage_port=demand.origin_port,
                generated_time=now,
            )
            before = _snapshot(context, shipment)
            assert (
                participant.UserStrategy.assign_associated_bookings(context, now, shipment) is False
            )
            assert _snapshot(context, shipment) == before
            found = True
            break
        if found:
            break

    assert found, "v6 candidate-only pure-leg multi-leg activation was not found"
