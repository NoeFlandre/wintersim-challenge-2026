"""Integration checks for the real Round 0 clock and smoke driver.

The candidate route-mutation contract is covered separately by
``test_safe_shuttle_recovery_round0.py`` using the organizer's own strategy
validator. These checks retain the independent clock-origin regression and
out-of-process smoke coverage. They skip when the private Round 0 source is
not bootstrapped.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from wsc2026_tools.cli import run_smoke
from wsc2026_tools.paths import round_source_dir

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
