"""Integration test: UserStrategy.adjust_bookings_before_cargo_handling policy.

Constructs the real Round 0 organizer disruption context in memory, picks
timestamps both inside and outside the configured disruption window, calls
the participant ``UserStrategy.adjust_bookings_before_cargo_handling`` and
asserts that:

* a timestamp inside the first active plan returns exactly ``False`` ("handled,
  suppress the organizer in-transit rebooking fallback");
* that active call leaves the complete organizer route/vessel/leg/booking/
  shipment/segment assignment snapshot unchanged for the supplied vessel;
* a timestamp outside any active plan returns ``None`` (delegated to the
  organizer fallback);
* the participant module loads through the same safe file-loader procedure
  used by existing tests.

This is the "in-transit-rebooking gate": it would catch a regression where a
strategy implementation mutates vessel assignment, carried bookings,
shipment references, or segment/berth membership. Skipped when the local
Round 0 source is not bootstrapped (CI does not include the organizer ZIP).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

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
        "wsc_participant_user_strategy_rebooking", str(participant_file)
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"could not build import spec for {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def _snapshot(context, vessel) -> dict:
    """Capture the identity-bearing state we expect the strategy to preserve."""
    return {
        "vessels_ids": tuple(id(v) for v in context.vessels),
        "legs_ids": tuple(id(leg) for leg in context.legs),
        "service_routes_ids": tuple(id(r) for r in context.service_routes),
        "disruption_plans_ids": tuple(id(p) for p in context.disruption_plans),
        "vessel.assigned_service_route": vessel.assigned_service_route,
        "vessel.pending_assigned_service_route": vessel.pending_assigned_service_route,
        "vessel.current_segment": vessel.current_segment,
        "vessel.current_berth": vessel.current_berth,
        "vessel.carried_shipments_ids": tuple(id(s) for s in vessel.carried_shipments),
        "vessel.carried_shipments_bookings": tuple(
            tuple(id(b) for b in getattr(s, "associated_bookings", []))
            for s in vessel.carried_shipments
        ),
        "vessel.carried_shipments_indices": tuple(
            getattr(s, "current_booking_index", None) for s in vessel.carried_shipments
        ),
        "route_deployed_vessels_ids": tuple(
            id(v) for r in context.service_routes for v in getattr(r, "deployed_vessels", [])
        ),
    }


def test_user_strategy_returns_false_inside_active_disruption_and_preserves_state() -> None:
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    assert context.disruption_plans, "the disruption scenario must define at least one plan"
    assert context.vessels, "the scenario must include vessels"

    UserStrategy = _load_participant_user_strategy()

    # Pick a timestamp strictly inside the FIRST disruption's active window.
    plan = context.disruption_plans[0]
    inside_day = plan.start_offset_days + (plan.duration_days / 2.0)
    now = datetime.min + timedelta(days=inside_day)

    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    assert is_disruption_active(context, now) is True, (
        f"test must pick a timestamp inside an active disruption; plan={plan!r} now={now!r}"
    )

    vessel = context.vessels[0]
    snapshot_before = _snapshot(context, vessel)

    # Active suppression must return exactly False, NOT None.
    result = UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)
    assert result is False, (
        "UserStrategy.adjust_bookings_before_cargo_handling must return False "
        "to suppress the organizer in-transit rebooking fallback during an "
        f"active disruption, got {result!r}"
    )

    snapshot_after = _snapshot(context, vessel)
    for key in snapshot_before:
        assert snapshot_after[key] == snapshot_before[key], (
            f"snapshot mismatch on {key!r}: before={snapshot_before[key]!r} "
            f"after={snapshot_after[key]!r}"
        )


def test_user_strategy_returns_none_outside_active_disruptions() -> None:
    """Outside any active disruption the participant delegates via ``None``.

    The organizer call sites fall through to the default in-transit rebooking
    strategy strictly on ``is None``. Returning False outside an active window
    would silently break that contract.
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
    after_last = (
        datetime.min
        + timedelta(days=last_plan.start_offset_days + last_plan.duration_days + 1)
    )

    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    assert is_disruption_active(context, after_last) is False, (
        "test must pick a timestamp outside any active disruption"
    )

    vessel = context.vessels[0]
    result = UserStrategy.adjust_bookings_before_cargo_handling(
        context, after_last, vessel
    )
    assert result is None


# Avoid the unused-import warning in static checkers.
_ = SimpleNamespace
