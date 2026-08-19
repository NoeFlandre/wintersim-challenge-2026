# Round 1 multi-TEU v3 hold suppression v22

## Decision

Test one subtractive refinement of the accepted Round 1 v3 policy. V3 holds a
new shipment when a disrupted direct service is estimated to recover sooner
than a safe detour requiring at least two service-route changes, without
considering cargo size. V18 kept only the v3 holds for multi-TEU synthetic
shipments and removed all 48 one-TEU holds; its full score worsened to
`20.744602632173724`. V20 and v21 also showed that adding extra holds for
multi-TEU cargo can be harmful. V22 tests the complementary boundary: retain
the proven v3 decision for one-TEU cargo, but delegate a v3 hold when the
shipment has a finite real `teu_size > 1`.

This is a single-hook, single-predicate delta. It does not add routes, alter
timing, or change any one-TEU decision. A multi-TEU hold is the only behavior
that can be removed. Missing, malformed, boolean, non-finite, and non-positive
cargo sizes retain the v3 decision rather than being guessed.

## Alternatives considered

1. **Selected: suppress existing multi-TEU v3 holds.** It is the direct
   complement of the measured v18 removal and is supported by the repeated
   degradation of multi-TEU additive policies in v20/v21. It is narrow,
   reversible, and has a clear audit oracle.
2. Re-add the unrestricted v12 mixed one-transfer extension. It was structurally
   live but scored `19.313383619092`, worse than v3; repeating it would not be
   a new falsifiable experiment.
3. Change a route-time estimate or add a new direct-booking path. V4–V17 and
   the direct-booking experiments were materially worse; they also carry more
   mutation and fallback-semantic risk.

The strongest failure mode is that multi-TEU holds are the most valuable v3
decisions because the official objective is TEU-weighted; suppressing them may
force long detours. The full 72-period scorer, not activation counts, decides.

## Exact policy and invariants

Only `UserStrategy.assign_associated_bookings` changes. Preserve the complete
v3 predicate and return `False` for every v3 hold except when the shipment's
`teu_size` is a finite, non-boolean real strictly greater than `1`; in that
case return `None` and let the organizer fallback decide. A value of exactly
`1`, zero, negative, missing, malformed, non-finite, or boolean leaves the v3
hold untouched. The other three hooks remain unconditional `None` delegates.

The participant code remains read-only, deterministic, standard-library-only,
identity-free, and free of I/O, environment/process/network access, wall-clock
use, randomness, organizer imports, mutable module state, route/date/seed
tables, or tuned constants. Delegation must not mutate supplied objects.

## Fixed run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and branch `main`;
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
- freshly verified control loss: `19.084638612143134`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- strict acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Candidate ATT, raw log, score JSON, aggregate, audit, and manifest remain
ignored/private under
`.challenge/round1/results/multi_teu_v3_hold_suppression_v22_20260819/` and
`experiments/results/round1_multi_teu_v3_hold_suppression_v22_20260819.json`.
Exactly one full candidate run is allowed. No tuning, duplicate, second
candidate, push, merge, PR, submission, upload, or history rewrite is part of
this experiment.

## Audit and rejection procedure

Before RED, a fresh read-only audit must evaluate 50 valid disruption
midpoints and all 19,000 demands using one- and two-TEU synthetic shipments.
It must reproduce 48 v3 holds, show 48 one-TEU candidate holds, 0 two-TEU
candidate holds, 48 control-only two-TEU cases, no mutation, no model advance,
and no Output write. A failed or dormant audit is a NO-GO and consumes no run.

After RED→GREEN and all preflight gates, preserve the fresh candidate ATT and
raw log before scoring or restoration. On equality, worsening, invalid output,
crash, incomplete markers, or failed final gate: commit the result, revert only
v22 code/tests in reverse order with `git revert`, synchronize v3, restore its
pinned ATT bytes, re-score exactly, rerun every final gate, and leave v3 active.
