# Round 1 disruption-weighted booking v1

**Status:** pre-run review; candidate implementation is not yet authorized to
run the full simulation.

## Hypothesis

The Round 1 organizer fallback removes every currently congested sailing leg
from its initial-booking graph. That can make cargo wait for recovery even when
the slowed leg is the only available connection or is faster than a long safe
detour. A policy that compares predicted sailing duration, including the
runtime disruption multiplier and recovery time, may reduce transport-time
backlog without changing the simulator.

## Exact candidate scope

Only `UserStrategy.assign_associated_bookings` is overridden. The other three
hooks return `None` and delegate to the organizer fallback.

During an active disruption, the candidate keeps closed ports as hard
exclusions, but permits congested legs and chooses a complete booking path by
predicted sailing duration. The estimate uses runtime route vessel speed,
active disruption-plan multipliers, and the end of a disruption when a leg
crosses that boundary. Existing deployed alternative routes are considered
only when their active disruption key matches. Ties use deterministic context
order.

The candidate returns `None` without mutation when there is no active
disruption, no valid path, or any malformed/ambiguous runtime object. It
validates the entire chain before replacing any booking references. It uses
only standard-library imports and no organizer imports, filesystem/network/
subprocess/environment/wall-clock access, randomness, or mutable module state.

## Starting control

- Starting branch: `main`
- Starting commit: `fe8235b`
- Starting strategy SHA-256:
  `b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`
- Round: `round1`
- Scenario: `create_with_disruption`
- Seed: `2026`
- Warm-up: 140 days
- Measured horizon: 360 days
- ATT interval: 5 days
- Required period count: 72
- Process environment: `PYTHONHASHSEED=0`
- Pinned fallback cumulative loss: `20.436668751255972`
- Pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- Pinned fallback snapshot:
  `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`

The historical Round 0 score is not a Round 1 threshold.

## Acceptance and evidence

Accept only if the complete candidate score satisfies, without rounding:

```text
candidate_loss < 20.436668751255972 - 1e-9
```

The one authorized candidate run must write a fresh 72-period ATT CSV. Before
any score-based restore, preserve the CSV, raw run log, SHA-256, byte size,
mtime, header, period count, mean ATT, full-precision scorer JSON, per-period
better/equal/worse counts, package hash, and package members in:

`.challenge/round1/results/disruption_weighted_booking_v1_20260807/`

The ignored aggregate record is:

`experiments/results/round1_disruption_weighted_booking_v1_20260807.json`

## Rejection and restoration

Equality, worsening, a crash, incomplete output, a non-72-period CSV, or any
failed gate is rejection. Preserve evidence and commit this report before
restoring anything. Revert candidate implementation and test commits in
reverse order with `git revert`; retain this contract and the result record.
Synchronize the restored no-op adapter from `submission/`, restore the pinned
fallback ATT bytes from its ignored snapshot, and re-score to exactly
`20.436668751255972`. Run every final gate again. Do not tune, rerun, try a
second candidate, submit an archive, push/merge/open a PR, or rewrite history
as part of this experiment.

## Pre-run gate

The full run is not authorized until RED tests have been observed, GREEN tests
and integration checks pass, lock/sync, Ruff, `ty`, mypy, coverage (minimum
90%), packaging twice, sync/cmp, smoke, restricted-material, diff, and process
checks all pass, and the candidate identity/fallback identity are pinned in a
review update to this file.
