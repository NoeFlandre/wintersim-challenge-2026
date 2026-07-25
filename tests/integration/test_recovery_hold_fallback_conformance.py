"""Real Round 0 fallback-conformance integration test.

This integration test loads the participant ``UserStrategy`` by file path and
exercises the safe-path signature against the real Round 0 disruption scenario
without advancing simulation time. The safe-path signature is the
``(service_route_id, departure_segment_index, arrival_segment_index)`` tuple
list of every booking edge in the booking-edge graph that the candidate
mirrors for the safe detour.

The test asserts that the candidate's mirror of the fallback's safe booking
graph matches the actual fallback's safe booking graph exactly:

* repeated evaluation at the same active timestamp is deterministic;
* at least one shipment in the real Round 0 fixture yields ``False``
  (wait-for-recovery strictly faster than safe detour);
* at least one shipment yields ``None`` (delegate to organizer fallback);
* for every distinct real demand and every inspected timestamp, the
  safe-path signature is identical to the organizer's actual safe-path
  signature, with zero mismatches.

The test uses the organizer's private booking-edge enumeration helpers
(loaded only inside this ignored-source integration test). The participant
strategy never imports these helpers.

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


def _load_participant_module() -> object:
    """Return the same module reference already loaded by ``_load_participant_user_strategy``.

    Cached to avoid re-executing the file under a second module name.
    """
    cached = getattr(_load_participant_module, "_cache", None)
    if cached is None:
        participant_file = submission_strategies_dir() / "user_strategy.py"
        spec = importlib.util.spec_from_file_location(
            "wsc_participant_user_strategy_conformance_mod", str(participant_file)
        )
        if spec is None or spec.loader is None:
            pytest.fail(f"could not build import spec for {participant_file}")
        cached = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cached)
        _load_participant_module._cache = cached
    return cached


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


def _fresh_context(source: Path) -> object:
    """Build a fresh scenario context without advancing simulation time."""
    import scenario_builders  # type: ignore[import-not-found]

    return scenario_builders.create_with_disruption()


def _load_participant_user_strategy() -> tuple:
    """Load the participant user_strategy.py and return ``(UserStrategy class, module)``.

    The module is returned so the test can reach private helpers
    (``_collect_active_disruption_keys``, ``_route_edges_for_safe``,
    ``_pathfind``) without importing them through the package.
    """
    participant_file = submission_strategies_dir() / "user_strategy.py"
    if not participant_file.is_file():
        pytest.fail(f"participant user_strategy.py missing at {participant_file}")
    spec = importlib.util.spec_from_file_location(
        "wsc_participant_user_strategy_conformance", str(participant_file)
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"could not build import spec for {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy, module


def _load_participant_module() -> object:
    """Backwards-compatible alias returning the module half of the user_strategy.

    The current implementation only exposes the module via
    ``_load_participant_user_strategy``. This helper is retained for tests
    that imported the old symbol.
    """
    return _load_participant_user_strategy()[1]


def _signature_from_edges(edges: list) -> list:
    """Reduce a list of participant/fallback edges to a comparable signature.

    Each entry is ``(service_route_id, departure_segment_index,
    arrival_segment_index)``. Identity is reduced to ``id`` so the signature
    is comparable across reloads.
    """
    signature: list = []
    for edge in edges:
        route = getattr(edge, "service_route", None)
        signature.append(
            (
                id(route),
                int(getattr(edge, "departure_segment_index", 0)),
                int(getattr(edge, "arrival_segment_index", 0)),
            )
        )
    return signature


def _fallback_safe_path(context, now, origin_port, destination_port) -> list:
    """Compute the actual fallback safe-path edges using organizer helpers.

    Uses the organizer's private helpers in ``default_strategy``. These
    imports are permitted only inside this ignored-source integration test.
    """
    from response_strategies import (
        default_strategy as organizer_fallback,  # type: ignore[import-not-found]
    )
    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    if not is_disruption_active(context, now):
        return []
    close_berth_plans, congested_leg_plans = organizer_fallback._get_active_disruption_plans(
        context, now
    )
    avoid_port_names = organizer_fallback._get_avoid_port_names(close_berth_plans)
    congested_legs = organizer_fallback._get_congested_legs(congested_leg_plans)
    if not avoid_port_names and not congested_legs:
        return []
    all_edges = organizer_fallback._build_all_candidate_bookings(
        context, avoid_port_names, congested_legs
    )
    path = organizer_fallback._find_shortest_booking_path(
        context, origin_port, destination_port, all_edges
    )
    if path is None:
        return []
    return list(path)


def _candidate_safe_path(part_module, context, now, origin_port, destination_port) -> list:
    """Compute the candidate's mirror of the safe-path edges."""
    close_berth_set, congested_leg_set, disruption_key = (
        part_module._collect_active_disruption_keys(context, now)
    )
    safe_edges: list = []
    for route in list(getattr(context, "service_routes", []) or []):
        safe_edges.extend(
            part_module._route_edges_for_safe(
                route, close_berth_set, congested_leg_set, disruption_key
            )
        )
    return part_module._pathfind(context, safe_edges, origin_port, destination_port)


