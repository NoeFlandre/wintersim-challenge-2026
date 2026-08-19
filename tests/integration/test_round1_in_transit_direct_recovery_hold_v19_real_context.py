"""Real-object contract for the Round 1 v19 in-transit policy."""

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
    path = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location("wsc_round1_v19_participant", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _timestamps(context: Any) -> tuple[dt.datetime, ...]:
    values: list[dt.datetime] = []
    for plan in context.disruption_plans:
        start = getattr(plan, "start_offset_days", None)
        duration = getattr(plan, "duration_days", None)
        if (
            isinstance(start, (int, float))
            and not isinstance(start, bool)
            and math.isfinite(start)
            and isinstance(duration, (int, float))
            and not isinstance(duration, bool)
            and math.isfinite(duration)
            and duration > 0
        ):
            values.extend(
                dt.datetime.min + dt.timedelta(days=start + duration * fraction)
                for fraction in (0.25, 0.5, 0.75)
            )
    return tuple(sorted(set(values)))


def _output_signature(source: Path) -> tuple[bool, str | None, int | None]:
    path = source / "Output" / "ATT_By_Statistics_Interval.csv"
    if not path.exists():
        return False, None, None
    data = path.read_bytes()
    return True, hashlib.sha256(data).hexdigest(), len(data)


def _snapshot(source: Path, context: Any, shipment: Any, vessel: Any) -> tuple[Any, ...]:
    booking = shipment.associated_bookings[0]
    segment = vessel.current_segment
    return (
        _output_signature(source),
        tuple(id(port) for port in context.ports),
        tuple(id(route) for route in context.service_routes),
        tuple(id(item) for item in vessel.carried_shipments),
        id(vessel.current_segment),
        getattr(segment, "sequence_index", None),
        id(booking.service_route),
        booking.sequence_index,
        booking.departure_segment_index,
        booking.arrival_segment_index,
        shipment.current_booking_index,
        id(shipment.carrying_vessel),
    )


def _install_carried(
    participant: Any,
    context: Any,
    now: dt.datetime,
    demand: Any,
    index: int,
    shipment_class: Any,
    booking_class: Any,
) -> tuple[Any, Any] | None:
    state = participant._active_state(context, now)
    if state is None:
        return None
    graphs = participant._graphs(context, state)
    if graphs is None:
        return None
    nominal = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[0]
    )
    safe = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[1]
    )
    if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
        return None
    changes = sum(
        left.route is not right.route for left, right in zip(safe, safe[1:], strict=False)
    )
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    if (
        changes < 2
        or recovery is None
        or nominal_hours is None
        or detour_hours is None
        or not max(0.0, (recovery - now).total_seconds() / 3600.0) + nominal_hours < detour_hours
    ):
        return None

    edge = nominal[0]
    route = edge.route
    segments = sorted(route.segments, key=lambda item: item.sequence_index)
    first = next(
        (
            position
            for position, segment in enumerate(segments)
            if segment.associated_leg is edge.legs[0]
        ),
        None,
    )
    if first is None:
        return None
    vessel = next((item for item in route.deployed_vessels if not item.carried_shipments), None)
    if vessel is None:
        return None
    shipment = shipment_class(
        index=index,
        teu_size=1,
        demand=demand,
        current_storage_port=demand.origin_port,
        generated_time=now,
    )
    arrival = (first + len(edge.legs) - 1) % len(segments)
    booking = booking_class(
        sequence_index=1,
        shipment=shipment,
        service_route=route,
        departure_segment_index=segments[first].sequence_index,
        arrival_segment_index=segments[arrival].sequence_index,
    )
    shipment.associated_bookings.append(booking)
    shipment.current_booking_index = 1
    shipment.carrying_vessel = vessel
    vessel.carried_shipments.append(shipment)
    vessel.current_segment = segments[(first - 1) % len(segments)]
    if vessel not in vessel.current_segment.current_vessels:
        vessel.current_segment.current_vessels.append(vessel)
    return shipment, vessel


def test_real_round1_direct_current_activation_is_non_mutating() -> None:
    source = round_source_dir("round1")
    if not source.is_dir():
        pytest.skip("Round 1 organizer source is unavailable")
    _prepare_imports(source)

    import main  # type: ignore[import-not-found]  # noqa: F401
    import scenario_builders  # type: ignore[import-not-found]
    from maritime_data_context.booking import Booking  # type: ignore[import-not-found]
    from maritime_data_context.shipment import Shipment  # type: ignore[import-not-found]
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )

    participant = _load_participant()
    template = scenario_builders.create_with_disruption()
    found = False
    for now in _timestamps(template):
        base = scenario_builders.create_with_disruption()
        DefaultStrategy.create_alternative_service_routes(base, now)
        for index, demand in enumerate(base.demands):
            probe = Shipment(
                index=index,
                teu_size=1,
                demand=demand,
                current_storage_port=demand.origin_port,
                generated_time=now,
            )
            if not participant._should_hold(base, now, probe):
                continue
            context = scenario_builders.create_with_disruption()
            DefaultStrategy.create_alternative_service_routes(context, now)
            setup = _install_carried(
                participant,
                context,
                now,
                context.demands[index],
                index,
                Shipment,
                Booking,
            )
            if setup is None:
                continue
            shipment, vessel = setup
            before = _snapshot(source, context, shipment, vessel)
            assert (
                participant.UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)
                is False
            )
            assert _snapshot(source, context, shipment, vessel) == before
            found = True
            break
        if found:
            break
    assert found, "v19 has no qualifying direct-current activation in real Round 1 objects"
