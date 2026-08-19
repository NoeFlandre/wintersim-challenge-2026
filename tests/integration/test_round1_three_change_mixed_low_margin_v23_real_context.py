"""Real Round 1 contract for the v23 low-margin delegation guard."""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

import pytest

from tests.integration.test_round1_multi_transfer_recovery_hold_v3_real_context import (
    _bootstrap_or_skip,
    _load_participant_module,
    _prepare_imports,
    _snapshot,
)

pytestmark = pytest.mark.integration


def _valid_midpoints(context: Any) -> tuple[dt.datetime, ...]:
    values: list[dt.datetime] = []
    for plan in context.disruption_plans:
        start_days = getattr(plan, "start_offset_days", None)
        duration_days = getattr(plan, "duration_days", None)
        if (
            not isinstance(start_days, (int, float))
            or isinstance(start_days, bool)
            or not math.isfinite(start_days)
            or not isinstance(duration_days, (int, float))
            or isinstance(duration_days, bool)
            or not math.isfinite(duration_days)
            or duration_days <= 0
        ):
            continue
        start = dt.datetime.min + dt.timedelta(days=start_days)
        end = start + dt.timedelta(days=duration_days)
        for integer_day in range(math.floor(start_days), math.ceil(start_days + duration_days)):
            midpoint = dt.datetime.min + dt.timedelta(days=integer_day + 0.5)
            if start <= midpoint < end:
                values.append(midpoint)
    return tuple(dict.fromkeys(values))


def _matching_constraints(participant: Any, edge: Any, state: Any) -> tuple[Any, ...]:
    leg_ids = {id(leg) for leg in edge.legs}
    arrival_names = {
        participant._port_name(port) for port in (*edge.intermediate_ports, edge.arrival)
    }
    return tuple(
        constraint
        for constraint in state.constraints
        if (constraint.kind == "leg" and constraint.target_identity in leg_ids)
        or (constraint.kind == "port" and constraint.arrival_name in arrival_names)
    )


def _is_v23_target(participant: Any, context: Any, now: Any, shipment: Any) -> bool:
    if not participant._should_hold(context, now, shipment):
        return False
    state = participant._active_state(context, now)
    if state is None:
        return False
    graphs = participant._graphs(context, state)
    demand = shipment.demand
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
    matching = _matching_constraints(participant, nominal[0], state)
    if changes != 3 or {item.kind for item in matching} != {"leg", "port"}:
        return False
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    profile = participant._route_profile(safe[0].route)
    if nominal_hours is None or detour_hours is None or recovery is None or profile is None:
        return False
    wait_hours = max(0.0, (recovery - now).total_seconds() / 3600.0)
    margin = detour_hours - (wait_hours + nominal_hours)
    return math.isfinite(margin) and 0.0 < margin < profile.headway_hours


def test_real_round1_v23_suppresses_only_derived_low_margin_case() -> None:
    source = _bootstrap_or_skip()
    _prepare_imports(source)

    import main  # type: ignore[import-not-found]  # noqa: F401, PLC0415
    import scenario_builders  # type: ignore[import-not-found]  # noqa: PLC0415
    from maritime_data_context.shipment import (  # type: ignore[import-not-found]  # noqa: PLC0415
        Shipment,
    )
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]  # noqa: PLC0415
        DefaultStrategy,
    )

    participant = _load_participant_module()
    template = scenario_builders.create_with_disruption()
    times = _valid_midpoints(template)
    assert times, "real Round 1 context must expose active midpoint timestamps"

    target_count = retained_count = 0
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
            before = _snapshot(context, shipment)
            target = _is_v23_target(participant, context, now, shipment)
            decision = participant.UserStrategy.assign_associated_bookings(context, now, shipment)
            assert _snapshot(context, shipment) == before
            if target:
                target_count += 1
                assert decision is None
            elif decision is False and participant._should_hold(context, now, shipment):
                retained_count += 1

    assert target_count > 0, "v23 target must activate in the real Round 1 context"
    assert retained_count > 0, "v23 must retain non-target v3 holds"
