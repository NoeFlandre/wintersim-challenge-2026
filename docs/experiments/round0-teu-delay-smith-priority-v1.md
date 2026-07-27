# Round 0 TEU-delay-per-berth-hour priority v1

**Status:** SUCCESS_REJECTED

## Hypothesis

The metric is backlog-adjusted and TEU-weighted. At any instant, delaying an
unfinished shipment by one hour adds approximately `shipment.teu_size * 1h`
to the system's accumulated transport-time burden. Cargo age does not change
that marginal one-hour cost.

When several vessels compete for a berth, the locally principled scheduling
rule is a Smith-style ratio:

  TEU whose progress depends on this vessel
  -------------------------------------------
  predicted berth-service time

Choose the vessel with the greatest TEU-delay relieved per berth-service hour.

## Exact Smith-ratio formula (with fixed 3-hour berthing overhead)

The organizer models berth occupancy as a fixed 3-hour berthing activity
(`simulation_model/berth_berthing.py`) followed by cargo handling
(`simulation_model/berth_handling_cargo.py`). The predicted berth-service
time is therefore:

  service_hours = 3.0 + handled_teu / (qc_count * 45.0)

The Smith ratio ("TEU-delay relieved per berth-service hour"):

  priority_ratio = affected_teu / service_hours

For exact integer comparison, the constant `45` is dropped:

  numerator   = affected_teu * qc_count
  denominator = 135 * qc_count + handled_teu

Vessel A outranks vessel B iff:

  A.numerator * B.denominator > B.numerator * A.denominator

Exact ties preserve the input `waiting_vessels` order. There is no
zero-service special case: a vessel with `handled_teu == 0` still
consumes three hours of berth time and is compared via the same ratio
path.

## Why age is intentionally excluded

Cargo age does not appear in the formula. The metric weights ATT per TEU,
so the marginal one-hour cost of delaying one TEU is constant. Multiplying
by age over-counts old cargo and under-counts fresh cargo whose delay is
equally expensive in the next hour. The earlier age-weighted candidate
(`round0-first-result`) scored worse than the fallback by ~22%; this
candidate deliberately avoids that mistake.

## Metric definitions (one-pass carried-cargo classification)

The metrics are computed by an explicit one-pass classification of carried
cargo:

  for each carried shipment:
      1. read and validate a positive integer teu; else delegate
      2. add it to carried_teu
      3. require a valid non-None current booking; else delegate
      4. if booking.service_route != vessel.assigned_service_route:
           contribute to carried_teu only (foreign cargo)
           do not add to occupied_teu
           do not add to discharge_teu
           continue
      5. if current_segment is not None and
         booking.arrival_segment_index == current_segment.sequence_index:
           add to discharge_teu
           do not add to occupied_teu
           continue
      6. otherwise: add to occupied_teu

  projected_load_teu = greedy load using (teu_capacity - occupied_teu)
  handled_teu        = discharge_teu + projected_load_teu
  affected_teu       = carried_teu + projected_load_teu
  qc_count           = max(1, int(vessel.vessel_class.loa / 55))

When `current_segment is None`:

  - discharge_teu must be zero;
  - assigned-route carried cargo is occupied;
  - foreign-route cargo is neither occupied nor discharged;
  - all carried cargo (including foreign) contributes to affected_teu.

The derived subtraction `discharge = carried - occupied` is not used
anywhere in the implementation; foreign cargo must not appear in
discharge_teu.

## Predicted-load calculation

`port.shipments_in_storage` is iterated in its existing deterministic order.
A stored shipment is an eligible loading candidate iff:

  * `shipment.carrying_vessel is None`;
  * `shipment.get_current_booking()` is a valid (non-None) booking;
  * `booking.service_route is vessel.assigned_service_route`;
  * `booking.departure_segment_index == next_segment.sequence_index`.

The greedy load fills remaining capacity in storage order without reordering,
partial loading, or mutation. Reading state is purely observational: the
candidate never appends to `vessel.carried_shipments`, never removes from
`port.shipments_in_storage`, never mutates any booking.

## One-hook scope

Only `UserStrategy.select_vessel_for_berth(...)` is changed. The other three
hooks return `None` unconditionally:

  * `create_alternative_service_routes`
  * `assign_associated_bookings`
  * `adjust_bookings_before_cargo_handling`

The candidate never mutates any input. It never returns `False`. It returns
`None` only when safe evaluation is impossible or `waiting_vessels` is empty.

## Invalid-input delegation

