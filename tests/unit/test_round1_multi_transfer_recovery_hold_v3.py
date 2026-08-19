"""Contract for the Round 1 multi-transfer recovery-hold policy."""

from __future__ import annotations

import ast
import datetime as dt
import inspect
import math
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from response_strategies.user_strategy import UserStrategy

ANCHOR = dt.datetime.min


def _port(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _route(
    name: str,
    ports: list[SimpleNamespace],
    distances: list[float],
    *,
    speed: float = 10.0,
    source: Any = None,
    disruption_key: Any = None,
    vessel_count: int = 1,
) -> SimpleNamespace:
    assert len(ports) == len(distances) + 1
    route = SimpleNamespace(
        name=name,
        source_service_route=source,
        disruption_key=disruption_key,
        associated_bookings=[],
    )
    route.segments = [
        SimpleNamespace(
            sequence_index=index,
            associated_leg=SimpleNamespace(
                departure_port=ports[index - 1],
                arrival_port=ports[index],
                sailing_distance=distance,
            ),
        )
        for index, distance in enumerate(distances, start=1)
    ]
    route.deployed_vessels = [
        SimpleNamespace(vessel_class=SimpleNamespace(sailing_speed=speed))
        for _ in range(vessel_count)
    ]
    return route


def _leg(route: SimpleNamespace, index: int = 0) -> SimpleNamespace:
    return route.segments[index].associated_leg


def _leg_plan(
    leg: SimpleNamespace,
    *,
    start_day: float = 10.0,
    duration_days: float = 5.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=leg,
        target_berth=None,
        start_offset_days=start_day,
        duration_days=duration_days,
        multiplier=2.0,
        close_berth=False,
    )


def _berth_plan(
    port: SimpleNamespace,
    *,
    start_day: float = 10.0,
    duration_days: float = 5.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        target_leg=None,
        target_berth=SimpleNamespace(port=port),
        start_offset_days=start_day,
        duration_days=duration_days,
        multiplier=1.0,
        close_berth=True,
    )


def _shipment(origin: Any, destination: Any, *, teu_size: Any = 1) -> SimpleNamespace:
    return SimpleNamespace(
        demand=SimpleNamespace(origin_port=origin, destination_port=destination),
        teu_size=teu_size,
        associated_bookings=[],
        current_booking_index=None,
    )


def _qualifying_fixture(
    *,
    safe_distances: tuple[float, float, float] = (1000.0, 1000.0, 1000.0),
) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace, dict[str, Any]]:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route(
        "safe-a",
        [origin, transfer_a, origin],
        [safe_distances[0], safe_distances[0]],
    )
    safe_b = _route(
        "safe-b",
        [transfer_a, transfer_b, transfer_a],
        [safe_distances[1], safe_distances[1]],
    )
    safe_c = _route(
        "safe-c",
        [transfer_b, destination, transfer_b],
        [safe_distances[2], safe_distances[2]],
    )
    plan = _leg_plan(_leg(nominal))
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[plan],
    )
    shipment = _shipment(origin, destination)
    now = ANCHOR + dt.timedelta(days=14.5)
    return (
        context,
        now,
        shipment,
        {
            "origin": origin,
            "transfer": transfer_a,
            "transfer_a": transfer_a,
            "transfer_b": transfer_b,
            "destination": destination,
            "nominal": nominal,
            "safe_a": safe_a,
            "safe_b": safe_b,
            "safe_c": safe_c,
            "plan": plan,
        },
    )


