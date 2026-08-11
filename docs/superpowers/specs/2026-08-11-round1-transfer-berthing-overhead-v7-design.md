# Round 1 transfer-berthing overhead v7 design

## Status

**DESIGN FROZEN — implementation and one full run are authorized by the
continuing experiment goal, subject to the mandatory preflight below.**

## Hypothesis

The accepted multi-transfer recovery-hold v3 policy compares the time to wait
for a disrupted direct service with a safe detour. Its detour estimate includes
sailing time and average service-route headway, but it does not include the
physical berthing phases required when cargo changes service routes. The local
Round 1 organizer runtime defines each berthing phase as exactly three hours.
At every service-route change, a cargo flow must pass through two vessel
berthing phases: the vessel leaving the transfer port and the vessel receiving
the cargo. This candidate adds those two organizer-defined phases (six hours)
per safe-path route change to the detour estimate.

The policy therefore keeps v3's proven hold decisions and adds only the missing
transfer-time term. It may hold a small number of marginal direct-service
shipments that v3 delegated when the physically corrected detour is slower.
The full cumulative resilience-loss score, not the audit, decides whether that
extension is useful.

## Read-only activation audit

A fresh audit used a new `create_with_disruption()` context for every midpoint
of every integer day inside the valid Round 1 disruption windows (50 timestamps
and all 19,000 demand-time observations). It evaluated v3 and the proposed
policy without advancing the event model, writing Output, or mutating runtime
objects.

- v3 control activations: the observed v3 hold set;
- candidate-only activations with six hours per route change: 4;
- candidate-only annual-TEU exposure proxy: 3,711;
- candidate-only shapes: safe paths of 3–5 edges with two or three route
  changes; timing margins were within the added transfer overhead;
- v3 decisions removed by the candidate: 0;
- observed mutation: none.

This is structural activation evidence only. It is not a performance claim.
The aggregate audit is private and ignored at
`.challenge/round1/results/transfer_berthing_overhead_v7_20260811/activation_audit.json`.

## Exact participant policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a non-`None` value. The other three hooks remain unconditional `None`
delegates.

The candidate preserves every v3 precondition and calculation:

- new shipment with no existing booking chain and distinct origin/destination;
- well-formed active disruption under `start <= now < end`;
- one-edge nominal shortest path intersecting an active constraint;
- complete safe shortest path with at least two service-route changes;
- positive, finite route, fleet, speed, distance, recovery, and timing data;
- deterministic context-order path ties and fail-closed malformed-input handling;
- strict `hold_hours < detour_hours` comparison at full precision.

The only changed arithmetic is:

```text
transfer_berthing_hours = 2 * 3 hours * safe_route_change_count
detour_hours = v3_detour_hours + transfer_berthing_hours
```

The three-hour value is copied from the verified organizer Round 1
`BerthBerthing` runtime, not tuned from a score. The participant implementation
must document this provenance and must not import organizer code.

The implementation is read-only, deterministic, standard-library-only, and
free of scenario identities, route/port tables, dates, seeds, I/O, environment
or process access, randomness, wall-clock reads, mutable module state, and
post-decision mutation. `None` delegates to the organizer; `False` means the
participant has chosen to hold the new shipment without editing its state.

## Fixed control and run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one local worktree and one local branch: `main`;
- current accepted control: multi-transfer recovery hold v3;
- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control cumulative resilience loss: `19.084638612143134`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- round/scenario: `round1` / `create_with_disruption`;
- organizer seed: `2026`;
- process hash seed: `PYTHONHASHSEED=0`;
- warm-up: 140 days;
- measured horizon: 360 days;
- ATT interval: 5 days;
- required numbered periods: 72;
- exact full-run command:
  `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`;
- candidate ATT evidence:
  `.challenge/round1/results/transfer_berthing_overhead_v7_20260811/ATT_By_Statistics_Interval.csv`;
- candidate raw log:
  `.challenge/round1/results/transfer_berthing_overhead_v7_20260811/full_run.log`;
- candidate score aggregate:
  `experiments/results/round1_transfer_berthing_overhead_v7_20260811.json`.

The sole acceptance expression is fixed before execution:

```text
candidate_cumulative_loss < 19.084638612143134 - 1e-9
```

Equality, worsening, a crash, incomplete output, a wrong period count, or any
failed gate is rejection.

## TDD and one-run rules

RED tests must fail against v3 for a qualifying marginal detour whose corrected
time crosses the strict boundary, while preserving the v3 result for a large
margin and all malformed/inactive/delegated cases. GREEN must be the minimum
participant change with no mutation and real Round 1 candidate-only activation.

Before launch, locked uv resolution/synchronization, Ruff format/lint, Ty,
mypy, true non-integration coverage of at least 90%, integration tests, Round 1
sync/cmp, smoke, deterministic participant-only packaging twice, current
control score/hash proof, restricted-material scans, one-worktree/one-branch
checks, clean diff, and no-live-process checks must pass. A non-overwriting
ignored manifest must pin the launch identities and gates.

Exactly one managed full run is allowed. After launch no code, tests,
documentation, policy, threshold, or runtime state may be changed before the
decision. Preserve the fresh CSV and raw log before scoring or any restore.
Apply the strict expression unchanged. If rejected, commit the result first,
revert only candidate implementation/tests in reverse order with `git revert`,
synchronize the accepted v3 participant strategy, restore its pinned ATT bytes,
re-score exactly, and rerun every final gate. Keep this design, plan, audit,
and result report; never track organizer source/input/output/archive material.
No tuning, duplicate run, second candidate, push, merge, PR, submission, or
history rewrite is part of this experiment.
