# Round 1 contiguous same-service normalization v5

## Decision

Test one additive refinement to the accepted Round 1 multi-transfer recovery
hold policy. The refinement keeps the v3 decision unchanged for every existing
case and admits only a nominal shortest path whose adjacent edges all belong to
the same service-route object. Recovery is taken from every nominal edge, so a
disruption on a later edge is not ignored.

This is a participant-only change in `submission/response_strategies/` and one
new unit/integration contract. It does not change the scorer, organizer source,
inputs, run configuration, or any other strategy hook.

## Current evidence and control

The current canonical checkout is `/Users/noeflandre/wintersim-challenge-2026`,
with one worktree, one local branch (`main`), and a clean tree at the guide
commit. Fresh control verification scored the active v3 strategy at
`19.084638612143134` over 72 periods. The active and pinned v3 ATT bytes have
SHA-256
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`, and the
tracked and Round 1 runtime strategy files are byte-identical at
`f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`.

A fresh read-only audit sampled the midpoint of every integer day that falls
inside the real disruption windows (50 derived timestamps). It evaluated every
demand in context order after preparing a fresh context for each timestamp:

| Measure | Result |
| --- | ---: |
| demand-time observations | 19,000 |
| v3 control holds | 48 |
| proposed-policy holds | 54 |
| candidate-only holds | 6 |
| candidate-only annual TEU proxy | 7,776 |
| candidate-only shape | nominal path 2 edges, safe path 3 edges, 2 safe route changes |
| observed mutation | none |

The audit is structural evidence only. It does not predict score, inspect or
publish organizer identities, advance the model, write Output, or tune a
threshold against a result. Its ignored JSON evidence will be retained under
`.challenge/round1/results/contiguous_same_service_normalization_v5_20260811/`.

## Alternatives considered

1. **Selected: contiguous same-service normalization.** Directly addresses the
   only observed v3 eligibility gap, is identity-free, and preserves the
   proven timing gate.
2. Broaden recovery to arbitrary multi-route nominal paths. Rejected because it
   changes the meaning of an actual transfer and has no isolated evidence that
   the transfer itself is harmful.
3. Add a headway or safety-margin threshold. Rejected because v4 showed that
   subtractive timing gates can remove valuable v3 holds, and a fitted numeric
   margin would be harder to generalize.

The selected policy is the highest-ranked non-vetoed option under the fixed
guide scorecard: direct adjacent evidence, reproducible candidate-only
activation, natural fit at the initial-booking hook, bounded downside through
the existing strict timing comparison, identity-free generalization, read-only
implementation, and direct synthetic plus real-context testability.

## Exact policy

`UserStrategy.assign_associated_bookings(context, now, shipment)` remains the
only hook that may return a non-`None` value. The candidate returns `False` only
when all v3 requirements hold and additionally:

1. the nominal shortest path is non-empty;
2. it has one edge (the existing v3 case), or it has multiple edges and every
   adjacent edge uses the same route object;
3. every nominal edge is considered when finding the latest active constraint
   recovery;
4. the safe path has at least two service-route changes;
5. all existing finite, positive, active-disruption, route, fleet, timing, and
   strict `hold_hours < detour_hours` checks pass.

All other states delegate with `None`. The candidate never creates bookings,
routes, files, processes, network calls, randomness, mutable module state, or
environment-dependent behavior. It uses context order for deterministic ties
and catches only the existing narrow data-error tuple at the public boundary.

## Test contract

RED tests must fail against the current v3 implementation for:

- a qualifying two-edge same-service nominal path returning `False`;
- a disruption on the later nominal edge being recognized;
- a distinct-route multi-edge nominal path delegating;
- malformed/incomplete and inactive states delegating without mutation;
- the existing one-edge v3 behavior remaining unchanged;
- the real ignored Round 1 context exposing candidate-only activation without
  mutation.

GREEN must be the minimum helper/predicate change, with the full existing
contract suite, type/lint checks, coverage, integration, synchronization,
smoke, and deterministic packaging passing before any full run.

## Run decision

The candidate receives exactly one full Round 1 run using the fixed
`create_with_disruption` scenario, organizer seed `2026`, `PYTHONHASHSEED=0`,
140-day warm-up, 360 measured days, five-day ATT intervals, and 72 required
periods. Accept only if the scorer reports:

```text
candidate_cumulative_loss < 19.084638612143134 - 1e-9
```

Mean ATT is descriptive; the complete cumulative loss decides. A crash,
incomplete output, invalid period count, equality, worsening score, failed
preflight, or restoration problem is rejection. Candidate ATT and logs are
copied before any command can overwrite Output. If rejected, record the result,
revert candidate code/tests with `git revert`, synchronize v3, restore the
pinned v3 ATT bytes, re-score, and rerun every final gate. No tuning, duplicate
run, second candidate, push, submission, or history rewrite is part of this
experiment.