def _freeze(value: Any, seen: dict[int, int] | None = None) -> Any:
    if seen is None:
        seen = {}
    if value is None or isinstance(value, (bool, int, float, str, dt.datetime)):
        return (type(value).__name__, repr(value))
    identity = id(value)
    if identity in seen:
        return ("ref", seen[identity])
    seen[identity] = len(seen)
    if isinstance(value, list):
        return ("list", identity, tuple(_freeze(item, seen) for item in value))
    if isinstance(value, tuple):
        return ("tuple", tuple(_freeze(item, seen) for item in value))
    if isinstance(value, dict):
        return (
            "dict",
            identity,
            tuple((repr(key), _freeze(item, seen)) for key, item in value.items()),
        )
    if hasattr(value, "__dict__"):
        return (
            type(value).__name__,
            identity,
            tuple((name, _freeze(item, seen)) for name, item in sorted(vars(value).items())),
        )
    return (type(value).__name__, identity, repr(value))


def _decision(context: SimpleNamespace, now: Any, shipment: SimpleNamespace) -> Any:
    return UserStrategy.assign_associated_bookings(context, now, shipment)


def test_qualifying_direct_service_hold_returns_false_without_mutation() -> None:
    context, now, shipment, _ = _qualifying_fixture()
    before = _freeze((context, shipment))

    result = _decision(context, now, shipment)

    assert result is False
    assert _freeze((context, shipment)) == before


def test_one_transfer_safe_path_delegates_without_mutation() -> None:
    origin = _port("Origin")
    transfer = _port("Transfer")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer, origin], [1000.0, 1000.0])
    safe_b = _route("safe-b", [transfer, destination, transfer], [1000.0, 1000.0])
    context = SimpleNamespace(
        ports=[origin, transfer, destination],
        service_routes=[nominal, safe_a, safe_b],
        disruption_plans=[_leg_plan(_leg(nominal))],
    )
    shipment = _shipment(origin, destination)
    before = _freeze((context, shipment))

    decision = _decision(context, ANCHOR + dt.timedelta(days=14.5), shipment)

    assert decision is None
    assert _freeze((context, shipment)) == before


def test_disruption_start_is_inclusive() -> None:
    context, _, shipment, _ = _qualifying_fixture()
    start = ANCHOR + dt.timedelta(days=10)

    assert _decision(context, start, shipment) is False


def test_disruption_end_is_exclusive() -> None:
    context, _, shipment, _ = _qualifying_fixture()
    end = ANCHOR + dt.timedelta(days=15)

    assert _decision(context, end, shipment) is None


def test_exact_hold_detour_equality_delegates() -> None:
    context, now, shipment, _ = _qualifying_fixture(safe_distances=(40.0, 40.0, 80.0))

    assert _decision(context, now, shipment) is None


def test_multi_teu_uses_one_safe_headway_buffer_without_mutation() -> None:
    context, now, shipment, _ = _qualifying_fixture(safe_distances=(40.0, 40.0, 80.0))
    shipment.teu_size = 2
    before = _freeze((context, shipment))

    assert _decision(context, now, shipment) is False
    assert _freeze((context, shipment)) == before


def test_one_teu_does_not_use_missed_connection_buffer() -> None:
    context, now, shipment, _ = _qualifying_fixture(safe_distances=(40.0, 40.0, 80.0))

    assert shipment.teu_size == 1
    assert _decision(context, now, shipment) is None


def test_exact_buffered_equality_delegates() -> None:
    context, now, shipment, _ = _qualifying_fixture(safe_distances=(32.0, 32.0, 64.0))
    shipment.teu_size = 2

    assert _decision(context, now, shipment) is None


@pytest.mark.parametrize("teu_size", [True, 2.0, 0, -1, None, math.nan])
def test_invalid_multi_teu_size_does_not_use_buffer(teu_size: Any) -> None:
    context, now, shipment, _ = _qualifying_fixture(safe_distances=(40.0, 40.0, 80.0))
    shipment.teu_size = teu_size

    assert _decision(context, now, shipment) is None


def test_missing_teu_size_does_not_use_buffer() -> None:
    context, now, shipment, _ = _qualifying_fixture(safe_distances=(40.0, 40.0, 80.0))
    del shipment.teu_size

    assert _decision(context, now, shipment) is None


