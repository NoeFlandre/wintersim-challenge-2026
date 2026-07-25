"""Synthetic helpers for recovery-hold-vs-detour unit tests.

Constructs minimal MaritimeDataContext-shaped objects for the participant
strategy's needs. The objects intentionally do not import the organizer-owned
``default_strategy`` or ``simulation_model`` modules; they only mirror the
attributes the candidate reads.

These helpers are used only by tests. They must never be imported by the
participant strategy itself.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterable
from types import SimpleNamespace


class _Port:
    __slots__ = (
        "name",
        "outgoing_legs",
        "incoming_legs",
        "outgoing_demands",
        "shipments_in_storage",
    )

    def __init__(self, name: str) -> None:
        self.name = name
        self.outgoing_legs: list[_Leg] = []
        self.incoming_legs: list[_Leg] = []
        self.outgoing_demands: list[SimpleNamespace] = []
        self.shipments_in_storage: list[SimpleNamespace] = []

    def __repr__(self) -> str:
        return self.name


class _Leg:
    __slots__ = ("departure_port", "arrival_port", "sailing_distance", "segments")

    def __init__(self, departure: _Port, arrival: _Port, distance: float) -> None:
        self.departure_port = departure
        self.arrival_port = arrival
        self.sailing_distance = float(distance)
        self.segments: list[_Segment] = []

    def __repr__(self) -> str:
        return f"{self.departure_port}->{self.arrival_port}({self.sailing_distance})"


class _Segment:
    __slots__ = ("sequence_index", "associated_leg", "associated_service_route", "current_vessels")

    def __init__(self, sequence_index: int, leg: _Leg, route: _ServiceRoute) -> None:
        self.sequence_index = sequence_index
        self.associated_leg = leg
        self.associated_service_route = route
        self.current_vessels: list[object] = []


class _VesselClass:
    __slots__ = ("name", "teu_capacity", "sailing_speed", "loa")

    def __init__(self, name: str, teu_capacity: int, sailing_speed: float, loa: float) -> None:
        self.name = name
        self.teu_capacity = teu_capacity
        self.sailing_speed = float(sailing_speed)
        self.loa = float(loa)


class _Vessel:
    __slots__ = (
        "index",
        "vessel_class",
        "assigned_service_route",
        "pending_assigned_service_route",
        "current_segment",
        "current_berth",
        "carried_shipments",
    )

    def __init__(self, index: int, vessel_class: _VesselClass, route: _ServiceRoute) -> None:
        self.index = index
        self.vessel_class = vessel_class
        self.assigned_service_route = route
        self.pending_assigned_service_route: _ServiceRoute | None = None
        self.current_segment: _Segment | None = None
        self.current_berth: object | None = None
        self.carried_shipments: list[object] = []


class _ServiceRoute:
    __slots__ = (
        "id",
        "name",
        "start_day_of_week",
        "segments",
        "deployed_vessels",
        "associated_bookings",
        "source_service_route",
        "disruption_key",
    )

    def __init__(self, route_id: str, name: str = "", start_day_of_week: float = 0.0) -> None:
        self.id = route_id
        self.name = name or route_id
        self.start_day_of_week = float(start_day_of_week)
        self.segments: list[_Segment] = []
        self.deployed_vessels: list[_Vessel] = []
        self.associated_bookings: list[object] = []
        self.source_service_route: _ServiceRoute | None = None
        self.disruption_key: tuple[tuple[str, ...], tuple[tuple[str, str], ...]] | None = None

    def __repr__(self) -> str:
        return self.id


class _Berth:
    __slots__ = ("index", "port", "occupying_vessel", "is_available")

    def __init__(self, index: int, port: _Port) -> None:
        self.index = index
        self.port = port
        self.occupying_vessel: object | None = None
        self.is_available = True


class _Shipment:
    __slots__ = (
        "index",
        "teu_size",
        "demand",
        "current_storage_port",
        "generated_time",
        "completion_time",
        "associated_bookings",
        "current_booking_index",
        "carrying_vessel",
    )

    def __init__(self, index: int, teu_size: int, demand: SimpleNamespace, origin: _Port) -> None:
        self.index = index
        self.teu_size = teu_size
        self.demand = demand
        self.current_storage_port = origin
        self.generated_time: dt.datetime | None = None
        self.completion_time: dt.datetime | None = None
        self.associated_bookings: list[object] = []
        self.current_booking_index: int | None = None
        self.carrying_vessel: object | None = None


class _DisruptionPlan:
    __slots__ = (
        "target_leg",
        "target_berth",
        "start_offset_days",
        "duration_days",
        "multiplier",
        "close_berth",
    )

    def __init__(
        self,
        *,
        target_leg: _Leg | None = None,
        target_berth: _Berth | None = None,
        start_offset_days: float | None = None,
        duration_days: float | None = None,
        multiplier: float = 1.0,
        close_berth: bool = False,
    ) -> None:
        self.target_leg = target_leg
        self.target_berth = target_berth
        self.start_offset_days = start_offset_days
        self.duration_days = duration_days
        self.multiplier = float(multiplier)
        self.close_berth = bool(close_berth)


def make_port(name: str) -> _Port:
    return _Port(name)


def make_leg(departure: _Port, arrival: _Port, distance: float) -> _Leg:
    return _Leg(departure, arrival, distance)


def make_segment(sequence_index: int, leg: _Leg, route: _ServiceRoute) -> _Segment:
    seg = _Segment(sequence_index, leg, route)
    leg.segments.append(seg)
    route.segments.append(seg)
    return seg


def make_vessel_class(
    name: str, teu_capacity: int, sailing_speed: float, loa: float = 300.0
) -> _VesselClass:
    return _VesselClass(name, teu_capacity, sailing_speed, loa)


def make_vessel(index: int, vessel_class: _VesselClass, route: _ServiceRoute) -> _Vessel:
    vessel = _Vessel(index, vessel_class, route)
    route.deployed_vessels.append(vessel)
    return vessel


def make_route(route_id: str, name: str = "", start_day_of_week: float = 0.0) -> _ServiceRoute:
    return _ServiceRoute(route_id, name, start_day_of_week)


def make_berth(index: int, port: _Port) -> _Berth:
    berth = _Berth(index, port)
    return berth


def make_shipment(index: int, teu_size: int, demand: SimpleNamespace, origin: _Port) -> _Shipment:
    return _Shipment(index, teu_size, demand, origin)


def make_disruption_plan(**kwargs: object) -> _DisruptionPlan:
    return _DisruptionPlan(**kwargs)


def make_demand(origin: _Port, destination: _Port, annual_teus: int = 1) -> SimpleNamespace:
    demand = SimpleNamespace(
        origin_port=origin,
        destination_port=destination,
        annual_teus=int(annual_teus),
        shipments=[],
    )
    origin.outgoing_demands.append(demand)
    return demand


class FakeContext:
    """MaritimeDataContext-shaped container for the candidate.

    Mirrors the attributes the candidate reads. No organizer import.
    """

    def __init__(
        self,
        ports: Iterable[_Port],
        service_routes: Iterable[_ServiceRoute],
        legs: Iterable[_Leg],
        vessels: Iterable[_Vessel],
        disruption_plans: Iterable[_DisruptionPlan] = (),
    ) -> None:
        self.ports: list[_Port] = list(ports)
        self.demands: list[SimpleNamespace] = []
        self.service_routes: list[_ServiceRoute] = list(service_routes)
        self.initial_service_routes: list[_ServiceRoute] = list(self.service_routes)
        self.legs: list[_Leg] = list(legs)
        self.partial_service_routes: list[_Segment] = []
        self.vessel_classes: list[_VesselClass] = []
        self.vessels: list[_Vessel] = list(vessels)
        self.disruption_plans: list[_DisruptionPlan] = list(disruption_plans)


def snapshot_context(context: FakeContext) -> dict:
    """Identity-bearing snapshot proving no mutation occurred."""
    return {
        "ports": tuple(context.ports),
        "service_routes": tuple(context.service_routes),
        "legs": tuple(context.legs),
        "vessels": tuple(context.vessels),
        "vessel_routes": tuple(v.assigned_service_route for v in context.vessels),
        "disruption_plans": tuple(context.disruption_plans),
        "vessel_classes": tuple(id(vc) for vc in context.vessel_classes),
    }


def snapshot_shipment(shipment: _Shipment) -> dict:
    return {
        "associated_bookings": tuple(shipment.associated_bookings),
        "current_booking_index": shipment.current_booking_index,
        "carrying_vessel": shipment.carrying_vessel,
        "current_storage_port": shipment.current_storage_port,
        "completion_time": shipment.completion_time,
    }


def plan_active_window(plan: _DisruptionPlan) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.min + dt.timedelta(days=plan.start_offset_days or 0.0)
    end = start + dt.timedelta(days=plan.duration_days or 0.0)
    return start, end


def finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0
