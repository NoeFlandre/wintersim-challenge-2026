"""Real Round 1 integration check for the narrow congestion-tail policy.

The selected New Jersey -> Cartagena congestion window is active before the
Cartagena closure starts.  The real disruption graph has no complete safe
booking path for an exact matching demand, so the candidate may install one
original-route booking.  The test exercises the public hook against the real
organizer context and verifies that only the shipment/route booking relation
changes.

Skipped when the private Round 1 source has not been bootstrapped.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration


def _round1_source() -> Path:
    return round_source_dir("round1")


def _bootstrap_or_skip() -> Path:
    source = _round1_source()
    if not source.is_dir():
        pytest.skip(
            "Round 1 source not bootstrapped at "
            f"{source}. Run 'wsc2026 bootstrap --round round1 --archive <path>' "
            "to enable this integration test."
        )
    return source


def _add_source_to_path(source: Path) -> None:
    source_text = str(source)
    o2des_text = str(source / "o2despy")
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    if o2des_text not in sys.path:
        sys.path.insert(0, o2des_text)

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


def _load_participant_strategy() -> tuple[type, object]:
    participant_file = submission_strategies_dir() / "user_strategy.py"
    spec = importlib.util.spec_from_file_location(
        "wsc_round1_no_safe_congestion_candidate", str(participant_file)
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"could not load participant strategy from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UserStrategy, module


def test_real_no_safe_congestion_tail_installs_original_booking() -> None:
    source = _bootstrap_or_skip()
    _add_source_to_path(source)

    # Import the organizer runtime first.  Its response_strategies package has
    # the same top-level name as the participant package.
    import scenario_builders  # type: ignore[import-not-found]
    import simulation_model  # type: ignore[import-not-found]  # noqa: F401
    from maritime_data_context import Shipment  # type: ignore[import-not-found]
    from response_strategies.default_strategy import (  # type: ignore[import-not-found]
        DefaultStrategy,
    )

    context = scenario_builders.create_with_disruption()
    plan = next(
        plan
        for plan in context.disruption_plans
        if not plan.close_berth
        and plan.target_leg.departure_port.name == "New Jersey"
        and plan.target_leg.arrival_port.name == "Cartagena"
    )
    now = dt.datetime.min + dt.timedelta(days=plan.start_offset_days + 0.1)

    # Match the simulation lifecycle: the user route hook delegates and the
    # organizer fallback then attempts its alternative-route construction.
    DefaultStrategy.create_alternative_service_routes(context, now)

    UserStrategy, candidate_module = _load_participant_strategy()
    target_leg = plan.target_leg
    demand = next(
        demand
        for demand in context.demands
        if demand.origin_port is target_leg.departure_port
        and demand.destination_port is target_leg.arrival_port
    )
    shipment = Shipment(index=999999, teu_size=1, demand=demand)

    route_snapshot = tuple(context.service_routes)
    booking_snapshot = {route: tuple(route.associated_bookings) for route in context.service_routes}
    assert (
        candidate_module._has_safe_path(  # noqa: SLF001
            context,
            target_leg.departure_port,
            target_leg.arrival_port,
            candidate_module._active_state(context, now),  # noqa: SLF001
        )
        is False
    )

    result = UserStrategy.assign_associated_bookings(context, now, shipment)

    assert result is True
    assert tuple(context.service_routes) == route_snapshot
    assert shipment.current_booking_index == 1
    assert len(shipment.associated_bookings) == 1
    booking = shipment.associated_bookings[0]
    assert booking.service_route.source_service_route is None
    assert booking.service_route is next(
        route
        for route in context.service_routes
        if any(segment.associated_leg is target_leg for segment in route.segments)
    )
    for route, before in booking_snapshot.items():
        if route is booking.service_route:
            assert tuple(route.associated_bookings) == (booking,)
        else:
            assert tuple(route.associated_bookings) == before
