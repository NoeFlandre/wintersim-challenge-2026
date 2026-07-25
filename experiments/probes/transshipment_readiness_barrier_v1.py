from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
import types
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, NamedTuple

from wsc2026_tools.paths import repo_root, round_source_dir, submission_strategies_dir

_RESULT_PATH = (
    repo_root() / "experiments" / "results" / "transshipment_readiness_barrier_v1_probe.json"
)
_PARTICIPANT_PACKAGE = "_wsc_transshipment_readiness_probe"
_ORGANIZER_PREFIXES = (
    "response_strategies",
    "scenario_builders",
    "simulation_model",
    "maritime_data_context",
    "config",
    "o2despy",
    "o2des",
)
_SEED = 2026
_TRAJECTORY_DAYS = 140 + 360
_MAX_REPLAY_EVENTS_AFTER_DECISION = 100_000
_MAX_OBSERVATION_EVENTS = 1_000_000


class ProbeError(RuntimeError):
    pass


class _Runtime(NamedTuple):
    readiness: Any
    scenario_builders: Any
    model_class: type
    organizer_user_strategy: type
    default_strategy: type


def _clear_modules(prefixes: tuple[str, ...]) -> None:
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)


@contextmanager
def _load_runtime() -> Iterator[_Runtime]:
    source = round_source_dir("round0")
    if not source.is_dir():
        raise ProbeError(f"Round 0 organizer source is unavailable at {source}")
    inserted: list[str] = []
    try:
        for path in (str(source / "o2despy"), str(source)):
            if path not in sys.path:
                sys.path.insert(0, path)
                inserted.append(path)
        _clear_modules(_ORGANIZER_PREFIXES)

        package = types.ModuleType(_PARTICIPANT_PACKAGE)
        strategies_dir = submission_strategies_dir()
        package.__path__ = [str(strategies_dir)]
        package.__package__ = _PARTICIPANT_PACKAGE
        sys.modules[_PARTICIPANT_PACKAGE] = package
        readiness_name = f"{_PARTICIPANT_PACKAGE}.transshipment_readiness"
        readiness_path = strategies_dir / "transshipment_readiness.py"
        spec = importlib.util.spec_from_file_location(readiness_name, readiness_path)
        if spec is None or spec.loader is None:
            raise ProbeError(f"cannot load participant helper from {readiness_path}")
        readiness = importlib.util.module_from_spec(spec)
        sys.modules[readiness_name] = readiness
        spec.loader.exec_module(readiness)

        scenario_builders = importlib.import_module("scenario_builders")
        model_class = importlib.import_module("simulation_model").Model
        berth_idle = importlib.import_module("simulation_model.berth_idle")
        default_strategy = importlib.import_module(
            "response_strategies.default_strategy"
        ).DefaultStrategy
        yield _Runtime(
            readiness=readiness,
            scenario_builders=scenario_builders,
            model_class=model_class,
            organizer_user_strategy=berth_idle.UserStrategy,
            default_strategy=default_strategy,
        )
    finally:
        _clear_modules((_PARTICIPANT_PACKAGE, *_ORGANIZER_PREFIXES))
        for path in inserted:
            if path in sys.path:
                sys.path.remove(path)


def _identity_index(values: Any, target: object) -> int:
    indexes = [index for index, value in enumerate(values) if value is target]
    if len(indexes) != 1:
        raise ProbeError("candidate vessel identity is not unique in waiting list")
    return indexes[0]


def _hook_snapshot(kwargs: dict[str, Any]) -> tuple[Any, ...]:
    context = kwargs["maritime_data_context"]
    port = kwargs["port"]
    waiting = tuple(kwargs["waiting_vessels"])
    available = tuple(kwargs["available_berths"])
    routes: list[object] = []
    for vessel in waiting:
        route = vessel.assigned_service_route
        if not any(existing is route for existing in routes):
            routes.append(route)
    shipments = tuple(port.shipments_in_storage)
    return (
        tuple(id(vessel) for vessel in waiting),
        tuple(id(berth) for berth in available),
        tuple(
            (
                id(vessel),
                id(vessel.assigned_service_route),
                id(vessel.pending_assigned_service_route),
                id(vessel.current_segment),
                id(vessel.current_berth),
                tuple(id(shipment) for shipment in vessel.carried_shipments),
            )
            for vessel in waiting
        ),
        tuple(
            (
                id(route),
                id(route.source_service_route),
                route.disruption_key,
                tuple(id(segment) for segment in route.segments),
                tuple(id(vessel) for vessel in route.deployed_vessels),
            )
            for route in routes
        ),
        tuple(
            (
                id(shipment),
                shipment.current_booking_index,
                id(shipment.current_storage_port),
                id(shipment.carrying_vessel),
                tuple(id(booking) for booking in shipment.associated_bookings),
            )
            for shipment in shipments
        ),
        tuple(id(plan) for plan in context.disruption_plans),
    )


