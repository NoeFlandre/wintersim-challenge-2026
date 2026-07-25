"""Real Round 0 contract test for the recovery-hold-vs-detour candidate.

This integration test loads the participant ``UserStrategy`` by file path and
exercises the recovery-aware ``assign_associated_bookings`` hook against the
real Round 0 disruption scenario without advancing simulation time.

The test asserts the documented contract:

* repeated evaluation at the same active timestamp is deterministic;
* at least one shipment in the real Round 0 fixture yields ``False``
  (wait-for-recovery strictly faster than safe detour);
* at least one shipment yields ``None`` (delegate to organizer fallback);
* context, shipment, routes, bookings, and vessel state are unchanged
  after each call.

The test is marked ``integration`` and is skipped when the local Round 0
source tree is not bootstrapped.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _round0_source() -> Path:
    return round_source_dir("round0")


def _bootstrap_or_skip() -> Path:
    source = _round0_source()
    if not source.is_dir():
        pytest.skip(
            "Round 0 source not bootstrapped at "
            f"{source}. Run 'wsc2026 bootstrap --round round0 --archive <path>' "
            "to enable this integration test."
        )
    return source


def _add_source_to_path(source: Path) -> None:
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
    participant_file = submission_strategies_dir() / "user_strategy.py"
    if not participant_file.is_file():
        pytest.fail(f"participant user_strategy.py missing at {participant_file}")
    spec = importlib.util.spec_from_file_location(
        "wsc_participant_user_strategy_recovery", str(participant_file)
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"could not build import spec for {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy


def _snapshot(context) -> dict:
    """Identity-bearing snapshot proving no mutation occurred."""
    return {
        "ports": tuple(context.ports),
        "legs": tuple(context.legs),
        "service_routes": tuple(context.service_routes),
        "vessels": tuple(context.vessels),
        "assigned_routes": tuple(v.assigned_service_route for v in context.vessels),
        "vessel_segments": tuple(getattr(v, "current_segment", None) for v in context.vessels),
        "disruption_plans": tuple(context.disruption_plans),
        "demands": tuple(context.demands),
    }


def _snapshot_shipment(shipment) -> dict:
    return {
        "associated_bookings": tuple(shipment.associated_bookings),
        "current_booking_index": shipment.current_booking_index,
        "carrying_vessel": shipment.carrying_vessel,
        "current_storage_port": shipment.current_storage_port,
        "completion_time": shipment.completion_time,
    }


def _select_disruption_inside_time(context) -> dt.datetime:
    """Pick a timestamp strictly inside the FIRST disruption's active window.

    Round 0 plans anchor at ``datetime.min + start_offset_days``, so the
    correct clock origin is ``datetime.min``, not ``datetime(2026, 1, 1)``.
    """
    plan = context.disruption_plans[0]
    inside_day = plan.start_offset_days + (plan.duration_days / 2.0)
    return dt.datetime.min + dt.timedelta(days=inside_day)


def _make_synthetic_shipments(context, max_picks: int = 6) -> list:
    """Construct Shipment objects attached to distinct real demands.

    The shipment generator is not run by ``create_with_disruption``; it only
    runs during the simulation. We construct a few synthetic shipments by
    hand so the integration test can exercise the participant hook against
    the real context without advancing the simulation clock.
    """
    from maritime_data_context import Shipment  # type: ignore[import-not-found]

    picked: list = []
    seen: set = set()
    next_index = 1
    for demand in list(getattr(context, "demands", []) or []):
        origin = getattr(demand, "origin_port", None)
        destination = getattr(demand, "destination_port", None)
        if origin is None or destination is None:
            continue
        key = (id(origin), id(destination))
        if key in seen:
            continue
        seen.add(key)
        shipment = Shipment(
            index=next_index,
            teu_size=1,
            demand=demand,
            current_storage_port=origin,
            generated_time=dt.datetime.min,
        )
        next_index += 1
        demand.shipments.append(shipment)
        picked.append(shipment)
        if len(picked) >= max_picks:
            break
    if not picked:
        pytest.skip(
            "Round 0 context has no demands to attach synthetic shipments to; "
            "the candidate cannot be audited."
        )
    return picked


def test_recovery_hold_real_context_contract() -> None:
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    assert context.disruption_plans, "the disruption scenario must define plans"
    UserStrategy = _load_participant_user_strategy()

    now = _select_disruption_inside_time(context)

    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    assert is_disruption_active(context, now), (
        "the test must select a timestamp inside an active disruption window"
    )

    # The real runtime builds disruption-aware alternative routes in
    # ``create_alternative_service_routes`` before calling
    # ``assign_associated_bookings`` for each shipment. Mirror that order
    # so the candidate sees the same graph the framework would actually
    # pass it.
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )

    DefaultStrategy.create_alternative_service_routes(context, now)

    shipments = _make_synthetic_shipments(context, max_picks=120)
    assert shipments, "at least one representative shipment must be available"

    results_first: list = []
    results_second: list = []
    saw_false = False
    saw_none = False
    for shipment in shipments:
        before_ctx = _snapshot(context)
        before_ship = _snapshot_shipment(shipment)
        result_first = UserStrategy.assign_associated_bookings(context, now, shipment)
        result_second = UserStrategy.assign_associated_bookings(context, now, shipment)
        results_first.append(result_first)
        results_second.append(result_second)
        if result_first is False:
            saw_false = True
        if result_first is None:
            saw_none = True
        # No-mutation guarantees for every result.
        assert _snapshot(context) == before_ctx, (
            "UserStrategy.assign_associated_bookings must not mutate the "
            f"context for shipment {shipment.index}; result={result_first!r}"
        )
        assert _snapshot_shipment(shipment) == before_ship, (
            "UserStrategy.assign_associated_bookings must not mutate the "
            f"shipment for shipment {shipment.index}; result={result_first!r}"
        )

    # Determinism: repeated evaluation at the same timestamp must yield the
    # same result for every shipment.
    assert results_first == results_second, (
        "UserStrategy.assign_associated_bookings is not deterministic across "
        "repeated calls at the same timestamp."
    )

    # Active disruption with at least one shipment must yield both a False
    # and a None for the policy to be meaningfully active. If zero False
    # decisions were observed, the candidate is behaviorally inactive and
    # the project manager must be informed; we fail the test loudly.
    assert saw_false, (
        "no shipment yielded False in the real Round 0 disruption window; "
        "the recovery-hold candidate is behaviorally inactive in this scenario"
    )
    assert saw_none, (
        "no shipment yielded None in the real Round 0 disruption window; "
        "the candidate never delegates, which contradicts the policy"
    )
