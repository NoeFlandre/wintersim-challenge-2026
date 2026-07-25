# Round 0 Experiment: Transshipment Readiness Barrier v1

## Status

**PRE_RUN_REVIEW**

This document controls one candidate only. No operational execution is authorized by this status.

## Hypothesis

At a single-berth port, a receiver vessel can begin `VesselBeingServed` at the same simulation timestamp before a physically stored transshipment shipment completes its zero-duration booking-advance activity. The receiver then misses cargo that is not yet loading-ready. Temporarily serving one buffer vessel first can provide enough event-processing and service time for the booking to advance, after which the receiver can be selected next and load the cargo. The barrier is justified only when a conservative TEU-hour benefit is strictly positive under stable routes and timing.

## Pinned experiment control

- Starting commit: `bd518be`
- Fallback Cumulative Resilience Loss: `18.673577819840556`
- Fallback ATT SHA-256: `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`
- Seed: `2026`
- Warm-up: `140` days
- Measured duration: `360` days
- Interval: `5` days
- Required periods: `72`
- Strict acceptance:

  ```text
  candidate_loss < 18.673577819840556 - 1e-9
  ```

- Equality is rejection.
- Thresholds must not change after results are observed.
- There is no second candidate.
- Parameters must not be tuned after the run.
- No full run may occur without explicit reviewer approval.

## Runtime scope

Only `UserStrategy.select_vessel_for_berth` may make a participant decision. It delegates its organizer arguments unchanged to:

```python
choose_buffer_vessel(
    maritime_data_context=maritime_data_context,
    port=port,
    waiting_vessels=waiting_vessels,
    available_berths=available_berths,
    current_time=current_time,
    waiting_since_by_vessel=waiting_since_by_vessel,
)
```

The other hooks return `None` unconditionally:

- `create_alternative_service_routes`
- `assign_associated_bookings`
- `adjust_bookings_before_cargo_handling`

The runtime helper uses only the Python standard library and organizer-provided duck-typed objects. It must not import organizer strategy or simulation modules, `wsc2026_tools`, filesystem or network modules, subprocess, or environment APIs. It has no mutable module-level state and never mutates organizer arguments or state.

`BarrierDecision` is immutable evidence with these fields:

- `receiver`
- `buffer`
- `guaranteed_transitional_teu`
- `next_opportunity_hours`
- `buffer_service_hours`
- `affected_receiver_teu`
- `net_teu_hours`

`evaluate_transshipment_readiness_barrier(...)` returns that evidence or `None`. `choose_buffer_vessel(...)` returns the original `decision.buffer` object or `None`. There are no runtime configuration parameters.

## Confirmed simulator event order

The policy is based on confirmed organizer call sites, not activity names:

1. `BerthIdle` builds ordered `waiting_vessels` and `available_berths`.
2. It calls the participant only when `len(waiting_vessels) >= len(available_berths) * 3`.
3. A participant `None` delegates to `DefaultStrategy`; otherwise the result must be the exact original waiting-vessel object.
4. `BerthIdle` assigns the selected vessel to a berth and starts `BerthBerthing`.
5. `BerthBerthing.on_start` immediately releases that vessel from `VesselQueuingForBerth`.
6. `VesselBeingServed` starts at the same simulation time and performs loading selection.
7. The fixed three-hour `BerthBerthing` duration finishes later.
8. `BerthHandlingCargo` then consumes cargo-handling time.

Therefore the selected vessel chooses loading cargo before the three-hour berthing delay ends. A physically stored transshipment shipment remains ineligible while its current booking is inbound. Its zero-duration transshipment-waiting activity must advance `current_booking_index` before receiver loading selection. The actual organizer integration proof must establish that immediate receiver service misses for this event-order reason, while buffer-first service allows readiness, next receiver selection, and loading of the exact shipment object. If immediate receiver service loads the shipment, the causal premise is false and the experiment stops.

## Independent fallback berth ranking

For waiting vessel `i`:

