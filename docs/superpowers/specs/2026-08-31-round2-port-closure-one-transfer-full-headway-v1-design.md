# Round 2 port-closure one-transfer recovery hold v1

## Decision

Run one Round 2 candidate from the accepted Round 1 v3 recovery-hold policy.
Keep every existing v3 decision unchanged and extend only
`UserStrategy.assign_associated_bookings` for a narrow, structurally strong
case: a new shipment whose direct service is affected by a port closure and
whose safe alternative requires exactly one service-route change.

The extension returns the normal origin-hold decision (`False`) only when the
safe alternative is robust by a full-headway margin. The margin is computed
from the live route distances, speeds, deployed fleets, recovery time, and
current timestamp. The candidate must satisfy:

1. all existing v3 new-shipment, active-disruption, path, timing, and safety
   guards;
2. exactly one service-route change in the safe path;
3. the nominal edge matches port-closure constraints only (no leg congestion
   and no mixed constraint set); and
4. `detour_hours - hold_hours` is strictly greater than the maximum full
   departure headway of every route used by the safe path.

All other cases retain the v3 result or delegate with `None` exactly as before.

## Why this is the selected experiment

Round 1 established that fragmented recovery holds can be beneficial, while
unfiltered one-transfer additions and low-margin suppressions were harmful.
Round 2 adds port closures and has a distinct structural opportunity: a direct
edge through a closed port can be replaced by a short two-edge path without the
multiple-transfer uncertainty that v3 intentionally avoids. A full-headway
buffer is a conservative, generalizable filter intended to keep only cases
where the computed waiting advantage is larger than an entire normal sailing
opportunity on every safe-route service.

The rule uses no port names, route IDs, dates, seed values, fitted constants,
output values, or scenario-specific tables. It is a single participant hook,
read-only, deterministic, standard-library-only, and fail-closed. Returning
`False` merely keeps the shipment in the normal origin waiting/retry lifecycle;
it does not alter event logic, bypass transportation, complete cargo early, or
move cargo to another port.

The strongest failure mode is that the organizer fallback's short alternative
may outperform waiting despite the static full-headway estimate because of
queue and capacity interactions. The official cumulative resilience-loss
score, not activation counts or timing proxies, decides the experiment.

## Validation and run contract

Before implementation, a read-only audit must exercise every valid integer-day
midpoint of every Round 2 disruption window in fresh contexts, all demands, and
context order without advancing a model or writing `Output`. It must record
candidate-only activations, exposure, no-mutation, and unchanged control ATT.

Implementation follows strict RED -> GREEN -> REFACTOR TDD. Only
`submission/response_strategies/user_strategy.py` and its participant README
may be evaluated as strategy changes; tests, specifications, and the public
experiment report are supporting repository material. No third-party package
is needed.

After all locked `uv`, Ruff, Ty, mypy, coverage, integration, sync/cmp, smoke,
packaging, restricted-material, clean-tree, and no-live-process gates pass, a
non-overwriting launch manifest must pin the candidate, Round 2 runtime,
baseline, fresh v3 control, package, configuration, and strict acceptance
expression. Exactly one full candidate run is allowed. Preserve its fresh ATT
and raw log before scoring or restoration, then accept only:

```text
candidate_loss < fresh_round2_v3_control_loss - 1e-9
```

Equality, worsening, invalid output, incomplete completion evidence, crash,
timeout, mutation, or a failed final gate rejects the candidate. On rejection,
record the result first, revert only this experiment's implementation/tests,
synchronize the v3 control, restore and re-score its pinned ATT, rerun all final
gates, and leave `main` clean. No tuning, duplicate run, second candidate,
push, merge, PR, upload, or submission is part of this experiment.