def _actual_fallback(runtime: _Runtime, kwargs: dict[str, Any]) -> object | None:
    return runtime.default_strategy.select_vessel_for_berth(**kwargs)


def _independent_fallback(
    runtime: _Runtime,
    kwargs: dict[str, Any],
) -> tuple[object | None, bool]:
    return runtime.readiness._fallback_ranking(
        kwargs["waiting_vessels"],
        kwargs["current_time"],
        kwargs["waiting_since_by_vessel"],
    )


def _safe_evidence(
    kwargs: dict[str, Any],
    decision: Any,
    *,
    parity: bool,
    no_mutation: bool,
) -> dict[str, Any]:
    waiting = tuple(kwargs["waiting_vessels"])
    return {
        "simulation_timestamp": kwargs["current_time"].isoformat(),
        "receiver_waiting_index": _identity_index(waiting, decision.receiver),
        "buffer_waiting_index": _identity_index(waiting, decision.buffer),
        "guaranteed_transitional_teu": decision.guaranteed_transitional_teu,
        "affected_receiver_teu": decision.affected_receiver_teu,
        "next_opportunity_hours": decision.next_opportunity_hours,
        "buffer_service_hours": decision.buffer_service_hours,
        "net_teu_hours": decision.net_teu_hours,
        "fallback_parity": parity,
        "no_mutation": no_mutation,
    }


def _new_model(runtime: _Runtime) -> Any:
    context = runtime.scenario_builders.create_with_disruption()
    return runtime.model_class(context, seed=_SEED)


def _run_until_horizon(model: Any, stop: Any, max_events: int) -> None:
    horizon = model.clock_time + timedelta(days=_TRAJECTORY_DAYS)
    event_cap = model.event_count + max_events
    while model.head_event_time <= horizon and model.event_count < event_cap:
        model.run_once()
        if stop():
            return


