"""Real Round 2 contract for the v9 pure-leg half-headway guard."""

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
        pytest.skip("Round 2 organizer source is unavailable")
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
    spec = importlib.util.spec_from_file_location("wsc_round2_v9_participant", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot(context: Any, shipment: Any) -> tuple[Any, ...]:
    return (
        tuple(map(id, getattr(context, "ports", ()))),
        tuple(map(id, getattr(context, "demands", ()))),
        tuple(map(id, getattr(context, "service_routes", ()))),
        tuple(map(id, getattr(context, "legs", ()))),
        tuple(map(id, getattr(context, "vessels", ()))),
        tuple(
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
        ),
        tuple(
            (
                id(plan),
                id(getattr(plan, "target_leg", None)),
                id(getattr(plan, "target_berth", None)),
                getattr(plan, "start_offset_days", None),
                getattr(plan, "duration_days", None),
                getattr(plan, "multiplier", None),
                getattr(plan, "close_berth", None),
            )
            for plan in getattr(context, "disruption_plans", ())
        ),
        (
            id(shipment),
            id(getattr(shipment, "demand", None)),
            tuple(map(id, getattr(shipment, "associated_bookings", ()))),
            getattr(shipment, "current_booking_index", None),
            getattr(shipment, "completion_time", None),
            id(getattr(shipment, "carrying_vessel", None)),
        ),
    )


def _pure_leg_profile(
    participant: Any, context: Any, now: dt.datetime, demand: Any
) -> tuple[bool, float, float]:
    state = participant._active_state(context, now)
    if state is None:
        return False, math.nan, math.nan
    graphs = participant._graphs(context, state)
    if graphs is None:
        return False, math.nan, math.nan
    nominal = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[0]
    )
    safe = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[1]
    )
    if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
        return False, math.nan, math.nan
    changes = sum(
        left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
    )
    matching = participant._matching_constraints(nominal[0], state)
    if changes < 2 or {item.kind for item in matching} != {"leg"}:
        return False, math.nan, math.nan
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    max_headway = participant._max_path_headway(safe)
    if recovery is None or nominal_hours is None or detour_hours is None or max_headway is None:
        return False, math.nan, math.nan
    hold_hours = max(0.0, (recovery - now).total_seconds() / 3600.0) + nominal_hours
    margin = detour_hours - hold_hours
    return math.isfinite(margin) and margin > 0.0, margin, max_headway


def test_real_round2_v9_changes_only_marginal_high_teu_pure_leg_hold() -> None:
    source = _source_or_skip()
    _prepare_imports(source)

    import main  # type: ignore[import-not-found]  # noqa: F401, PLC0415
    import scenario_builders  # type: ignore[import-not-found]  # noqa: PLC0415
    from maritime_data_context.shipment import Shipment  # type: ignore[import-not-found]
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )

    participant = _load_participant()
    values = sorted(
        float(demand.annual_teus) for demand in scenario_builders.create_with_disruption().demands
    )
    threshold = values[(3 * (len(values) - 1)) // 4]
    weak: tuple[Any, Any, Any] | None = None
    strong: tuple[Any, Any, Any] | None = None
    for now in (
        dt.datetime.min + dt.timedelta(days=336.5),
        dt.datetime.min + dt.timedelta(days=337.5),
        dt.datetime.min + dt.timedelta(days=338.5),
        dt.datetime.min + dt.timedelta(days=339.5),
    ):
        context = scenario_builders.create_with_disruption()
        DefaultStrategy.create_alternative_service_routes(context, now)
        for demand in context.demands:
            if float(demand.annual_teus) < threshold:
                continue
            active, margin, headway = _pure_leg_profile(participant, context, now, demand)
            if not active:
                continue
            if margin <= 0.5 * headway and weak is None:
                weak = context, now, demand
            if margin > 0.5 * headway and strong is None:
                strong = context, now, demand
    assert weak is not None and strong is not None

    for context, now, demand in (weak, strong):
        shipment = Shipment(
            index=context.demands.index(demand),
            teu_size=1,
            demand=demand,
            current_storage_port=demand.origin_port,
            generated_time=now,
        )
        before = _snapshot(context, shipment)
        result = participant.UserStrategy.assign_associated_bookings(context, now, shipment)
        expected = None if context is weak[0] else False
        assert result is expected
        assert _snapshot(context, shipment) == before
