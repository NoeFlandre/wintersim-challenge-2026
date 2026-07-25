# Round 0 recovery-aware origin hold versus disruption detour v1

**Status:** PHASE_A_REVIEW2 (corrections committed; awaiting second review gate
before any sync, smoke, full run, push, merge, PR, submission, or history
rewrite).

## Fixed hypothesis

The organizer fallback for `assign_associated_bookings` immediately assigns a
shipment to a complete disruption-safe booking path whenever one exists, even
when that safe path is sufficiently long or transfer-heavy that simply holding
the shipment at its origin until the relevant disruption recovers, and then
allowing the normal distance-shortest path, would complete strictly earlier.

This candidate implements a deterministic, model-derived decision that returns
`False` only when waiting for recovery is predicted to complete strictly
earlier than taking the fallback's currently available safe detour. Returning
`False` uses the existing organizer retry lifecycle (`False` means "no booking
can currently be assigned (may cause retry/wait)"); no new scheduler, route,
leg, vessel, booking, or event is created.

## Exact one-hook scope

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` is
changed. The other three hooks continue to return `None` unconditionally:

- `select_vessel_for_berth`
- `create_alternative_service_routes`
- `adjust_bookings_before_cargo_handling`

The candidate never creates bookings, routes, legs, vessels, or events. Its
only non-`None` result is `False`. `True` is never returned.

## Decision policy

`assign_associated_bookings` returns exactly `False` only when every
condition below succeeds. Any single failure returns exactly `None` without
mutation.

1. At least one valid disruption plan is active:
   `start <= now < end`, where
   `start = datetime.min + timedelta(days=start_offset_days)` and
   `end   = start + timedelta(days=duration_days)`.
2. A complete nominal distance-shortest booking path exists from the
   shipment's demand origin to its destination using only original service
   routes (those whose `source_service_route is None`).
3. That nominal path intersects at least one currently active disruption:
   - a closed-berth target port appears as a departure, intermediate, or
     arrival port on the path, or
   - a targeted congested leg appears in the path.
4. A complete disruption-safe path currently exists using the same
   availability and filtering semantics as the organizer fallback:
   - original routes are eligible without further restriction,
   - an alternative route is eligible only when its disruption key matches
     the current disruption key **and** it has at least one deployed vessel,
   - closed ports are excluded as arrival or intermediate ports of an
     edge (the departure port is not independently filtered),
   - congested legs are excluded as any segment of a candidate edge.
5. Both paths have valid deterministic expected-duration estimates:
   - every leg has a finite positive sailing distance,
   - every relevant route has at least one positive sailing speed,
   - the cycle distance of every relevant route is finite and positive.

The participant mirror's safe-path signature must match the organizer's
actual safe-path signature for every distinct real demand and every
inspected timestamp. This is enforced by the ignored-source integration
test `test_recovery_hold_fallback_conformance.py`.

### Recovery time

The recovery time is the latest end time among active disruption plans that
**actually intersect** the nominal path:

- For a closed-berth plan, intersection means the target port appears as any
  departure, intermediate, or arrival port of a booking edge in the nominal
  path.
- For a congested-leg plan, intersection means the target leg appears in the
  segment set of any booking edge in the nominal path.

Plans that carry both valid effects contribute both; a plan that targets
the same leg as another plan collapses to a single key entry. The
disruption key is the organizer's ordered-set representation:
`(tuple(sorted(avoid_port_names)), tuple(sorted(congested_leg_keys)))`.

Irrelevant plans (those that are active but do not touch the nominal path) do
not extend the recovery time.

### Duration estimation per booking edge

For each selected booking edge (a contiguous slice of one cyclic service
route), the candidate computes an expected duration without mutation:

- Let `d` be the cumulative sailing distance of the edge.
- Let `V` be the set of "eligible" vessels for the edge's route:
  the route's currently deployed vessels; if the route has none deployed,
  vessels on the route's segments are also considered, but only vessels
  whose `assigned_service_route is route` qualify.
- Let `S = [s_1, s_2, ..., s_k]` be the set of positive sailing speeds of
  vessels in `V`. If `S` is empty or no positive speed exists, the candidate
  delegates with `None`.
- Edge sailing hours: `edge_sailing_hours = d / mean(S)`, where
  `mean(S) = sum(S) / len(S)`.
- Let `cycle_distance` be the sum of `leg.sailing_distance` over the route's
  segments. If `cycle_distance` is not finite or not positive, the candidate
  delegates with `None`.
- Per-edge expected boarding wait: `0.5 * headway_hours`, where
  `headway_hours = 1 / sum(s / cycle_distance for s in S)`. If
  `sum(s / cycle_distance for s in S)` is zero or non-finite, the candidate
  delegates with `None`.
- `edge_expected_hours = edge_sailing_hours + 0.5 * headway_hours`.
- The path duration is the sum of `edge_expected_hours` over every edge.

No cargo-handling or berth constant is added. Transfers naturally add another
half-headway because every edge contributes one expected boarding wait.

### Final comparison

Define:

- `wait_then_nominal = hours_until_relevant_recovery + nominal_expected_hours`
- `safe_now = safe_expected_hours`

where `hours_until_relevant_recovery` is the timedelta from `now` to the
recovery time, expressed in hours.

Return exactly `False` only when:

  `wait_then_nominal < safe_now`

Use strict comparison with no tuned margin. Equality delegates with `None`.
All other cases (including invalid or missing inputs) return exactly `None`.

## Path construction requirements

- Enumerate proper contiguous slices of cyclic service routes; never create a
  whole-cycle origin-to-same-origin edge.
- Preserve `context.service_routes` order, `context.ports` order, and
  segment ordering within each route (sorted by `sequence_index`).
- Use deterministic Dijkstra behavior with these rules:
  - distances start at infinity except the origin (0.0);
  - the unvisited frontier is iterated in `context.ports` order, selecting
    the unvisited port with the strictly minimum distance;
  - ties on equal distance are resolved by the earlier `context.ports`
    index, **not** by arbitrary set/hash iteration order;
  - predecessor is updated only on a **strictly lower** distance;
  - use object identity where the organizer uses object identity (e.g. legs
    are compared with `is`, ports with `is`).
- Fully validate needed numeric values as finite and positive.
- Catch only narrow expected exceptions (`AttributeError`, `TypeError`,
  `ValueError`, `ZeroDivisionError`, `FloatingPointError`,
  `OverflowError`); any other exception type propagates and the candidate
  delegates with `None`.
- Invalid, missing, or ambiguous data causes `None`, never a guessed
  decision.
- No mutation is permitted on either the `False` or `None` path; the
  reachable state of `context`, `now`, and `shipment` is preserved.

## Invariants and forbidden behavior

- No port names, route IDs, seed-specific maps, scenario constants, dates,
  or tuned thresholds.
- No filesystem, environment, network, subprocess, current-working-directory,
  wall-clock, or unseeded randomness.
- No mutable module-level or cross-run cache. The only module-level
  assignment is the immutable `_NARROW_EXCEPTIONS` tuple; AST inspection
  rejects any other module-level assignment.
- No parameter tuning; no broad `except Exception` or `except BaseException`.
- No new vessel, leg, route, segment, booking, port, or event is created.
- No mutation of any organizer state (vessels, routes, segments, legs,
  ports, bookings, shipments, disruption_plans).
- Only the participant-owned `response_strategies` files are used.
- Standard-library imports only (`datetime`, `math`, `typing.Any`). The
  participant strategy does **not** import organizer modules
  (`default_strategy`, `simulation_model`, `maritime_data_context`).
- Exact public method signatures preserved.

## Candidate identity (committed)

- Branch: `codex/round0-recovery-hold-vs-detour-v1`
- Base commit: `a78f9a8` (`docs: add controlled WSC experiment skill`)
- This experiment contract commit: `c9acfa3`
- RED-test commit: `2caaeea`
- Implementation commit: `a83d6c7`
- Coverage commit: `efeac31`
- Reformat commit: `cda389c`
- Review-correction commits (this pass):
  - RED correction tests: `e692b9e`
  - Implementation/cleanup: pending atomic commit to be added in this pass.

## Review-correction history (this pass)

A second review pass after the first Phase A stop-for-review recorded six
corrections that were applied with TDD discipline:

1. The packaged README was updated to describe the recovery-aware
   origin-hold candidate rather than the no-op fallback.
2. Eligible-vessel filtering now requires
   `vessel.assigned_service_route is route` for every included vessel. The
   previous implementation accepted a foreign vessel on a route segment.
3. Disruption-key collection now evaluates `close_berth` and
   `multiplier > 1` independently; a plan carrying both effects contributes
   both. Duplicate plans targeting the same leg collapse to a single key
   entry, matching the organizer's ordered-set semantics.
4. A new ignored-source integration test creates a fresh context for every
   inspected timestamp, mirrors runtime order, and compares the candidate
   safe-path signature against the actual fallback safe-path signature for
   every distinct real demand at active start+1s, midpoint, and end-1s. Zero
   mismatches are required. The participant strategy does not import the
   organizer's private helpers.
5. The two structurally identical booking-edge classes were consolidated
   into a single `_BookingEdge` class.
6. Weak tests were replaced with stronger assertions:
   - `_plan_active_window` is tested directly at exact start, start+1s,
     end-1s, and exact end.
   - The equal-distance tie-break test invokes the pathfinder directly
     and asserts the exact chosen edge under the documented port-order
     tie-break.
   - The tautological SHA-256 test was deleted.
   - The weak no-forbidden-global-state reload test was replaced with an
     AST-based assertion rejecting any module-level mutable assignment.
   - Line-coverage-only tests were consolidated while maintaining ≥90%
     coverage through meaningful contract and boundary tests.

## Fixed full-run configuration (Phase B; not run in Phase A)

- Scenario: `create_with_disruption`
- Seed: `2026`
- Warm-up: `140 days`
- Measured duration: `360 days`
- Statistics interval: `5 days`
- Required numbered periods: `72`
- Command: `uv run wsc2026 run --round round0 --full`

## Pinned comparison and acceptance

Current-checkout fallback (to be freshly verified but not silently changed):

- Cumulative Resilience Loss: `18.673577819840556`
- ATT SHA-256:
  `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`
- Mean ATT across numbered period rows: about `20.336944444444445` days
- Required periods: `72`

Historical secondary evidence only:

- Cumulative Resilience Loss: `18.276620672293834`
- ATT SHA-256: `ed4f274f827959ce4261303996bbde035aa784f7b7d070b9bbdf6bea1c7cbb03`

**Acceptance rule:** retain the candidate only when its complete 72-period
Cumulative Resilience Loss is strictly lower than
`18.673577819840556 - 1e-9`. Equality is rejection. The historical value is
reported separately and does not control this checkout's accept/reject
decision.

## Planned ignored evidence paths (Phase B)

- Candidate ATT snapshot:
  `.challenge/round0/results/recovery_hold_vs_detour_v1_2026/ATT_By_Statistics_Interval.csv`
- Aggregate result JSON:
  `experiments/results/recovery_hold_vs_detour_v1_2026.json`

Both paths are gitignored and must remain untracked.

## One-candidate rule

Exactly one candidate is authorized for this experiment. Do not attempt a
second strategy regardless of outcome.

## Rejection and restoration procedure

If the run is equal, worse, incomplete, or invalid:

1. Preserve the candidate ATT and aggregate metrics under the ignored
   evidence paths above.
2. Update this document to `SUCCESS_REJECTED` with evidence-limited wording.
3. Commit the result documentation separately:
   `docs: record rejected recovery-hold-vs-detour result`.
4. Revert the candidate implementation and candidate-specific test commits
   with `git revert` in reverse order; do not manually reconstruct the no-op
   adapter.
5. Synchronize the restored no-op fallback adapter into the organizer tree.
6. Restore `.challenge/round0/source/Output/ATT_By_Statistics_Interval.csv`
   from a verified current-checkout fallback snapshot.
7. Verify the restored SHA is exactly
   `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`.
8. Verify its score is exactly `18.673577819840556`.
9. Rerun final lint, type, test, integration, packaging, safety, and
   cleanliness gates.
10. Leave the experiment branch clean with the no-op fallback active.

No second candidate, tuning pass, push, merge, PR, submission, or history
rewrite is authorized.

## Mandatory pre-run review gate

This document, the RED tests, the implementation, and the ignored-source
integration tests must be reviewed before Phase B begins. The Phase A stop
condition is enforced: no `wsc2026 sync`, no `wsc2026 smoke`, no
`wsc2026 run`, no organizer `main.py`, no partial or full simulation, no
performance experiment, no candidate comparison, and no submission archive
may be produced before explicit approval.