```text
F_i =
    0.4 * norm(wait_hours_i)
  + 0.3 * norm(carried_teu_i)
  + 0.2 * norm(capacity_teu_i)
  - 0.1 * norm(handling_teu_i)
```

All TEU values are TEU and wait is hours.

`wait_hours_i` is:

```text
(current_time - waiting_start).total_seconds() / 3600
```

It is clamped below at zero. A missing wait-start uses `current_time`, yielding zero. Datetime arithmetic must be valid.

`carried_teu_i` is the sum of finite shipment `teu_size` values in `vessel.carried_shipments`.

`capacity_teu_i` is `vessel.vessel_class.teu_capacity`.

`handling_teu_i` is discharge TEU from `get_discharging_shipments_at_current_segment()` plus loading TEU from `get_loading_shipments_at_next_segment()`.

Each vector is normalized independently:

```text
(value - minimum) / (maximum - minimum)
```

If every value in a vector is equal, every normalized value in that vector is zero.

The original waiting-list order wins exact score ties. The receiver may be used only when exactly one vessel has the maximum finite score. No epsilon is used. The winner and any returned buffer preserve their original object references. Invalid or non-finite values delegate. Only specific expected type, attribute, arithmetic, or lookup errors may be caught to fail closed. Broad `Exception` or `BaseException` catches are forbidden.

Private integration tests compare this independent result by identity with the ignored organizer `DefaultStrategy` for valid states. Any mismatch blocks the experiment.

## Receiver and route validation

The strict unique fallback winner is receiver `R`. The barrier requires:

- exactly one available berth;
- that berth belongs to the current port;
- exactly one total berth in `port.berths`;
- `R` belongs by identity to `waiting_vessels`;
- `R.vessel_class` is valid;
- `R.assigned_service_route` is stable;
- `R.pending_assigned_service_route is None`;
- `R.assigned_service_route.source_service_route is None`;
- `R.assigned_service_route.disruption_key is None`;
- route segments have unique, complete sequence indexes, are ordered, connected, and cyclic;
- `R.current_segment` belongs by identity to that route;
- `R.get_next_segment()` is valid.

`T` is `R`'s next segment and must depart from the current port.

## Stored shipment and booking validation

`port.shipments_in_storage` is inspected in its existing order. Organizer collections are not reordered unnecessarily.

Every considered shipment must satisfy:

- `shipment.current_storage_port is port`;
- `shipment.carrying_vessel is None`;
- `shipment.teu_size` is finite and strictly positive;
- `associated_bookings` is nonempty;
- booking sequence indexes are unique;
- every `booking.shipment is shipment`;
- every booking has a valid service route;
- departure and arrival indexes resolve to real route segments;
- booking endpoints are directionally consistent;
- `current_booking_index` resolves to exactly one booking.

A mature receiver shipment belongs to `M_R` when its current booking uses `R.assigned_service_route`, its departure index equals `T.sequence_index`, and that departure segment leaves the current port.

A transitional receiver shipment is one whose current booking is inbound and arrives at the current port; whose immediate next booking is the booking with the smallest sequence index strictly greater than the current booking; whose next booking uses `R.assigned_service_route`, departs on `T.sequence_index`, and leaves the current port; and whose current and next bookings use different service-route objects. This must be a genuine transfer, not same-service continuation.

A stored shipment that could be relevant but cannot be classified safely causes delegation of the entire decision. Uncertain TEU is never silently omitted.

## Receiver TEU quantities and capacity guarantee

Discharging shipment membership is classified by object identity.

- `D_R`: TEU carried by `R` that discharges at its current segment.
- `O_R`: TEU carried by `R` that remains onboard after discharge.
- `M_R`: TEU of all mature stored shipments eligible for `R`'s next segment.
- `G_R`: TEU of all whole identified transitional shipments, all conservatively guaranteed to fit.
- `C_R`: receiver capacity in TEU.

The mandatory whole-set capacity guarantee is:

```text
O_R + M_R + G_R <= C_R
```

Capacity equality is allowed. A one-TEU overflow delegates. The policy never selects a favorable subset and never depends on unordered loading behavior.

