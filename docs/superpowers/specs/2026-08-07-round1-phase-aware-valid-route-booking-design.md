# Round 1 phase-aware valid-route booking design

## Context

Round 1's retained no-op adapter scores `20.436668751255972` on the fixed
`create_with_disruption` scenario. Five candidates have been rejected. The
previous disruption-weighted booking candidate was 32.24% worse because it
allowed active congested legs and estimated sailing time without service phase.
The older transfer-aware candidate likewise failed after using a static weekly
penalty. The organizer fallback currently chooses the shortest nominal-distance
path among valid routes, but it does not estimate when the next vessel on each
route can actually serve the shipment.

## Hypothesis

During active disruptions, among paths that obey the fallback's closed-port and
congested-leg exclusions, the next service opportunity can dominate a small
sailing-distance difference. Choosing a path by estimated next-service wait plus
nominal sailing time will reduce TEU-weighted transport time without exposing
shipments to a disrupted leg.

## Candidate boundary

Only `UserStrategy.assign_associated_bookings` is changed. It is active only
when at least one valid disruption plan is active. Inactive periods return
`None` and delegate unchanged. The other three hooks remain unconditional
`None`.

The candidate must:

1. Mirror the fallback's active closed-port and congested-leg filtering and
   route-availability rule.
2. Enumerate complete contiguous booking edges in deterministic context order.
3. Estimate each edge using its route's deployed vessel phase, the route's
   cyclic segment order, the fixed seven-day headway for an initial release,
   and nominal distance/speed sailing time.
4. Use deterministic Dijkstra tie-breaking; equal costs retain context order.
5. Build and validate a complete path before mutation, then install it with
   rollback if any mutation fails.
6. Return `None` on malformed/missing runtime state, no active disruption, or
   no valid path. It must never mutate context, routes, vessels, or the
   shipment on a delegated path.

The implementation is standard-library-only, self-contained in the submitted
`response_strategies` package, deterministic, and free of filesystem,
environment, network, subprocess, wall-clock, randomness, organizer imports at
module import, and mutable module-level state.

## Alternatives considered

- Another berth-ranking policy has low expected upside because three distinct
  berth policies produced byte-identical Round 1 output.
- A broader in-transit rebooking gate is high risk because suppressing future
  rebooking already degraded the score by 14.44%.
- The selected policy addresses the documented phase failure while retaining
  all fallback disruption safety filters.

## Validation and acceptance

Use strict RED→GREEN unit tests, a real Round 1 integration contract, all
quality/package/safety gates, and exactly one full run with:

```text
PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full
```

Configuration is seed `2026`, 140 warm-up days, 360 measured days, five-day
statistics, and 72 periods. Accept only:

```text
candidate_loss < 20.436668751255972 - 1e-9
```

Equality, worsening, invalid output, crash, incomplete run, or failed gate is
rejection. Preserve evidence before restoration, record the result, revert
candidate-only code/tests with Git, restore the no-op adapter and pinned ATT,
re-score exactly, and run all final gates. No second run, tuning, submission,
publication, push, merge, or history rewrite is part of this experiment.
