"""Integration test: UserStrategy.create_alternative_service_routes policy.

Constructs the real Round 0 organizer disruption context in memory, picks
timestamps both inside and outside the configured disruption window, calls
the participant ``UserStrategy.create_alternative_service_routes`` and
asserts that:

* a timestamp inside the first active plan returns exactly ``False``
  ("handled, suppress the organizer alternative-route fallback"),
* that active call leaves the complete organizer route/vessel/leg assignment
  snapshot unchanged,
* a timestamp outside any active plan returns ``None`` (delegated to the
  organizer fallback),
* the participant module loads through the same safe file-loader procedure
  used by existing tests.

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
    round_source_dir,
    submission_strategies_dir,
)

pytestmark = pytest.mark.integration


def _round0_source() -> Path:
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

    # Unit tests import the participant-owned ``response_strategies`` package
    # before this integration module runs. Changing sys.path cannot replace an
    # already-cached package, so clear the organizer-facing namespaces and all
    # their submodules before importing the real runtime tree.
    prefixes = (
        "response_strategies",
        "scenario_builders",
        "simulation_model",
        "maritime_data_context",
        "config",
        "o2despy",
        "o2des",
    )
    for module_name in list(sys.modules):
        if any(
            module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes
        ):
            sys.modules.pop(module_name, None)


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
        "assigned_routes": {vessel: vessel.assigned_service_route for vessel in context.vessels},
        "disruption_plans": tuple(context.disruption_plans),
    }


def test_user_strategy_returns_false_inside_active_disruption_and_preserves_state() -> None:
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

    # Pick a timestamp strictly inside the FIRST disruption's active window.
    # The organizer's is_disruption_active anchors offsets at datetime.min,
    # so the absolute reference clock is:
    #   now = datetime.min + timedelta(days=start_offset_days + duration/2)
    plan = context.disruption_plans[0]
    inside_day = plan.start_offset_days + (plan.duration_days / 2.0)
    now = datetime.min + timedelta(days=inside_day)

    # Import is_disruption_active directly. The package init is independent
    # of scenario_builders so the order does not conflict.
    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    # Genuine proof that the disruption is active at the chosen timestamp.
    assert is_disruption_active(context, now) is True, (
        f"test must pick a timestamp inside an active disruption; plan={plan!r} now={now!r}"
    )

    snapshot_before = _snapshot(context)

    vessel = context.vessels[0] if context.vessels else None
    result = UserStrategy.create_alternative_service_routes(context, now, vessel)

    # The active suppression policy must return exactly False, NOT None.
    assert result is False, (
        "UserStrategy.create_alternative_service_routes must return False "
        "to suppress the organizer alternative-route fallback during an "
        f"active disruption, got {result!r}"
    )

    snapshot_after = _snapshot(context)
    assert snapshot_after == snapshot_before, (
        "UserStrategy.create_alternative_service_routes must not mutate the "
        f"context. Before: {snapshot_before['service_routes']!r}, "
        f"after: {snapshot_after['service_routes']!r}"
    )


def test_user_strategy_returns_none_outside_active_disruptions() -> None:
    """Outside any active disruption the participant delegates via ``None``.

    The organizer call sites fall through to the default alternative-route
    strategy (which performs cleanup and restoration) strictly on
    ``is None``. Returning False outside an active window would silently
    break that contract.
    """
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    UserStrategy = _load_participant_user_strategy()

    # Pick a timestamp 1 day after the last plan ends -- guaranteed outside
    # any active window while still being within datetime.min+offset range.
    last_plan = max(
        context.disruption_plans,
        key=lambda plan: plan.start_offset_days + (plan.duration_days or 0.0),
    )
    after_last = datetime.min + timedelta(
        days=last_plan.start_offset_days + last_plan.duration_days + 1
    )

    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    assert is_disruption_active(context, after_last) is False, (
        "test must pick a timestamp outside any active disruption"
    )

    result = UserStrategy.create_alternative_service_routes(context, after_last, vessel=None)
    assert result is None


def test_active_disruption_clock_origin_is_datetime_min() -> None:
    """The previous test used ``datetime(2026, 1, 1)`` as the clock origin.

    With that origin, is_disruption_active returns False even when the
    relative offset clearly falls inside the disruption window: every plan
    anchors at datetime.min, so adding 200 days to a fixed 2026 date lands
    outside the window. This test makes the regression explicit and locks
    the contract: ``datetime.min + offset`` is the only correct origin.
    """
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    plan = context.disruption_plans[0]
    inside_day = plan.start_offset_days + (plan.duration_days / 2.0)

    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    # The naive 2026-anchored timestamp is NOT inside the disruption window.
    bad_now = datetime(2026, 1, 1) + timedelta(days=inside_day)
    assert is_disruption_active(context, bad_now) is False, (
        "with datetime(2026, 1, 1) origin the helper must return False -- "
        "proving the previous test was off-clock"
    )

    # The correct anchor (datetime.min) lands inside the disruption.
    good_now = datetime.min + timedelta(days=inside_day)
    assert is_disruption_active(context, good_now) is True


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