@pytest.mark.parametrize("teu_size", [1, 2, True, None])
def test_existing_v3_strict_hold_is_preserved_for_every_size(teu_size: Any) -> None:
    context, now, shipment, _ = _qualifying_fixture()
    shipment.teu_size = teu_size

    assert _decision(context, now, shipment) is False


def test_safe_direct_path_delegates() -> None:
    context, now, shipment, items = _qualifying_fixture()
    direct_safe = _route(
        "direct-safe",
        [items["origin"], items["destination"], items["origin"]],
        [200.0, 200.0],
    )
    context.service_routes.append(direct_safe)

    assert _decision(context, now, shipment) is None


def test_multi_booking_nominal_path_delegates() -> None:
    origin = _port("Origin")
    nominal_transfer = _port("Nominal Transfer")
    safe_transfer = _port("Safe Transfer")
    destination = _port("Destination")
    nominal_a = _route("nominal-a", [origin, nominal_transfer, origin], [50.0, 50.0])
    nominal_b = _route("nominal-b", [nominal_transfer, destination, nominal_transfer], [50.0, 50.0])
    safe_a = _route("safe-a", [origin, safe_transfer, origin], [1000.0, 1000.0])
    safe_b = _route("safe-b", [safe_transfer, destination, safe_transfer], [1000.0, 1000.0])
    context = SimpleNamespace(
        ports=[origin, nominal_transfer, safe_transfer, destination],
        service_routes=[nominal_a, nominal_b, safe_a, safe_b],
        disruption_plans=[_leg_plan(_leg(nominal_a))],
    )

    assert (
        _decision(
            context,
            ANCHOR + dt.timedelta(days=14.5),
            _shipment(origin, destination),
        )
        is None
    )


def test_nominal_path_unaffected_by_active_disruption_delegates() -> None:
    context, now, shipment, _ = _qualifying_fixture()
    other_a = _port("Other A")
    other_b = _port("Other B")
    other_route = _route("other", [other_a, other_b, other_a], [10.0, 10.0])
    context.disruption_plans = [_leg_plan(_leg(other_route))]

    assert _decision(context, now, shipment) is None


