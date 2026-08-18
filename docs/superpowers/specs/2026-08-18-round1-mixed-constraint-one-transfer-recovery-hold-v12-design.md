# Round 1 mixed-constraint one-transfer recovery hold v12

## Decision

Run one candidate experiment only if a fresh, read-only activation audit proves
that the proposed branch is live in the current Round 1 organizer context. The
candidate is an additive extension of the accepted multi-transfer recovery-hold
v3 policy. It changes only `assign_associated_bookings` and leaves the other
three hooks delegated.

## Hypothesis

V3 holds new cargo when the nominal shortest path is one disrupted booking edge,
the safe path needs at least two service-route changes, and recovery plus direct
service is strictly faster than the safe detour. Pure-leg one-transfer additions
were rejected in v6 and v8, while removing port-involved v3 holds was harmful in
v10 and v11. The unresolved structural complement is a one-transfer safe path
whose nominal edge matches both a congested leg and a closed-port constraint.

For that exact, identity-free state, waiting for the latest matching recovery and
then using the direct service may beat the one-transfer detour. The candidate
must preserve every v3 hold and add no pure-leg or port-only one-transfer hold.

Strongest failure mode: one-transfer holds may be harmful even under compound
leg-and-port exposure, or the static timing estimate may omit queue and capacity
effects. A full score, not activation or mean ATT, decides the experiment.

## Frozen policy

The target hook is:

```text
UserStrategy.assign_associated_bookings(context, now, shipment)
```

Existing v3 gates remain unchanged: valid new-shipment state, an active and
well-formed disruption, complete nominal and safe graphs, one nominal booking
edge, at least two safe booking edges, finite positive route profiles, and strict
`hold_hours < detour_hours` timing.

After those gates, the safe path is eligible when either:

1. it has at least two service-route identity changes (the existing v3 rule); or
2. it has exactly one service-route identity change and the nominal edge’s
   matching active constraint kinds are exactly `{"leg", "port"}`.

Matching uses the existing v3 semantics: leg object identity for leg constraints,
normalized intermediate or final-arrival port names for port constraints (never
departure-port-only), and the latest recovery from the same matching set. A
shared helper must provide both the matching set and recovery so the semantics
cannot diverge. Equal or slower holds delegate with `None`; a qualifying hold
returns exactly `False`.

The implementation must remain read-only, deterministic, standard-library-only,
fail-closed, free of mutable module state and forbidden capabilities, and must
not use identities, dates, route names, demand indexes, constants fitted to the
run, or organizer imports. Public signatures and all non-target hooks remain
unchanged.

## Activation gate

Before RED tests or participant implementation, an ignored audit will evaluate
the v3 oracle and the proposed v12 predicate on fresh
`create_with_disruption()` contexts at every identity-free integer-day midpoint
inside valid disruption windows and every demand in context order. It will not
advance a model, write Output, or retain a context after organizer route setup.

The audit must reproduce the historical v3 count of 48 activations under the
matching 50-timestamp/19,000-observation protocol and must find at least one
candidate-only case with exactly one safe route change, exactly `{"leg", "port"}`
matching kinds, finite positive strict timing margin, and no observed mutation.
Zero or malformed activation is a hard NO-GO: stop without implementation or a
full run. Activation and annual-TEU exposure are structural evidence only.

## Fixed run contract

These values were freshly verified in the current checkout before implementation:

| Field | Value |
| --- | --- |
| round / scenario | `round1` / `create_with_disruption` |
| seed / `PYTHONHASHSEED` | `2026` / `0` |
| warm-up / measured horizon | `140` / `360` days |
| ATT interval / required periods | `5` days / exactly `72` |
| accepted control strategy SHA-256 | `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded` |
| accepted control ATT SHA-256 | `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a` |
| control loss | `19.084638612143134` |
| authoritative baseline ATT SHA-256 | `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d` |
| acceptance | `candidate_loss < 19.084638612143134 - 1e-9` |

The control snapshot is
`.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`.
Candidate evidence belongs only in the ignored
`.challenge/round1/results/mixed_constraint_one_transfer_recovery_hold_v12_20260818/`
directory and the ignored aggregate
`experiments/results/round1_mixed_constraint_one_transfer_recovery_hold_v12_20260818.json`.

## Boundaries

The canonical layout is one checkout, one worktree, and `main`. Participant
changes are limited to `submission/response_strategies/user_strategy.py` and
`submission/response_strategies/README.md`; tests and public records are
development documentation only. No full simulation, push, merge, PR, upload,
submission, history rewrite, tuning, or second candidate is authorized in this
experiment. The process must stop for senior review after the pre-run manifest
and all preflight gates are complete.
