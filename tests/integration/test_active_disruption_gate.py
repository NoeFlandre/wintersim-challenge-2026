"""Integration test: UserStrategy.create_alternative_service_routes is a no-op.

Constructs the real Round 0 organizer disruption context in memory, picks a
timestamp inside the configured disruption window, calls the participant
``UserStrategy.create_alternative_service_routes`` and asserts that:

* the call returns ``None`` (delegated to the organizer fallback), and
* the context is left untouched (vessels, legs, service_routes, vessel
  assignments, and the disruption_plans list are all unchanged).

This is the "active-disruption gate": it would catch a regression where a
strategy implementation mutates the context, returns an invalid object, or
silently swallows an exception. Skipped when the local Round 0 source is
not bootstrapped (CI does not include the organizer ZIP).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from wsc2026_tools.cli import run_smoke
from wsc2026_tools.paths import (
    submission_strategies_dir,
)

pytestmark = pytest.mark.integration

SOURCE = round_source_dir() if False else None  # placeholder; computed below


def _round0_source() -> Path:
    from wsc2026_tools.paths import round_source_dir

    return round_source_dir("round0")


def _bootstrap_or_skip() -> Path:
    """Skip the test with an actionable message when source is absent."""
    source = _round0_source()
    if not source.is_dir():
        pytest.skip(
            "Round 0 source not bootstrapped at "
            f"{source}. Run 'wsc2026 bootstrap --round round0 --archive <path>' "
            "to enable this integration test."
        )
    return source


def _add_source_to_path(source: Path) -> None:
    """Prepend the source root (and o2despy) to sys.path for this process.

    The organizer's ``response_strategies`` package and the participant's
    ``submission/response_strategies`` share the same top-level name, so we
    must put the organizer's source first; otherwise Python resolves
    ``response_strategies.default_strategy`` to the submission package and
    crashes. The participant strategy is loaded by absolute file path below.
    """
    src = str(source)
    o2des = str(source / "o2despy")
    if src not in sys.path:
        sys.path.insert(0, src)
    if o2des not in sys.path:
        sys.path.insert(0, o2des)


def _load_participant_user_strategy() -> type:
    """Load ``submission/response_strategies/user_strategy.py`` by file path.

    Bypasses the ``response_strategies`` namespace collision between the
    organizer's package and the participant's package.
    """
    participant_file = submission_strategies_dir() / "user_strategy.py"
    if not participant_file.is_file():
        pytest.fail(f"participant user_strategy.py missing at {participant_file}")
    spec = importlib.util.spec_from_file_location(
        "wsc_participant_user_strategy", str(participant_file)
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"could not build import spec for {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def _snapshot(context) -> dict:
    """Capture the identity-bearing state we expect the strategy to preserve."""
    return {
        "vessels": tuple(context.vessels),
        "legs": tuple(context.legs),
        "service_routes": tuple(context.service_routes),
        "assigned_routes": {
            vessel: vessel.assigned_service_route for vessel in context.vessels
        },
        "disruption_plans": tuple(context.disruption_plans),
    }


def test_user_strategy_is_no_op_inside_active_disruption() -> None:
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    # Import the organizer-side scenario_builders BEFORE the participant
    # strategy. simulation_model imports ``response_strategies.default_strategy``
    # eagerly; if the participant module is imported first, the package is
    # mid-init and the constructor crashes.
    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    assert context.disruption_plans, "the disruption scenario must define at least one plan"

    UserStrategy = _load_participant_user_strategy()

    # Pick a timestamp inside the FIRST disruption's active window. Each plan's
    # start_offset_days is measured from warm-up start; mid-window is a safe
    # representative timestamp.
    plan = context.disruption_plans[0]
    inside_day = plan.start_offset_days + (plan.duration_days / 2.0)
    now = datetime(2026, 1, 1) + timedelta(days=inside_day)

    snapshot_before = _snapshot(context)

    vessel = context.vessels[0] if context.vessels else None
    result = UserStrategy.create_alternative_service_routes(context, now, vessel)

    # The baseline must return None to delegate to the organizer fallback.
    assert result is None

    snapshot_after = _snapshot(context)
    assert snapshot_after == snapshot_before, (
        "UserStrategy.create_alternative_service_routes must not mutate the "
        f"context. Before: {snapshot_before['service_routes']!r}, "
        f"after: {snapshot_after['service_routes']!r}"
    )


def test_round0_smoke_spawn_against_real_source() -> None:
    """The smoke subprocess driver still works against the local Round 0 tree.

    Companion check: the active-disruption gate above runs in-process; this
    test asserts the out-of-process driver still works against the same
    tree, catching regressions in PYTHONPATH construction or environment
    handling.
    """
    source = _bootstrap_or_skip()
    result = run_smoke(source, days=1, timeout=300.0)
    assert result.returncode == 0, (
        f"smoke against real Round 0 failed: rc={result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "SMOKE_OK" in result.stdout
