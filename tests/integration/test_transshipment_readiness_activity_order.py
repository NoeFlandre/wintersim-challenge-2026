from __future__ import annotations

import importlib.util
import sys
import types
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from wsc2026_tools.paths import round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration

_ORGANIZER_PREFIXES = (
    "response_strategies",
    "scenario_builders",
    "simulation_model",
    "maritime_data_context",
    "config",
    "o2despy",
    "o2des",
)
_PARTICIPANT_PACKAGE = "_wsc_participant_transshipment_readiness"


@pytest.fixture
def round0_runtime() -> Iterator[Path]:
    source = round_source_dir("round0")
    if not source.is_dir():
        pytest.skip(f"Round 0 organizer source is unavailable at {source}")
    inserted: list[str] = []
    try:
        for path in (str(source / "o2despy"), str(source)):
            if path not in sys.path:
                sys.path.insert(0, path)
                inserted.append(path)
        for module_name in list(sys.modules):
            if any(
                module_name == prefix or module_name.startswith(f"{prefix}.")
                for prefix in _ORGANIZER_PREFIXES
            ):
                sys.modules.pop(module_name, None)
        yield source
    finally:
        for path in inserted:
            if path in sys.path:
                sys.path.remove(path)
        for module_name in list(sys.modules):
            if any(
                module_name == prefix or module_name.startswith(f"{prefix}.")
                for prefix in _ORGANIZER_PREFIXES
            ):
                sys.modules.pop(module_name, None)


def _organizer_source() -> Path:
    source = round_source_dir("round0")
    if not source.is_dir():
        pytest.skip(f"Round 0 organizer source is unavailable at {source}")
    return source


def _prepare_organizer_imports(source: Path) -> None:
    for path in (str(source / "o2despy"), str(source)):
        if path not in sys.path:
            sys.path.insert(0, path)
    for module_name in list(sys.modules):
        if any(
            module_name == prefix or module_name.startswith(f"{prefix}.")
            for prefix in _ORGANIZER_PREFIXES
        ):
            sys.modules.pop(module_name, None)


