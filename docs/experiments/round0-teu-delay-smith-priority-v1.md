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
  predicted berth handling time

Choose the vessel with the greatest TEU-delay relieved per berth-service hour.

## Exact Smith-ratio formula

For each vessel in `waiting_vessels`, predict the next berth service:

  carried_teu       = sum(s.teu_size for s in vessel.carried_shipments)
  discharge_teu     = sum(s.teu_size for s in
                          vessel.get_discharging_shipments_at_current_segment())
  projected_load_teu = TEU selected by the read-only loading prediction
  affected_teu      = carried_teu + projected_load_teu
  handled_teu       = discharge_teu + projected_load_teu
  qc_count          = max(1, int(vessel.vessel_class.loa / 55))
  service_hours     = handled_teu / (qc_count * 45.0)

The Smith ratio ("TEU-delay relieved per berth-service hour"):

  affected_teu
  ---------------  =  (affected_teu * qc_count * 45) / handled_teu
  service_hours

Since `45` is constant across all candidates, the constant can be dropped and
the ranking is preserved by comparing:

  priority_ratio = (affected_teu * qc_count) / handled_teu

When `handled_teu == 0` the service consumes zero simulated berth time, so
the vessel must rank ahead of every positive-service-time vessel. Among
zero-service vessels, ordering preserves `waiting_vessels` position.

Vessel A outranks vessel B iff one of:

  * A.handled_teu == 0 and B.handled_teu > 0;
  * both have positive handled_teu AND
    (A.affected_teu * A.qc_count) * B.handled_teu
    > (B.affected_teu * B.qc_count) * A.handled_teu
    (exact cross multiplication, no floating-point comparison);
  * both are zero-service AND A appears earlier in `waiting_vessels`.

## Why age is intentionally excluded

Cargo age does not appear in the formula. The metric weights ATT per TEU,
so the marginal one-hour cost of delaying one TEU is constant. Multiplying
by age over-counts old cargo and under-counts fresh cargo whose delay is
equally expensive in the next hour. The earlier age-weighted candidate
(`round0-first-result`) scored worse than the fallback by ~22%; this
candidate deliberately avoids that mistake.

## Predicted-load calculation

`port.shipments_in_storage` is iterated in its existing deterministic order.
A stored shipment is an eligible loading candidate iff:

  * `shipment.carrying_vessel is None`;
  * `shipment.get_current_booking()` is a valid booking;
  * `booking.service_route is vessel.assigned_service_route`;
  * `booking.departure_segment_index == next_segment.sequence_index`.

Occupied capacity after expected discharge is computed by iterating
`vessel.carried_shipments`, including a shipment only if its current booking
belongs to `vessel.assigned_service_route`, and excluding shipments whose
booking arrival-segment-index equals the current-segment sequence-index
(they will discharge before departure). When `vessel.current_segment is
None`, all currently carried cargo counts as occupied (matches organizer
behavior in `VesselBeingServed.attempt_start`).

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
