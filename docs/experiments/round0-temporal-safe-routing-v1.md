# Round 0 temporal lower-bound safe routing v1

**Status:** PENDING_RUN

## Hypothesis

The organizer's initial-booking fallback removes every active closed port and
congested leg from the booking graph. This is conservative: it applies based
on assignment time, not the earliest time the shipment could reach that
resource.

A shipment generated during a disruption may be routed from a distant origin.
Even with:

- zero wait for a vessel,
- zero berth handling time,
- zero transshipment delay, and
- the vessel sailing 5% faster than nominal,

it may still be impossible for the shipment to encounter the disrupted
resource until after recovery. Holding or detouring such a shipment is
unnecessary and may contribute to the long loss tail after the Round 0
disruption.

Round 0 read-only topology analysis found:

- About 16.77% of annual demand has a nominal shortest path affected by the
  active Kaohsiung disruptions.
- Only about 2.05% has a fully disruption-avoiding alternative, generally
  involving large detours.
- Depending on the active day, roughly 1.77%–3.79% of annual demand has an
  affected nominal path whose earliest physically possible encounter is
  already after recovery.

## Policy

Override `assign_associated_bookings` only when **all** of these are true:

1. At least one disruption plan is currently active.
2. The shipment's nominal distance-shortest path over original service routes
   touches at least one currently active closed port or congested leg.
3. For every active disrupted resource touched by that nominal path, the
   earliest physically possible encounter is at or after that plan's recovery
   time.
4. A complete valid nominal booking chain exists.

If all conditions hold:

- Atomically assign that nominal path.
- Return exactly `True`.

Otherwise:

- Return exactly `None` without mutation so the organizer fallback makes the
  decision.

The other three hooks remain unconditional `None` delegates:

- `select_vessel_for_berth`
- `create_alternative_service_routes`
- `adjust_bookings_before_cargo_handling`

This is the only authorized strategy change. The candidate must not return
`False` from any hook.

## Exact one-hook scope

Only `assign_associated_bookings(context, now, shipment)` is changed. All
other hooks continue to return `None` unconditionally.

## Lower-bound definition

Use simulation time only. An active plan is:

  `start <= now < end`

where:

  `start = datetime.datetime.min + timedelta(days=start_offset_days)`
  `end   = start + timedelta(days=duration_days)`

Recognition:

- **Closed port:** `plan.close_berth is true` and
  `plan.target_berth is not None`.
- **Congested leg:** `plan.multiplier > 1` and
  `plan.target_leg is not None`.

For duplicate closed-berth plans at one port, use the latest active recovery
time for that port.

The nominal distance-shortest path is built using **only original service
routes** (those whose `source_service_route is None`). Every proper
contiguous slice of each cyclic route is enumerated; a whole-cycle
origin-to-same-origin edge is **never** created. Edge cost is the cumulative
sailing distance. The deterministic Dijkstra order is:

- `context.ports` order controls equal-distance resolution.
- Route and segment iteration order is preserved.
- Predecessor is updated only on a **strictly lower** distance.

The encounter-time forecast starts at elapsed zero:

- A closed origin port is encountered at elapsed zero.
- A congested leg is encountered immediately **before** sailing that leg.
- A closed arrival/intermediate/destination port is encountered **after**
  sailing into it.
- Transfer waits, berth waits, cargo handling, and all other delays are
  zero in this calculation. This intentionally makes the bound optimistic.
- For each booking edge, the fastest valid sailing speed among the original
  route's currently deployed vessels is used.
- That speed is multiplied by exactly 1.05 to account for the organizer's
  maximum 5% fast-sailing variation.
- Disruption multipliers are **ignored** in the lower bound; ignoring them
  makes arrival earlier and therefore keeps the proof conservative.
- If speed information is absent, invalid, or nonpositive, the candidate
  delegates with `None`.
- An encounter at exactly the recovery instant is safe because the active
  interval is end-exclusive.
- Override is performed only if every affected encounter is at or after its
  associated recovery time.
- If the nominal path touches no currently active target, `None` is
  returned to preserve fallback behavior exactly.

No lookahead, penalties, timetable prediction, demand-specific constants,
port names, route IDs, thresholds, caching, learning, or tuning are added.

## Active/inactive return behavior

- During an active disruption, with every condition met: return exactly
  `True` and atomically install the nominal booking chain.
