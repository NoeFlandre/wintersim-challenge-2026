# Round 1 multi-TEU mixed one-transfer recovery hold v21

## Decision

Test one additive refinement to the accepted Round 1 v3 recovery-hold policy.
V3 already holds new cargo when a disrupted direct service is estimated to
recover sooner than a safe detour requiring at least two service-route
changes. V12 added six mixed leg-plus-port cases with exactly one service
change and was close to, but worse than, v3. V18 showed that a cargo-size
boundary is a real runtime distinction, although its broader one-TEU removal
was harmful. V21 tests the intersection: retain the v12 mixed one-transfer
extension only for multi-TEU shipments.

This is one hook and one policy delta. It preserves every v3 decision, adds no
new timing constant, and delegates exact-one-TEU or malformed cargo data.

## Alternatives considered

1. **Selected: multi-TEU mixed one-transfer extension.** It combines the
   already observed v12 topology with the previously tested identity-free
   cargo-size boundary, while reducing the number of added holds relative to
   an unrestricted v12 extension.
2. Recompute safe paths by estimated service time instead of distance. This
   was rejected before v20 because it repeats the broad phase/time-routing
   direction that worsened earlier runs and changes the proven path semantics.
3. Remove another subset of v3 holds using a margin, route-cycle, or
   constraint-kind threshold. V4, v9, v10, v11, v13, v14, v16, and v17 show
   that subtractive refinements removed useful recovery holds; no direct
   evidence justifies another broad removal.

The strongest failure mode is that even multi-TEU one-transfer holds create
queue and capacity pressure whose network cost exceeds their direct delay
benefit. The full 72-period scorer, not activation counts or TEU exposure,
decides the experiment.

## Exact policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a non-`None` value. The candidate first applies the unchanged v3
predicate. It then allows the v12 mixed one-transfer extension only when:

1. the shipment is new and unbooked, with distinct origin and destination;
2. the disruption, nominal graph, safe graph, finite timing, and route-shape
   checks from v3 all succeed;
3. the nominal path is one edge and its matching active constraints contain
   exactly both `leg` and `port` kinds;
4. the safe path has exactly one service-route change; and
5. `shipment.teu_size` is a finite real strictly greater than `1` and is not a
   boolean.

The unchanged v3 multi-transfer branch remains eligible for every cargo size.
Exact one TEU, missing, boolean, non-positive, non-finite, or otherwise
ambiguous cargo size delegates the new one-transfer case with `None`; it does
not remove any v3 hold. The timing comparison remains the existing strict
`hold_hours < detour_hours` comparison at full precision. The other three
hooks remain unconditional `None` delegates.

The implementation must be read-only, deterministic, standard-library-only,
fail-closed, identity-free, and free of I/O, environment/process/network
access, randomness, wall-clock use, mutable module state, and organizer-owned
imports. It must use context order for ties and leave all supplied objects
unchanged on both handled and delegated paths.

## Activation audit and result contract

The pre-code audit uses fresh `create_with_disruption()` contexts at each
integer-day midpoint in every valid disruption window and every demand in
context order: 50 timestamps and 19,000 observations. It evaluates v3 with a
one-TEU shipment, the candidate with one TEU, and the candidate with two TEU
shipments while preserving complete before/after snapshots and Output
metadata. The audit reported:

- 48 v3 holds;
- 0 one-TEU candidate holds;
- 54 two-TEU candidate holds;
- 6 candidate-only two-TEU holds, all exact mixed leg-plus-port,
  one-change cases;
- annual-TEU exposure proxy `38,880` for the candidate-only observations;
- zero two-TEU control-only holds;
- no mutation, no model advancement, and unchanged Output.

These are structural reachability facts only. The immutable ignored audit is
written to
`.challenge/round1/results/multi_teu_mixed_one_transfer_v21_20260819/activation_audit.json`.

## Fixed run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and one local `main` branch;
- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / interval: `140` / `360` / `5` days;
- required numbered ATT periods: `72`;
- accepted v3 strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- accepted v3 ATT snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- accepted v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- freshly verified v3 control loss: `19.084638612143134` over 72 periods;
- acceptance expression: `candidate_loss < 19.084638612143134 - 1e-9`.

Candidate ATT, raw log, score JSON, aggregate, manifest, and audit remain
ignored/private. Exactly one full candidate run is allowed. No tuning,
duplicate run, second candidate, push, merge, PR, upload, submission, or
history rewrite is part of this experiment.

## Rejection procedure

On equality, worsening, invalid output, a crash, incomplete completion
markers, stale ATT, mutation, or any failed final gate: preserve the fresh
candidate ATT and log first; commit this result; revert only the v21
implementation and RED-test commits in reverse order with `git revert`; sync
the restored v3 participant files; restore the pinned v3 ATT snapshot
byte-for-byte; re-score exactly; rerun every final gate; and leave v3 active.
Design, audit, and result history remain retained.
