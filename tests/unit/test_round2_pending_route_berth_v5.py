"""RED contract for Round 2 pending-route berth activation v5."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

from response_strategies.user_strategy import UserStrategy

ANCHOR = dt.datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _closure_plan(port: Any, *, start: float = 0.0) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=None,
        target_berth=SimpleNamespace(port=port),
        start_offset_days=start,
        duration_days=5.0,
        multiplier=1.0,
        close_berth=True,
    )


def _congestion_plan() -> SimpleNamespace:
    leg = SimpleNamespace(
        departure_port=_port("Leg origin"),
        arrival_port=_port("Leg destination"),
    )
    return SimpleNamespace(
        target_leg=leg,
        target_berth=None,
        start_offset_days=0.0,
        duration_days=5.0,
        multiplier=5.0,
        close_berth=False,
    )


def _pending_route(start: Any, key: Any) -> SimpleNamespace:
    return SimpleNamespace(
        source_service_route=object(),
        disruption_key=key,
        segments=[
            SimpleNamespace(
                sequence_index=1,
                associated_leg=SimpleNamespace(
                    departure_port=start,
                    arrival_port=_port("route middle"),
                ),
            ),
            SimpleNamespace(
                sequence_index=2,
                associated_leg=SimpleNamespace(
                    departure_port=_port("route end"),
                    arrival_port=start,
                ),
            ),
        ],
    )


def _fixture() -> tuple[Any, Any, Any, Any, Any]:
    berth_port = _port("Berth")
    context = SimpleNamespace(disruption_plans=[_closure_plan(_port("Closed"))])
    key = (("closed",), ())
    route = _pending_route(berth_port, key)
    ordinary = SimpleNamespace(carried_shipments=[])
    pending = SimpleNamespace(
        carried_shipments=[],
        pending_assigned_service_route=route,
    )
    return context, berth_port, ordinary, pending, route


def _call(context: Any, port: Any, vessels: Any, now: dt.datetime = ANCHOR) -> Any:
    return UserStrategy.select_vessel_for_berth(
        maritime_data_context=context,
        port=port,
        waiting_vessels=vessels,
        available_berths=[SimpleNamespace(port=port)],
        current_time=now + dt.timedelta(days=1),
        waiting_since_by_vessel=None,
    )


def test_active_closure_selects_pending_vessel_when_not_queue_head() -> None:
    context, port, ordinary, pending, _ = _fixture()

    assert _call(context, port, [ordinary, pending]) is pending


def test_pending_vessel_already_first_delegates() -> None:
    context, port, ordinary, pending, _ = _fixture()

    assert _call(context, port, [pending, ordinary]) is None


def test_inactive_closure_delegates() -> None:
    context, port, ordinary, pending, _ = _fixture()

    assert _call(context, port, [ordinary, pending], ANCHOR + dt.timedelta(days=10)) is None


def test_mixed_closure_and_congestion_delegates() -> None:
    context, port, ordinary, pending, _ = _fixture()
    context.disruption_plans.append(_congestion_plan())

    assert _call(context, port, [ordinary, pending]) is None


def test_carried_pending_vessel_delegates() -> None:
    context, port, ordinary, pending, _ = _fixture()
    pending.carried_shipments = [object()]

    assert _call(context, port, [ordinary, pending]) is None


def test_wrong_pending_route_start_port_delegates() -> None:
    context, port, ordinary, pending, _ = _fixture()
    pending.pending_assigned_service_route = _pending_route(_port("Other"), (("closed",), ()))

    assert _call(context, port, [ordinary, pending]) is None


def test_stale_pending_route_disruption_key_delegates() -> None:
    context, port, ordinary, pending, _ = _fixture()
    pending.pending_assigned_service_route = _pending_route(port, (("other",), ()))

    assert _call(context, port, [ordinary, pending]) is None


def test_malformed_pending_route_delegates_without_mutation() -> None:
    context, port, ordinary, pending, route = _fixture()
    route.segments[1].sequence_index = route.segments[0].sequence_index
    before = (list(context.disruption_plans), list(route.segments))

    assert _call(context, port, [ordinary, pending]) is None
    assert (context.disruption_plans, route.segments) == before


def test_malformed_queue_delegates() -> None:
    context, port, _, _, _ = _fixture()

    assert _call(context, port, object()) is None


def test_empty_queue_and_duplicate_queue_delegate() -> None:
    context, port, ordinary, _, _ = _fixture()

    assert _call(context, port, []) is None
    assert _call(context, port, [ordinary, ordinary]) is None


def test_none_or_malformed_vessel_delegates() -> None:
    context, port, ordinary, pending, route = _fixture()

    assert _call(context, port, [ordinary, None, pending]) is None
    malformed = SimpleNamespace(carried_shipments=None, pending_assigned_service_route=route)
    assert _call(context, port, [ordinary, malformed]) is None


def test_malformed_pending_route_fields_delegate() -> None:
    context, port, ordinary, pending, route = _fixture()

    route.source_service_route = None
    assert _call(context, port, [ordinary, pending]) is None
    route.source_service_route = object()
    route.segments = []
    assert _call(context, port, [ordinary, pending]) is None
    route.segments = [SimpleNamespace(sequence_index=True, associated_leg=object())]
    assert _call(context, port, [ordinary, pending]) is None
    route.segments = [SimpleNamespace(sequence_index=1, associated_leg=None)]
    assert _call(context, port, [ordinary, pending]) is None


def test_pending_route_without_start_port_delegates() -> None:
    context, port, ordinary, pending, route = _fixture()
    route.segments[0].associated_leg = SimpleNamespace(departure_port=None)

    assert _call(context, port, [ordinary, pending]) is None


def test_selector_fails_closed_on_unexpected_data_error() -> None:
    class BrokenContext:
        @property
        def disruption_plans(self) -> Any:
            raise AttributeError("broken context")

    assert (
        UserStrategy.select_vessel_for_berth(
            BrokenContext(),
            _port("Berth"),
            [SimpleNamespace(carried_shipments=[])],
            [],
            ANCHOR,
        )
        is None
    )
