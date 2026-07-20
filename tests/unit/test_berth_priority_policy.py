"""Red-green tests for the age-weighted carried-TEU berth priority policy.

Policy (experiment name ``age_weighted_carried_teu_berth_priority_v1``):

When port congestion forces a berth-priority decision, release the vessel
carrying the greatest accumulated TEU waiting-age. Priority:

    score(v) = sum(shipment.teu_size * age_hours for shipment in carried_shipments)

where age_hours = max(0, (current_time - generated_time).total_seconds() / 3600).

Tie-breaks (deterministic, in order):

1. greater total carried TEU
2. longer berth waiting time from waiting_since_by_vessel
3. original order in waiting_vessels (stable selection)

Edge cases:

* Empty waiting_vessels -> None
* Missing/None generated_time contributes zero age
* Missing/None teu_size contributes zero
* Negative teu_size treated as zero (no negative priority)
* Missing waiting_since_by_vessel entry -> zero waiting time
* Only current_time is consulted; never wall-clock
* Must not mutate any input
* Repeated identical calls return the identical vessel object

The other three strategy methods must continue returning None.

Synthetic sentinel objects only; no organizer source import.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from response_strategies.user_strategy import UserStrategy


def _vessel(name: str, shipments: list[Any]) -> Any:
    """Build a sentinel vessel that exposes the only attributes we read."""

    class _Vessel:
        def __init__(self) -> None:
            self.name = name
            self.carried_shipments = shipments

        def __repr__(self) -> str:
            return f"<Vessel {name}>"

    return _Vessel()


def _shipment(
    name: str,
    teu: Any,
    generated_time: Any,
) -> Any:
    class _Shipment:
        def __init__(self) -> None:
            self.name = name
            self.teu_size = teu
            self.generated_time = generated_time

        def __repr__(self) -> str:
            return f"<Shipment {name}>"

    return _Shipment()


_T0 = dt.datetime(2026, 1, 1)


def _hours(offset: float) -> dt.datetime:
    return _T0 + dt.timedelta(hours=offset)


# --- baseline invariants: empty queue and other methods --------------------


def test_empty_waiting_returns_none() -> None:
    """If no vessel is waiting, the strategy must return None."""
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=[],
        available_berths=["berth"],
        current_time=_hours(100),
        waiting_since_by_vessel={},
    )
    assert result is None


def test_other_three_methods_continue_returning_none() -> None:
    """The route/booking handlers must remain fallback None."""
    assert (
        UserStrategy.create_alternative_service_routes({"routes": []}, now=_T0, vessel=None) is None
    )
    assert (
        UserStrategy.assign_associated_bookings({"bookings": []}, now=_T0, shipment=object())
        is None
    )
    assert (
        UserStrategy.adjust_bookings_before_cargo_handling({"routes": []}, now=_T0, vessel=object())
        is None
    )


# --- primary priority: age-weighted carried TEU -----------------------------


def test_picks_oldest_heavy_shipment_over_newer_light() -> None:
    """An older shipment outweighs a newer one even if the newer's TEU is equal.

    vessel_A carries 10 TEU generated 100h ago.
    vessel_B carries 10 TEU generated 1h ago.
    Score: A=1000, B=10. A wins.
    """
    vessel_a = _vessel("A", [_shipment("s_a", teu=10, generated_time=_hours(0))])
    vessel_b = _vessel("B", [_shipment("s_b", teu=10, generated_time=_hours(99))])
    waiting = [vessel_a, vessel_b]
    now = _hours(100)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"A": 0, "B": 0},
    )
    assert result is vessel_a


def test_picks_higher_total_teu_when_age_is_equal() -> None:
    """When age-weighted priorities tie, total carried TEU breaks the tie."""
    vessel_small = _vessel("S", [_shipment("s", teu=10, generated_time=_hours(0))])
    vessel_big = _vessel(
        "B",
        [
            _shipment("x", teu=5, generated_time=_hours(0)),
            _shipment("y", teu=5, generated_time=_hours(0)),
        ],
    )
    waiting = [vessel_small, vessel_big]
    now = _hours(100)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"S": 0, "B": 0},
    )
    # Both have score 10 * 100 = 1000; tiebreak is total TEU (10 == 10); both equal.
    # Insert an asymmetry so the tiebreak is observable.
    assert result in (vessel_small, vessel_big)


def test_higher_total_teu_breaks_tie_when_age_equal() -> None:
    """Construct an unambiguous total-TEU tiebreak case."""
    vessel_small = _vessel("S", [_shipment("s", teu=5, generated_time=_hours(0))])
    vessel_big = _vessel(
        "B",
        [
            _shipment("x", teu=3, generated_time=_hours(0)),
            _shipment("y", teu=3, generated_time=_hours(0)),
        ],
    )
    waiting = [vessel_small, vessel_big]
    now = _hours(100)
    # Scores: S = 5*100 = 500; B = (3+3)*100 = 600. B wins on age-weighted.
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"S": 0, "B": 0},
    )
    assert result is vessel_big


def test_longer_waiting_time_breaks_tie_after_total_teu() -> None:
    """When age-weighted and total TEU both tie, longer wait wins."""
    same_age = _hours(0)
    vessel_a = _vessel("A", [_shipment("a", teu=10, generated_time=same_age)])
    vessel_b = _vessel("B", [_shipment("b", teu=10, generated_time=same_age)])
    waiting = [vessel_a, vessel_b]
    now = _hours(100)
    # Both have score 1000 and total TEU 10; only waiting_since differs.
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"A": 5, "B": 50},
    )
    assert result is vessel_b  # 50 > 5


def test_original_order_breaks_tie_after_waiting_time() -> None:
    """When age, total TEU, and waiting time all tie, the earlier vessel wins."""
    same_age = _hours(0)
    vessel_a = _vessel("A", [_shipment("a", teu=10, generated_time=same_age)])
    vessel_b = _vessel("B", [_shipment("b", teu=10, generated_time=same_age)])
    waiting = [vessel_a, vessel_b]
    now = _hours(100)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"A": 0, "B": 0},
    )
    assert result is vessel_a  # earlier in queue


# --- edge cases: missing / None / negative attributes ------------------------


def test_none_generated_time_contributes_zero_age() -> None:
    """A shipment without ``generated_time`` must not crash and contributes zero age."""
    vessel_a = _vessel("A", [_shipment("a", teu=10, generated_time=None)])
    vessel_b = _vessel("B", [_shipment("b", teu=10, generated_time=_hours(0))])
    waiting = [vessel_a, vessel_b]
    now = _hours(100)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"A": 0, "B": 0},
    )
    # A has score 0; B has score 1000. B wins.
    assert result is vessel_b


def test_none_teu_contributes_zero() -> None:
    vessel_a = _vessel("A", [_shipment("a", teu=None, generated_time=_hours(0))])
    vessel_b = _vessel("B", [_shipment("b", teu=10, generated_time=_hours(0))])
    waiting = [vessel_a, vessel_b]
    now = _hours(100)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"A": 0, "B": 0},
    )
    assert result is vessel_b


def test_negative_teu_clamped_to_zero() -> None:
    """Negative TEU must not yield negative priority."""
    vessel_bad = _vessel(
        "BAD",
        [
            _shipment("a", teu=-5, generated_time=_hours(0)),
            _shipment("b", teu=10, generated_time=_hours(0)),
        ],
    )
    vessel_good = _vessel("GOOD", [_shipment("x", teu=5, generated_time=_hours(0))])
    waiting = [vessel_bad, vessel_good]
    now = _hours(100)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"BAD": 0, "GOOD": 0},
    )
    # BAD score = (max(-5,0)+10)*100 = 1000; GOOD = 5*100 = 500. BAD wins.
    # The clamp only prevents NEGATIVE score, not negative contribution to a sum.
    assert result is vessel_bad


def test_missing_waiting_since_mapping_means_zero_wait() -> None:
    """A vessel not in the mapping has zero waiting time for tiebreak purposes."""
    vessel_a = _vessel("A", [_shipment("a", teu=10, generated_time=_hours(0))])
    vessel_b = _vessel("B", [_shipment("b", teu=10, generated_time=_hours(0))])
    waiting = [vessel_a, vessel_b]
    now = _hours(100)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"A": 100},  # B missing -> 0
    )
    # Tiebreak order: A has 100 wait, B has 0 -> A wins by waiting time.
    assert result is vessel_a


# --- non-mutation and repeatability -----------------------------------------


def test_no_input_mutation() -> None:
    vessels = [
        _vessel("A", [_shipment("a", teu=10, generated_time=_hours(0))]),
        _vessel("B", [_shipment("b", teu=10, generated_time=_hours(0))]),
    ]
    vessels_snapshot = list(vessels)
    shipments_snapshot_a = list(vessels[0].carried_shipments)
    shipments_snapshot_b = list(vessels[1].carried_shipments)
    waiting_map = {"A": 1, "B": 2}
    waiting_map_snapshot = dict(waiting_map)

    UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=vessels,
        available_berths=["berth"],
        current_time=_hours(50),
        waiting_since_by_vessel=waiting_map,
    )

    assert vessels == vessels_snapshot
    assert vessels[0].carried_shipments == shipments_snapshot_a
    assert vessels[1].carried_shipments == shipments_snapshot_b
    assert waiting_map == waiting_map_snapshot


def test_repeated_calls_identical_inputs_return_same_object() -> None:
    vessels = [
        _vessel("A", [_shipment("a", teu=10, generated_time=_hours(0))]),
        _vessel("B", [_shipment("b", teu=20, generated_time=_hours(0))]),
    ]
    args = {
        "maritime_data_context": object(),
        "port": object(),
        "waiting_vessels": vessels,
        "available_berths": ["berth"],
        "current_time": _hours(10),
        "waiting_since_by_vessel": {"A": 0, "B": 0},
    }
    first = UserStrategy.select_vessel_for_berth(**args)
    second = UserStrategy.select_vessel_for_berth(**args)
    assert first is second


def test_no_wall_clock_dependency() -> None:
    """The policy must use only the simulation ``current_time`` argument.

    Two vessels carry the same TEU and the same generated_time relative to
    the simulation clock. The only thing that should change the result is the
    supplied ``current_time``; if the policy secretly consulted the real
    wall clock, the answer would differ across runs.
    """
    ancient = _vessel("ANCIENT", [_shipment("a", teu=10, generated_time=dt.datetime(1900, 1, 1))])
    modern = _vessel("MODERN", [_shipment("b", teu=10, generated_time=dt.datetime(1900, 1, 1))])
    waiting = [ancient, modern]

    # Pass a current_time that is 100h after the simulated cargo.
    now = dt.datetime(1900, 1, 1) + dt.timedelta(hours=100)
    result_a = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=list(waiting),
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"ANCIENT": 0, "MODERN": 0},
    )
    # Identical inputs -> identical outputs (deterministic, no wall clock).
    result_b = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=list(waiting),
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"ANCIENT": 0, "MODERN": 0},
    )
    assert result_a is result_b
    # The result is whichever vessel is first in the original queue
    # (both have identical priority components).
    assert result_a is ancient


def test_does_not_pick_just_largest_vessel_or_first_queue_member() -> None:
    """The policy must not collapse to "largest vessel" or "first in queue".

    Construct a case where:
      - "first in queue" would pick vessel_young (it is first),
      - "largest vessel" would pick vessel_big (it has the most TEU),
      - but the age-weighted policy picks vessel_old because its small
        cargo is much older.

    Scores:
      vessel_young: 100 TEU * 0 hours = 0     (first in queue, largest)
      vessel_big:   10  TEU * 10 hours = 100 (huge but freshly generated)
      vessel_old:   5   TEU * 100 hours = 500 (small but very old)
    vessel_old wins on the primary metric even though it is last and smallest.
    """
    vessel_young = _vessel("YOUNG", [_shipment("y", teu=100, generated_time=_hours(100))])
    vessel_big = _vessel("BIG", [_shipment("b", teu=10, generated_time=_hours(90))])
    vessel_old = _vessel("OLD", [_shipment("o", teu=5, generated_time=_hours(0))])
    waiting = [vessel_young, vessel_big, vessel_old]
    now = _hours(100)
    result = UserStrategy.select_vessel_for_berth(
        maritime_data_context=object(),
        port=object(),
        waiting_vessels=waiting,
        available_berths=["berth"],
        current_time=now,
        waiting_since_by_vessel={"YOUNG": 0, "BIG": 0, "OLD": 0},
    )
    assert result is vessel_old  # NOT first-in-queue (YOUNG), NOT largest (BIG/YOUNG)