`_read_positive_teu` accepts positive ``int`` only (excluding ``bool``);
fractional floats such as 1.5 are rejected, strings, ``None``,
non-finite or fractional floats, ``bool``, zero, and negative values
all raise a narrow `(TypeError, ValueError)`. None bookings on carried
or stored shipments also raise `AttributeError`. `_validate_vessel_inputs`
raises a narrow exception when `vessel.vessel_class`,
`vessel_class.loa`, `vessel_class.teu_capacity`, or
`vessel.assigned_service_route` is missing, non-finite, or nonpositive.
The public selector catches only `(AttributeError, TypeError, ValueError,
OverflowError)` and delegates with `None`. No broad `except Exception` or
`except BaseException` is used anywhere in submission code.

## Full-run configuration

- Branch: `codex/round0-teu-delay-smith-priority-v1`
- Strategy SHA-256 (candidate): `e80c5b5bf488acae4455564511fe350c19a497dc8044f9ec6988afc590ee6c63`
- Strategy SHA-256 (active fallback after revert): `b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`
- Scenario: `create_with_disruption`
- Seed: `2026`
- Warm-up: `140 days`
- Measured duration: `360 days`
- Interval: `5 days`
- Period count: `72`
- Simulation clock runtime: `00:28:23`
- Run command: `uv run wsc2026 run --round round0 --full`

## Current comparable fallback (locally reproduced)

- Score: `18.673577819840556`
- ATT SHA-256: `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`
- Mean ATT across numbered period rows: about 20.336944444444445 days
- 72 periods

## Acceptance rule

Retain the candidate only if the complete 72-period Cumulative Resilience
Loss is strictly lower than `18.673577819840556` by more than `1e-9`.
Equality is rejection. This rule was applied without alteration after seeing
the result.

## Full result

| Measure | Value |
| --- | --- |
| Candidate Cumulative Resilience Loss | `18.673577819840556` |
| Candidate ATT SHA-256 | `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658` |
| Fallback score threshold | `18.673577819840556` |
| Delta vs baseline threshold | `0.0` |
| Relative percentage change | `0.0%` |
| Mean ATT across numbered period rows (days) | `20.336944444444445` |
| Period count | `72` |
| Simulation clock runtime | `00:28:23` |
| Periods better than fallback | `0` |
| Periods equal to fallback | `72` |
| Periods worse than fallback | `0` |
| Beats fallback `18.673577819840556`? | `No` (equal — rejection) |

The candidate Cumulative Resilience Loss is byte-identical to the pinned
fallback reproduction. Within this seed, warm-up, horizon, and scenario, the
candidate made no selection that diverged from the organizer fallback's
berth assignment; the produced `ATT_By_Statistics_Interval.csv` matches the
fallback snapshot exactly
(`10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`).

## Implementation / correction commits (the approved f04daad candidate)

- `dde3854` — `docs: define TEU-delay Smith-priority experiment`
- `5734c8c` — `feat: prioritize TEU delay relieved per berth hour`
- `6c3c635` — `fix: include full berth time in Smith priority`
- `f04daad` — `fix: classify carried cargo for Smith metrics`

## Reject / restore commits

- `4b8ebf6` — `revert: restore fallback after Smith-priority experiment`

This revert rolls back the three implementation/correction commits
`f04daad`, `6c3c635`, and `5734c8c` (in newest-to-oldest order) and restores
the no-op fallback `UserStrategy` adapter with all four hooks returning
`None` unconditionally. It also deletes the candidate-specific unit and
integration tests and restores the pre-experiment README. The active
`Output/ATT_By_Statistics_Interval.csv` was overwritten from the verified
fallback snapshot
`.challenge/round0/results/fallback_reproduction_current_checkout_run1/ATT_By_Statistics_Interval.csv`
with SHA `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`
and re-scored to confirm `18.673577819840556` exactly.

The result recorded above applies to the final approved `f04daad` candidate
only; conclusions are evidence-limited to this single seed and scenario.

## Evidence paths (ignored)

- Candidate ATT snapshot: `.challenge/round0/results/teu_delay_smith_priority_v1_2026/ATT_By_Statistics_Interval.csv` (SHA `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`)
- Aggregate metrics JSON: `experiments/results/teu_delay_smith_priority_v1_2026.json`
- Active Output ATT after restore: `.challenge/round0/source/Output/ATT_By_Statistics_Interval.csv` (SHA `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`)

Both ignored locations are untracked and contain no organizer source.

## Resume point

- The fallback (`18.673577819840556`, SHA `10234375...`) is the authoritative
  comparable reference.
- The coordinated owner-authorized history purge and force-push that
  removed the restricted Round 0 ZIP and the restricted blob
  (`3f5be8fecbcc829753785c4da55c69c89c44629e`) from reachable local
  history has been completed. **Residual warning:** old local clones,
  pre-purge forks, and any GitHub dangling, cache, or fork objects that
  captured the prior history may still hold those bytes.
