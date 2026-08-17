# Round 1 port-involved margin guard v11

## Decision

Run one Round 1 candidate from the accepted multi-transfer recovery-hold v3
control. Change only `UserStrategy.assign_associated_bookings`.

The v3 policy currently holds a new shipment when its disrupted one-edge
nominal service is estimated to recover sooner than a safe path requiring at
least two service-route changes. V11 keeps that policy except for a matching
port-closure constraint whose timing advantage is smaller than the first safe
service route's full headway. Those borderline port-involved cases delegate to
the organizer fallback; pure leg-congestion holds and port-involved cases with
an advantage at least one full safe headway remain v3 holds.

The exact predicate is:

```text
if matching constraint kinds include "port" and
   detour_hours - hold_hours < first_safe_route_headway_hours:
    return None
else:
    return the existing v3 decision
```

The boundary is inclusive for retention: equality with the first safe
headway keeps the v3 hold. All existing v3 guards, strict `hold_hours <
detour_hours` comparison, exception handling, and three delegated hooks remain
unchanged.

## Why this candidate

The accepted v3 audit contains 48 live holds. V10 tested the broad complementary
removal of every port-involved hold (26 cases) and worsened the full score to
`22.096980694905298`; that broad result must not be repeated. A fresh
identity-free audit of the same 19,000 observations shows that only 13 of those
port-involved holds have a timing advantage below the first safe headway (9,876
annual-TEU exposure proxy). The other 13 port-involved holds and all 22 pure-leg
holds remain active. The guard therefore tests a smaller semantic uncertainty:
whether borderline port-closure waits are too fragile to justify holding, while
retaining the high-margin recovery decisions that v10 did not isolate.

This is a qualitative scorecard selection:

| Dimension | Score | Reason |
| --- | ---: | --- |
| Adjacent evidence | 2 | V10 directly identifies port-involved holds as the unresolved subset; this narrows rather than repeats it. |
| Candidate-only activation | 2 | 13 structurally derived real-context delegations and 9,876 annual-TEU exposure. |
| Call-site fit | 2 | `None` is the natural fallback delegation branch for uncertain initial booking. |
| Upside/downside | 1 | It may remove fragile holds, but any removed hold may have been useful. |
| Hidden-scenario generalization | 2 | Uses constraint kind, computed timing margin, and route headway; no identities or dates. |
| Safety | 2 | Read-only, standard-library-only, fail-closed, and one small predicate. |
| Novelty | 2 | New margin guard; not the v4 wait-headway gate or v10 all-port removal. |
| Testability | 2 | Synthetic boundary tests plus real-context candidate-only activation. |

The strongest failure mode is that even a small positive advantage is valuable
when the safe path is fragmented, so delegating borderline port cases could
increase loss. A full scorer result, not the audit or mean ATT, decides.

## Audit contract

The read-only audit sampled every integer-day midpoint inside each valid
disruption window, created a fresh `create_with_disruption()` context for every
timestamp, prepared alternative routes only as setup, and evaluated every
demand in context order. It did not advance a model, write organizer Output,
or retain a mutated context. It observed 50 timestamps and 19,000
demand-time observations:

- v3 control holds: 48;
- v11 retained holds: 35;
- v11 candidate-only delegations: 13;
- candidate-only annual-TEU exposure proxy: 9,876;
- no mutation observed;
- all 13 candidate-only cases matched both `leg` and `port` constraints and
  had a timing margin below the first safe-route headway.

These are activation and exposure evidence only, not a performance prediction.
The ignored audit record will be written under
`.challenge/round1/results/port_involved_margin_guard_v11_20260817/`.

## Invariants and challenge boundary

- Only participant files under `submission/response_strategies/` may change.
- The three other hooks remain unconditional `None` delegates.
- Every return path is read-only and preserves complete runtime state.
- Missing, malformed, inactive, non-finite, non-positive, or ambiguous data
  delegates with `None`.
- No port names, route IDs, dates, seeds, fitted constants, filesystem,
  environment, network, subprocess, wall-clock, randomness, mutable global
  state, or organizer imports are allowed.
- Ties and traversal use deterministic context/list order.
- The candidate is one frozen policy and one full run only; no tuning or second
  candidate is allowed.
- No push, merge, PR, submission, upload, or history rewrite is authorized.

## Fixed control and run identity

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and one local branch: `main`;
- starting HEAD: `17eb756cf71fb2fa96be3476925b871777e93ab8`;
- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control mean ATT: `20.3675` days;
- control score: `19.084638612143134` over 72 periods;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- round/scenario: `round1` / `create_with_disruption`;
- seed and environment: `2026` / `PYTHONHASHSEED=0`;
- warm-up / measured horizon: `140 / 360` days;
- ATT interval / required numbered periods: `5` days / `72`;
- candidate evidence directory:
  `.challenge/round1/results/port_involved_margin_guard_v11_20260817/`;
- ignored aggregate:
  `experiments/results/round1_port_involved_margin_guard_v11_20260817.json`;
- immutable acceptance expression:
  `candidate_loss < 19.084638612143134 - 1e-9`.

## Rejection and restoration

If the candidate is equal, worse, invalid, incomplete, crashes, times out, or
fails any gate, preserve the fresh ATT and log first, commit the result report,
then revert only the v11 implementation and test commits in reverse order with
`git revert`. Synchronize the v3 participant, restore the pinned v3 ATT bytes,
re-score exactly to `19.084638612143134`, rerun every final gate, and leave
`main` clean. If accepted, retain the candidate and rerun final gates without
changing policy. No action after launch may change code, tests, thresholds, or
the acceptance rule.