- Otherwise: return exactly `None` (no mutation).

`False` is **not** a permitted return value for any hook.

## No-mutation rule on the delegation path

Every delegation path must leave the complete reachable state unchanged:

- `context` collections (legs, routes, segments, bookings, vessels, ports,
  shipment lists, demand lists, disruption_plans, ...).
- `shipment.associated_bookings`, `shipment.current_booking_index`,
  `shipment.carrying_vessel`, `shipment.completion_time`,
  `shipment.current_storage_port`.
- Booking sequence references, departure/arrival segment indices, service
  route `associated_bookings` lists.
- Segment `current_vessels` lists.
- Vessel assignment (`assigned_service_route`, `pending_assigned_service_route`,
  `current_segment`, `current_berth`, deployed-vessels membership).
- Any object reachable from `context`, `now`, or `shipment`.

## Atomic-mutation rule on the override path

When the override fires:

1. The complete path and every Booking object are **fully constructed**
   before mutating any shipment or route.
2. Old bookings are removed from their
   `service_route.associated_bookings` lists.
3. `shipment.associated_bookings` is replaced.
4. Each new booking is appended to its service route's
   `associated_bookings`.
5. `shipment.current_booking_index` is set to 1.
6. `True` is returned.

If any of those steps fails, no mutation must persist.

## Full-run configuration

- Scenario: `create_with_disruption` (measurement-relative disruption offsets)
- Seed: 2026
- Warm-up: 140 days
- Measured duration: 360 days
- Statistics interval: 5 days
- Period count: 72

## Starting commit

`cc0d3ec` on `codex/round0-in-transit-rebooking-suppression-v1` (predecessor
branch). The new branch is `codex/round0-temporal-safe-routing-v1`.

## Current comparable fallback (locally reproduced)

- Score: `18.673577819840556`
- ATT SHA-256: `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`
- 72 periods
- Mean ATT across numbered period rows: about 20.336944444444445 days

## Historical reference (secondary reporting only)

- Score: `18.276620672293834`
- ATT SHA-256: `ed4f274f827959ce4261303996bbde035aa784f7b7d070b9bbdf6bea1c7cbb03`

Report separately whether the candidate also beats this historical value. It
does not affect the accept/reject decision in this checkout.

## Acceptance rule

Retain the candidate only if the complete 72-period Cumulative Resilience
Loss is strictly lower than `18.673577819840556` by more than `1e-9`. A
smoke run, partial run, or mean ATT alone can never satisfy acceptance.

## Rejection/restoration procedure

If the candidate score is equal to or above `18.673577819840556`:

1. Update this document to `SUCCESS_REJECTED` with evidence-limited wording.
2. Record all metrics, hashes, runtime, and the rejection reason.
3. Commit the result documentation separately:
   `docs: record rejected temporal safe-routing result`
4. Revert the implementation commit with `git revert`; do not manually
   recreate the no-op adapter.
5. Synchronize the reverted no-op adapter into the organizer tree.
6. Restore
   `.challenge/round0/source/Output/ATT_By_Statistics_Interval.csv` from a
   verified current-checkout fallback snapshot.
7. Verify the restored SHA is exactly
   `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`.
8. Verify its score is exactly `18.673577819840556`.
9. Rerun final gates and deterministic packaging.
10. Leave the experiment branch clean with the no-op fallback active.

## No-second-candidate rule

Do not attempt another hypothesis regardless of outcome. This is the only
authorized candidate for this experiment.

## Full result

To be filled in after the candidate run.

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

## Decision

TBD.

## Private (ignored) evidence

To be filled in after the candidate run.

- Candidate ATT snapshot:
  `.challenge/round0/results/temporal_lower_bound_safe_routing_v1_2026/ATT_By_Statistics_Interval.csv`
- Aggregate result:
  `experiments/results/temporal_lower_bound_safe_routing_v1_2026.json`

Both locations remain ignored and untracked.

## Resume point

- The current-checkout locally reproduced fallback (`18.673577819840556`,
  SHA `10234375...`) is the authoritative comparable reference.
- Treat `18.276620672293834` and `ed4f274f...` as historical evidence only.
- Public release and merge remain blocked pending an owner-authorized history
  purge and coordinated force-push of the restricted Round 0 ZIP.
