# Round 1 pure-congestion exclusion v9

## Decision

Test one narrow subtraction from the accepted Round 1 multi-transfer recovery
hold v3 policy. Keep v3's read-only hold for fragmented safe detours, but
delegate when every active disruption intersecting the nominal direct booking
edge is a congested-leg constraint and no closed-berth constraint intersects
that edge.

This is one policy delta in one hook:
`UserStrategy.assign_associated_bookings(context, now, shipment)`. The other
three hooks remain unconditional `None` delegates.

## Evidence and ranking

A fresh, identity-free audit sampled the midpoint of every integer day inside
each valid disruption window, created a fresh organizer context per timestamp,
prepared fallback alternatives only as setup, and evaluated every demand in
context order. It observed 19,000 demand-time calls and 48 live v3 holds. The
proposed v9 subtraction covers 22 pure-leg v3 holds with an annual-TEU exposure
proxy of 55,272. Complete state snapshots remained unchanged. These are
activation facts, not performance predictions.

The candidate was chosen because two prior additive pure-congestion extensions
(v6 multi-physical-leg one-transfer and v8 single-physical-leg one-transfer)
both worsened the v3 score. Removing the pure-leg subset tests whether that
harm is caused by v3 holding cargo while a slowed, still-open direct service is
available. It preserves mixed leg/closed-port cases, where waiting may still
avoid a materially longer detour.

The rejected alternatives were:

1. Removing mixed leg-plus-closed-port holds: live, but only 26 observations
   and 21,126 annual-TEU exposure; it discards the cases with the strongest
   closure-driven reason to wait.
2. Adding another headway or berthing threshold: a numeric refinement of the
   already rejected v4/v7 assumptions, with no new causal evidence.

## Exact candidate behavior

All existing v3 guards remain unchanged: new shipment, active well-formed
disruption, nominal direct edge, complete safe path with at least two service
route changes, finite positive timing, and strict `hold_hours < detour_hours`.

The only new gate classifies constraints intersecting the nominal edge by
structural kind. If the non-empty set is exactly `{leg}`, v9 returns `None`
and delegates to the organizer fallback. If it contains `port`, v9 retains
v3's `False` hold decision. Missing, malformed, non-finite, ambiguous, or
unsupported data delegates without mutation.

The policy is identity-free, deterministic, standard-library-only,
participant-owned, read-only, fail-closed, and has no filesystem, environment,
network, subprocess, wall-clock, randomness, mutable cross-run state, route or
port names, seed tables, fitted threshold, or organizer import.

## Frozen run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- sole branch/worktree: `main` (the current user constraint);
- starting control HEAD: `35e669441419c0a30b299c24b22d5dd3b4ff8ba4`;
- control participant/runtime SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control score: `19.084638612143134` over 72 periods;
- authoritative Round 1 baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- round/scenario: `round1` / `create_with_disruption`;
- organizer seed: `2026`; `PYTHONHASHSEED=0`;
- warm-up/measured horizon: `140 / 360` days;
- ATT interval/periods: `5` days / `72`;
- full command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`;
- candidate evidence directory:
  `.challenge/round1/results/pure_congestion_exclusion_v9_20260812/`;
- aggregate evidence:
  `experiments/results/round1_pure_congestion_exclusion_v9_20260812.json`.

Acceptance is frozen at full precision:

```text
candidate_cumulative_loss < 19.084638612143134 - 1e-9
```

Exactly one candidate run is allowed. No code, tests, documentation, policy,
threshold, or second candidate may change after launch. Candidate ATT and raw
log bytes will be preserved before scoring, synchronization, smoke, or
restoration. On equality, worsening, crash, invalid periods, stale output, or
any failed gate, the result is committed first; candidate integration/test
corrections, implementation, and RED commits are reverted in reverse order;
the v3 participant is synchronized; the pinned v3 ATT is restored byte-for-
byte and re-scored; and all final gates are rerun. No push, PR, submission,
upload, email, merge, or history rewrite is authorized.
