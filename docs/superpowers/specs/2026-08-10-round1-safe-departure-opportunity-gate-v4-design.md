# Round 1 safe-departure opportunity gate v4 design

**Status:** approved on 2026-08-10 for one controlled candidate experiment.

## Objective

Test whether the accepted Round 1 multi-transfer recovery-hold v3 policy can
be improved by refusing long origin holds when the safe detour would offer
more than one service departure before the interrupted direct service
recovers.

The sole success criterion is a valid 72-period candidate whose cumulative
resilience loss is strictly lower than the current best by more than `1e-9`:

```text
candidate_cumulative_loss < 19.084638612143134 - 1e-9
```

Lower is better. Equality is rejection. The threshold, policy, and run
configuration are fixed before execution and must not be changed after seeing
the result.

## Organizer and repository boundaries

- Only participant-owned files under `response_strategies` are eligible for
  organizer evaluation. Runtime behavior therefore remains entirely in
  `submission/response_strategies/` and the synchronized Round 1 copy.
- The four public `UserStrategy` method signatures and their `None`/boolean
  contracts remain exact.
- The candidate uses only the Python standard library and runtime objects
  supplied to the hook.
- It performs no filesystem, network, subprocess, environment, wall-clock, or
  random access and has no mutable module-level state.
- It contains no scenario name, seed, calendar date, port name, route ID,
  demand identity, or value fitted to a known input row.
- It is deterministic and read-only. Exact ties retain organizer context
  ordering; sets are used only for membership.
- The user's standing constraint overrides generic worktree guidance: use only
  `/Users/noeflandre/wintersim-challenge-2026` and the sole local branch
  `main`. Do not create another checkout, worktree, clone, or branch.
- No push, pull request, upload, email, or submission is authorized by this
  experiment.

## Current accepted control

Fresh pre-design verification established:

- active policy: multi-transfer recovery hold v3;
- participant/runtime strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- accepted ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- cumulative resilience loss: `19.084638612143134`;
- period count: `72`;
- evidence snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- original Round 1 no-op fallback loss: `20.436668751255972`.

The active Output and accepted snapshot were byte-identical when the design
was approved. No WSC simulator was running and the tracked tree was clean.

## Evidence and hypothesis

Version 3 improved the preceding accepted v2 result from
`19.828803374740612` to `19.084638612143134`. It holds new cargo only when an
interrupted one-booking nominal route is estimated to recover and deliver
sooner than a currently safe route requiring at least two service changes.

The accepted run nevertheless produced 25 period ATT values worse than v2.
Its operational summaries showed the intended reduction in persistent
transshipment waiting, but also increased origin waiting in parts of the
horizon. That combination suggests that fragmented detours are often worth
avoiding while some long holds remain too conservative.

A read-only structural audit sampled daily midpoints of every active Round 1
disruption window. It used fresh organizer contexts, created the organizer's
eligible alternative routes in memory, and evaluated all demands without
advancing or writing a simulation. It is activation evidence, not causal
performance evidence. Among 19,000 demand-time observations it found:

- 48 observations where v3 would hold, covering five anonymous demands;
- all 48 in the first disruption window;
- 34 with two route changes and 14 with three;
- 21 where recovery occurred within one headway of the first safe service;
- those 21 retained `54,585 / 77,478`, or about `70.45%`, of the
  annual-TEU-weighted v3 activation exposure;
- the retained subset included every observed high-volume short-wait case;
  the removed subset consisted of longer waits and disproportionately lower
  demand exposure.

The hypothesis is that preserving the short-wait, high-exposure holds will
retain v3's protection from fragmented transshipment paths, while delegating
long holds will reduce origin delay enough to lower cumulative resilience
loss.

## Alternatives considered

1. **Safe-first-service headway gate — selected.** Compare remaining recovery
   time with the live headway of the first route the rejected safe detour would
   board. This directly expresses how many safe departure opportunities are
   forgone and retained about `70.45%` of weighted audit exposure.
2. **Nominal direct-service headway gate — rejected.** It retained 19 of 48
   observations and about `69.34%` of weighted exposure, but the direct
   service is disrupted; its cadence is less relevant to the opportunity being
   declined.
3. **Require a benefit margin larger than one nominal headway — rejected.** It
   retained 28 observations but only about `30.61%` of weighted exposure,
   discarding the high-volume cases most likely to affect TEU-weighted ATT.
4. **Require at least three route changes — rejected.** It retained only 546
   annual-TEU-weighted observation units and would probably make the policy
   nearly dormant.
5. **Predict exact vessel phases — rejected.** It materially expands state and
   failure handling, while the previous phase-aware candidate worsened loss to
   `24.21744876585007`.

## Exact candidate policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a non-`None` result. The other three hooks remain unconditional `None`
delegates.

Version 4 retains every v3 precondition and calculation:

1. The shipment is new, has no bookings, and has a distinct origin and
   destination.
2. At least one well-formed relevant disruption is active under
   `start <= now < end`.
3. The deterministic nominal shortest path is exactly one booking edge and
   intersects an active closed-port or congested-leg constraint.
4. The deterministic safe shortest path is complete and uses only eligible
   original or active alternative routes while excluding active constraints.
5. The safe path contains at least two adjacent service-route identity
   changes, so it requires at least three boardings.
6. Every required route, segment, leg, distance, deployed vessel, speed,
   disruption recovery, and computed time is finite and structurally valid.
7. The existing estimate remains:

   ```text
   hold_hours = remaining hours until the affected direct edge recovers
                + nominal direct-path boarding and sailing hours

   detour_hours = safe-path boarding, transfer, and sailing hours
   ```

