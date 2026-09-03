"""Minimal declarations for the organizer-supplied ``maritime_data_context``.

This package is provided by the organizer's evaluation runtime and is not part
of this repository, so type checkers cannot see it. Only the surface the
participant submission actually uses is declared here: the ``Booking``
constructor documented for ``assign_associated_bookings``. This file is
participant-owned, is never packaged into a submission, and has no runtime
effect.
"""

from typing import Any

__all__ = ["Booking"]

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