def test_closed_intermediate_port_on_direct_service_can_trigger_hold() -> None:
    origin = _port("Origin")
    closed = _port("Closed")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route(
        "nominal",
        [origin, closed, destination, origin],
        [50.0, 50.0, 100.0],
    )
    safe_a = _route("safe-a", [origin, transfer_a, origin], [1000.0, 1000.0])
    safe_b = _route("safe-b", [transfer_a, transfer_b, transfer_a], [1000.0, 1000.0])
    safe_c = _route("safe-c", [transfer_b, destination, transfer_b], [1000.0, 1000.0])
    context = SimpleNamespace(
        ports=[origin, closed, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[_berth_plan(closed)],
    )

    assert (
        _decision(
            context,
            ANCHOR + dt.timedelta(days=14.5),
            _shipment(origin, destination),
        )
        is False
    )


def test_matching_deployed_alternative_routes_are_eligible() -> None:
    context, now, shipment, items = _qualifying_fixture()
    disruption_key = ((), (("origin", "destination"),))
    for route in (items["safe_a"], items["safe_b"], items["safe_c"]):
        route.source_service_route = items["nominal"]
        route.disruption_key = disruption_key

    assert _decision(context, now, shipment) is False


@pytest.mark.parametrize("failure", ["wrong-key", "no-vessels"])
def test_unavailable_alternative_routes_delegate(failure: str) -> None:
    context, now, shipment, items = _qualifying_fixture()
    disruption_key = ((), (("origin", "destination"),))
    for route in (items["safe_a"], items["safe_b"], items["safe_c"]):
        route.source_service_route = items["nominal"]
        route.disruption_key = disruption_key
    if failure == "wrong-key":
        items["safe_a"].disruption_key = (("other",), ())
    else:
        items["safe_a"].deployed_vessels = []

    assert _decision(context, now, shipment) is None


def test_single_service_indirect_safe_path_is_not_a_transfer() -> None:
    context, now, shipment, items = _qualifying_fixture()
    safe_single_route = _route(
        "safe-single",
        [
            items["origin"],
            items["transfer_a"],
            items["transfer_b"],
            items["destination"],
            items["origin"],
        ],
        [1000.0, 1000.0, 1000.0, 1000.0],
    )
    context.service_routes = [items["nominal"], safe_single_route]

    assert _decision(context, now, shipment) is None


def _tie_fixture(port_order: list[str]) -> tuple[SimpleNamespace, dt.datetime, Any]:
    ports = {name: _port(name) for name in ["O", "X1", "X2", "Y1", "Y2", "D"]}
    nominal = _route("nominal", [ports["O"], ports["D"], ports["O"]], [100.0, 100.0])
    fast_a = _route("fast-a", [ports["O"], ports["X1"], ports["O"]], [40.0, 40.0])
    fast_b = _route("fast-b", [ports["X1"], ports["X2"], ports["X1"]], [40.0, 40.0])
    fast_c = _route("fast-c", [ports["X2"], ports["D"], ports["X2"]], [80.0, 80.0])
    slow_a = _route("slow-a", [ports["O"], ports["Y1"], ports["O"]], [40.0, 40.0], speed=1.0)
    slow_b = _route("slow-b", [ports["Y1"], ports["Y2"], ports["Y1"]], [40.0, 40.0], speed=1.0)
    slow_c = _route("slow-c", [ports["Y2"], ports["D"], ports["Y2"]], [80.0, 80.0], speed=1.0)
    context = SimpleNamespace(
        ports=[ports[name] for name in port_order],
        service_routes=[nominal, fast_a, fast_b, fast_c, slow_a, slow_b, slow_c],
        disruption_plans=[_leg_plan(_leg(nominal))],
    )
    return context, ANCHOR + dt.timedelta(days=14.5), _shipment(ports["O"], ports["D"])


def test_equal_distance_ties_follow_context_port_order() -> None:
    fast_first = _tie_fixture(["O", "X1", "X2", "Y1", "Y2", "D"])
    slow_first = _tie_fixture(["O", "Y1", "Y2", "X1", "X2", "D"])

    assert _decision(*fast_first) is None
    assert _decision(*slow_first) is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda context, shipment, items: setattr(shipment, "associated_bookings", [object()]),
        lambda context, shipment, items: setattr(shipment, "current_booking_index", 0),
        lambda context, shipment, items: setattr(
            shipment.demand, "destination_port", shipment.demand.origin_port
        ),
        lambda context, shipment, items: setattr(items["plan"], "duration_days", None),
        lambda context, shipment, items: setattr(items["plan"], "start_offset_days", math.nan),
        lambda context, shipment, items: setattr(items["plan"], "multiplier", math.inf),
        lambda context, shipment, items: setattr(
            items["plan"], "target_berth", SimpleNamespace(port=items["origin"])
        ),
        lambda context, shipment, items: setattr(
            items["nominal"].segments[1],
            "sequence_index",
            items["nominal"].segments[0].sequence_index,
        ),
        lambda context, shipment, items: setattr(
            items["safe_a"].segments[0].associated_leg, "sailing_distance", math.nan
        ),
        lambda context, shipment, items: setattr(
            items["safe_b"].deployed_vessels[0].vessel_class,
            "sailing_speed",
            0.0,
        ),
        lambda context, shipment, items: setattr(items["safe_a"], "segments", []),
        lambda context, shipment, items: setattr(shipment, "demand", None),
        lambda context, shipment, items: setattr(context, "disruption_plans", None),
        lambda context, shipment, items: setattr(context, "service_routes", None),
        lambda context, shipment, items: setattr(context, "ports", None),
        lambda context, shipment, items: context.ports.append(context.ports[0]),
        lambda context, shipment, items: context.ports.remove(items["destination"]),
        lambda context, shipment, items: setattr(
            items["safe_a"].segments[0], "sequence_index", True
        ),
        lambda context, shipment, items: setattr(
            items["safe_a"].segments[0].associated_leg,
            "arrival_port",
            items["safe_a"].segments[0].associated_leg.departure_port,
        ),
        lambda context, shipment, items: setattr(
            items["safe_a"].segments[1].associated_leg,
            "departure_port",
            items["destination"],
        ),
        lambda context, shipment, items: setattr(items["nominal"], "deployed_vessels", []),
        lambda context, shipment, items: setattr(items["plan"], "start_offset_days", 1e308),
    ],
    ids=[
        "existing-bookings",
        "current-booking-index",
        "same-origin-destination",
        "missing-duration",
        "nonfinite-start",
        "nonfinite-multiplier",
        "ambiguous-target",
        "duplicate-sequence-index",
        "nonfinite-distance",
        "zero-speed",
        "empty-route",
        "missing-demand",
        "missing-plans",
        "missing-routes",
        "missing-ports",
        "duplicate-port-identity",
        "destination-outside-context",
        "boolean-sequence-index",
        "self-loop-leg",
        "incoherent-cycle",
        "empty-nominal-fleet",
        "overflowing-window",
    ],
)
def test_malformed_or_ineligible_state_fails_closed_without_mutation(
    mutate: Callable[[SimpleNamespace, SimpleNamespace, dict[str, Any]], None],
) -> None:
    context, now, shipment, items = _qualifying_fixture()
    mutate(context, shipment, items)
    before = _freeze((context, shipment))

    assert _decision(context, now, shipment) is None
    assert _freeze((context, shipment)) == before