Affected receiver TEU is:

```text
A_R = total TEU currently carried by R + M_R
```

`A_R` includes receiver cargo that discharges because buffer service delays that discharge. It excludes `G_R`, which is accounted for separately as caught rather than missed cargo. `G_R > 0`, `A_R >= 0`, and every quantity must be finite.

## Conservative next compatible opportunity

`W_R` is a lower bound in hours until the same route and departure segment could next carry the transitional cargo if it misses `R`.

For each sailing leg and vessel speed:

```text
minimum_sailing_hours =
    0.95 * sailing_distance_nautical_miles / sailing_speed_knots
```

Distance is nautical miles, speed is knots, and the result is hours. The `0.95` factor deliberately understates time and makes intervention harder to justify.

Complete receiver fleet validation requires:

- `R` appears by identity in `route.deployed_vessels`;
- every deployed vessel is assigned to that exact route object;
- every pending assigned route is `None`;
- every deployed vessel has finite positive sailing speed;
- every current segment belongs by identity to the route;
- no fleet phase is unknown;
- all required sailing distances are finite and nonnegative;
- segment order is unique, complete, connected, and cyclic.

For `R`, full-cycle return to `T` sums every route leg exactly once at `R`'s speed.

For another deployed vessel `V`, the remainder of `V.current_segment` is conservatively zero. Starting immediately after that segment, cyclic leg times are summed until `V` reaches `T`'s departure port. `T` itself is excluded because `W_R` measures when `V` can begin `T`. If `V.current_segment` immediately precedes `T`, its lower bound is zero. Cyclic wrapping and each vessel's own speed are used.

```text
W_R = min(
    R full-cycle return to T,
    each other deployed vessel earliest compatible arrival
)
```

Berth queues, handling, disruption delay, and current-leg residual time are omitted, preserving a lower bound. Zero, ambiguous, invalid, or non-finite `W_R` delegates.

## Relevant disruption and route-stability gate

Organizer time offsets use:

```text
start = datetime.min + timedelta(days=start_offset_days)
end = start + timedelta(days=duration_days)
active iff start <= current_time < end
```

The barrier delegates when an active disruption affects any receiver route leg, the current port berth, a berth at any port required for receiver compatible-return calculation, or a route/segment required for a buffer service calculation.

It also delegates when a relevant leg's live `sailing_time_multiplier` is not exactly `1`; a relevant route has `source_service_route` or `disruption_key`; a relevant vessel has a pending route assignment; or route/deployed-vessel membership is inconsistent. The candidate isolates event-order readiness under stable timing and does not predict disrupted routing.

## Buffer eligibility and service bound

Possible buffers `B` are evaluated in original `waiting_vessels` order. A buffer is excluded when:

- `B is R`;
- it is not an original waiting-vessel object;
- vessel class, route, segment, capacity, speed, or LOA is invalid;
- `pending_assigned_service_route is not None`;
- its route is alternative (`source_service_route` or `disruption_key` set);
- its route/current port is affected by a relevant active disruption;
- its next segment does not validly depart from the current port;
- it can receive the same transitional cargo because it has the same route and next departure segment as `R`;
- stored transitional cargo waits for its route and next segment;
- it discharges cargo whose immediate next booking requires receiver route `R` and segment `T`;
- any required booking/cargo relationship is malformed.

Buffer quantities:

- `D_B`: carried TEU discharging at the current segment.
- `O_B`: carried TEU remaining onboard after discharge.
- `E_B`: TEU returned by `get_loading_shipments_at_next_segment()`.
- `C_B`: vessel capacity in TEU.
- `LOA_B`: length overall in metres.

Quay-crane count:

```text
Q_B = max(1, floor(LOA_B / 55))
```

Conservative service bound in hours:

```text
S_B =
    3
    + (
        D_B
        + E_B
        + max(0, C_B - O_B)
      ) / (45 * Q_B)
```

The fixed `3` is berthing hours. `45` is TEU per crane-hour. The formula intentionally assumes `B` can fill all capacity remaining after discharge, including its apparent conservatism or double counting. It must not be simplified. TEU values must be finite and nonnegative; capacity, LOA, speed, and `S_B` must be finite and strictly positive.

