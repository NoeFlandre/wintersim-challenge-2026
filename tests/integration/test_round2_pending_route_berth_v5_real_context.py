"""Real Round 2 object contract for pending-route berth activation v5."""

from __future__ import annotations

import datetime as dt
import importlib.util
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
        if any(module_name == p or module_name.startswith(f"{p}.") for p in prefixes):
            sys.modules.pop(module_name, None)


def _load_participant() -> Any:
    path = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("round2_v5_participant", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _midpoint(plan: Any) -> dt.datetime:
    return dt.datetime.min + dt.timedelta(
        days=float(plan.start_offset_days) + float(plan.duration_days) / 2.0
    )


def _snapshot(context: Any) -> tuple[Any, ...]:
    return (
        tuple(
            (
                id(route),
                id(getattr(route, "source_service_route", None)),
                repr(getattr(route, "disruption_key", None)),
                tuple(map(id, getattr(route, "segments", ()))),
                tuple(map(id, getattr(route, "deployed_vessels", ()))),
            )
            for route in context.service_routes
        ),
        tuple(
            (
                id(vessel),
                id(getattr(vessel, "assigned_service_route", None)),
                id(getattr(vessel, "pending_assigned_service_route", None)),
                tuple(map(id, getattr(vessel, "carried_shipments", ()))),
            )
            for vessel in context.vessels
        ),
    )


def test_real_round2_pending_route_selection_is_live_and_read_only() -> None:
    source = _source_or_skip()
    _prepare_imports(source)

    import main  # type: ignore[import-not-found]  # noqa: F401, PLC0415
    import scenario_builders  # type: ignore[import-not-found]  # noqa: PLC0415
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )

    participant = _load_participant()
    template = scenario_builders.create_with_disruption()
    closure = next(
        plan for plan in template.disruption_plans if getattr(plan, "close_berth", False)
    )
    now = _midpoint(closure)
    context = scenario_builders.create_with_disruption()
    DefaultStrategy.create_alternative_service_routes(context, now)

    pending_vessels = [
        vessel
        for vessel in context.vessels
        if getattr(vessel, "pending_assigned_service_route", None) is not None
        and not getattr(vessel, "carried_shipments", ())
    ]
    assert pending_vessels, "real Round 2 closure must reserve a pending vessel"
    pending = pending_vessels[0]
    pending_route = pending.pending_assigned_service_route
    first_segment = min(pending_route.segments, key=lambda segment: segment.sequence_index)
    port = first_segment.associated_leg.departure_port
    ordinary = next(
        vessel
        for vessel in context.vessels
        if vessel is not pending
        and not getattr(vessel, "carried_shipments", ())
        and getattr(vessel, "pending_assigned_service_route", None) is None
        and vessel.assigned_service_route.segments[0].associated_leg.departure_port is port
    )
    before = _snapshot(context)
    result = participant.UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=[ordinary, pending],
        available_berths=list(getattr(port, "berths", ()))[:1],
        current_time=now,
        waiting_since_by_vessel=None,
    )
    assert result is pending
    assert result in (ordinary, pending)
    assert _snapshot(context) == before

