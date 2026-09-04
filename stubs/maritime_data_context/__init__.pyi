"""Minimal declarations for the organizer-supplied ``maritime_data_context``.

This package is provided by the organizer's evaluation runtime and is not part
of this repository, so type checkers cannot see it. Only the surface the
participant submission actually uses is declared here: the ``Booking``
constructor documented for ``assign_associated_bookings``, and the
``ServiceRoute``/``Segment`` constructors documented for
``create_alternative_service_routes``. This file is
participant-owned, is never packaged into a submission, and has no runtime
effect.
"""

from typing import Any

__all__ = ["Booking", "Segment", "ServiceRoute"]

class Booking:
    sequence_index: int
    shipment: Any
    service_route: Any
    departure_segment_index: int
    arrival_segment_index: int

    def __init__(
        self,
        sequence_index: int = ...,
        shipment: Any = ...,
        service_route: Any = ...,
        departure_segment_index: int = ...,
        arrival_segment_index: int = ...,
    ) -> None: ...

class Segment:
    sequence_index: int
    associated_leg: Any
    associated_service_route: Any
    current_vessels: list[Any]

    def __init__(
        self,
        sequence_index: int = ...,
        associated_leg: Any = ...,
        associated_service_route: Any = ...,
    ) -> None: ...

class ServiceRoute:
    id: str
    name: str
    start_day_of_week: float
    segments: list[Any]
    deployed_vessels: list[Any]
    associated_bookings: list[Any]
    source_service_route: Any
    disruption_key: Any

    def __init__(
        self,
        id: str = ...,
        name: str = ...,
        start_day_of_week: float = ...,
    ) -> None: ...