## Guarantee that the receiver is actually next

For each `B`, the policy copies the waiting list and removes `B` by identity without mutating the original.

It first independently recomputes fallback ranking on the remaining list and requires `R` to remain the strict unique winner.

It then models the repository's actual one-berth congestion gate:

- If `len(remaining_waiting) >= 3`, strategy/default ranking is consulted and `R` must remain the strict unique fallback winner.
- If `len(remaining_waiting) < 3`, both strategies are bypassed and `remaining_waiting[0]` must be exactly `R`.

If neither path guarantees `R`, `B` is excluded. New arrivals during buffer service remain a hypothesis risk that only an approved bounded real replay may test.

## Net benefit and tie behavior

For each eligible buffer:

```text
N_B = G_R * (W_R - S_B) - A_R * S_B
```

Units are TEU-hours.

`G_R * (W_R - S_B)` is the conservative delay avoided for transitional cargo that catches `R` instead of waiting for the next compatible service. `A_R * S_B` is delay imposed on cargo already exposed to receiver departure timing.

The candidate requires all of:

- `G_R > 0`;
- `W_R > S_B`;
- `N_B > 0`;
- every value finite.

The eligible buffer with maximum `N_B` is selected. An exact tie preserves original waiting-list order. There is no epsilon and no secondary ranking. Invalid, incomplete, ambiguous, unsafe, non-finite, or zero-benefit states delegate with `None`.

## Validation and delegation summary

All quantities used by arithmetic must have the required sign and be finite. Identity-sensitive organizer relationships are validated by object identity. Sequence indexes must resolve uniquely. Route connectivity, cyclic closure, fleet deployment, booking direction (no full-cycle bookings, no identical departure/arrival endpoints), storage ownership, carrying ownership, berth ownership, and next-selection behavior must be unambiguous. Any violation delegates. The strategy does not mutate lists, mappings, context, routes, bookings, cargo, vessels, or berths. It returns only an original waiting-vessel object.

## TDD and proof controls

Every production behavior follows RED, GREEN, then refactor while green. A valid RED must be an assertion failure caused by absent behavior, not an import, fixture, syntax, or collection error. Assertions are not weakened to obtain GREEN.

Mandatory initial REDs:

1. `test_positive_transition_margin_selects_original_buffer_object`, through the final public hook, must fail against `bd518be` because it returns `None` rather than the exact original buffer.
2. `test_real_activity_order_receiver_misses_without_barrier_and_catches_with_barrier`, using actual ignored organizer activities and scheduler, must first prove immediate receiver miss for the predicted event-order reason, then fail against the no-op strategy because no buffer is selected.

Focused tests cover the fallback formula and parity, identity and hook contracts, booking classification, whole-set capacity, route phase and `W_R`, service bound, exclusions, actual-next guarantee, strict net margin, deterministic repeated calls, immutable state, forbidden imports, no mutable globals, organizer activity order, overlay, packaging, and the read-only probe surface.

### RED/GREEN evidence ledger

Operational trajectory commands are never used for this ledger.

#### Initial RED

- Command:

  ```text
  uv run pytest tests/unit/test_transshipment_readiness.py::test_positive_transition_margin_selects_original_buffer_object -q
  ```

  Result: `1 failed`. The final public hook returned `None`, so the identity assertion `selected is state["buffer"]` failed against the no-op baseline.

- Command:

  ```text
  uv run pytest tests/integration/test_transshipment_readiness_activity_order.py::test_real_activity_order_receiver_misses_without_barrier_and_catches_with_barrier -q
  ```

  Result: `1 failed`. Before the feature assertion, the actual organizer activity test proved that immediate receiver assignment started service before booking advancement, left the exact shipment stored and absent from receiver cargo, advanced the booking only afterward, and left the shipment pending for loading. The feature assertion then failed because the no-op participant hook returned `None` instead of the original buffer object.

#### Initial GREEN

