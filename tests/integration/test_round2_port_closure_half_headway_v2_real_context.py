"""Real Round 2 contract for the port-closure half-headway experiment.

The contract evaluates fresh organizer contexts only.  It never advances the
model and never writes an output file; it proves that the new one-transfer
predicate is live, read-only, and limited to a port-only disruption.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _bootstrap_or_skip() -> Path:
    source = round_source_dir("round2")
    if not source.is_dir():
        pytest.skip(
            "Round 2 source is unavailable; bootstrap the organizer archive "
            "to run this real-context integration contract."
        )
    return source


def _prepare_imports(source: Path) -> None:
    for path in (str(source), str(source / "o2despy")):
        if path not in sys.path:
            sys.path.insert(0, path)
    prefixes = (
        "config",
        "main",
        "maritime_data_context",
        "o2des",
        "o2despy",
        "response_strategies",
        "scenario_builders",
        "simulation_model",
    )
    for module_name in list(sys.modules):
        if any(
            module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes
        ):
            sys.modules.pop(module_name, None)


def _load_participant() -> Any:
    participant_file = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location(
        "wsc_round2_port_closure_half_headway_v2_participant", participant_file
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(value: Any) -> int | None:
    return None if value is None else id(value)


def _context_signature(context: Any) -> tuple[Any, ...]:
    ports = tuple(
        (
            id(port),
            getattr(port, "name", None),
            tuple(map(id, getattr(port, "berths", ()))),
            tuple(map(id, getattr(port, "outgoing_legs", ()))),
            tuple(map(id, getattr(port, "incoming_legs", ()))),
            tuple(map(id, getattr(port, "shipments_in_storage", ()))),
        )
        for port in context.ports
    )
    legs = tuple(
        (
            id(leg),
            _identity(getattr(leg, "departure_port", None)),
            _identity(getattr(leg, "arrival_port", None)),
            getattr(leg, "sailing_distance", None),
            getattr(leg, "sailing_time_multiplier", None),
        )
        for leg in context.legs
    )
    routes = tuple(
        (
            id(route),
            getattr(route, "name", None),
            _identity(getattr(route, "source_service_route", None)),
            repr(getattr(route, "disruption_key", None)),
            tuple(
                (
                    id(segment),
                    getattr(segment, "sequence_index", None),
                    _identity(getattr(segment, "associated_leg", None)),
                    tuple(map(id, getattr(segment, "current_vessels", ()))),
                )
                for segment in getattr(route, "segments", ())
            ),
            tuple(map(id, getattr(route, "deployed_vessels", ()))),
            tuple(map(id, getattr(route, "associated_bookings", ()))),
        )
        for route in context.service_routes
    )
    vessels = tuple(
        (
            id(vessel),
            _identity(getattr(vessel, "assigned_service_route", None)),
            _identity(getattr(vessel, "pending_assigned_service_route", None)),
            _identity(getattr(vessel, "current_segment", None)),
            _identity(getattr(vessel, "current_berth", None)),
            tuple(map(id, getattr(vessel, "carried_shipments", ()))),
        )
        for vessel in context.vessels
    )
    plans = tuple(
        (
            id(plan),
            _identity(getattr(plan, "target_leg", None)),
            _identity(getattr(plan, "target_berth", None)),
            getattr(plan, "start_offset_days", None),
            getattr(plan, "duration_days", None),
            getattr(plan, "multiplier", None),
            getattr(plan, "close_berth", None),
        )
        for plan in context.disruption_plans
    )
    return (
        tuple(map(id, context.ports)),
        tuple(map(id, context.demands)),
        tuple(map(id, context.service_routes)),
        tuple(map(id, context.initial_service_routes)),
        tuple(map(id, context.legs)),
        tuple(map(id, context.vessels)),
        tuple(map(id, context.disruption_plans)),
        ports,
        legs,
        routes,
        vessels,
        plans,
    )


def _shipment_signature(shipment: Any) -> tuple[Any, ...]:
    return (
        id(shipment),
        getattr(shipment, "index", None),
        getattr(shipment, "teu_size", None),
        _identity(getattr(shipment, "demand", None)),
        _identity(getattr(shipment, "current_storage_port", None)),
        getattr(shipment, "generated_time", None),
        getattr(shipment, "completion_time", None),
        tuple(map(id, getattr(shipment, "associated_bookings", ()))),
        getattr(shipment, "current_booking_index", None),
        _identity(getattr(shipment, "carrying_vessel", None)),
    )


def _output_signature(path: Path) -> tuple[bool, int, str | None, int | None]:
    if not path.exists():
        return False, 0, None, None
    data = path.read_bytes()
    return True, len(data), hashlib.sha256(data).hexdigest(), path.stat().st_mtime_ns


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _port_closure_times(context: Any) -> tuple[dt.datetime, ...]:
    """Return integer-day midpoints for the port-closure windows only.

    The experiment is intentionally scoped to port closures.  Restricting the
    contract to those windows keeps the real-context test bounded while still
    covering every active day in the relevant plans.
    """
    values: list[dt.datetime] = []
    for plan in context.disruption_plans:
        if (
            getattr(plan, "close_berth", None) is not True
            or getattr(plan, "target_berth", None) is None
            or getattr(plan, "target_leg", None) is not None
        ):
            continue
        start_days = _finite(getattr(plan, "start_offset_days", None))
        duration_days = _finite(getattr(plan, "duration_days", None))
        if start_days is None or duration_days is None or duration_days <= 0.0:
            continue
        first_day = math.floor(start_days)
        last_day = math.ceil(start_days + duration_days)
        start = dt.datetime.min + dt.timedelta(days=start_days)
        end = start + dt.timedelta(days=duration_days)
        for integer_day in range(first_day, last_day):
            midpoint = dt.datetime.min + dt.timedelta(days=integer_day + 0.5)
            if start <= midpoint < end:
                values.append(midpoint)
    return tuple(dict.fromkeys(values))


def _outside_time(context: Any) -> dt.datetime:
    starts = [
        dt.datetime.min + dt.timedelta(days=plan.start_offset_days)
        for plan in context.disruption_plans
        if _finite(getattr(plan, "start_offset_days", None)) is not None
    ]
    assert starts
    earliest = min(starts)
    assert earliest > dt.datetime.min
    return earliest - dt.timedelta(microseconds=1)


def _half_headway_candidate(participant: Any, context: Any, now: Any, shipment: Any) -> bool:
    """Independently identify the newly enabled, half-headway population."""
    state = participant._active_state(context, now)
    demand = getattr(shipment, "demand", None)
    if state is None or demand is None:
        return False
    graphs = participant._graphs(context, state)
    if graphs is None:
        return False
    nominal = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[0]
    )
    safe = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[1]
    )
    if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
        return False
    changes = sum(
        left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
    )
    if changes != 1:
        return False
    matching = participant._matching_constraints(nominal[0], state)
    if {constraint.kind for constraint in matching} != {"port"}:
        return False
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    max_headway = participant._max_path_headway(safe)
    if recovery is None or nominal_hours is None or detour_hours is None or max_headway is None:
        return False
    wait_hours = max(0.0, (recovery - now).total_seconds() / 3600.0)
    hold_hours = wait_hours + nominal_hours
    margin = detour_hours - hold_hours
    return math.isfinite(margin) and 0.5 * max_headway < margin <= max_headway


def test_real_round2_context_exercises_half_headway_without_mutation() -> None:
    source = _bootstrap_or_skip()
    _prepare_imports(source)

    # Import the organizer entry point first.  It initializes the runtime
    # package graph before ``response_strategies.default_strategy`` is loaded;
    # importing the latter directly can otherwise expose its circular import.
    import main  # type: ignore[import-not-found]  # noqa: F401, PLC0415
    import scenario_builders  # type: ignore[import-not-found]  # noqa: PLC0415
    from maritime_data_context.shipment import Shipment  # type: ignore[import-not-found]
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )

    participant = _load_participant()
    template = scenario_builders.create_with_disruption()
    times = _port_closure_times(template)
    assert times, "the real Round 2 scenario must expose active disruption windows"
    output = source / "Output" / "ATT_By_Statistics_Interval.csv"
    output_before = _output_signature(output)
    candidate_count = 0
    observations = 0

    for now in times:
        context = scenario_builders.create_with_disruption()
        DefaultStrategy.create_alternative_service_routes(context, now)
        for index, demand in enumerate(context.demands):
            shipment = Shipment(
                index=index,
                teu_size=1,
                demand=demand,
                current_storage_port=demand.origin_port,
                generated_time=now,
            )
            before = (_context_signature(context), _shipment_signature(shipment))
            candidate = _half_headway_candidate(participant, context, now, shipment)
            decision = participant.UserStrategy.assign_associated_bookings(context, now, shipment)
            after = (_context_signature(context), _shipment_signature(shipment))
            assert after == before, "participant decision mutated real Round 2 state"
            observations += 1
            if candidate:
                candidate_count += 1
                assert decision is False, "a qualifying half-headway case must hold"
                # One real qualifying observation is sufficient to prove the
                # wiring is live; the exhaustive activation population is
                # covered by the separate ignored audit before a full run.
                break
        if candidate_count:
            break

    assert observations > 0
    assert candidate_count > 0, "the real context must exercise the new policy"
    assert _output_signature(output) == output_before, "strategy wrote organizer Output"

    outside = _outside_time(template)
    context = scenario_builders.create_with_disruption()
    demand = context.demands[0]
    shipment = Shipment(
        index=0,
        teu_size=1,
        demand=demand,
        current_storage_port=demand.origin_port,
        generated_time=outside,
    )
    before = (_context_signature(context), _shipment_signature(shipment))
    assert participant.UserStrategy.assign_associated_bookings(context, outside, shipment) is None
    assert (_context_signature(context), _shipment_signature(shipment)) == before