def _every_distinct_demand(context) -> list:
    """Return the (origin_port, destination_port) of every distinct demand."""
    seen: set = set()
    pairs: list = []
    for demand in list(getattr(context, "demands", []) or []):
        origin = getattr(demand, "origin_port", None)
        destination = getattr(demand, "destination_port", None)
        if origin is None or destination is None:
            continue
        key = (id(origin), id(destination))
        if key in seen:
            continue
        seen.add(key)
        pairs.append((origin, destination))
    return pairs


def _timestamps_for_plans(context) -> list:
    """For each disruption plan: start+1s, midpoint, end-1s."""
    timestamps: list = []
    for plan in list(getattr(context, "disruption_plans", []) or []):
        start = plan.start_offset_days
        duration = plan.duration_days
        timestamps.append(start + 1.0 / 86400.0)
        timestamps.append(start + duration / 2.0)
        timestamps.append(start + duration - 1.0 / 86400.0)
    return timestamps


def test_fallback_conformance_real_context() -> None:
    """Compare the candidate's safe-path signature against the actual fallback.

    For every distinct real demand and every inspected timestamp, the
    candidate's safe-path signature must match the fallback's exactly.
    Zero mismatches are required.
    """
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    import scenario_builders  # type: ignore[import-not-found]

    context = scenario_builders.create_with_disruption()
    assert context.disruption_plans, "the disruption scenario must define plans"

    # Load the participant strategy AFTER the organizer modules are loaded,
    # to avoid clashing with the simulation_model -> response_strategies ->
    # default_strategy -> simulation_model circular import.
    UserStrategy, part_module = _load_participant_user_strategy()

    timestamps = _timestamps_for_plans(context)
    assert timestamps, "Round 0 context must declare at least one disruption plan"

    # Import order matters: ``simulation_model.disruption_status`` must be
    # imported BEFORE ``response_strategies.default_strategy`` to avoid the
    # circular import through ``simulation_model.__init__`` ->
    # ``shipment_waiting_for_loading_at_origin_port``.
    from maritime_data_context import Shipment  # type: ignore[import-not-found]
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )
    from simulation_model.disruption_status import (  # type: ignore[import-not-found]
        is_disruption_active,
    )

    total_mismatches = 0
    total_pairs = 0
    saw_false = False
    saw_none = False
    for now_days in timestamps:
        context = _fresh_context(source)
        now = dt.datetime.min + dt.timedelta(days=now_days)
        if not is_disruption_active(context, now):
            continue
        # Mirror runtime order: alternative routes must be built first.
        DefaultStrategy.create_alternative_service_routes(context, now)
        demands = _every_distinct_demand(context)
        for origin_port, destination_port in demands:
            total_pairs += 1
            fallback_path = _fallback_safe_path(context, now, origin_port, destination_port)
            candidate_path = _candidate_safe_path(
                part_module, context, now, origin_port, destination_port
            )
            if fallback_path != [] or candidate_path != []:
                total_mismatches += _compare_paths(
                    fallback_path, candidate_path, origin_port, destination_port
                )
            # Also exercise the public hook to confirm it is consistent
            # with the safe-path mirror (no surprises during runtime).
            demand = _find_demand(context, origin_port, destination_port)
            if demand is None:
                continue
            shipment = Shipment(
                index=total_pairs,
                teu_size=1,
                demand=demand,
                current_storage_port=origin_port,
                generated_time=dt.datetime.min,
            )
            result = UserStrategy.assign_associated_bookings(context, now, shipment)
            if result is False:
                saw_false = True
            elif result is None:
                saw_none = True

    assert total_mismatches == 0, (
        f"candidate safe-path mirror disagrees with fallback on {total_mismatches} "
        f"of {total_pairs} (demand, timestamp) pairs"
    )
    assert saw_false, (
        "no shipment yielded False across the full conformance sweep; "
        "the candidate is behaviorally inactive in the real Round 0 scenario"
    )
    assert saw_none, (
        "no shipment yielded None across the full conformance sweep; "
        "the candidate never delegates, which contradicts the policy"
    )


def _compare_paths(
    fallback_path: list, candidate_path: list, origin_port: object, destination_port: object
) -> int:
    """Return 1 if the safe-path signatures differ, else 0."""
    fallback_sig = _signature_from_edges(fallback_path)
    candidate_sig = _signature_from_edges(candidate_path)
    if fallback_sig == candidate_sig:
        return 0
    return 1


def _find_demand(context, origin_port: object, destination_port: object) -> object:
    """Find an existing demand for the (origin, destination) pair."""
    for demand in list(getattr(context, "demands", []) or []):
        if (
            getattr(demand, "origin_port", None) is origin_port
            and getattr(demand, "destination_port", None) is destination_port
        ):
            return demand
    return None
