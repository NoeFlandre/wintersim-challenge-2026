from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta
from math import isclose
from pathlib import Path
from typing import Any

import pytest
import response_strategies.transshipment_readiness as readiness
from response_strategies.user_strategy import UserStrategy


class Obj:
    pass


class Vessel:
    def __init__(
        self,
        *,
        index: int,
        vessel_class: Any,
        route: Any,
        current_segment: Any,
        carried_shipments: list[Any] | None = None,
        discharging_shipments: list[Any] | None = None,
        loading_shipments: list[Any] | None = None,
    ) -> None:
        self.index = index
        self.vessel_class = vessel_class
        self.assigned_service_route = route
        self.pending_assigned_service_route = None
        self.current_segment = current_segment
        self.carried_shipments = list(carried_shipments or [])
        self._discharging_shipments = list(discharging_shipments or [])
        self._loading_shipments = list(loading_shipments or [])

    def get_next_segment(self) -> Any:
        segments = self.assigned_service_route.segments
        position = next(i for i, segment in enumerate(segments) if segment is self.current_segment)
        return segments[(position + 1) % len(segments)]

    def get_discharging_shipments_at_current_segment(self) -> list[Any]:
        return list(self._discharging_shipments)

    def get_loading_shipments_at_next_segment(self) -> list[Any]:
        return list(self._loading_shipments)


def _port(name: str) -> Any:
    port = Obj()
    port.name = name
    port.berths = []
    port.shipments_in_storage = []
    return port


def _route(route_id: str, ports: list[Any], distances: list[float]) -> Any:
    route = Obj()
    route.id = route_id
    route.source_service_route = None
    route.disruption_key = None
    route.deployed_vessels = []
    route.segments = []
    for index, (departure, arrival, distance) in enumerate(
        zip(ports, ports[1:] + ports[:1], distances, strict=True)
    ):
        leg = Obj()
        leg.departure_port = departure
        leg.arrival_port = arrival
        leg.sailing_distance = distance
        leg.sailing_time_multiplier = 1
        segment = Obj()
        segment.sequence_index = index
        segment.associated_leg = leg
        segment.associated_service_route = route
        route.segments.append(segment)
    return route


def _vessel_class(*, capacity: float, speed: float, loa: float) -> Any:
    vessel_class = Obj()
    vessel_class.teu_capacity = capacity
    vessel_class.sailing_speed = speed
    vessel_class.loa = loa
    return vessel_class


def _booking(
    *,
    sequence_index: int,
    shipment: Any,
    route: Any,
    departure_segment_index: int,
    arrival_segment_index: int,
) -> Any:
    booking = Obj()
    booking.sequence_index = sequence_index
    booking.shipment = shipment
    booking.service_route = route
    booking.departure_segment_index = departure_segment_index
    booking.arrival_segment_index = arrival_segment_index
    return booking


