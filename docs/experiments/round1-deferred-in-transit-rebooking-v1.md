# Round 1 deferred in-transit rebooking v1

**Status:** pre-run contract. No Round 1 candidate run has started.

## Hypothesis

The organizer fallback re-plans every carried shipment as soon as any later
booking contains an active disruption. That can discharge cargo and create an
extra transshipment while the vessel is still on an unaffected segment. The
candidate will defer only those **future-only** re-plans: it will let the
current booking continue until the vessel's current segment or current port is
directly affected. When the current segment is directly affected, it delegates
to the organizer fallback so the existing disruption avoidance remains intact.

This is a single, general policy hypothesis. It uses the actual disruption
objects and route/booking relationships supplied at runtime; it does not use
port names, route IDs, dates, seed-specific tables, or tuned numeric margins.
The earlier Round 0 experiment that suppressed all in-transit rebooking was
worse than fallback, so this experiment deliberately preserves fallback
behavior for direct impacts and narrows only premature decisions.

## Exact scope and return contract

Only `UserStrategy.adjust_bookings_before_cargo_handling` is overridden. The
other three hooks return `None` and delegate to the organizer fallback.

- `None` means “delegate”; the hook must not mutate anything on that path.
- `False` means “handled with no re-plan”; the hook must not mutate anything.
- An active disruption is relevant only when a carried shipment's unfinished
  current or later bookings contain an active closed port or congested leg.
- If a relevant shipment's current segment/current port is directly affected,
  return `None` and let the fallback perform its normal re-plan.
- If relevant impacts are future-only for every affected shipment on the
  vessel, return `False` and preserve all bookings and vessel state.
- Any missing, ambiguous, malformed, or non-finite runtime relationship
  delegates (`None`) rather than guessing.

The implementation must use standard-library-only imports, no I/O, no
environment or process access, no randomness, no mutable module state, and no
organizer imports. It must preserve object identity and deterministic context
order. It may read runtime objects but must not mutate them.

## TDD and evidence requirements

RED tests must cover inactive/no-impact delegation, future-only suppression,
direct-impact delegation, mixed-impact delegation, closed-port boundaries,
invalid-state fail-closed behavior, signature/static-method compatibility, and
state immutability. The RED commit must fail because the current no-op returns
`None` for the future-only case. The minimum implementation then makes all
focused tests GREEN, followed by the real Round 1 smoke/integration and full
preflight gates.

## Fixed run identity and controls

- scenario: `create_with_disruption`
- seed: `2026`
- warm-up: `140` days
- measured horizon: `360` days
- statistics interval: `5` days
- required period count: `72`
- process environment: `PYTHONHASHSEED=0` (used for both control and candidate)
- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`

The fresh no-op Round 1 control completed at Period 72 before this contract
was committed. Its exact reference is:

- cumulative resilience loss: `20.436668751255972`
- ATT SHA-256: `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- mean ATT: `20.451` days
- period count: `72`
- ignored snapshot: `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`
- ignored run log: `.challenge/round1/results/fallback_control_seed0_20260803/run.log`

An earlier unpinned control is retained separately as diagnostic evidence; it
has the same ATT bytes in this checkout. The historical Round 0 value is not
used as the Round 1 threshold.

## Acceptance rule and evidence paths

Accept only if the candidate's complete scorer result satisfies, without
rounding:

```text
candidate_cumulative_loss < 20.436668751255972 - 1e-9
```

The candidate ATT must contain exactly 72 numbered periods and be copied before
any restore to:

`.challenge/round1/results/deferred_in_transit_rebooking_v1_20260803/ATT_By_Statistics_Interval.csv`

The full log and JSON score belong in that same ignored result directory and
`experiments/results/round1_deferred_in_transit_rebooking_v1_20260803.json`.
Record SHA-256, byte size, mtime, mean ATT, full-precision score, per-period
comparison counts/delta, and the package hash/member list.

## Rejection and restoration

Equality, worsening, a crash, an incomplete output, a failed validation gate,
or a non-72-period CSV is rejection. Preserve raw ignored evidence first, then
record the result, revert the candidate implementation/tests in reverse order
with `git revert`, synchronize the no-op adapter to the private Round 1 source,
restore the pinned fallback ATT bytes, and re-score to exactly
`20.436668751255972`. Do not recreate the adapter manually and do not attempt
another candidate or tune any threshold.

## One-candidate and publication rules

Exactly one candidate full run is authorized after the pre-run review. No
second idea, parameter sweep, partial-run substitution, post-result code
change, submission archive, push, merge, pull request, or history rewrite is
allowed as part of this experiment. Organizer archives, source, input, and
output remain ignored/private and must not enter Git history or the package.
