# Round 0 temporal lower-bound safe routing v1

**Status:** SUCCESS_REJECTED

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

| Measure | Value |
| --- | --- |
| Candidate Cumulative Resilience Loss | `22.732416871465396` |
| Candidate ATT SHA-256 | `e6da21ae5bd1f4e24d3c26e8b9920d436b59bb058e2f68aff092ed4a59476c92` |
| Baseline score threshold (current-checkout fallback) | `18.673577819840556` |
| Delta vs baseline threshold | `+4.05883905162484` (much worse, not lower by more than `1e-9`) |
| Relative change vs baseline | `+21.735733%` |
| Mean ATT across numbered period rows (days) | `20.584444444444454` |
| Period count | `72` |
| Runtime | `21:17` |
| Beats historical `18.276620672293834`? | No |
| Beats current-checkout `18.673577819840556`? | No (much worse) |

The candidate produced a different ATT output than the current-checkout
fallback (different SHA, different per-period values). The candidate score
`22.732416871465396` is well above the current-checkout acceptance
threshold of `18.673577819840556` (delta `+4.058839`, `+21.74%` worse), so
the candidate is rejected on the acceptance rule alone.

The experiment did not instrument per-cargo flow or per-route usage
sufficiently to establish whether the degradation came from extra
overrides that produced lower-quality paths, from trips that the candidate
attempted to override but the organizer fallback would have routed
differently, or from the assignment-timing difference between the
candidate's lower-bound path and the organizer's disruption-aware
shortest path. All those categories remain possible explanations; the
experiment only proves that the policy as a whole, with the documented
encounter-time forecast and atomic-mutation contract, performs worse than
the organizer fallback on this Round 0 scenario.

## Decision

Reject. The candidate score `22.732416871465396` is above the
current-checkout acceptance threshold of `18.673577819840556` by more than
`1e-9`. The underlying cause of the degradation was not established by
this experiment.

## Rejection/restoration procedure (executed)

1. This document was updated to `SUCCESS_REJECTED` (this file).
2. All metrics, hashes, and runtime recorded above.
3. Result documentation committed separately via
   `docs: record rejected temporal safe-routing result`.
4. Implementation commit (`3160905`) reverted via `git revert`; the
   no-op adapter is restored automatically.
5. The reverted no-op adapter synchronized into the organizer tree.
6. `.challenge/round0/source/Output/ATT_By_Statistics_Interval.csv` was
   restored from a verified current-checkout fallback snapshot (the
   bytes were preserved in
   `.challenge/round0/results/fallback_reproduction_current_checkout_run1/`
   and `_run2/`).
7. Verified restored SHA:
   `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`.
8. Verified restored score: `18.673577819840556`.
9. Final gates rerun; deterministic packaging re-verified.
10. Branch left clean with the no-op fallback active.

## Final implementation commit (rejected)

- Implementation commit SHA: `3160905`
- Revert commit SHA: `33cc936`

## Final state confirmation

- Candidate score: `22.732416871465396`.
- Candidate ATT SHA-256: `e6da21ae5bd1f4e24d3c26e8b9920d436b59bb058e2f68aff092ed4a59476c92`.
- The candidate ATT output is **different** from the current-checkout
  locally reproduced fallback (different SHA, different per-period
  values), confirming the policy had a measurable scoring effect.
- Rejection reason: the candidate score `22.732416871465396` is well
  above the current-checkout acceptance threshold of
  `18.673577819840556` (delta `+4.058839`).
- Only one candidate was attempted for this experiment; no second
  strategy was tried.
- The active strategy is restored to the no-op organizer-fallback
  adapter; the implementation commit was reverted via `git revert`.

## Private (ignored) evidence

- Candidate ATT snapshot:
  `.challenge/round0/results/temporal_lower_bound_safe_routing_v1_2026/ATT_By_Statistics_Interval.csv`
  — SHA `e6da21ae5bd1f4e24d3c26e8b9920d436b59bb058e2f68aff092ed4a59476c92`
- Candidate full run log: `/tmp/wsc2026_candidate_run.log` (private
  shell-side log; not committed)
- Aggregate result:
  `experiments/results/temporal_lower_bound_safe_routing_v1_2026.json`

All three locations remain ignored and untracked.

## Deviations found in the rejected implementation commit (`3160905`)

Post-run review of the rejected implementation found three deviations from
the abstract policy as described above. The measured score, hashes and
runtime recorded above apply to that exact rejected implementation, which
is the only thing that ran on the simulation framework.

1. **Mutable module-level `_Booking` cache.** The rejected module held a
   module-level `_Booking` reference and a `_get_booking_class()` helper
   that memoized the imported organizer `Booking` class for the lifetime
   of the process. This is **mutable cross-run global state**, which the
   submission contract forbids ("no mutable cross-run global state in
   submission code"). The override path would still resolve correctly
   per-process; however the cache violates the documented contract and
   must not be carried into a future candidate.

2. **Set-based Dijkstra `unvisited` collection.** The shortest-path helper
   used a `set` for the unvisited frontier and selected the next node with
   `min(unvisited, key=distances.get)`. Ties on equal distance therefore
   resolved by **arbitrary `set` iteration order**, not by the documented
   `context.ports` order. The intended deterministic tie-break by
   `context.ports` order was not enforced in the implementation that ran.
   The unit tests use very small synthetic networks where ties do not
   occur, so this defect was not caught by the test suite. The score and
   per-period numbers above reflect this non-deterministic tie resolution.

3. **No transactional rollback on installation failure.** The
   `_install_path` helper removes old bookings, replaces
   `shipment.associated_bookings`, and appends new bookings to service
   routes in place. If a step fails partway through (for example a
   constructor that raises after the old bookings have already been
   detached), the reachable state can be left partially mutated. The
   abstract "Atomic-mutation rule on the override path" above requires
   that no mutation persist on failure; the implementation that ran did
   not implement that rollback. In practice the in-memory paths used
   here raise predictably or not at all, so this latent defect did not
   affect the measured score; it is recorded here so a future candidate
   is not assumed to satisfy the atomicity contract based on this
   experiment.

**Scope of validation.** The score
`22.732416871465396` and the SHA
`e6da21ae5bd1f4e24d3c26e8b9920d436b59bb058e2f68aff092ed4a59476c92` are
evidence that *this exact implementation*, including the three deviations
above, scores worse than the current-checkout fallback. They do **not**
cleanly validate every detail of the abstract policy described earlier in
this document. Specifically: the deterministic tie-break claim, the
"mutable cross-run global state" rule, and the atomic rollback guarantee
were not actually exercised by the experiment.

## Resume point

- The current-checkout locally reproduced fallback (`18.673577819840556`,
  SHA `10234375...`) is the authoritative comparable reference.
- Treat `18.276620672293834` and `ed4f274f...` as historical evidence only.
- The coordinated owner-authorized history purge and force-push that
  removed the restricted Round 0 ZIP and the restricted blob
  (`3f5be8fecbcc829753785c4da55c69c89c44629e`) from reachable local
  history has been completed. `git rev-list --objects --all` and
  `git ls-files` contain neither the archive path nor the restricted
  blob. **Residual warning:** old local clones, pre-purge forks, and any
  GitHub-side dangling, cache, or fork objects that captured the prior
  history may still hold those bytes. Treat any pre-purge clone as
  not-public-safe until its own reachable objects are re-verified.