- Command:

  ```text
  uv run pytest tests/unit/test_transshipment_readiness.py::test_positive_transition_margin_selects_original_buffer_object -q
  ```

  Result: `1 passed`. The public hook returned the exact original buffer object.

- Command:

  ```text
  uv run pytest tests/integration/test_transshipment_readiness_activity_order.py::test_real_activity_order_receiver_misses_without_barrier_and_catches_with_barrier -q
  ```

  Result: `1 passed`. The actual organizer activity proof confirmed immediate receiver miss, buffer selection, booking readiness during buffer service, receiver-next selection, and loading/carrying of the exact guaranteed shipment object.

#### Probe fail-closed RED → GREEN (corrections phase)

- RED command:

  ```text
  uv run pytest tests/unit/test_transshipment_readiness_probe.py -q
  ```

  RED result (15 failures, 1 pass):
  - `install_observer`, `remove_observer`, `_validate_decision_safety`,
    `_record_evidence_atomic`, and `NoDivergenceLifecycle` were
    missing from the probe module.
  - `MAX_OBSERVATION_EVENTS`, `MAX_REPLAY_SEARCH_EVENTS`,
    `EXPECTED_CUMULATIVE_RESILIENCE_LOSS`, and
    `EXPECTED_OBSERVATION_HASH` were not exported.
  - `_validate_decision_safety` did not raise on parity, mutation,
    strictness, or receiver-identity mismatches (the legacy observer
    silently skipped those cases).
  - `_record_evidence_atomic` did not exist; the legacy code wrote
    evidence non-atomically and could overwrite existing files.

- GREEN command:

  ```text
  uv run pytest tests/unit/test_transshipment_readiness_probe.py tests/unit/test_transshipment_readiness.py tests/unit/test_overlay.py tests/unit/test_packaging.py tests/unit/test_cli.py -q
  ```

  GREEN result: all assertions pass; the probe is implemented but not
  executed against a real simulation in this phase.

## Overlay and packaging control

The submission surface is:

- **Required runtime files** (must be present): `transshipment_readiness.py`, `user_strategy.py`.
- **Allowlisted optional files** (copied if present): `README.md`.

A submission missing either required runtime file is atomic-failed by both the overlay and the packager BEFORE any file is copied or any archive is written. A submission missing `README.md` is silently accepted; the overlay copies only the runtime pair and the packager ships the archive without a README. The default candidate still includes `README.md`, so the documented archive contents below assume all three files are present.

The overlay must copy the runtime pair, leave organizer files byte-identical, reject unknown helpers, refuse a partial copy (atomic on missing-helper), and remain idempotent.

The package must contain only participant-owned allowlisted files below its `response_strategies` directory. The relative import in `user_strategy.py` must resolve to the packaged helper. Unknown participant modules and organizer-owned modules remain rejected. Two archives from identical candidate inputs must be byte-identical.

Run packaging locally with:

```bash
uv run wsc2026 package --team DetTeam --round 1
```

The archive contains exactly (when all three files are present):

- `Round1_DetTeam/response_strategies/README.md`
- `Round1_DetTeam/response_strategies/transshipment_readiness.py`
- `Round1_DetTeam/response_strategies/user_strategy.py`

When `README.md` is intentionally omitted, the archive contains only the runtime pair (in sorted order):

- `Round1_DetTeam/response_strategies/transshipment_readiness.py`
- `Round1_DetTeam/response_strategies/user_strategy.py`

The current measured archive SHA-256 (when all three files are present) is `a61c06166fb829234407fbc14c9fe44eeb19a53412996345363f6c110f257cbb`. The archive is recomputed deterministically on every run.

## Private probe control

`experiments/probes/transshipment_readiness_barrier_v1.py` is development-only and must never be packaged. **The probe is implemented but not executed against a real simulation in this phase.** The probe's bounded no-divergence lifecycle is verified with fakes (see `tests/unit/test_transshipment_readiness_probe.py`).

The probe is **FAIL-CLOSED** at every layer:

