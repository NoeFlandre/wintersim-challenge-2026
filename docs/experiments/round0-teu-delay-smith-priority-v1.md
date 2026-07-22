# Round 0 TEU-delay-per-berth-hour priority v1

**Status:** IMPLEMENTED_AWAITING_REVIEW

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
                  = (affected_teu * qc_count * 45) / (135 * qc_count + handled_teu)

For exact integer comparison, the constant `45` is dropped:

  numerator   = affected_teu * qc_count
  denominator = 135 * qc_count + handled_teu

Vessel A outranks vessel B iff:

  A.numerator * B.denominator > B.numerator * A.denominator

Exact ties preserve the input `waiting_vessels` order. There is no
zero-service special case: a vessel with `handled_teu == 0` still
consumes three hours of berth time and is compared via the same ratio
path.

### Worked example

  Vessel A: carried=0, handled=0, qc=1
            num=0,     den=135
  Vessel B: carried=10, handled=10, qc=1
            num=10,    den=145
  A.num * B.den = 0 * 145 = 0
  B.num * A.den = 10 * 135 = 1350
  B wins.

## Why age is intentionally excluded

Cargo age does not appear in the formula. The metric weights ATT per TEU,
so the marginal one-hour cost of delaying one TEU is constant. Multiplying
by age over-counts old cargo and under-counts fresh cargo whose delay is
equally expensive in the next hour. The earlier age-weighted candidate
(`round0-first-result`) scored worse than the fallback by ~22%; this
candidate deliberately avoids that mistake.

## Metric definitions

  carried_teu       = sum(s.teu_size for s in vessel.carried_shipments)
  discharge_teu     = carried_teu - occupied_after_discharge
  projected_load_teu = TEU selected by the read-only loading prediction
  handled_teu       = discharge_teu + projected_load_teu
  affected_teu      = carried_teu + projected_load_teu
  qc_count          = max(1, int(vessel.vessel_class.loa / 55))

`occupied_after_discharge` mirrors `VesselBeingServed._calc_occupied_teu`:

  for each carried shipment:
      booking = shipment.get_current_booking()
      if booking.service_route != assigned_route: continue
      if current_seg_index is not None and
         booking.arrival_segment_index == current_seg_index: continue
      total += teu_size

When `current_segment is None`, the discharge exclusion is skipped but the
route-exclusion still applies.

## Predicted-load calculation

`port.shipments_in_storage` is iterated in its existing deterministic order.
A stored shipment is an eligible loading candidate iff:

  * `shipment.carrying_vessel is None`;
  * `shipment.get_current_booking()` is a valid booking;
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

`_read_positive_teu` raises a narrow `(TypeError, ValueError)` when
`shipment.teu_size` is missing, None, non-numeric, non-finite, zero, or
negative. `_validate_vessel_inputs` raises a narrow exception when
`vessel.vessel_class`, `vessel_class.loa`, `vessel_class.teu_capacity`, or
`vessel.assigned_service_route` is missing, non-finite, or nonpositive.
The public selector catches only `(AttributeError, TypeError, ValueError,
OverflowError)` and delegates with `None`. No broad `except Exception` or
`except BaseException` is used anywhere in submission code.

## Current comparable fallback (locally reproduced)

- Score: `18.673577819840556`
- ATT SHA-256: `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`
- 72 periods
- Mean ATT across numbered period rows: about 20.336944444444445 days

## Historical secondary reference

- Score: `18.276620672293834`
- ATT SHA-256: `ed4f274f827959ce4261303996bbde035aa784f7b7d070b9bbdf6bea1c7cbb03`

Report separately whether the candidate also beats this historical value. It
does not affect the accept/reject decision in this checkout.

## Future acceptance rule (not yet evaluated)

After a complete 72-period run with seed `2026`, warm-up `140`, measured
`360`, interval `5`, scenario `create_with_disruption`, retain the candidate
only if its Cumulative Resilience Loss is strictly lower than
`18.673577819840556` by more than `1e-9`. A smoke run, partial run, or mean
ATT alone can never satisfy acceptance.

## Reviewer gate (explicit)

**No performance simulation, scoring, optimization, parameter sweep, or
second candidate may be run before reviewer approval.** The repository
must remain at the implemented candidate, awaiting review.

Only the following gates are permitted prior to review:

  * `uv lock --check`
  * `uv sync --locked --group dev --group simulation`
  * `uv run ruff format --check .`
  * `uv run ruff check .`
  * `uv run mypy src/wsc2026_tools submission`
  * Focused new unit tests
  * Complete non-integration test suite with coverage >= 90%
  * Focused new integration/contract tests against real organizer domain
    objects (without running the simulation horizon)
  * `uv run wsc2026 sync --round round0`
  * `cmp` of participant and organizer strategy copies
  * `uv run wsc2026 smoke --round round0` (import/wiring gate only)
  * Deterministic ValidationTeam packaging twice
  * Archive member inspection
  * Git/restricted-material integrity checks

Smoke is permitted only as an import/wiring gate. It is not evidence of
performance and must not be scored or used for acceptance.

## No-second-candidate rule

Do not attempt another hypothesis regardless of outcome. This is the only
authorized candidate for this experiment.

## Full result

To be filled in only after reviewer approval.

| Measure | Value |
| --- | --- |
| Candidate Cumulative Resilience Loss | TBD |
| Candidate ATT SHA-256 | TBD |
| Baseline score threshold (current-checkout fallback) | `18.673577819840556` |
| Delta vs baseline threshold | TBD |
| Mean ATT across numbered period rows (days) | TBD |
| Period count | `72` |
| Runtime | TBD |
| Beats historical `18.276620672293834`? | TBD |
| Beats current-checkout `18.673577819840556`? | TBD |

## Resume point

- The current-checkout locally reproduced fallback (`18.673577819840556`,
  SHA `10234375...`) is the authoritative comparable reference.
- Treat `18.276620672293834` and `ed4f274f...` as historical evidence only.
- The coordinated owner-authorized history purge and force-push that
  removed the restricted Round 0 ZIP and the restricted blob
  (`3f5be8fecbcc829753785c4da55c69c89c44629e`) from reachable local
  history has been completed. **Residual warning:** old local clones,
  pre-purge forks, and any GitHub dangling, cache, or fork objects that
  captured the prior history may still hold those bytes.