def run_observation_probe(output_path: Path = _RESULT_PATH) -> dict[str, Any]:
    with _load_runtime() as runtime:
        model = _new_model(runtime)
        original_hook = runtime.organizer_user_strategy.select_vessel_for_berth
        found: dict[str, Any] | None = None
        rejected: dict[str, Any] | None = None

        def observe(**kwargs: Any) -> None:
            nonlocal found, rejected
            if found is not None:
                return None
            before = _hook_snapshot(kwargs)
            decision = runtime.readiness.evaluate_transshipment_readiness_barrier(**kwargs)
            after = _hook_snapshot(kwargs)
            independent, is_strict = _independent_fallback(runtime, kwargs)
            actual = _actual_fallback(runtime, kwargs)
            parity = independent is actual
            no_mutation = before == after
            if decision is None:
                return None
            if not is_strict or decision.receiver is not independent:
                return None
            if not parity or not no_mutation:
                rejected = {
                    "simulation_timestamp": kwargs["current_time"].isoformat(),
                    "reason": "parity_or_no_mutation_failed",
                    "parity": parity,
                    "no_mutation": no_mutation,
                }
                return None
            found = _safe_evidence(
                kwargs,
                decision,
                parity=parity,
                no_mutation=no_mutation,
            )
            return None

        runtime.organizer_user_strategy.select_vessel_for_berth = staticmethod(observe)
        try:
            _run_until_horizon(model, lambda: found is not None, _MAX_OBSERVATION_EVENTS)
        finally:
            runtime.organizer_user_strategy.select_vessel_for_berth = original_hook

    if found is None:
        detail = f" last rejected: {rejected}" if rejected else ""
        raise ProbeError(
            "no strict transshipment-readiness divergence with parity and no-mutation "
            "was observed within the trajectory horizon and event cap." + detail
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(found, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return found


def _guaranteed_shipments(runtime: _Runtime, decision: Any, port: Any) -> tuple[object, ...]:
    route = decision.receiver.assigned_service_route
    segments = runtime.readiness._validate_route_fleet(route, decision.receiver)
    target = runtime.readiness._next_segment(decision.receiver, segments)
    cargo = runtime.readiness._classify_receiver_cargo(port, route, target)
    if cargo.transitional_teu != decision.guaranteed_transitional_teu:
        raise ProbeError("guaranteed transitional TEU changed during replay")
    return cargo.transitional_shipments


def _shipments_ready(
    runtime: _Runtime,
    shipments: tuple[object, ...],
    receiver: Any,
) -> bool:
    route = receiver.assigned_service_route
    segments = runtime.readiness._validate_route_fleet(route, receiver)
    target = runtime.readiness._next_segment(receiver, segments)
    for shipment in shipments:
        chain = runtime.readiness._booking_chain(shipment)
        departure = runtime.readiness._segment_by_index(
            chain.current.service_route,
            chain.current.departure_segment_index,
        )
        if chain.current.service_route is not route or departure is not target:
            return False
    return True


def _matches_recorded_event(
    kwargs: dict[str, Any],
    decision: Any,
    evidence: dict[str, Any],
) -> bool:
    waiting = tuple(kwargs["waiting_vessels"])
    return (
        kwargs["current_time"].isoformat() == evidence["simulation_timestamp"]
        and _identity_index(waiting, decision.receiver) == evidence["receiver_waiting_index"]
        and _identity_index(waiting, decision.buffer) == evidence["buffer_waiting_index"]
        and decision.guaranteed_transitional_teu == evidence["guaranteed_transitional_teu"]
        and decision.affected_receiver_teu == evidence["affected_receiver_teu"]
        and decision.next_opportunity_hours == evidence["next_opportunity_hours"]
        and decision.buffer_service_hours == evidence["buffer_service_hours"]
        and decision.net_teu_hours == evidence["net_teu_hours"]
    )


def run_bounded_replay(evidence_path: Path = _RESULT_PATH) -> dict[str, bool]:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if not evidence.get("fallback_parity", False) or not evidence.get("no_mutation", False):
        raise ProbeError("stored evidence lacks required safety flags; refuse to replay")
    with _load_runtime() as runtime:
        model = _new_model(runtime)
        original_hook = runtime.organizer_user_strategy.select_vessel_for_berth
        target: dict[str, Any] | None = None

        def allow_recorded_candidate(**kwargs: Any) -> object | None:
            nonlocal target
            decision = runtime.readiness.evaluate_transshipment_readiness_barrier(**kwargs)
            if target is not None or decision is None:
                return None
            independent, is_strict = _independent_fallback(runtime, kwargs)
            actual = _actual_fallback(runtime, kwargs)
            if (
                is_strict
                and independent is actual is decision.receiver
                and _matches_recorded_event(kwargs, decision, evidence)
            ):
                target = {
                    "decision": decision,
                    "berth": tuple(kwargs["available_berths"])[0],
                    "shipments": _guaranteed_shipments(
                        runtime,
                        decision,
                        kwargs["port"],
                    ),
                    "time": kwargs["current_time"],
                }
                return decision.buffer
            return None

        runtime.organizer_user_strategy.select_vessel_for_berth = staticmethod(
            allow_recorded_candidate
        )
        try:
            horizon = model.clock_time + timedelta(days=_TRAJECTORY_DAYS)
            while model.head_event_time <= horizon and target is None:
                model.run_once()
            if target is None:
                raise ProbeError("recorded candidate event was not reproduced")

            decision = target["decision"]
            berth = target["berth"]
            shipments = target["shipments"]
            deadline = target["time"] + timedelta(hours=decision.buffer_service_hours + 24.0)
            buffer_served = berth.occupying_vessel is decision.buffer
            shipments_ready = _shipments_ready(
                runtime,
                shipments,
                decision.receiver,
            )
            buffer_first_occupant_seen: bool = buffer_served
            buffer_departed = False
            receiver_selected_next = False
            guaranteed_shipments_loaded = False

            for _ in range(_MAX_REPLAY_EVENTS_AFTER_DECISION):
                if model.head_event_time > deadline:
                    break
                model.run_once()
                occupant = berth.occupying_vessel
                buffer_served = buffer_served or occupant is decision.buffer
                if buffer_served and not buffer_first_occupant_seen:
                    buffer_first_occupant_seen = occupant is decision.buffer
                if buffer_first_occupant_seen and occupant is not decision.buffer:
                    buffer_departed = True
                if buffer_departed and not receiver_selected_next:
                    if occupant is decision.receiver:
                        receiver_selected_next = True
                    elif occupant is not None:
                        raise ProbeError(
                            "bounded replay: a vessel other than the receiver "
                            "occupied the berth right after the buffer"
                        )
                shipments_ready = shipments_ready or _shipments_ready(
                    runtime,
                    shipments,
                    decision.receiver,
                )
                guaranteed_shipments_loaded = all(
                    any(carried is shipment for carried in decision.receiver.carried_shipments)
                    and shipment.carrying_vessel is decision.receiver
                    for shipment in shipments
                )
                if (
                    buffer_served
                    and shipments_ready
                    and receiver_selected_next
                    and guaranteed_shipments_loaded
                ):
                    break
        finally:
            runtime.organizer_user_strategy.select_vessel_for_berth = original_hook

    result = {
        "buffer_served": buffer_served,
        "shipments_ready": shipments_ready,
        "receiver_selected_next": receiver_selected_next,
        "guaranteed_shipments_loaded": guaranteed_shipments_loaded,
    }
    if not all(result.values()):
        raise ProbeError(f"bounded replay mechanism proof failed: {result}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("observe", "replay"))
    parser.add_argument("--evidence", type=Path, default=_RESULT_PATH)
    args = parser.parse_args(argv)
    if args.mode == "observe":
        run_observation_probe(args.evidence)
    else:
        run_bounded_replay(args.evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