def test_inactive_context_delegates_without_mutation() -> None:
    context, _, shipment, _ = _qualifying_fixture()
    before = _freeze((context, shipment))

    assert _decision(context, ANCHOR + dt.timedelta(days=1), shipment) is None
    assert _freeze((context, shipment)) == before


def test_public_surface_and_non_target_hooks_remain_exact() -> None:
    expected = {
        "select_vessel_for_berth": [
            "maritime_data_context",
            "port",
            "waiting_vessels",
            "available_berths",
            "current_time",
            "waiting_since_by_vessel",
        ],
        "create_alternative_service_routes": ["context", "now", "vessel"],
        "assign_associated_bookings": ["context", "now", "shipment"],
        "adjust_bookings_before_cargo_handling": ["context", "now", "vessel"],
    }
    for name, parameters in expected.items():
        assert isinstance(inspect.getattr_static(UserStrategy, name), staticmethod)
        assert list(inspect.signature(getattr(UserStrategy, name)).parameters) == parameters

    sentinel = SimpleNamespace(value=[1, 2, 3])
    before = _freeze(sentinel)
    assert UserStrategy.select_vessel_for_berth(sentinel, object(), [], [], ANCHOR, None) is None
    assert UserStrategy.create_alternative_service_routes(sentinel, ANCHOR) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(sentinel, ANCHOR, object()) is None
    assert _freeze(sentinel) == before


def test_participant_source_has_no_forbidden_runtime_capabilities_or_mutable_globals() -> None:
    source_path = Path(inspect.getsourcefile(UserStrategy) or "")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_roots = {
        "asyncio",
        "http",
        "importlib",
        "multiprocessing",
        "os",
        "pathlib",
        "random",
        "requests",
        "socket",
        "subprocess",
        "sys",
        "time",
        "urllib",
        "wsc2026_tools",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden_roots for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert node.module.split(".")[0] not in forbidden_roots
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            names = {child.id for child in ast.walk(node.type) if isinstance(child, ast.Name)}
            assert "Exception" not in names
            assert "BaseException" not in names

    mutable_nodes = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            assert value is None or not isinstance(value, mutable_nodes)
