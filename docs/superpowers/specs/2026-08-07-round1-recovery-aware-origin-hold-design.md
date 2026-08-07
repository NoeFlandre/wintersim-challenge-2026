# Round 1 recovery-aware origin hold design

## Status

This is one isolated Round 1 experiment from the restored no-op fallback at
`main` (`1f5d1fe`). No full simulation is authorized until RED tests, the
minimal implementation, real-context checks, and every pre-run gate are green.

## Hypothesis

During an active disruption, the organizer fallback immediately assigns a
shipment to the shortest currently safe detour. For a nominal route whose
affected resource will recover soon, that detour can add a long sailing leg or
an extra transfer. If a deterministic estimate says that waiting for the
affected nominal route to recover and then taking that route is faster than
the safe detour, keeping the shipment in the existing origin retry lifecycle
should reduce transport time.

This experiment tests that decision without changing any route, vessel,
booking, or event. It returns `False` only for the strict model-derived
comparison below; all other calls return `None` and delegate unchanged to the
organizer fallback.

## Exact participant policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` is
non-trivial. The policy:

1. Parse valid active disruption plans using the runtime's half-open window
   `datetime.min + start_offset <= now < datetime.min + start_offset + duration`.
2. Build the nominal shortest booking path over original service routes only,
   preserving context route/segment/port order and excluding whole-cycle
   origin-to-origin edges.
3. Require that the nominal path intersects at least one active closed berth
   port or congested physical leg. Otherwise delegate.
4. Record the latest recovery time among active plans that actually intersect
   that nominal path.
5. Build the same currently-safe booking graph used by the organizer: original
   routes remain eligible; alternative routes are eligible only when their
   disruption key equals the active key and they have deployed vessels; closed
   ports are excluded as intermediate/arrival ports; active congested legs are
   excluded from every edge.
6. Require a complete safe path.
7. Estimate each path from its route slice distance, the mean positive speed
   of that route's currently eligible vessels, and one half of the route
   headway (`cycle_distance / sum(eligible_speeds)`). The estimate is a
   transparent expected sailing-plus-boarding time, not a tuned threshold.
8. Return exactly `False` only when
   `hours_until_relevant_recovery + nominal_expected_hours < safe_expected_hours`.
   Equality delegates. `False` uses the organizer's existing retry scheduler;
   the candidate never creates a retry, booking, route, vessel, or event.

Malformed, missing, non-finite, or non-positive values fail closed to `None`.
The other three hooks remain unconditional `None` delegates.

## Invariants and challenge compliance

- The hook performs no mutation on either return path.
- No organizer strategy import, filesystem, environment, network,
  subprocess, wall-clock, randomness, port-name table, route-ID table, seed
  table, or mutable module-level state.
- The participant surface remains standard-library-only and self-contained.
- Dijkstra ties use `context.ports` order and strict-less predecessor updates.
- No threshold or acceptance rule changes after the run starts.

## Fixed run contract

- round/scenario: `round1` / `create_with_disruption`
- seed: `2026`; `PYTHONHASHSEED=0`
- warm-up: `140` days
- measured horizon: `360` days
- ATT interval: `5` days; required periods: `72`
- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- strict acceptance: `candidate_loss < 20.436668751255972 - 1e-9`
- ignored candidate evidence:
  `.challenge/round1/results/recovery_aware_origin_hold_v1_20260807/`
- ignored aggregate:
  `experiments/results/round1_recovery_aware_origin_hold_v1_20260807.json`

Exactly one candidate full run is authorized. A crash, incomplete output,
invalid period count, equality, worsening score, or failed final gate is
rejection. Before any restore or second command can overwrite `Output/`, the
fresh ATT and raw log must be copied and hashed. On rejection, commit the
result record, revert candidate code/tests in reverse order, synchronize the
no-op adapter, restore the pinned fallback ATT bytes, re-score exactly, rerun
all final gates, remove the temporary worktree, and publish only the public
audit/docs commits to `main`. No second candidate, tuning, submission, or
history rewrite is permitted.
