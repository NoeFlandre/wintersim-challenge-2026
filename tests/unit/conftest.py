"""Unit-test scaffolding for the participant strategy.

The submission imports ``Booking`` from the organizer's ``maritime_data_context``
package, which is an allowlisted submission import but is not part of this
repository. Unit tests must stay hermetic, so when the organizer tree is not on
``sys.path`` a minimal stand-in is installed that provides only the attributes
the strategy uses. Integration tests purge this module and insert the real
organizer package instead.
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

    module.Booking = Booking  # type: ignore[attr-defined]
    module.__all__ = ["Booking"]  # type: ignore[attr-defined]
    sys.modules["maritime_data_context"] = module


_install_maritime_data_context_stub()