8. The first safe edge's route profile is derived with the existing
   `_route_profile` function. Its headway is the route cycle distance divided
   by the sum of positive finite deployed-vessel speeds.
9. The candidate returns the exact boolean `False` only when both conditions
   are true at full precision:

   ```text
   hold_hours < detour_hours
   remaining_recovery_wait_hours <= safe_first_route_headway_hours
   ```

10. If the recovery wait is longer than one safe-first-route headway, the
    candidate returns `None` and the organizer fallback assigns the safe
    detour. Equality at the headway boundary is eligible to hold; equality in
    the hold-versus-detour comparison still delegates.

Any missing, malformed, ambiguous, non-finite, or unexpected state returns
`None`. Both `False` and `None` outcomes leave the shipment, bookings, routes,
segments, legs, ports, vessels, plans, and context collections unchanged.

## Minimal implementation boundary

The only behavioral edit is inside `_should_hold` in
`submission/response_strategies/user_strategy.py`:

- derive the first safe route profile with existing `_route_profile`;
- fail closed if it is unavailable;
- after deriving `wait_hours`, delegate when
  `wait_hours > safe_first_profile.headway_hours`;
- leave all graph, path, disruption, timing, tie-breaking, and public-hook
  logic untouched.

Update only participant descriptions and the corresponding v4 test/report
names. Do not add a new module, dependency, cache, parameter, configuration
surface, or optimization framework.

## TDD contract

Strict RED -> GREEN is mandatory:

1. Rename the v3 unit and real-context integration contracts to v4.
2. Before production edits, add a synthetic long-wait case where v3 returns
   `False` but v4 must return `None`, with a complete before/after snapshot.
3. Run the focused suite and require a genuine assertion failure showing
   `False is None`; collection or fixture errors are not valid RED evidence.
4. Add boundary coverage proving wait below headway holds, wait exactly equal
   to headway holds, and wait above headway delegates.
5. Preserve all v3 topology, malformed-state, deterministic-order,
   forbidden-capability, public-signature, and no-mutation tests.
6. Strengthen the real Round 1 context test to find both a short-wait retained
   case and a long-wait delegated case from derived active windows, without
   hard-coding any participant-visible identity.
7. Implement only the minimum gate, run focused GREEN, then refactor names and
   prose without changing behavior.

## Fixed run identity

- round: `round1`;
- scenario: organizer `create_with_disruption`;
- seed: `2026`;
- `PYTHONHASHSEED=0`;
- warm-up: `140` days;
- measured horizon: `360` days;
- reporting interval: `5` days;
- required numbered periods: `72`;
- launch command:
  `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`;
- accepted control loss: `19.084638612143134`;
- accepted control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- candidate evidence directory:
  `.challenge/round1/results/safe_departure_opportunity_gate_v4_20260810/`;
- ignored aggregate:
  `experiments/results/round1_safe_departure_opportunity_gate_v4_20260810.json`.

Exactly one full candidate run belongs to this experiment. A failed preflight
does not consume the run because no simulator starts. A crash or invalid
completed attempt does consume it and is rejection. No tuning, threshold
change, second candidate, or duplicate process is permitted within v4.

## Pre-run and evidence protocol

Before launch, require all of the following at the immutable launch commit:

- `uv lock --check` and `uv sync --locked --all-groups`;
- Ruff format and lint;
- Ty and mypy on participant/dev-tool sources;
- focused RED/GREEN evidence and the complete unit suite with true branch
  coverage at least `90%`;
- real-context integration suite;
- synchronized participant/runtime byte identity;
- one-day Round 1 smoke with `SMOKE_OK`, followed by identity recheck;
- two byte-identical validation packages containing only the participant
  README and `user_strategy.py`, then removal from the repository;
- fresh control re-score and control snapshot hash;
- clean tracked state, one worktree, one local branch, no live WSC simulator,
  and clean restricted-material scans;
- an atomic ignored manifest that pins HEAD, hashes, package members, control,
  configuration, gates, stale Output metadata, command, and acceptance rule.

Stream the sole full run to the fixed ignored log. Monitor the same process;
never launch a duplicate. Require exit zero, Day 360, Period 72 (Days 356-360),
`Simulation completed.`, and a fresh ATT write. Copy the fresh ATT
byte-for-byte to the candidate evidence directory before scoring, sync,
smoke, or restoration. Validate hash equality, finite values, and 72 periods.

Score only the preserved candidate against the authoritative Round 1 baseline
CSV using the repository scorer. Record full-precision score, per-period
losses, ATT hash, mean, period comparisons, runtime/log identity, and the
unchanged decision expression in the ignored aggregate and tracked report.

## Decision and restoration

If the candidate strictly satisfies the acceptance expression, retain v4 as
the active participant policy, update all public current-best documentation,
and rerun every final gate.

On equality, worsening, crash, invalid evidence, or any failed required gate:

1. preserve and document the v4 result before restoration;
2. revert only the candidate implementation and v4 test rename/behavior
   commits in reverse order with Git;
3. synchronize the restored v3 participant code into Round 1;
4. restore the accepted v3 ATT snapshot byte-for-byte to active Output;
5. require the v3 participant and ATT hashes above;
6. re-score exactly `19.084638612143134` over 72 periods;
7. rerun all final gates and document v4 as rejected;
8. leave a clean `main` and do not push or submit.

If v4 is rejected, a later strategy must be a separately specified experiment
with its own RED/GREEN cycle, immutable threshold, and single run.
