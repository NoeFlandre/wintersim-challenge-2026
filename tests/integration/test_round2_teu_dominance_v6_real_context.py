"""Real Round 2 activation contract for the v6 TEU guard."""

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
    participant_file = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_round2_teu_dominance_v6", participant_file)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _timestamps(context: Any) -> tuple[dt.datetime, ...]:
    values: list[dt.datetime] = []
    for plan in context.disruption_plans:
        start_days = getattr(plan, "start_offset_days", None)
        duration_days = getattr(plan, "duration_days", None)
        if not isinstance(start_days, (int, float)) or isinstance(start_days, bool):
            continue
        if not isinstance(duration_days, (int, float)) or isinstance(duration_days, bool):
            continue
        if not math.isfinite(start_days) or not math.isfinite(duration_days) or duration_days <= 0:
            continue
        start = dt.datetime.min + dt.timedelta(days=start_days)
        end = start + dt.timedelta(days=duration_days)
        for day in range(math.floor(start_days), math.ceil(start_days + duration_days)):
            midpoint = dt.datetime.min + dt.timedelta(days=day + 0.5)
            if start <= midpoint < end:
                values.append(midpoint)
    return tuple(dict.fromkeys(values))


def _snapshot(context: Any, shipment: Any) -> tuple[Any, ...]:
    routes = tuple(
        (
            id(route),
            id(getattr(route, "source_service_route", None)),
            repr(getattr(route, "disruption_key", None)),
            tuple(
                (
                    id(segment),
                    getattr(segment, "sequence_index", None),
                    id(getattr(segment, "associated_leg", None)),
                    tuple(map(id, getattr(segment, "current_vessels", ()))),
                )
                for segment in getattr(route, "segments", ())
            ),
            tuple(map(id, getattr(route, "deployed_vessels", ()))),
            tuple(map(id, getattr(route, "associated_bookings", ()))),
        )
        for route in getattr(context, "service_routes", ())
    )
    vessels = tuple(
        (
            id(vessel),
            id(getattr(vessel, "assigned_service_route", None)),
            id(getattr(vessel, "pending_assigned_service_route", None)),
            id(getattr(vessel, "current_segment", None)),
            tuple(map(id, getattr(vessel, "carried_shipments", ()))),
        )
        for vessel in getattr(context, "vessels", ())
    )
    shipment_state = (
        id(shipment),
        tuple(map(id, getattr(shipment, "associated_bookings", ()))),
        getattr(shipment, "current_booking_index", None),
        id(getattr(shipment, "carrying_vessel", None)),
    )
    return (
        tuple(map(id, getattr(context, "service_routes", ()))),
        routes,
        vessels,
        tuple(map(id, getattr(context, "demands", ()))),
        shipment_state,
    )


def _accepted_v1_shape(participant: Any, context: Any, now: dt.datetime, demand: Any) -> bool:
    state = participant._active_state(context, now)
    if state is None or not state.closed_port_names or state.congested_leg_keys:
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
    if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
        return False
    changes = sum(
        left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
    )
    if changes != 1:
        return False
    matching = participant._matching_constraints(nominal[0], state)
    if not matching or {constraint.kind for constraint in matching} != {"port"}:
        return False
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    max_headway = participant._max_path_headway(safe)
    if recovery is None or nominal_hours is None or detour_hours is None or max_headway is None:
        return False
    wait_hours = max(0.0, (recovery - now).total_seconds() / 3600.0)
    margin = detour_hours - (wait_hours + nominal_hours)
    return math.isfinite(margin) and margin > max_headway


def test_real_round2_context_has_high_volume_activation_and_low_volume_delegate() -> None:
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
    timestamps = _timestamps(template)
    assert timestamps
    high_activation = False
    low_delegate = False

    for now in timestamps:
        context = scenario_builders.create_with_disruption()
        DefaultStrategy.create_alternative_service_routes(context, now)
        for index, demand in enumerate(context.demands):
            if not _accepted_v1_shape(participant, context, now, demand):
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
            assert _snapshot(context, shipment) == before
            if decision is False:
                high_activation = True
            elif decision is None:
                low_delegate = True
        if high_activation and low_delegate:
            break

    assert high_activation, "v6 must activate for at least one real upper-quartile demand"
    assert low_delegate, "v6 must delegate at least one real lower-volume control case"
