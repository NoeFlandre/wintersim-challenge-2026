"""RED/GREEN tests for empty-vessel alternative-route reservations."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from response_strategies.user_strategy import UserStrategy


def _now(day: float) -> datetime:
    return datetime.min + timedelta(days=day)


def _fixture(
    *,
    old_carried: bool = True,
    candidate_carried: bool = False,
    pending_key: object | None = None,
) -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    origin = SimpleNamespace(name="Origin")
    destination = SimpleNamespace(name="Destination")
    leg = SimpleNamespace(departure_port=origin, arrival_port=destination)
    plan = SimpleNamespace(
        start_offset_days=10.0,
        duration_days=5.0,
        multiplier=2.0,
        close_berth=False,
        target_leg=leg,
        target_berth=None,
    )
    source = SimpleNamespace(id="S1", deployed_vessels=[])
    alternative = SimpleNamespace(
        id="S1-ALT-1",
        source_service_route=source,
        disruption_key=((), (("origin", "destination"),)) if pending_key is None else pending_key,
    )
    old = SimpleNamespace(
        index=2,
        assigned_service_route=source,
        pending_assigned_service_route=alternative,
        carried_shipments=[SimpleNamespace(teu_size=10)] if old_carried else [],
    )
    candidate = SimpleNamespace(
        index=3,
        assigned_service_route=source,
        pending_assigned_service_route=None,
        carried_shipments=[SimpleNamespace(teu_size=1)] if candidate_carried else [],
    )
    source.deployed_vessels = [old, candidate]
    context = SimpleNamespace(
        disruption_plans=[plan],
        service_routes=[source, alternative],
        legs=[leg],
        vessels=[old, candidate],
    )
    return context, old, candidate, alternative


def test_empty_source_vessel_replaces_carrying_pending_reservation() -> None:
    context, old, candidate, alternative = _fixture()
    routes_before = tuple(context.service_routes)
    vessels_before = tuple(context.vessels)
    legs_before = tuple(context.legs)

    result = UserStrategy.create_alternative_service_routes(context, _now(12.0))

    assert result is True
    assert old.pending_assigned_service_route is None
    assert candidate.pending_assigned_service_route is alternative
    assert tuple(context.service_routes) == routes_before
    assert tuple(context.vessels) == vessels_before
    assert tuple(context.legs) == legs_before
    assert old.assigned_service_route is candidate.assigned_service_route


@pytest.mark.parametrize(
    ("now", "fixture_kwargs"),
    [
        (_now(9.999), {}),
        (_now(15.0), {}),
        (_now(12.0), {"old_carried": False}),
        (_now(12.0), {"candidate_carried": True}),
        (_now(12.0), {"pending_key": (((), (("wrong", "port"),)))}),
    ],
)
def test_non_actionable_state_delegates_without_mutation(
    now: datetime, fixture_kwargs: dict[str, object]
) -> None:
    context, old, candidate, alternative = _fixture(**fixture_kwargs)
    before = (
        old.pending_assigned_service_route,
        candidate.pending_assigned_service_route,
        tuple(context.service_routes),
        tuple(context.vessels),
        tuple(context.legs),
    )

    assert UserStrategy.create_alternative_service_routes(context, now) is None
    assert (
        old.pending_assigned_service_route,
        candidate.pending_assigned_service_route,
        tuple(context.service_routes),
        tuple(context.vessels),
        tuple(context.legs),
    ) == before
    assert alternative is context.service_routes[1]


@pytest.mark.parametrize(
    "context_mutation",
    [
        lambda context: setattr(context, "disruption_plans", None),
        lambda context: setattr(context.disruption_plans[0], "target_leg", None),
        lambda context: setattr(context.disruption_plans[0], "duration_days", float("nan")),
        lambda context: setattr(context, "service_routes", None),
        lambda context: setattr(context, "vessels", object()),
    ],
)
def test_malformed_state_fails_closed(context_mutation) -> None:
    context, old, candidate, _alternative = _fixture()
    context_mutation(context)
    old_before = old.pending_assigned_service_route
    candidate_before = candidate.pending_assigned_service_route

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is None
    assert old.pending_assigned_service_route is old_before
    assert candidate.pending_assigned_service_route is candidate_before


def test_candidate_with_existing_pending_reservation_is_not_reused() -> None:
    context, old, candidate, alternative = _fixture()
    other = SimpleNamespace(id="S2-ALT-1")
    candidate.pending_assigned_service_route = other

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is None
    assert old.pending_assigned_service_route is alternative
    assert candidate.pending_assigned_service_route is other


def test_first_empty_source_vessel_is_selected_in_context_order() -> None:
    context, old, first_candidate, alternative = _fixture()
    second_candidate = SimpleNamespace(
        index=4,
        assigned_service_route=old.assigned_service_route,
        pending_assigned_service_route=None,
        carried_shipments=[],
    )
    old.assigned_service_route.deployed_vessels.append(second_candidate)
    context.vessels.append(second_candidate)

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is True
    assert first_candidate.pending_assigned_service_route is alternative
    assert second_candidate.pending_assigned_service_route is None


def test_each_matching_alternative_gets_at_most_one_replacement() -> None:
    context, old, candidate, alternative = _fixture()
    source_two = SimpleNamespace(id="S2", deployed_vessels=[])
    alternative_two = SimpleNamespace(
        id="S2-ALT-1",
        source_service_route=source_two,
        disruption_key=alternative.disruption_key,
    )
    old_two = SimpleNamespace(
        index=5,
        assigned_service_route=source_two,
        pending_assigned_service_route=alternative_two,
        carried_shipments=[SimpleNamespace(teu_size=2)],
    )
    candidate_two = SimpleNamespace(
        index=6,
        assigned_service_route=source_two,
        pending_assigned_service_route=None,
        carried_shipments=[],
    )
    source_two.deployed_vessels = [old_two, candidate_two]
    context.service_routes.extend([source_two, alternative_two])
    context.vessels.extend([old_two, candidate_two])

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is True
    assert old.pending_assigned_service_route is None
    assert candidate.pending_assigned_service_route is alternative
    assert old_two.pending_assigned_service_route is None
    assert candidate_two.pending_assigned_service_route is alternative_two


def test_closed_berth_disruption_key_is_normalized() -> None:
    context, old, candidate, alternative = _fixture()
    plan = context.disruption_plans[0]
    plan.close_berth = True
    plan.target_berth = SimpleNamespace(port=SimpleNamespace(name="Closed Port"))
    plan.multiplier = 1.0
    alternative.disruption_key = (("closed port",), ())

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is True
    assert old.pending_assigned_service_route is None
    assert candidate.pending_assigned_service_route is alternative


@pytest.mark.parametrize(
    "mutation",
    [
        lambda context: setattr(context, "disruption_plans", object()),
        lambda context: setattr(context.disruption_plans[0], "start_offset_days", None),
        lambda context: setattr(context.disruption_plans[0], "duration_days", 0),
        lambda context: setattr(context.disruption_plans[0], "close_berth", True),
        lambda context: setattr(context.disruption_plans[0], "multiplier", "slow"),
        lambda context: setattr(context.disruption_plans[0], "target_leg", None),
    ],
)
def test_malformed_active_plan_delegates_without_pointer_mutation(mutation) -> None:
    context, old, candidate, _alternative = _fixture()
    mutation(context)
    old_before = old.pending_assigned_service_route
    candidate_before = candidate.pending_assigned_service_route

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is None
    assert old.pending_assigned_service_route is old_before
    assert candidate.pending_assigned_service_route is candidate_before


@pytest.mark.parametrize("attribute", ["carried_shipments", "pending_assigned_service_route"])
def test_missing_vessel_state_fails_closed(attribute: str) -> None:
    context, old, candidate, _alternative = _fixture()
    if attribute == "carried_shipments":
        old.carried_shipments = None
    else:
        candidate.pending_assigned_service_route = None
        delattr(candidate, "carried_shipments")

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is None
    assert old.pending_assigned_service_route is not None


def test_malformed_deployed_vessel_collection_fails_closed() -> None:
    context, old, _candidate, _alternative = _fixture()
    old.assigned_service_route.deployed_vessels = object()

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is None
    assert old.pending_assigned_service_route is not None


def test_non_source_pending_vessel_is_not_reassigned() -> None:
    context, old, _candidate, _alternative = _fixture()
    old.assigned_service_route = SimpleNamespace(id="other")

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is None
    assert old.pending_assigned_service_route is not None


def test_stale_pending_route_defers_to_fallback_cleanup() -> None:
    context, old, candidate, _alternative = _fixture()
    stale = SimpleNamespace(disruption_key=((), (("stale", "leg"),)))
    candidate.pending_assigned_service_route = stale

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is None
    assert old.pending_assigned_service_route is not None
    assert candidate.pending_assigned_service_route is stale


def test_failing_pointer_write_rolls_back_old_reservation() -> None:
    context, old, candidate, alternative = _fixture()

    class FailingVessel:
        def __init__(self) -> None:
            self.assigned_service_route = old.assigned_service_route
            self.carried_shipments: list[object] = []

        @property
        def pending_assigned_service_route(self):
            return None

        @pending_assigned_service_route.setter
        def pending_assigned_service_route(self, value):
            raise RuntimeError("synthetic write failure")

    failing = FailingVessel()
    old.assigned_service_route.deployed_vessels[1] = failing
    context.vessels[1] = failing

    assert UserStrategy.create_alternative_service_routes(context, _now(12.0)) is None
    assert old.pending_assigned_service_route is alternative
    assert candidate.pending_assigned_service_route is None


def test_other_hooks_still_delegate() -> None:
    assert UserStrategy.select_vessel_for_berth(None, None, [], [], _now(1.0), {}) is None
    assert UserStrategy.assign_associated_bookings(None, _now(1.0), None) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(None, _now(1.0), None) is None
