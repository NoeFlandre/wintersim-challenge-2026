# Round 1 multi-leg congestion hold v6

## Decision

Test one narrow additive refinement to the accepted Round 1 multi-transfer
recovery-hold v3 policy. The existing policy holds new cargo only when a
disrupted one-booking direct service is estimated to recover sooner than a
safe detour requiring at least two service-route changes. This experiment adds
one structurally distinct case: a direct booking edge that spans multiple
physical legs, where the only active constraint affecting that edge is a
congested leg and the safe path needs exactly one service-route change.

The change is participant-only, read-only, deterministic, standard-library-only,
and limited to `submission/response_strategies/user_strategy.py` plus its
behavioral tests and public audit documentation. It does not modify the
scorer, organizer source, inputs, run configuration, or another strategy hook.

## Current evidence and control

The canonical checkout is `/Users/noeflandre/wintersim-challenge-2026`, with
one worktree, one local branch (`main`), and a clean accepted v3 control at
`a57872b`. Fresh verification gives the accepted v3 cumulative resilience loss
`19.084638612143134` over 72 periods. The pinned and active v3 ATT bytes are
SHA-256
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`, and the
participant/runtime strategy bytes are identical at SHA-256
`f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`.

The latest read-only audit used a fresh `create_with_disruption()` context for
each midpoint of every integer day inside each valid disruption window (50
derived timestamps), evaluated every demand in context order, and did not
advance the model or write Output. Relative to v3 it found:

| Measure | Result |
| --- | ---: |
| demand-time observations | 19,000 |
| v3 control holds | 48 |
| proposed candidate-only holds | 4 |
| candidate-only annual TEU exposure proxy | 12,960 |
| candidate-only shape | one nominal booking edge spanning at least two physical legs; safe path with one route change; active constraint type only `leg` |
| candidate-only timing margin | positive in all 4 observations; approximately 168–240 hours |
| observed mutation | none |

The exposure and timing values are structural audit evidence, not a score
prediction. The audit intentionally records anonymous counts and aggregates;
it does not publish organizer identities, input rows, or source.

## Why this candidate

The accepted v2 policy held all eligible safe detours with at least one route
change. V3's controlled improvement came from removing the broad one-transfer
subset. The fresh decomposition shows that the one-transfer subset is not
uniform: small single-leg cases and mixed leg-plus-port cases are different
from the four pure-congestion cases where the direct booking spans multiple
physical legs and the detour remains substantially slower. V6 tests only that
identity-free structural slice instead of re-enabling all one-transfer holds.

The strongest failure mode is that a congested leg inside a multi-leg direct
service can still make waiting at origin worse than accepting a one-transfer
detour, or that the organizer's retry lifecycle treats this shape differently
than the static timing model. The official full scorer, not the audit, decides.

## Alternatives rejected before implementation

1. Re-enable every one-transfer hold: rejected because v2's aggregate result
   was worse than v3 and would confound several structural cases.
2. Re-enable one-transfer holds for closed-berth or mixed constraints:
   rejected because the audit does not isolate a bounded benefit and port
   closures have a different operational mechanism.
3. Add a numeric margin or headway threshold: rejected because it would fit a
   value to this seed and v4 showed that subtractive timing gates can remove
   valuable v3 holds.
4. Change berth selection, alternative-route creation, or in-transit
   rebooking: rejected because the relevant prior candidates were dormant or
   materially harmful, while this candidate is a live gap in the accepted
   hook's semantics.

## Exact candidate policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a non-`None` value. The other three hooks remain unconditional `None`
delegates.

V6 preserves every existing v3 precondition: a new unbooked shipment with a
distinct origin and destination; a well-formed active disruption; a
deterministic one-edge nominal shortest path intersecting an active
constraint; a complete safe path; finite positive route, fleet, speed,
distance, recovery, and timing data; and a strict full-precision timing
comparison.

The only policy change is the safe-path eligibility rule:

- keep returning `False` for the existing v3 case where the safe path has at
  least two service-route changes;
- additionally return `False` when the safe path has exactly one service-route
  change, the nominal edge traverses at least two physical legs, and every
  active constraint that intersects that nominal edge is a congested-leg
  constraint;
- delegate with `None` for all other one-transfer paths, including single-leg
  nominal services and any closed-berth or mixed constraint set.

The implementation must derive all decisions from supplied runtime objects. It
must not use scenario/port/route/vessel identities, calendar dates, seed tables,
fitted constants, filesystem/environment/network/subprocess access, randomness,
wall-clock time, mutable cross-run state, organizer imports, or unordered
choice iteration. All `None` and `False` paths remain mutation-free and fail
closed on malformed data.

## Fixed run and decision contract

The candidate receives exactly one full Round 1 run with `create_with_disruption`,
organizer seed `2026`, `PYTHONHASHSEED=0`, 140 warm-up days, 360 measured days,
five-day ATT intervals, and 72 numbered periods. The acceptance expression is
frozen as:

```text
candidate_cumulative_loss < 19.084638612143134 - 1e-9
```

Mean ATT is descriptive only. Equality, worsening, a crash, incomplete output,
wrong period count, stale output, failed gate, or restoration failure is
rejection. Candidate ATT and raw logs must be copied to the ignored evidence
directory before scoring, synchronization, smoke, or restoration.

If rejected, commit the result report first, revert candidate tests and code in
reverse order with `git revert`, synchronize the accepted v3 participant
strategy, restore its pinned ATT bytes, re-score exactly, and rerun every final
gate. No tuning, duplicate run, second candidate, push, submission, merge, PR,
or history rewrite is part of this experiment.
