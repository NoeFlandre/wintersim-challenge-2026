"""Real Round 1 context gate for the recovery-aware origin hold."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.integration


def _source() -> Path:
    return Path(__file__).parents[2] / ".challenge" / "round1" / "source"


def _load_participant() -> type:
    path = Path(__file__).parents[2] / "submission" / "response_strategies" / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("round1_participant_hold", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load participant strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def _prepare_runtime(source: Path) -> None:
    for path in (str(source), str(source / "o2despy")):
        if path not in sys.path:
            sys.path.insert(0, path)
    prefixes = (
        "response_strategies",
        "scenario_builders",
        "simulation_model",
        "maritime_data_context",
        "config",
        "o2des",
    )
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)


def _snapshot(context) -> tuple:
    return (
        tuple(context.ports),
        tuple(context.legs),
        tuple(context.service_routes),
        tuple(context.vessels),
        tuple(context.disruption_plans),
        tuple(
            (vessel, vessel.assigned_service_route, vessel.pending_assigned_service_route)
            for vessel in context.vessels
        ),
    )


def test_real_round1_active_nominal_congestion_can_hold_without_mutation() -> None:
    source = _source()
    if not source.is_dir():
        pytest.skip(f"Round 1 source not bootstrapped at {source}")
    _prepare_runtime(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    UserStrategy = _load_participant()
    held_case = None
    for target_plan in context.disruption_plans:
        target_leg = getattr(target_plan, "target_leg", None)
        if target_leg is None or target_plan.multiplier <= 1.0:
            continue
        for demand in context.demands:
            if (
                demand.origin_port is not target_leg.departure_port
                or demand.destination_port is not target_leg.arrival_port
            ):
                continue
            shipment = SimpleNamespace(
                demand=demand,
                associated_bookings=[],
                current_booking_index=None,
            )
            now = dt.datetime.min + dt.timedelta(
                days=target_plan.start_offset_days + target_plan.duration_days - 0.01
            )
            before = _snapshot(context)
            result = UserStrategy.assign_associated_bookings(context, now, shipment)
            if result is False:
                held_case = (before, shipment)
                break
        if held_case is not None:
            break

    assert held_case is not None, (
        "the real Round 1 scenario must expose at least one active congestion "
        "case where recovery-aware holding is faster than the safe detour"
    )
    before, shipment = held_case
    assert _snapshot(context) == before
    assert shipment.associated_bookings == []
    assert shipment.current_booking_index is None
