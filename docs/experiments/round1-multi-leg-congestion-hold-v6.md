# Round 1 multi-leg congestion hold v6

## Status

**PRE-RUN DESIGN FROZEN — no candidate simulation authorized yet.** This file
is the tracked contract for one separately named candidate experiment. It will
be updated with immutable preflight, run, score, and restoration evidence only
after the corresponding steps complete.

## Hypothesis

The accepted v3 hold policy correctly protects direct services against long
multi-transfer detours, but its removal of all one-transfer cases may be too
broad. A direct booking edge that spans multiple physical legs and is affected
only by a congested leg is structurally closer to the proven multi-leg direct
case than to a simple single-leg transfer. If its one-transfer safe detour is
still slower under the existing timing model, holding at origin may reduce
transport time.

The strongest failure mode is that the retry lifecycle or congestion dynamics
make even this seemingly dominated one-transfer detour preferable. The full
scorer is the only performance decision.

## Frozen policy

Only `assign_associated_bookings` may return non-`None`. V6 keeps every v3
condition and keeps its existing `False` result for safe paths with at least
two route changes. It adds one branch for a safe path with exactly one route
change only when the one nominal edge spans at least two physical legs and all
active constraints intersecting that edge are congested-leg constraints.
Single-leg nominal edges, closed-berth constraints, mixed constraints, and all
malformed or uncertain states still delegate with `None`.

The strategy remains read-only, deterministic, standard-library-only,
identity-free, fail-closed, and mutation-free on both delegate and handled
paths. The other three hooks remain unconditional fallback delegates.

## Fresh activation audit

Before implementation, a read-only audit sampled 50 identity-free timestamps
(integer-day midpoints inside every valid disruption window), built a fresh
organizer context per timestamp, prepared fallback routes only as setup, and
evaluated 19,000 demand-time observations without advancing a model or writing
Output. It found 4 candidate-only observations and an annual TEU exposure proxy
of 12,960. Every candidate-only observation had the frozen structural shape:
one nominal booking edge spanning at least two physical legs, a safe path with
one service-route change, and only a congested-leg constraint intersecting the
nominal edge. The timing margin was positive in all four observations, roughly
168–240 hours. Complete observed state remained unchanged.

These are activation and exposure observations, not score evidence. Aggregate
audit JSON will remain ignored under:

```text
.challenge/round1/results/multi_leg_congestion_hold_v6_20260811/activation_audit.json
```

## Alternatives and prior evidence

V2's broad one-transfer extension worsened the accepted v3 result, so V6 does
not re-enable every one-transfer case. V4's broad subtractive headway gate also
worsened v3, so V6 adds no fitted numeric threshold. Berth, alternative-route,
and in-transit policies were previously dormant or harmful. This candidate is
the smallest live, identity-free semantic slice left by the v2→v3 comparison.

## Control and run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and one local branch: `main`;
- starting accepted control: v3 at `a57872b`;
- control cumulative loss: `19.084638612143134` over 72 periods;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control participant/runtime strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- scenario: `create_with_disruption`;
- organizer seed: `2026`;
- `PYTHONHASHSEED`: `0`;
- warm-up / measured horizon: `140 / 360` days;
- ATT interval / required periods: `5` days / `72`;
- candidate ATT: `.challenge/round1/results/multi_leg_congestion_hold_v6_20260811/ATT_By_Statistics_Interval.csv`;
- candidate log: `.challenge/round1/results/multi_leg_congestion_hold_v6_20260811/full_run.log`;
- candidate aggregate: `experiments/results/round1_multi_leg_congestion_hold_v6_20260811.json`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

## TDD and pre-run gate

RED tests must fail only because v3 delegates the four qualifying
candidate-only contexts. GREEN must be the minimum participant-only policy
change and must preserve all existing behavior, no-mutation guarantees,
deterministic ties, exact signatures, forbidden-capability checks, and real
context parity. Before the full run, locked uv/Ruff/Ty/mypy/coverage,
integration, sync/cmp, smoke, deterministic package, restricted-material,
clean-layout, and no-live-process gates must all pass and be recorded in a
non-overwriting ignored manifest.

## One-run decision and restoration

Exactly one full run is allowed. No code, tests, prose, policy, threshold, or
second candidate may change after launch. A crash, timeout, stale or incomplete
ATT, wrong period count, equality, worsening score, or failed gate is rejection.

On rejection, preserve ignored evidence first, commit this result update, use
`git revert` for candidate implementation and RED-test commits in reverse
order, synchronize the accepted v3 strategy, restore its pinned ATT bytes,
re-score exactly to `19.084638612143134`, rerun every final gate, and leave the
canonical `main` checkout clean. No push, merge, PR, submission, archive
upload, or history rewrite is authorized by this experiment.