@contextmanager
def _participant_strategy() -> Iterator[type]:
    strategies_dir = submission_strategies_dir()
    participant_file = strategies_dir / "user_strategy.py"
    package = types.ModuleType(_PARTICIPANT_PACKAGE)
    package.__path__ = [str(strategies_dir)]
    package.__package__ = _PARTICIPANT_PACKAGE
    sys.modules[_PARTICIPANT_PACKAGE] = package
    module_name = f"{_PARTICIPANT_PACKAGE}.user_strategy"
    spec = importlib.util.spec_from_file_location(module_name, participant_file)
    if spec is None or spec.loader is None:
        pytest.fail(f"cannot load participant strategy from {participant_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        yield module.UserStrategy
    finally:
        for name in list(sys.modules):
            if name == _PARTICIPANT_PACKAGE or name.startswith(f"{_PARTICIPANT_PACKAGE}."):
                sys.modules.pop(name, None)


def _append_route(context: Any, route_id: str, ports: list[Any], distances: list[float]) -> Any:
    from maritime_data_context import Leg, Segment, ServiceRoute

    route = ServiceRoute(id=route_id, name=route_id)
    for index, (departure, arrival, distance) in enumerate(
        zip(ports, ports[1:] + ports[:1], distances, strict=True)
    ):
        leg = Leg(departure_port=departure, arrival_port=arrival, sailing_distance=distance)
        segment = Segment(
            sequence_index=index,
            associated_leg=leg,
            associated_service_route=route,
        )
        leg.segments.append(segment)
        departure.outgoing_legs.append(leg)
        arrival.incoming_legs.append(leg)
        context.legs.append(leg)
        route.segments.append(segment)
    context.service_routes.append(route)
    context.initial_service_routes.append(route)
    return route


def _append_vessel(
    context: Any,
    *,
    index: int,
    route: Any,
    capacity: int,
    speed: float,
    loa: float,
) -> Any:
    from maritime_data_context import Vessel, VesselClass

    vessel_class = VesselClass(
        name=f"class-{index}", teu_capacity=capacity, sailing_speed=speed, loa=loa
    )
    vessel = Vessel(index=index, vessel_class=vessel_class, assigned_service_route=route)
    vessel.current_segment = route.segments[-1]
    route.segments[-1].current_vessels.append(vessel)
    vessel_class.vessels.append(vessel)
    route.deployed_vessels.append(vessel)
    context.vessel_classes.append(vessel_class)
    context.vessels.append(vessel)
    return vessel


def _real_state() -> dict[str, Any]:
    from maritime_data_context import Berth, Booking, Demand, MaritimeDataContext, Port, Shipment
    from simulation_model import Model

    context = MaritimeDataContext()
    model = Model(context, seed=2026)

    transfer = Port("transfer")
    destination = Port("destination")
    origin = Port("origin")
    buffer_destination = Port("buffer-destination")
    other_destination = Port("other-destination")
    context.ports.extend([transfer, destination, origin, buffer_destination, other_destination])

    berth = Berth(index=0, port=transfer)
    transfer.berths.append(berth)

    receiver_route = _append_route(context, "receiver", [transfer, destination], [100.0, 100.0])
    feeder_route = _append_route(context, "feeder", [origin, transfer], [20.0, 20.0])
    buffer_route = _append_route(context, "buffer", [transfer, buffer_destination], [10.0, 10.0])
    other_route = _append_route(context, "other", [transfer, other_destination], [10.0, 10.0])

    receiver = _append_vessel(
        context, index=0, route=receiver_route, capacity=100, speed=10.0, loa=220.0
    )
    buffer = _append_vessel(context, index=1, route=buffer_route, capacity=10, speed=10.0, loa=54.0)
    other = _append_vessel(context, index=2, route=other_route, capacity=10, speed=10.0, loa=54.0)

    demand = Demand(origin_port=origin, destination_port=destination, annual_teus=5)
    shipment = Shipment(
        index=0,
        teu_size=5,
        demand=demand,
        current_storage_port=transfer,
        generated_time=model.clock_time,
    )
    inbound = Booking(
        sequence_index=1,
        shipment=shipment,
        service_route=feeder_route,
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    outbound = Booking(
        sequence_index=2,
        shipment=shipment,
        service_route=receiver_route,
        departure_segment_index=0,
        arrival_segment_index=0,
    )
    shipment.associated_bookings.extend([inbound, outbound])
    shipment.current_booking_index = 1
    feeder_route.associated_bookings.append(inbound)
    receiver_route.associated_bookings.append(outbound)
    demand.shipments.append(shipment)
    origin.outgoing_demands.append(demand)
    destination.incoming_demands.append(demand)
    transfer.shipments_in_storage.append(shipment)
    context.demands.append(demand)

    return {
        "context": context,
        "model": model,
        "port": transfer,
        "berth": berth,
        "receiver": receiver,
        "buffer": buffer,
        "other": other,
        "shipment": shipment,
        "waiting_vessels": [receiver, buffer, other],
    }


def _run_until_berth_assignment(state: dict[str, Any]) -> None:
    model = state["model"]
    for vessel in state["waiting_vessels"]:
        model.vessel_queuing_for_berth.signal_start(vessel)
    model.berth_idle.signal_start(state["berth"])

    for _ in range(100):
        if state["berth"].occupying_vessel is not None:
            return
        assert model.head_event_time == model.clock_time
        model.run_once()
    pytest.fail("berth assignment did not occur within the bounded same-time event drain")


def _drain_current_timestamp(model: Any) -> None:
    timestamp = model.clock_time
    for _ in range(200):
        if model.head_event_time != timestamp:
            return
        model.run_once()
    pytest.fail("same-time scheduler events did not drain within the bounded limit")


def _organizer_policy_snapshot(state: dict[str, Any]) -> tuple[Any, ...]:
    context = state["context"]
    return (
        tuple(id(port) for port in context.ports),
        tuple(id(leg) for leg in context.legs),
        tuple(id(route) for route in context.service_routes),
        tuple(id(vessel) for vessel in context.vessels),
        tuple(
            (
                id(route),
                route.source_service_route,
                route.disruption_key,
                tuple(id(segment) for segment in route.segments),
                tuple(id(vessel) for vessel in route.deployed_vessels),
            )
            for route in context.service_routes
        ),
        tuple(
            (
                id(vessel),
                id(vessel.assigned_service_route),
                vessel.pending_assigned_service_route,
                id(vessel.current_segment),
                id(vessel.current_berth),
                tuple(id(shipment) for shipment in vessel.carried_shipments),
            )
            for vessel in context.vessels
        ),
        tuple(id(shipment) for shipment in state["port"].shipments_in_storage),
        state["shipment"].current_booking_index,
        state["shipment"].current_storage_port,
        state["shipment"].carrying_vessel,
        state["berth"].occupying_vessel,
    )


def test_independent_fallback_ranking_matches_real_default_strategy() -> None:
    source = _organizer_source()
    _prepare_organizer_imports(source)
    state = _real_state()
    waiting_since = dict.fromkeys(state["waiting_vessels"], state["model"].clock_time)

    from response_strategies.default_strategy import DefaultStrategy

    actual = DefaultStrategy.select_vessel_for_berth(
        state["context"],
        state["port"],
        state["waiting_vessels"],
        [state["berth"]],
        state["model"].clock_time,
        waiting_since,
    )
    with _participant_strategy():
        readiness_module = sys.modules[f"{_PARTICIPANT_PACKAGE}.transshipment_readiness"]
        independent, is_strict = readiness_module._fallback_ranking(
            state["waiting_vessels"],
            state["model"].clock_time,
            waiting_since,
        )

    assert is_strict is True
    assert independent is actual is state["receiver"]


def test_captured_real_hook_state_has_fallback_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _organizer_source()
    _prepare_organizer_imports(source)
    state = _real_state()
    captured: dict[str, Any] = {}

    import simulation_model.berth_idle as berth_idle_module
    from response_strategies.default_strategy import DefaultStrategy

    def capture_and_delegate(**kwargs: Any) -> None:
        captured.update(kwargs)
        captured["waiting_vessels"] = list(kwargs["waiting_vessels"])
        captured["available_berths"] = list(kwargs["available_berths"])
        captured["waiting_since_by_vessel"] = dict(kwargs["waiting_since_by_vessel"])
        return None

    monkeypatch.setattr(
        berth_idle_module.UserStrategy,
        "select_vessel_for_berth",
        capture_and_delegate,
    )
    _run_until_berth_assignment(state)
    assert captured

    actual = DefaultStrategy.select_vessel_for_berth(**captured)
    with _participant_strategy():
        readiness_module = sys.modules[f"{_PARTICIPANT_PACKAGE}.transshipment_readiness"]
        independent, is_strict = readiness_module._fallback_ranking(
            captured["waiting_vessels"],
            captured["current_time"],
            captured["waiting_since_by_vessel"],
        )

    assert is_strict is True
    assert independent is actual is state["receiver"]


def test_policy_evaluation_does_not_mutate_real_organizer_objects() -> None:
    source = _organizer_source()
    _prepare_organizer_imports(source)
    state = _real_state()
    waiting_since = dict.fromkeys(state["waiting_vessels"], state["model"].clock_time)
    before = _organizer_policy_snapshot(state)

    with _participant_strategy():
        readiness_module = sys.modules[f"{_PARTICIPANT_PACKAGE}.transshipment_readiness"]
        decision = readiness_module.evaluate_transshipment_readiness_barrier(
            maritime_data_context=state["context"],
            port=state["port"],
            waiting_vessels=state["waiting_vessels"],
            available_berths=[state["berth"]],
            current_time=state["model"].clock_time,
            waiting_since_by_vessel=waiting_since,
        )

    assert decision is not None
    assert decision.receiver is state["receiver"]
    assert decision.buffer is state["buffer"]
    assert _organizer_policy_snapshot(state) == before


def test_real_activity_order_receiver_misses_without_barrier_and_catches_with_barrier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _organizer_source()
    _prepare_organizer_imports(source)

    no_barrier = _real_state()
    _run_until_berth_assignment(no_barrier)
    assert no_barrier["berth"].occupying_vessel is no_barrier["receiver"]

    no_barrier["model"].shipment_waiting_for_loading_at_transshipment_port.signal_start(
        no_barrier["shipment"]
    )
    _drain_current_timestamp(no_barrier["model"])

    assert no_barrier["shipment"].current_booking_index == 2
    assert no_barrier["shipment"] not in no_barrier["receiver"].carried_shipments
    assert no_barrier["shipment"] in no_barrier["port"].shipments_in_storage
    assert no_barrier["shipment"] in no_barrier["model"].vessel_being_served.p_start_signals

    barrier = _real_state()
    with _participant_strategy() as ParticipantStrategy:
        waiting_since = dict.fromkeys(barrier["waiting_vessels"], barrier["model"].clock_time)
        selected = ParticipantStrategy.select_vessel_for_berth(
            maritime_data_context=barrier["context"],
            port=barrier["port"],
            waiting_vessels=barrier["waiting_vessels"],
            available_berths=[barrier["berth"]],
            current_time=barrier["model"].clock_time,
            waiting_since_by_vessel=waiting_since,
        )
        assert selected is barrier["buffer"]

        import simulation_model.berth_idle as berth_idle_module

        monkeypatch.setattr(
            berth_idle_module.UserStrategy,
            "select_vessel_for_berth",
            ParticipantStrategy.select_vessel_for_berth,
        )
        _run_until_berth_assignment(barrier)
        assert barrier["berth"].occupying_vessel is barrier["buffer"]

        barrier["model"].shipment_waiting_for_loading_at_transshipment_port.signal_start(
            barrier["shipment"]
        )
        _drain_current_timestamp(barrier["model"])
        assert barrier["shipment"].current_booking_index == 2
        assert barrier["shipment"] not in barrier["buffer"].carried_shipments

        barrier["model"].run_until(barrier["model"].clock_time + timedelta(hours=3))

        assert barrier["berth"].occupying_vessel is barrier["receiver"]
        assert barrier["shipment"] in barrier["receiver"].carried_shipments
        assert barrier["shipment"].carrying_vessel is barrier["receiver"]
        assert barrier["shipment"] not in barrier["port"].shipments_in_storage