def _positive_state() -> dict[str, Any]:
    port = _port("transfer")
    destination = _port("destination")
    origin = _port("origin")
    buffer_destination = _port("buffer-destination")
    other_destination = _port("other-destination")

    berth = Obj()
    berth.port = port
    port.berths.append(berth)

    receiver_route = _route("receiver", [port, destination], [100.0, 100.0])
    feeder_route = _route("feeder", [origin, port], [20.0, 20.0])
    buffer_route = _route("buffer", [port, buffer_destination], [10.0, 10.0])
    other_route = _route("other", [port, other_destination], [10.0, 10.0])

    receiver = Vessel(
        index=0,
        vessel_class=_vessel_class(capacity=100.0, speed=10.0, loa=220.0),
        route=receiver_route,
        current_segment=receiver_route.segments[1],
    )
    buffer = Vessel(
        index=1,
        vessel_class=_vessel_class(capacity=10.0, speed=10.0, loa=54.0),
        route=buffer_route,
        current_segment=buffer_route.segments[1],
    )
    other = Vessel(
        index=2,
        vessel_class=_vessel_class(capacity=10.0, speed=10.0, loa=54.0),
        route=other_route,
        current_segment=other_route.segments[1],
    )
    receiver_route.deployed_vessels = [receiver]
    buffer_route.deployed_vessels = [buffer]
    other_route.deployed_vessels = [other]

    shipment = Obj()
    shipment.teu_size = 5.0
    shipment.current_storage_port = port
    shipment.carrying_vessel = None
    inbound = _booking(
        sequence_index=1,
        shipment=shipment,
        route=feeder_route,
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    outbound = _booking(
        sequence_index=2,
        shipment=shipment,
        route=receiver_route,
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    shipment.associated_bookings = [inbound, outbound]
    shipment.current_booking_index = 1
    port.shipments_in_storage.append(shipment)

    context = Obj()
    context.disruption_plans = []
    context.ports = [port, destination, origin, buffer_destination, other_destination]

    current_time = datetime(2026, 1, 2)
    waiting_vessels = [receiver, buffer, other]
    waiting_since = {
        receiver: current_time - timedelta(hours=10),
        buffer: current_time,
        other: current_time,
    }
    return {
        "context": context,
        "port": port,
        "berth": berth,
        "receiver": receiver,
        "buffer": buffer,
        "other": other,
        "shipment": shipment,
        "receiver_route": receiver_route,
        "feeder_route": feeder_route,
        "buffer_route": buffer_route,
        "other_route": other_route,
        "destination": destination,
        "origin": origin,
        "waiting_vessels": waiting_vessels,
        "waiting_since": waiting_since,
        "current_time": current_time,
    }


def test_positive_transition_margin_selects_original_buffer_object() -> None:
    state = _positive_state()

    selected = UserStrategy.select_vessel_for_berth(
        maritime_data_context=state["context"],
        port=state["port"],
        waiting_vessels=state["waiting_vessels"],
        available_berths=[state["berth"]],
        current_time=state["current_time"],
        waiting_since_by_vessel=state["waiting_since"],
    )

    assert selected is state["buffer"]
    assert any(selected is vessel for vessel in state["waiting_vessels"])


def test_fallback_tie_preserves_original_order_but_is_not_strict() -> None:
    state = _positive_state()
    for vessel in state["waiting_vessels"]:
        vessel.vessel_class.teu_capacity = 10.0
        state["waiting_since"][vessel] = state["current_time"]

    rank = getattr(
        readiness,
        "_fallback_ranking",
        lambda *args: (None, False),
    )
    winner, is_strict = rank(
        state["waiting_vessels"],
        state["current_time"],
        state["waiting_since"],
    )

    assert winner is state["receiver"]
    assert is_strict is False


def _decision(state: dict[str, Any]) -> readiness.BarrierDecision | None:
    return readiness.evaluate_transshipment_readiness_barrier(
        maritime_data_context=state["context"],
        port=state["port"],
        waiting_vessels=state["waiting_vessels"],
        available_berths=[state["berth"]],
        current_time=state["current_time"],
        waiting_since_by_vessel=state["waiting_since"],
    )


def _select(state: dict[str, Any], available_berths: list[Any] | None = None) -> object | None:
    return UserStrategy.select_vessel_for_berth(
        maritime_data_context=state["context"],
        port=state["port"],
        waiting_vessels=state["waiting_vessels"],
        available_berths=[state["berth"]] if available_berths is None else available_berths,
        current_time=state["current_time"],
        waiting_since_by_vessel=state["waiting_since"],
    )


def _cargo(teu: float) -> Any:
    shipment = Obj()
    shipment.teu_size = teu
    return shipment


def _add_mature_shipment(state: dict[str, Any], teu: float) -> Any:
    shipment = Obj()
    shipment.teu_size = teu
    shipment.current_storage_port = state["port"]
    shipment.carrying_vessel = None
    booking = _booking(
        sequence_index=1,
        shipment=shipment,
        route=state["receiver_route"],
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    shipment.associated_bookings = [booking]
    shipment.current_booking_index = 1
    state["port"].shipments_in_storage.append(shipment)
    return shipment


def _snapshot(state: dict[str, Any]) -> tuple[Any, ...]:
    routes = (
        state["receiver_route"],
        state["feeder_route"],
        state["buffer_route"],
        state["other_route"],
    )
    vessels = tuple(state["waiting_vessels"])
    shipments = tuple(state["port"].shipments_in_storage)
    return (
        tuple(id(vessel) for vessel in state["waiting_vessels"]),
        tuple(id(berth) for berth in state["port"].berths),
        tuple((id(vessel), value) for vessel, value in state["waiting_since"].items()),
        tuple(
            (
                id(route),
                route.source_service_route,
                route.disruption_key,
                tuple(id(segment) for segment in route.segments),
                tuple(id(vessel) for vessel in route.deployed_vessels),
            )
            for route in routes
        ),
        tuple(
            (
                id(vessel),
                id(vessel.assigned_service_route),
                vessel.pending_assigned_service_route,
                id(vessel.current_segment),
                tuple(id(shipment) for shipment in vessel.carried_shipments),
            )
            for vessel in vessels
        ),
        tuple(
            (
                id(shipment),
                shipment.teu_size,
                id(shipment.current_storage_port),
                shipment.carrying_vessel,
                shipment.current_booking_index,
                tuple(id(booking) for booking in shipment.associated_bookings),
            )
            for shipment in shipments
        ),
        tuple(id(shipment) for shipment in state["port"].shipments_in_storage),
        tuple(id(plan) for plan in state["context"].disruption_plans),
    )


def test_positive_decision_uses_exact_formulas_and_units() -> None:
    decision = _decision(_positive_state())

    assert decision is not None
    assert decision.guaranteed_transitional_teu == 5.0
    assert decision.next_opportunity_hours == 0.95 * 200.0 / 10.0
    expected_service = 3.0 + 10.0 / 45.0
    assert decision.buffer_service_hours == expected_service
    assert decision.affected_receiver_teu == 0.0
    assert decision.net_teu_hours == 5.0 * (19.0 - expected_service)


def test_fallback_missing_wait_start_is_zero() -> None:
    state = _positive_state()
    for vessel in state["waiting_vessels"]:
        vessel.vessel_class.teu_capacity = 10.0
    state["waiting_since"] = {
        state["buffer"]: state["current_time"],
        state["other"]: state["current_time"],
    }

    winner, strict = readiness._fallback_ranking(
        state["waiting_vessels"], state["current_time"], state["waiting_since"]
    )

    assert winner is state["receiver"]
    assert strict is False


def test_fallback_negative_wait_clamps_to_zero() -> None:
    state = _positive_state()
    for vessel in state["waiting_vessels"]:
        vessel.vessel_class.teu_capacity = 10.0
        state["waiting_since"][vessel] = state["current_time"]
    state["waiting_since"][state["receiver"]] = state["current_time"] + timedelta(hours=5)

    winner, strict = readiness._fallback_ranking(
        state["waiting_vessels"], state["current_time"], state["waiting_since"]
    )

    assert winner is state["receiver"]
    assert strict is False


def test_fallback_carried_teu_contributes_thirty_percent() -> None:
    state = _positive_state()
    for vessel in state["waiting_vessels"]:
        vessel.vessel_class.teu_capacity = 10.0
        state["waiting_since"][vessel] = state["current_time"]
    state["buffer"].carried_shipments.append(_cargo(1.0))

    winner, strict = readiness._fallback_ranking(
        state["waiting_vessels"], state["current_time"], state["waiting_since"]
    )

    assert winner is state["buffer"]
    assert strict is True


def test_fallback_capacity_contributes_twenty_percent() -> None:
    state = _positive_state()
    for vessel in state["waiting_vessels"]:
        state["waiting_since"][vessel] = state["current_time"]

    winner, strict = readiness._fallback_ranking(
        state["waiting_vessels"], state["current_time"], state["waiting_since"]
    )

    assert winner is state["receiver"]
    assert strict is True


def test_fallback_discharge_plus_loading_workload_has_ten_percent_penalty() -> None:
    state = _positive_state()
    for vessel in state["waiting_vessels"]:
        vessel.vessel_class.teu_capacity = 10.0
        state["waiting_since"][vessel] = state["current_time"]
    state["receiver"]._discharging_shipments = [_cargo(2.0)]
    state["receiver"]._loading_shipments = [_cargo(3.0)]
    state["buffer"]._loading_shipments = [_cargo(10.0)]
    state["other"]._discharging_shipments = [_cargo(20.0)]

    winner, strict = readiness._fallback_ranking(
        state["waiting_vessels"], state["current_time"], state["waiting_since"]
    )

    assert winner is state["receiver"]
    assert strict is True


@pytest.mark.parametrize("available_count", [0, 2])
def test_requires_exactly_one_available_berth(available_count: int) -> None:
    state = _positive_state()
    available = [state["berth"]] * available_count

    assert _select(state, available) is None


def test_requires_exactly_one_total_port_berth() -> None:
    state = _positive_state()
    extra = Obj()
    extra.port = state["port"]
    state["port"].berths.append(extra)

    assert _select(state) is None


def test_available_berth_must_belong_to_port() -> None:
    state = _positive_state()
    state["berth"].port = state["destination"]

    assert _select(state) is None


def test_strict_unique_fallback_receiver_is_required() -> None:
    state = _positive_state()
    for vessel in state["waiting_vessels"]:
        vessel.vessel_class.teu_capacity = 10.0
        state["waiting_since"][vessel] = state["current_time"]

    assert _select(state) is None


def test_valid_mature_shipment_enters_capacity_and_affected_teu() -> None:
    state = _positive_state()
    _add_mature_shipment(state, 7.0)

    decision = _decision(state)

    assert decision is not None
    assert decision.guaranteed_transitional_teu == 5.0
    assert decision.affected_receiver_teu == 7.0


def test_same_route_continuation_is_not_a_transfer() -> None:
    state = _positive_state()
    shipment = state["shipment"]
    shipment.associated_bookings[0].service_route = state["receiver_route"]

    assert _select(state) is None


def test_next_booking_is_smallest_sequence_greater_than_current() -> None:
    state = _positive_state()
    shipment = state["shipment"]
    unrelated_route = state["other_route"]
    middle = _booking(
        sequence_index=2,
        shipment=shipment,
        route=unrelated_route,
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    shipment.associated_bookings[1].sequence_index = 3
    shipment.associated_bookings.insert(1, middle)

    assert _select(state) is None


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_current",
        "duplicate_indexes",
        "broken_reference",
        "missing_route",
        "missing_segment",
        "wrong_storage_port",
        "carried_storage",
        "nonpositive_teu",
    ],
)
def test_malformed_potential_receiver_cargo_delegates(mutation: str) -> None:
    state = _positive_state()
    shipment = state["shipment"]
    if mutation == "missing_current":
        shipment.current_booking_index = 99
    elif mutation == "duplicate_indexes":
        shipment.associated_bookings[1].sequence_index = 1
    elif mutation == "broken_reference":
        shipment.associated_bookings[0].shipment = Obj()
    elif mutation == "missing_route":
        shipment.associated_bookings[0].service_route = None
    elif mutation == "missing_segment":
        shipment.associated_bookings[0].arrival_segment_index = 99
    elif mutation == "wrong_storage_port":
        shipment.current_storage_port = state["destination"]
    elif mutation == "carried_storage":
        shipment.carrying_vessel = state["receiver"]
    else:
        shipment.teu_size = 0.0

    assert _select(state) is None


def test_capacity_equality_is_allowed_for_onboard_mature_and_transitional_teu() -> None:
    state = _positive_state()
    mature = _add_mature_shipment(state, 5.0)
    onboard = _cargo(10.0)
    state["receiver"].carried_shipments = [onboard]
    state["receiver"].vessel_class.teu_capacity = 20.0
    assert mature in state["port"].shipments_in_storage

    assert _select(state) is state["buffer"]


def test_one_teu_whole_set_capacity_overflow_delegates_without_subset_selection() -> None:
    state = _positive_state()
    _add_mature_shipment(state, 5.0)
    state["receiver"].carried_shipments = [_cargo(11.0)]
    state["receiver"].vessel_class.teu_capacity = 20.0

    assert _select(state) is None


def test_receiver_discharge_cargo_remains_in_affected_teu_but_not_onboard_after_discharge() -> None:
    state = _positive_state()
    discharge = _cargo(10.0)
    state["receiver"].carried_shipments = [discharge]
    state["receiver"]._discharging_shipments = [discharge]
    state["receiver"].vessel_class.teu_capacity = 5.0

    decision = _decision(state)

    assert decision is not None
    assert decision.affected_receiver_teu == 10.0


def test_transitional_teu_is_excluded_from_affected_receiver_teu() -> None:
    decision = _decision(_positive_state())

    assert decision is not None
    assert decision.guaranteed_transitional_teu == 5.0
    assert decision.affected_receiver_teu == 0.0


def test_route_full_cycle_uses_every_leg_speed_and_point_ninety_five_factor() -> None:
    state = _positive_state()
    state["receiver_route"].segments[0].associated_leg.sailing_distance = 30.0
    state["receiver_route"].segments[1].associated_leg.sailing_distance = 70.0
    state["receiver"].vessel_class.sailing_speed = 20.0

    decision = _decision(state)

    assert decision is not None
    assert decision.next_opportunity_hours == 0.95 * 100.0 / 20.0


def test_other_deployed_vessel_uses_own_speed_and_minimum_opportunity() -> None:
    state = _positive_state()
    route = state["receiver_route"]
    extra = Vessel(
        index=9,
        vessel_class=_vessel_class(capacity=20.0, speed=20.0, loa=100.0),
        route=route,
        current_segment=route.segments[0],
    )
    route.deployed_vessels.append(extra)

    decision = _decision(state)

    assert decision is not None
    assert decision.next_opportunity_hours == 0.95 * 100.0 / 20.0


def test_other_vessel_immediate_predecessor_zero_opportunity_delegates() -> None:
    state = _positive_state()
    route = state["receiver_route"]
    extra = Vessel(
        index=9,
        vessel_class=_vessel_class(capacity=20.0, speed=20.0, loa=100.0),
        route=route,
        current_segment=route.segments[1],
    )
    route.deployed_vessels.append(extra)

    assert _select(state) is None


@pytest.mark.parametrize(
    "mutation",
    [
        "disconnected",
        "duplicate_indexes",
        "missing_current",
        "receiver_not_deployed",
        "pending_receiver",
        "alternative_route",
        "zero_speed",
        "nan_distance",
        "unstable_multiplier",
    ],
)
def test_invalid_or_unstable_receiver_route_delegates(mutation: str) -> None:
    state = _positive_state()
    route = state["receiver_route"]
    if mutation == "disconnected":
        route.segments[0].associated_leg.arrival_port = state["origin"]
    elif mutation == "duplicate_indexes":
        route.segments[1].sequence_index = route.segments[0].sequence_index
    elif mutation == "missing_current":
        state["receiver"].current_segment = Obj()
    elif mutation == "receiver_not_deployed":
        route.deployed_vessels = []
    elif mutation == "pending_receiver":
        state["receiver"].pending_assigned_service_route = state["other_route"]
    elif mutation == "alternative_route":
        route.disruption_key = "alternative"
    elif mutation == "zero_speed":
        state["receiver"].vessel_class.sailing_speed = 0.0
    elif mutation == "nan_distance":
        route.segments[0].associated_leg.sailing_distance = float("nan")
    else:
        route.segments[0].associated_leg.sailing_time_multiplier = 1.1

    assert _select(state) is None


def test_buffer_service_bound_uses_fixed_time_cranes_and_capacity_fill() -> None:
    state = _positive_state()
    buffer = state["buffer"]
    buffer.vessel_class.loa = 110.0
    onboard = _cargo(4.0)
    discharge = _cargo(1.0)
    loading = _cargo(2.0)
    buffer.carried_shipments = [onboard, discharge]
    buffer._discharging_shipments = [discharge]
    buffer._loading_shipments = [loading]
    buffer.vessel_class.teu_capacity = 10.0

    service = readiness._buffer_service_hours(buffer)

    assert service == 3.0 + (1.0 + 2.0 + (10.0 - 4.0)) / (45.0 * 2.0)


def test_buffer_service_uses_at_least_one_crane_below_fifty_five_metres() -> None:
    state = _positive_state()
    state["buffer"].vessel_class.loa = 1.0

    assert readiness._buffer_service_hours(state["buffer"]) == 3.0 + 10.0 / 45.0


def test_pending_buffer_reassignment_excludes_only_that_buffer() -> None:
    state = _positive_state()
    state["buffer"].pending_assigned_service_route = state["receiver_route"]

    assert _select(state) is state["other"]


def test_buffer_on_same_receiver_departure_causes_safe_delegation() -> None:
    state = _positive_state()
    buffer = state["buffer"]
    buffer.assigned_service_route = state["receiver_route"]
    buffer.current_segment = state["receiver"].current_segment
    state["receiver_route"].deployed_vessels.append(buffer)

    assert _select(state) is None


def test_buffer_with_transition_waiting_for_its_departure_is_excluded() -> None:
    state = _positive_state()
    shipment = Obj()
    shipment.teu_size = 1.0
    shipment.current_storage_port = state["port"]
    shipment.carrying_vessel = None
    inbound = _booking(
        sequence_index=1,
        shipment=shipment,
        route=state["feeder_route"],
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    outbound = _booking(
        sequence_index=2,
        shipment=shipment,
        route=state["buffer_route"],
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    shipment.associated_bookings = [inbound, outbound]
    shipment.current_booking_index = 1
    state["port"].shipments_in_storage.append(shipment)

    assert _select(state) is state["other"]


def test_below_congestion_threshold_requires_receiver_first_after_buffer_removal() -> None:
    state = _positive_state()
    state["waiting_vessels"] = [state["buffer"], state["other"], state["receiver"]]

    assert _select(state) is None


def test_at_congestion_threshold_recomputes_strict_receiver_ranking() -> None:
    state = _positive_state()
    fourth_route = _route(
        "fourth",
        [state["port"], _port("fourth-destination")],
        [10.0, 10.0],
    )
    fourth = Vessel(
        index=3,
        vessel_class=_vessel_class(capacity=10.0, speed=10.0, loa=54.0),
        route=fourth_route,
        current_segment=fourth_route.segments[1],
    )
    fourth_route.deployed_vessels = [fourth]
    state["waiting_vessels"].append(fourth)
    state["waiting_since"][fourth] = state["current_time"]

    assert _select(state) is state["buffer"]


def test_highest_positive_net_benefit_wins() -> None:
    state = _positive_state()
    state["buffer"].vessel_class.teu_capacity = 1000.0

    assert _select(state) is state["other"]


def test_exact_net_benefit_tie_preserves_original_buffer_order() -> None:
    state = _positive_state()

    assert _select(state) is state["buffer"]


def test_equal_or_shorter_next_opportunity_than_service_delegates() -> None:
    state = _positive_state()
    state["other"].pending_assigned_service_route = state["other_route"]
    state["buffer"].vessel_class.teu_capacity = 45.0
    cycle_hours = 3.0 + 10.0 / 45.0
    distance = cycle_hours * 10.0 / (0.95 * 2.0)
    for segment in state["receiver_route"].segments:
        segment.associated_leg.sailing_distance = distance

    assert _select(state) is None


def test_negative_net_benefit_delegates() -> None:
    state = _positive_state()
    carried = _cargo(100.0)
    state["receiver"].carried_shipments = [carried]
    state["receiver"]._discharging_shipments = [carried]
    state["receiver"].vessel_class.teu_capacity = 100.0

    assert _select(state) is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_candidate_input_delegates(value: float) -> None:
    state = _positive_state()
    state["shipment"].teu_size = value

    assert _select(state) is None


def test_repeated_calls_are_deterministic_and_do_not_mutate_override_state() -> None:
    state = _positive_state()
    before = _snapshot(state)

    first = _select(state)
    second = _select(state)

    assert first is state["buffer"]
    assert second is first
    assert _snapshot(state) == before


def test_delegation_does_not_mutate_deep_state() -> None:
    state = _positive_state()
    state["shipment"].teu_size = float("nan")
    before = _snapshot(state)

    assert _select(state) is None
    assert _snapshot(state) == before


def test_runtime_module_has_no_forbidden_imports_broad_catches_or_mutable_globals() -> None:
    source = inspect.getsource(readiness)
    tree = ast.parse(source)
    forbidden = {
        "default_strategy",
        "strategy_validation",
        "simulation_model",
        "wsc2026_tools",
        "os",
        "pathlib",
        "socket",
        "subprocess",
        "sys",
    }
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    broad_catches = [
        handler
        for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        for handler in node.handlers
        if handler.type is None
        or (
            isinstance(handler.type, ast.Name) and handler.type.id in {"Exception", "BaseException"}
        )
    ]
    mutable_globals = [
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(getattr(node, "value", None), (ast.List, ast.Dict, ast.Set))
    ]

    assert not imported_roots.intersection(forbidden)
    assert broad_catches == []
    assert mutable_globals == []


def _active_plan(*, state: dict[str, Any], target_leg: Any = None, target_berth: Any = None) -> Any:
    plan = Obj()
    plan.target_leg = target_leg
    plan.target_berth = target_berth
    plan.start_offset_days = (state["current_time"] - datetime.min).days
    plan.duration_days = 1.0
    return plan


def test_active_receiver_leg_disruption_delegates_using_datetime_min_offset() -> None:
    state = _positive_state()
    state["context"].disruption_plans.append(
        _active_plan(
            state=state,
            target_leg=state["receiver_route"].segments[0].associated_leg,
        )
    )

    assert _select(state) is None


def test_active_current_port_berth_disruption_delegates() -> None:
    state = _positive_state()
    state["context"].disruption_plans.append(_active_plan(state=state, target_berth=state["berth"]))

    assert _select(state) is None


def test_active_buffer_route_disruption_excludes_only_affected_buffer() -> None:
    state = _positive_state()
    state["context"].disruption_plans.append(
        _active_plan(
            state=state,
            target_leg=state["buffer_route"].segments[0].associated_leg,
        )
    )

    assert _select(state) is state["other"]


def test_inactive_relevant_disruption_does_not_block_stable_timing() -> None:
    state = _positive_state()
    plan = _active_plan(
        state=state,
        target_leg=state["receiver_route"].segments[0].associated_leg,
    )
    plan.start_offset_days += 2.0
    state["context"].disruption_plans.append(plan)

    assert _select(state) is state["buffer"]


def test_wrong_receiver_route_or_departure_segment_is_not_transitional() -> None:
    state = _positive_state()
    state["shipment"].associated_bookings[1].service_route = state["other_route"]
    assert _select(state) is None

    state = _positive_state()
    state["shipment"].associated_bookings[1].departure_segment_index = 1
    assert _select(state) is None


def test_buffer_discharging_cargo_that_connects_to_receiver_is_excluded() -> None:
    state = _positive_state()
    shipment = Obj()
    shipment.teu_size = 1.0
    shipment.current_storage_port = None
    shipment.carrying_vessel = state["buffer"]
    inbound = _booking(
        sequence_index=1,
        shipment=shipment,
        route=state["buffer_route"],
        departure_segment_index=0,
        arrival_segment_index=1,
    )
    outbound = _booking(
        sequence_index=2,
        shipment=shipment,
        route=state["receiver_route"],
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    shipment.associated_bookings = [inbound, outbound]
    shipment.current_booking_index = 1
    state["buffer"].carried_shipments = [shipment]
    state["buffer"]._discharging_shipments = [shipment]

    assert _select(state) is state["other"]


def test_malformed_buffer_discharge_booking_excludes_that_buffer() -> None:
    state = _positive_state()
    shipment = Obj()
    shipment.teu_size = 1.0
    shipment.associated_bookings = []
    shipment.current_booking_index = None
    state["buffer"].carried_shipments = [shipment]
    state["buffer"]._discharging_shipments = [shipment]

    assert _select(state) is state["other"]


def test_receiver_losing_after_buffer_removal_is_not_guaranteed_next() -> None:
    state = _positive_state()
    receiver, buffer, other = state["waiting_vessels"]
    for vessel in state["waiting_vessels"]:
        state["waiting_since"][vessel] = state["current_time"]
    receiver.vessel_class.teu_capacity = 20.0
    buffer.vessel_class.teu_capacity = 10.0
    other.vessel_class.teu_capacity = 10.0
    buffer.carried_shipments = [_cargo(2.0)]
    buffer._loading_shipments = [_cargo(1.0)]
    other.carried_shipments = [_cargo(1.0)]

    original_winner, original_strict = readiness._fallback_ranking(
        state["waiting_vessels"], state["current_time"], state["waiting_since"]
    )
    assert original_winner is receiver
    assert original_strict is True
    assert (
        readiness._receiver_is_guaranteed_next(
            tuple(state["waiting_vessels"]),
            buffer,
            receiver,
            state["current_time"],
            state["waiting_since"],
        )
        is False
    )


def test_above_congestion_threshold_recomputes_strict_receiver_ranking() -> None:
    state = _positive_state()
    for index in (3, 4):
        destination = _port(f"destination-{index}")
        route = _route(f"route-{index}", [state["port"], destination], [10.0, 10.0])
        vessel = Vessel(
            index=index,
            vessel_class=_vessel_class(capacity=10.0, speed=10.0, loa=54.0),
            route=route,
            current_segment=route.segments[1],
        )
        route.deployed_vessels = [vessel]
        state["waiting_vessels"].append(vessel)
        state["waiting_since"][vessel] = state["current_time"]

    assert _select(state) is state["buffer"]


def _set_receiver_cycle_hours(state: dict[str, Any], hours: float) -> None:
    state["receiver"].vessel_class.sailing_speed = 0.95
    distance = hours / len(state["receiver_route"].segments)
    for segment in state["receiver_route"].segments:
        segment.associated_leg.sailing_distance = distance


def test_next_opportunity_equal_to_service_delegates_exactly() -> None:
    state = _positive_state()
    state["buffer"].vessel_class.teu_capacity = 45.0
    state["other"].pending_assigned_service_route = state["other_route"]
    _set_receiver_cycle_hours(state, 4.0)

    assert readiness._buffer_service_hours(state["buffer"]) == 4.0
    assert _select(state) is None


def test_next_opportunity_shorter_than_service_delegates() -> None:
    state = _positive_state()
    state["buffer"].vessel_class.teu_capacity = 45.0
    state["other"].pending_assigned_service_route = state["other_route"]
    _set_receiver_cycle_hours(state, 3.0)

    assert readiness._buffer_service_hours(state["buffer"]) == 4.0
    assert _select(state) is None


def test_exact_zero_net_benefit_delegates_without_epsilon() -> None:
    state = _positive_state()
    discharge = _cargo(5.0)
    state["receiver"].carried_shipments = [discharge]
    state["receiver"]._discharging_shipments = [discharge]
    state["receiver"].vessel_class.teu_capacity = 5.0
    state["buffer"].vessel_class.teu_capacity = 45.0
    state["other"].pending_assigned_service_route = state["other_route"]
    _set_receiver_cycle_hours(state, 8.0)

    assert readiness._buffer_service_hours(state["buffer"]) == 4.0
    assert _select(state) is None


def test_multiple_other_vessels_choose_minimum_with_cyclic_wrap_and_zero_residual() -> None:
    state = _positive_state()
    third_port = _port("third")
    route = _route(
        "three-leg-receiver",
        [state["port"], state["destination"], third_port],
        [10.0, 20.0, 30.0],
    )
    receiver = state["receiver"]
    receiver.assigned_service_route = route
    receiver.current_segment = route.segments[2]
    receiver.vessel_class.sailing_speed = 10.0
    fast = Vessel(
        index=8,
        vessel_class=_vessel_class(capacity=20.0, speed=20.0, loa=100.0),
        route=route,
        current_segment=route.segments[0],
    )
    slow = Vessel(
        index=9,
        vessel_class=_vessel_class(capacity=20.0, speed=10.0, loa=100.0),
        route=route,
        current_segment=route.segments[1],
    )
    route.deployed_vessels = [receiver, fast, slow]
    state["receiver_route"] = route
    state["shipment"].associated_bookings[1].service_route = route

    hours = readiness._next_opportunity_hours(receiver, route, route.segments[0])

    assert isclose(hours, 0.95 * 50.0 / 20.0)


def test_private_probe_has_observation_and_bounded_replay_modes() -> None:
    probe = (
        Path(__file__).parents[2]
        / "experiments"
        / "probes"
        / "transshipment_readiness_barrier_v1.py"
    )
    assert probe.is_file()
    source = probe.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert {"run_observation_probe", "run_bounded_replay", "main"} <= functions
    assert "evaluate_transshipment_readiness_barrier" in source
    assert "DefaultStrategy" in source
    assert "return None" in source
    assert "transshipment_readiness_barrier_v1_probe.json" in source
    assert "write_all" not in source
    assert "package_submission" not in source


def test_numeric_validation_rejects_wrong_sign_type_and_sequence_index() -> None:
    with pytest.raises(TypeError, match="numeric"):
        readiness._number("1")
    with pytest.raises(ValueError, match="nonnegative"):
        readiness._number(-1.0, nonnegative=True)
    with pytest.raises(TypeError, match="sequence index"):
        readiness._index(1.0)
    with pytest.raises(TypeError, match="datetime"):
        readiness._waiting_hours(datetime.now(), 0)


def test_teu_validation_rejects_duplicate_identity_and_overflow() -> None:
    shipment = _cargo(1.0)
    with pytest.raises(ValueError, match="duplicate"):
        readiness._teu_sum([shipment, shipment])
    with pytest.raises(ValueError, match="non-finite"):
        readiness._teu_sum([_cargo(1e308), _cargo(1e308)])


def test_route_validation_rejects_missing_empty_and_incomplete_routes() -> None:
    with pytest.raises(ValueError, match="route required"):
        readiness._route_segments(None)

    empty = Obj()
    empty.source_service_route = None
    empty.disruption_key = None
    empty.segments = []
    with pytest.raises(ValueError, match="nonempty"):
        readiness._route_segments(empty)

    first = _port("first")
    second = _port("second")
    route = _route("gap", [first, second], [1.0, 1.0])
    route.segments[1].sequence_index = 2
    with pytest.raises(ValueError, match="complete"):
        readiness._route_segments(route)


def test_route_validation_rejects_membership_and_missing_leg() -> None:
    first = _port("first")
    second = _port("second")
    route = _route("membership", [first, second], [1.0, 1.0])
    route.segments[0].associated_service_route = Obj()
    with pytest.raises(ValueError, match="membership"):
        readiness._route_segments(route)

    route = _route("missing-leg", [first, second], [1.0, 1.0])
    route.segments[0].associated_leg = None
    with pytest.raises(ValueError, match="leg"):
        readiness._route_segments(route)


def test_full_cycle_booking_with_same_endpoint_port_delegates() -> None:
    state = _positive_state()
    inbound = state["shipment"].associated_bookings[0]
    inbound.departure_segment_index = 0
    inbound.arrival_segment_index = 1

    assert _select(state) is None


def test_booking_validation_rejects_missing_departure_segment() -> None:
    state = _positive_state()
    state["shipment"].associated_bookings[0].departure_segment_index = 99

    assert _select(state) is None


def test_teu_sum_clamps_non_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        readiness._teu_sum([_cargo(-1.0)], positive=True)


def test_buffer_service_uses_lower_floor_when_loa_below_fifty_five() -> None:
    state = _positive_state()
    state["buffer"].vessel_class.loa = 30.0

    service = readiness._buffer_service_hours(state["buffer"])

    assert service == 3.0 + 10.0 / 45.0


def test_evaluate_wraps_validation_errors_as_safe_none() -> None:
    state = _positive_state()
    state["receiver_route"].segments[0].associated_leg.sailing_distance = float("inf")

    assert _select(state) is None


def test_evaluate_falls_through_on_overall_exception() -> None:
    state = _positive_state()

    # Replace receiver with a sentinel that explodes on attribute access
    # to exercise the broad except in choose_buffer_vessel.
    class Boom:
        def __getattr__(self, name):
            raise KeyError("boom")

    state["waiting_vessels"] = [Boom(), state["buffer"], state["other"]]
    state["waiting_since"] = {}

    assert _select(state) is None


def test_evaluate_path_with_extra_2x_distance_buffer() -> None:
    state = _positive_state()
    # Add a vessel with much larger cycle so receiver's next opportunity
    # is governed by the receiver itself.
    fast_route = _route("fast", [state["port"], _port("f-dest")], [10.0, 10.0])
    fast = Vessel(
        index=11,
        vessel_class=_vessel_class(capacity=20.0, speed=20.0, loa=100.0),
        route=fast_route,
        current_segment=fast_route.segments[1],
    )
    fast_route.deployed_vessels = [fast]
    state["waiting_vessels"].append(fast)
    state["waiting_since"][fast] = state["current_time"]

    assert _select(state) is state["buffer"]


def test_evaluate_with_strict_receiver_excluded_by_buffer_exclusion() -> None:
    state = _positive_state()
    # Buffer departs from same segment as receiver target — exclusion applies
    buffer = state["buffer"]
    buffer.assigned_service_route = state["receiver_route"]
    buffer.current_segment = state["receiver"].current_segment
    state["receiver_route"].deployed_vessels.append(buffer)

    assert _select(state) is None


def test_evaluate_with_buffer_route_disruption_only() -> None:
    state = _positive_state()
    plan = Obj()
    plan.target_leg = state["buffer_route"].segments[0].associated_leg
    plan.target_berth = None
    plan.start_offset_days = (state["current_time"] - datetime.min).days
    plan.duration_days = 1.0
    state["context"].disruption_plans.append(plan)

    assert _select(state) is state["other"]


def test_evaluate_with_pending_other_buffer_only() -> None:
    state = _positive_state()
    # Both buffer and other have pending assignments -> the only
    # strict receiver is the receiver, so _select delegates
    state["buffer"].pending_assigned_service_route = state["receiver_route"]
    state["other"].pending_assigned_service_route = state["other_route"]

    assert _select(state) is None


def test_evaluate_path_with_strict_fallback_only() -> None:
    state = _positive_state()
    # Reorder so that "other" is the buffer candidate (remaining[0]=receiver
    # after removal). Receiver is still the strict fallback winner.
    for vessel in state["waiting_vessels"]:
        state["waiting_since"][vessel] = state["current_time"]
    state["waiting_vessels"] = [state["other"], state["receiver"], state["buffer"]]
    state["receiver"].vessel_class.teu_capacity = 1000.0
    state["receiver"].vessel_class.loa = 220.0

    assert _select(state) is state["other"]


def test_booking_chain_resolves_next_booking_in_sequence() -> None:
    state = _positive_state()
    shipment = state["shipment"]
    feeder = state["feeder_route"]
    receiver_route = state["receiver_route"]
    booking1 = _booking(
        sequence_index=1,
        shipment=shipment,
        route=feeder,
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    booking2 = _booking(
        sequence_index=2,
        shipment=shipment,
        route=feeder,
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    booking3 = _booking(
        sequence_index=3,
        shipment=shipment,
        route=receiver_route,
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    shipment.associated_bookings = [booking1, booking2, booking3]
    shipment.current_booking_index = 1

    chain = readiness._booking_chain(shipment)
    assert chain.next_booking is booking2
    assert chain.current is booking1


def test_evaluate_only_keeps_highest_net_teu_hours() -> None:
    state = _positive_state()
    # Create a 3rd waiting vessel with strict tie-breaking at exactly 5.0 net.
    extra_route = _route("extra", [state["port"], _port("extra-dest")], [5.0, 5.0])
    extra = Vessel(
        index=12,
        vessel_class=_vessel_class(capacity=10.0, speed=10.0, loa=54.0),
        route=extra_route,
        current_segment=extra_route.segments[1],
    )
    extra_route.deployed_vessels = [extra]
    state["waiting_vessels"].append(extra)
    state["waiting_since"][extra] = state["current_time"]

    assert _select(state) is state["buffer"]


def test_segment_position_rejects_non_member() -> None:
    state = _positive_state()
    with pytest.raises(ValueError, match="segment must belong"):
        readiness._segment_position(state["receiver_route"].segments, Obj())


def test_next_segment_rejects_vessel_mismatch() -> None:
    state = _positive_state()

    class FakeVessel:
        current_segment = Obj()

        def get_next_segment(self):
            return Obj()

    with pytest.raises(ValueError, match="segment must belong"):
        readiness._next_segment(FakeVessel(), state["receiver_route"].segments)


def test_validate_route_fleet_rejects_no_deployed() -> None:
    state = _positive_state()
    state["receiver_route"].deployed_vessels = []

    with pytest.raises(ValueError, match="valid deployed fleet"):
        readiness._validate_route_fleet(state["receiver_route"], state["receiver"])


def test_validate_route_fleet_rejects_pending_assignment() -> None:
    state = _positive_state()
    state["buffer"].pending_assigned_service_route = state["receiver_route"]

    with pytest.raises(ValueError, match="pending route"):
        readiness._validate_route_fleet(state["buffer_route"], state["buffer"])


def test_booking_chain_rejects_duplicate_sequence() -> None:
    state = _positive_state()
    shipment = state["shipment"]
    shipment.associated_bookings[0].sequence_index = 2
    shipment.associated_bookings[1].sequence_index = 2

    with pytest.raises(ValueError, match="duplicate"):
        readiness._booking_chain(shipment)


def test_booking_chain_rejects_wrong_shipment_link() -> None:
    state = _positive_state()
    state["shipment"].associated_bookings[0].shipment = Obj()

    with pytest.raises(ValueError, match="shipment"):
        readiness._booking_chain(state["shipment"])


def test_booking_chain_rejects_missing_current_index() -> None:
    state = _positive_state()
    state["shipment"].current_booking_index = 99

    with pytest.raises(ValueError, match="current booking"):
        readiness._booking_chain(state["shipment"])


def test_evaluate_falls_through_when_fallback_vessel_missing() -> None:
    state = _positive_state()
    state["waiting_vessels"] = [state["buffer"], state["other"]]

    assert _select(state) is None


def test_evaluate_skips_buffer_with_no_vessel_class() -> None:
    state = _positive_state()
    # Make other ineligible as a buffer to ensure None when no buffer can
    # be selected.
    state["other"].pending_assigned_service_route = state["other_route"]
    state["buffer"].vessel_class = None

    assert _select(state) is None


def test_evaluate_rejects_buffer_with_pending_assignment() -> None:
    state = _positive_state()
    state["other"].pending_assigned_service_route = state["other_route"]
    state["buffer"].pending_assigned_service_route = state["receiver_route"]

    assert _select(state) is None


def test_evaluate_skips_buffer_with_receiver_target_on_different_port() -> None:
    state = _positive_state()
    state["other"].pending_assigned_service_route = state["other_route"]
    state["buffer"].current_segment = state["buffer_route"].segments[0]
    state["buffer_route"].segments[0].associated_leg.departure_port = state["origin"]
    state["buffer_route"].segments[0].associated_leg.arrival_port = state["destination"]

    assert _select(state) is None


def test_evaluate_skips_buffer_on_active_disruption() -> None:
    state = _positive_state()
    plan = Obj()
    plan.target_leg = state["buffer_route"].segments[1].associated_leg
    plan.target_berth = None
    plan.start_offset_days = (state["current_time"] - datetime.min).days
    plan.duration_days = 1.0
    state["context"].disruption_plans.append(plan)

    assert _select(state) is state["other"]


def test_evaluate_skips_buffer_with_malformed_discharge() -> None:
    state = _positive_state()
    state["other"].pending_assigned_service_route = state["other_route"]
    shipment = Obj()
    shipment.teu_size = 1.0
    shipment.associated_bookings = []
    shipment.current_booking_index = None
    state["buffer"].carried_shipments = [shipment]
    state["buffer"]._discharging_shipments = [shipment]
    state["buffer"].vessel_class.teu_capacity = 1000.0

    assert _select(state) is None


def test_evaluate_skips_buffer_with_nonfinite_service() -> None:
    state = _positive_state()
    state["other"].pending_assigned_service_route = state["other_route"]
    state["buffer"].vessel_class.teu_capacity = float("inf")
    state["buffer"].vessel_class.loa = 10.0
    state["buffer"]._loading_shipments = [_cargo(float("inf"))]

    assert _select(state) is None


def test_validate_route_fleet_rejects_vessel_route_mismatch() -> None:
    state = _positive_state()
    state["receiver"].assigned_service_route = state["other_route"]
    state["other"].assigned_service_route = state["receiver_route"]

    with pytest.raises(ValueError, match="deployed route"):
        readiness._validate_route_fleet(state["receiver_route"], state["receiver"])


def test_validate_route_fleet_rejects_no_vessel_class() -> None:
    state = _positive_state()
    state["buffer"].vessel_class = None

    with pytest.raises(ValueError, match="vessel class"):
        readiness._validate_route_fleet(state["buffer_route"], state["buffer"])


def test_validate_route_fleet_rejects_non_positive_speed() -> None:
    state = _positive_state()
    state["buffer"].vessel_class.sailing_speed = 0.0

    with pytest.raises(ValueError, match="positive"):
        readiness._validate_route_fleet(state["buffer_route"], state["buffer"])


def test_validate_route_fleet_rejects_vessel_not_in_deployed() -> None:
    state = _positive_state()
    state["receiver_route"].deployed_vessels = []

    with pytest.raises(ValueError, match="valid deployed|vessel not deployed"):
        readiness._validate_route_fleet(state["receiver_route"], state["receiver"])


def test_route_segments_rejects_duplicate_segments() -> None:
    route = _route("dup", [_port("a"), _port("b")], [1.0, 1.0])
    route.segments.append(route.segments[0])

    with pytest.raises(ValueError, match="unique"):
        readiness._route_segments(route)


def test_teu_sum_clamps_non_finite() -> None:
    shipment = _cargo(1.0)
    with pytest.raises((TypeError, ValueError, AttributeError)):
        readiness._teu_sum([shipment, None])
