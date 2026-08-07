"""Integration contract for replacing a carried pending-route reservation."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _source_or_skip() -> Path:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip(
            "Round 1 source not bootstrapped at "
            f"{source}; bootstrap the private archive to enable this check."
        )
    return source


def _load_organizer_tree(source: Path) -> None:
    for root in (str(source), str(source / "o2despy")):
        if root not in sys.path:
            sys.path.insert(0, root)
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


def _load_participant() -> type:
    path = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_round1_participant", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load participant strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def test_real_pending_carried_vessel_is_replaced_by_empty_source_vessel() -> None:
    source = _source_or_skip()
    _load_organizer_tree(source)

    import scenario_builders  # type: ignore[import-not-found]
    import simulation_model  # type: ignore[import-not-found]  # noqa: F401
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )

    context = scenario_builders.create_with_disruption()
    now = datetime.min + timedelta(days=200.5)
    DefaultStrategy.create_alternative_service_routes(context, now, None)

    old = next(
        vessel
        for vessel in context.vessels
        if vessel.pending_assigned_service_route is not None
    )
    alternative = old.pending_assigned_service_route
    assert alternative is not None
    source_route = old.assigned_service_route
    assert source_route is not None
    candidate = next(
        vessel
        for vessel in source_route.deployed_vessels
        if vessel is not old
        and vessel.assigned_service_route is source_route
        and vessel.pending_assigned_service_route is None
    )

    # The runtime may only invoke this hook after cargo has been loaded.  A
    # small ephemeral shipment-shaped object is enough to model that state.
    old.carried_shipments.append(SimpleNamespace(teu_size=1))
    before = {
        "vessels": tuple(context.vessels),
        "routes": tuple(context.service_routes),
        "legs": tuple(context.legs),
        "assigned": tuple(
            (vessel, vessel.assigned_service_route) for vessel in context.vessels
        ),
    }

    UserStrategy = _load_participant()
    result = UserStrategy.create_alternative_service_routes(context, now, None)

    assert result is True
    assert old.pending_assigned_service_route is None
    assert candidate.pending_assigned_service_route is alternative
    assert tuple(context.vessels) == before["vessels"]
    assert tuple(context.service_routes) == before["routes"]
    assert tuple(context.legs) == before["legs"]
    assert tuple(
        (vessel, vessel.assigned_service_route) for vessel in context.vessels
    ) == before["assigned"]
