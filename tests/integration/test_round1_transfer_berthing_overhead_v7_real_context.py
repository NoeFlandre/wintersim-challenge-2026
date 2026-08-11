"""Real Round 1 activation contract for transfer-berthing overhead v7."""

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


def _load_participant() -> Any:
    path = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_round1_transfer_v7", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)


def _times(context: Any) -> tuple[dt.datetime, ...]:
    values: list[dt.datetime] = []
    for plan in context.disruption_plans:
        start = getattr(plan, "start_offset_days", None)
        duration = getattr(plan, "duration_days", None)
        if (
            not isinstance(start, (int, float))
            or isinstance(start, bool)
            or not math.isfinite(start)
            or not isinstance(duration, (int, float))
            or isinstance(duration, bool)
            or not math.isfinite(duration)
            or duration <= 0
        ):
            continue
        for day in range(math.ceil(start), math.floor(start + duration)):
            values.append(dt.datetime.min + dt.timedelta(days=day + 0.5))
    return tuple(sorted(set(values)))


def _snapshot(context: Any, shipment: Any) -> tuple[Any, ...]:
    return (
        tuple(id(port) for port in context.ports),
        tuple(
            (
                id(route),
                id(getattr(route, "source_service_route", None)),
                repr(getattr(route, "disruption_key", None)),
                tuple(id(segment) for segment in route.segments),
                tuple(id(vessel) for vessel in route.deployed_vessels),
                tuple(id(booking) for booking in route.associated_bookings),
            )
            for route in context.service_routes
        ),
        tuple(id(vessel) for vessel in context.vessels),
        tuple(
            (
                id(plan),
                id(getattr(plan, "target_leg", None)),
                id(getattr(plan, "target_berth", None)),
                plan.start_offset_days,
                plan.duration_days,
                plan.multiplier,
                plan.close_berth,
            )
            for plan in context.disruption_plans
        ),
        (
            id(shipment),
            tuple(id(booking) for booking in shipment.associated_bookings),
            shipment.current_booking_index,
            id(getattr(shipment, "current_storage_port", None)),
            id(getattr(shipment, "carrying_vessel", None)),
        ),
    )


def test_real_context_exposes_candidate_only_marginal_transfer_holds() -> None:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip("Round 1 organizer source is unavailable")
    _prepare_imports(source)

    import main  # noqa: F401, PLC0415
    import scenario_builders  # type: ignore[import-not-found]  # noqa: PLC0415
    from maritime_data_context.shipment import (
        Shipment,  # type: ignore[import-not-found]  # noqa: PLC0415
    )
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]  # noqa: PLC0415
        DefaultStrategy,
    )

    participant = _load_participant()
    template = scenario_builders.create_with_disruption()
    candidate_only = 0

    for now in _times(template):
        context = scenario_builders.create_with_disruption()
        DefaultStrategy.create_alternative_service_routes(context, now)
        state = participant._active_state(context, now)
        assert state is not None
        graphs = participant._graphs(context, state)
        assert graphs is not None

        for index, demand in enumerate(context.demands):
            shipment = Shipment(
                index=index,
                teu_size=1,
                demand=demand,
                current_storage_port=demand.origin_port,
                generated_time=now,
            )
            nominal = participant._shortest_path(
                context, demand.origin_port, demand.destination_port, graphs[0]
            )
            safe = participant._shortest_path(
                context, demand.origin_port, demand.destination_port, graphs[1]
            )
            if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
                continue
            changes = sum(
                left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
            )
            if changes < 2:
                continue
            recovery = participant._edge_constraint_recovery(nominal[0], state)
            nominal_hours = participant._path_service_hours(nominal)
            detour_hours = participant._path_service_hours(safe)
            if recovery is None or nominal_hours is None or detour_hours is None:
                continue
            hold_hours = max(0.0, (recovery - now).total_seconds() / 3600.0) + nominal_hours
            v3_would_hold = hold_hours < detour_hours
            before = _snapshot(context, shipment)
            decision = participant.UserStrategy.assign_associated_bookings(context, now, shipment)
            assert _snapshot(context, shipment) == before
            if decision is False and not v3_would_hold:
                candidate_only += 1

    assert candidate_only > 0, "v7 is dormant in the real Round 1 context"
