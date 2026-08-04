"""Real Round 1 context check for the progress-first berth policy."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _source_or_skip() -> Path:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip(
            f"Round 1 source not bootstrapped at {source}; run the private bootstrap first."
        )
    return source


def _prepare_organizer_imports(source: Path) -> None:
    for path in (str(source), str(source / "o2despy")):
        if path not in sys.path:
            sys.path.insert(0, path)
    prefixes = (
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


def _load_participant_strategy() -> type:
    participant_file = submission_strategies_dir() / "user_strategy.py"
    if not participant_file.is_file():
        pytest.fail(f"participant user_strategy.py missing at {participant_file}")
    package_name = "wsc_round1_participant_response_strategies"
    for name in list(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)
    package_spec = importlib.util.spec_from_loader(package_name, loader=None, is_package=True)
    if package_spec is None:
        pytest.fail("could not create participant package spec")
    package = importlib.util.module_from_spec(package_spec)
    package.__path__ = [str(participant_file.parent)]  # type: ignore[attr-defined]
    sys.modules[package_name] = package
    spec = importlib.util.spec_from_file_location(
        f"{package_name}.user_strategy", str(participant_file)
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"could not build import spec for {participant_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.UserStrategy


def _previous_segment(route: object, target: object) -> object:
    segments = sorted(route.segments, key=lambda segment: segment.sequence_index)
    target_index = next(index for index, segment in enumerate(segments) if segment is target)
    return segments[target_index - 1]


def _next_segment(route: object, current: object) -> object:
    segments = sorted(route.segments, key=lambda segment: segment.sequence_index)
    index = next(index for index, segment in enumerate(segments) if segment is current)
    return segments[(index + 1) % len(segments)]


def test_real_round1_context_selects_original_progress_vessel_without_mutation() -> None:
    source = _source_or_skip()
    _prepare_organizer_imports(source)
    import scenario_builders  # type: ignore[import-not-found]
    from maritime_data_context import Vessel  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    plans = tuple(context.disruption_plans)
    congestion = next(plan for plan in plans if plan.multiplier > 1)
    blocked_route = next(
        route
        for route in context.initial_service_routes
        if any(segment.associated_leg is congestion.target_leg for segment in route.segments)
    )
    blocked_segment = next(
        segment
        for segment in blocked_route.segments
        if segment.associated_leg is congestion.target_leg
    )

    active_day = congestion.start_offset_days
    now = dt.datetime.min + dt.timedelta(days=active_day)
    closed_ports = tuple(
        plan.target_berth.port
        for plan in plans
        if plan.close_berth
        and plan.start_offset_days <= active_day < plan.start_offset_days + plan.duration_days
    )
    congested_legs = tuple(
        plan.target_leg
        for plan in plans
        if plan.multiplier > 1
        and plan.start_offset_days <= active_day < plan.start_offset_days + plan.duration_days
    )
    progress_route, progress_segment = next(
        (route, segment)
        for route in context.initial_service_routes
        for segment in route.segments
        if segment.associated_leg not in congested_legs
        and segment.associated_leg.arrival_port not in closed_ports
        and _next_segment(route, segment).associated_leg not in congested_legs
        and _next_segment(route, segment).associated_leg.arrival_port not in closed_ports
    )

    vessel_class = context.vessels[0].vessel_class
    blocked_vessel = Vessel(9001, vessel_class, blocked_route)
    blocked_vessel.current_segment = _previous_segment(blocked_route, blocked_segment)
    progress_vessel = Vessel(9002, vessel_class, progress_route)
    progress_vessel.current_segment = progress_segment
    waiting = [blocked_vessel, progress_vessel]
    waits = {vessel: now - dt.timedelta(hours=index + 1) for index, vessel in enumerate(waiting)}

    state_before = (
        tuple(context.vessels),
        tuple(context.legs),
        tuple(context.initial_service_routes),
        tuple(context.disruption_plans),
        tuple((plan.target_leg, plan.target_berth) for plan in context.disruption_plans),
        blocked_vessel.current_segment,
        progress_vessel.current_segment,
    )
    UserStrategy = _load_participant_strategy()
    result = UserStrategy.select_vessel_for_berth(
        context,
        congestion.target_leg.departure_port,
        waiting,
        list(congestion.target_leg.departure_port.berths),
        now,
        waits,
    )

    assert result is progress_vessel
    assert result in waiting
    state_after = (
        tuple(context.vessels),
        tuple(context.legs),
        tuple(context.initial_service_routes),
        tuple(context.disruption_plans),
        tuple((plan.target_leg, plan.target_berth) for plan in context.disruption_plans),
        blocked_vessel.current_segment,
        progress_vessel.current_segment,
    )
    assert state_after == state_before
