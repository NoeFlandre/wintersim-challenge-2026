"""Real Round 2 contract for the v10 one-transfer pure-leg extension."""

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
    participant_file = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_round2_v10_participant", participant_file)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    return (
        tuple(map(id, getattr(context, "ports", ()))),
        tuple(map(id, getattr(context, "demands", ()))),
        tuple(map(id, getattr(context, "service_routes", ()))),
        tuple(map(id, getattr(context, "vessels", ()))),
        routes,
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
            id(getattr(shipment, "current_storage_port", None)),
            tuple(map(id, getattr(shipment, "associated_bookings", ()))),
            getattr(shipment, "current_booking_index", None),
            getattr(shipment, "completion_time", None),
            id(getattr(shipment, "carrying_vessel", None)),
        ),
    )


def _is_pure_leg_one_transfer(
    participant: Any, context: Any, now: dt.datetime, demand: Any
) -> bool:
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
    if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
        return False
    changes = sum(
        left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
    )
    if changes != 1 or {
        item.kind for item in participant._matching_constraints(nominal[0], state)
    } != {"leg"}:
        return False
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    return (
        recovery is not None
        and nominal_hours is not None
        and detour_hours is not None
        and math.isfinite(
            detour_hours - (max(0.0, (recovery - now).total_seconds() / 3600.0) + nominal_hours)
        )
        and detour_hours > max(0.0, (recovery - now).total_seconds() / 3600.0) + nominal_hours
    )


def test_real_v10_holds_high_teu_and_delegates_lower_teu() -> None:
    source = _bootstrap_or_skip()
    _prepare_imports(source)

    import main  # type: ignore[import-not-found]  # noqa: F401, PLC0415
    import scenario_builders  # type: ignore[import-not-found]  # noqa: PLC0415
    from maritime_data_context.shipment import Shipment  # type: ignore[import-not-found]
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )

    participant = _load_participant()
    context = scenario_builders.create_with_disruption()
    values = sorted(float(demand.annual_teus) for demand in context.demands)
    threshold = values[(3 * (len(values) - 1)) // 4]
    assert math.isfinite(threshold) and threshold == 1801.0

    now = dt.datetime(1, 8, 28, 12)
    DefaultStrategy.create_alternative_service_routes(context, now)
    high = context.demands[54]  # Shenzhen -> New Jersey, 3,767 TEU
    low = context.demands[35]  # Singapore -> New Jersey, 1,570 TEU
    assert high.annual_teus >= threshold > low.annual_teus
    assert _is_pure_leg_one_transfer(participant, context, now, high)
    assert _is_pure_leg_one_transfer(participant, context, now, low)

    for index, demand, expected in ((54, high, False), (35, low, None)):
        shipment = Shipment(
            index=index,
            teu_size=1,
            demand=demand,
            current_storage_port=demand.origin_port,
            generated_time=now,
        )
        before = _snapshot(context, shipment)
        assert (
            participant.UserStrategy.assign_associated_bookings(context, now, shipment) is expected
        )
        assert _snapshot(context, shipment) == before