- the observation observer aborts with `ProbeError` on any parity, mutation, strictness, or receiver-identity mismatch;
- no valid-looking evidence is written after a safety violation;
- the original hook is restored on every code path (success and failure);
- evidence is written atomically (temp file + rename) and never overwrites existing evidence;
- the observation event cap (`MAX_OBSERVATION_EVENTS = 1_000_000`) aborts on exhaustion with a clear `ProbeError`;
- the replay event caps (`MAX_REPLAY_SEARCH_EVENTS = 100_000`,
  `MAX_REPLAY_EVENTS_AFTER_DECISION = 100_000`) abort on exhaustion with a
  clear `ProbeError`;
- malformed, stale, incomplete, or safety-flag-false evidence is refused
  before any model is loaded;
- `_load_runtime` restores `sys.path` and removes every inserted package
  from `sys.modules` on every entry and exit path.

The lifecycle constants and documented invariants:

- `WARMUP_DAYS = 140`
- `MEASURED_DAYS = 360`
- `ATT_PERIOD_DAYS = 5`
- `EXPECTED_PERIODS = 72`
- `EXPECTED_CUMULATIVE_RESILIENCE_LOSS = 18.673577819840556`
- `EXPECTED_OBSERVATION_HASH = 10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`

A later approved observation mode will replay the real fallback trajectory up to an event-count cap, monkeypatch the organizer berth hook in-process, evaluate the shared immutable decision, compare the independent fallback receiver with actual `DefaultStrategy`, always return `None`, refuse any candidate whose independent ranking disagrees with the real hook or whose evaluation mutates organizer state, stop at the first strict candidate divergence, and write only derived evidence to ignored `experiments/results/transshipment_readiness_barrier_v1_probe.json`:

- simulation timestamp;
- anonymized stable participant-side vessel indexes;
- `G_R`;
- `A_R`;
- `W_R`;
- `S_B`;
- `N_B`;
- parity result;
- no-mutation result.

It must not serialize organizer source, input rows, complete objects, or private data.

A later approved bounded replay mode may replay seed `2026`, locate the same event under the bounded search cap, allow the candidate only there, and verify all of:

- `B` is served at the berth,
- the exact guaranteed shipments become ready,
- the first vessel to occupy the berth after `B` departs is exactly `R` (no other vessel in between),
- every guaranteed transitional shipment is loaded on `R`.

This is mechanism evidence, not score evidence. The replay refuses to honor any stored evidence whose parity or no-mutation flag is not `True`, and it cleans up the participant and organizer modules from `sys.modules` on exit.

The static actual-next gate in the bounded lifecycle assumes the queue is unchanged for the duration of the measured horizon (no vessel arrivals or departures during ATT sampling). This is a documented hypothesis; it is not verified until a real run is approved.

## Pre-review boundary

Authorized checks are lock verification, dependency sync, formatting, lint, typecheck, focused RED/GREEN unit tests, non-integration coverage at or above 90% (current measured 90.27%), bounded synthetic integration tests using actual organizer activities, integration tests that do not launch a full trajectory, deterministic packaging, member verification, `git diff --check`, restricted-material search, and clean Git status. Run each check via `uv run <command>` from the repo root; never embed absolute paths.

Before reviewer approval, do not run:

- `uv run wsc2026 sync --round round0`
- `uv run wsc2026 smoke --round round0`
- the real-context trajectory probe (probe is implemented but not executed)
- bounded replay from the real seed (replay is implemented but not executed)
- `uv run wsc2026 run --round round0 --full`
- any complete fallback or candidate simulation

Passing tests alone does not authorize a run.

## Rejection and restoration

Rejection requires all of:

1. Preserve private derived evidence in ignored storage.
2. Revert participant behavior to the known no-op strategy.
3. Restore the fallback ATT output.
4. Verify fallback ATT SHA-256 exactly equals `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`.
5. Verify fallback Cumulative Resilience Loss exactly equals `18.673577819840556`.
6. Preserve the rejection decision and evidence references.

No threshold changes, second candidate, parameter tuning, or additional full run may follow the observed result.
