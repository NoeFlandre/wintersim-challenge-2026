"""Real Round 0 validation for the participant recovery shuttle."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration
SOURCE = round_source_dir("round0")


def load_participant_strategy():
    path = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_safe_shuttle_candidate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def test_real_round0_builds_valid_idempotent_recovery_shuttle() -> None:
    if not SOURCE.is_dir():
        pytest.skip("Round 0 source is not bootstrapped")
    source = str(SOURCE)
    o2des = str(SOURCE / "o2despy")
    sys.path.insert(0, source)
    sys.path.insert(0, o2des)
    prefixes = (
        "response_strategies",
        "scenario_builders",
        "simulation_model",
        "maritime_data_context",
        "config",
        "o2despy",
        "o2des",
    )
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)

    import scenario_builders  # type: ignore[import-not-found]
    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )
    from response_strategies.strategy_validation import (  # type: ignore[import-not-found]
        capture_alternative_route_strategy_state,
        validate_alternative_route_strategy_result,
    )

    context = scenario_builders.create_with_disruption()
    strategy = load_participant_strategy()
    plan = context.disruption_plans[0]
    active_now = dt.datetime.min + dt.timedelta(days=plan.start_offset_days, seconds=1)
    assert is_disruption_active(context, active_now)
    original_legs = tuple(context.legs)
    snapshot = capture_alternative_route_strategy_state(context)

    assert strategy.create_alternative_service_routes(context, active_now) is True
    validate_alternative_route_strategy_result(context, snapshot)
    shuttles = [
        route
        for route in context.service_routes
        if getattr(route, "is_participant_recovery_shuttle", False)
    ]
    assert shuttles
    assert all(
        segment.associated_leg in original_legs for route in shuttles for segment in route.segments
    )
    assert all(
        [segment.sequence_index for segment in route.segments]
        == list(range(1, len(route.segments) + 1))
        for route in shuttles
    )

    identities = [id(route) for route in shuttles]
    assert strategy.create_alternative_service_routes(context, active_now) is True
    assert [
        id(route)
        for route in context.service_routes
        if getattr(route, "is_participant_recovery_shuttle", False)
    ] == identities
