"""Unit-test scaffolding for the participant strategy.

The submission imports ``Booking``, ``Segment`` and ``ServiceRoute`` from the
organizer's ``maritime_data_context`` package, an allowlisted submission import
that is not part of this repository. Unit tests must stay hermetic, so when the
organizer tree is not on ``sys.path`` a minimal stand-in is installed that
provides only the attributes the strategy uses. Integration tests purge this
module and insert the real organizer package instead.
"""

from __future__ import annotations

import importlib.util
import sys
import types


def _install_maritime_data_context_stub() -> None:
    if importlib.util.find_spec("maritime_data_context") is not None:
        return

    module = types.ModuleType("maritime_data_context")

    class Booking:
        """Stand-in with the organizer ``Booking`` constructor signature."""

        def __init__(
            self,
            sequence_index: int = 0,
            shipment: object = None,
            service_route: object = None,
            departure_segment_index: int = 0,
            arrival_segment_index: int = 0,
        ) -> None:
            self.sequence_index = sequence_index
            self.shipment = shipment
            self.service_route = service_route
            self.departure_segment_index = departure_segment_index
            self.arrival_segment_index = arrival_segment_index

    class Segment:
        """Stand-in with the organizer ``Segment`` constructor signature."""

        def __init__(
            self,
            sequence_index: int = 0,
            associated_leg: object = None,
            associated_service_route: object = None,
        ) -> None:
            self.sequence_index = sequence_index
            self.associated_leg = associated_leg
            self.associated_service_route = associated_service_route
            self.current_vessels: list[object] = []

    class ServiceRoute:
        """Stand-in with the organizer ``ServiceRoute`` constructor signature."""

        def __init__(
            self,
            id: str = "",
            name: str = "",
            start_day_of_week: float = 0.0,
        ) -> None:
            self.id = id
            self.name = name
            self.start_day_of_week = start_day_of_week
            self.segments: list[object] = []
            self.deployed_vessels: list[object] = []
            self.associated_bookings: list[object] = []
            self.source_service_route: object = None
            self.disruption_key: object = None

    module.Booking = Booking  # type: ignore[attr-defined]
    module.Segment = Segment  # type: ignore[attr-defined]
    module.ServiceRoute = ServiceRoute  # type: ignore[attr-defined]
    module.__all__ = ["Booking", "Segment", "ServiceRoute"]  # type: ignore[attr-defined]
    sys.modules["maritime_data_context"] = module


_install_maritime_data_context_stub()
