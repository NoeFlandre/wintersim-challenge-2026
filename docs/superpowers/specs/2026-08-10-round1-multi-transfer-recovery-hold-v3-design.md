# Round 1 multi-transfer recovery hold v3 design

## Status and purpose

This document pre-registers exactly one WSC 2026 Round 1 experiment. The
candidate is a strict refinement of the accepted recovery-aware direct-service
hold v2 policy: it will hold a new shipment only when the currently safe path
requires at least two changes between service routes, rather than at least one.
All other v2 behavior, estimators, safety gates, and delegation paths remain
unchanged.

The experiment asks one falsifiable question: did v2's simpler one-transfer
holds dilute the benefit obtained from avoiding highly fragmented disruption
detours? The candidate is accepted only if its official cumulative resilience
loss strictly beats the accepted v2 result.

## Evidence and considered approaches

The accepted v2 strategy scores `19.828803374740612` over 72 periods, improving
the former no-op fallback by `2.9743858155845607%`. Its ATT is lower than the
fallback in 28 periods, equal in 19, and higher in 25. That mixed period profile
supports narrowing the intervention, but it does not identify any individual
hold as causal.

A read-only static topology audit sampled active Round 1 contexts every half
day. Among v2-qualifying origin/destination observations, 13 used a safe path
with exactly one service-route change and 48 used a path with at least two
changes. The repeated-snapshot TEU totals were 38,232 and 77,478 respectively.
These are duplicated structural observations across time, not simulated cargo
outcomes, and are used only to prove that the proposed gate is neither dormant
nor equivalent to v2.

Three approaches were considered:

1. **Require at least two route changes (selected).** This one-line structural
   refinement delegates simple one-transfer detours while retaining the most
   fragmented detours. It is deterministic, scenario-agnostic, and introduces
   no fitted numeric threshold.
2. **Require a detour advantage larger than one route headway.** This could
   absorb estimator error, but it introduces a debatable margin and risks
   discarding good holds based on an aggregate timing approximation.
3. **Estimate live next-vessel arrival phases.** This is more detailed in
   theory, but materially more complex and closely related to a prior
   phase-aware booking experiment that worsened the score to
   `24.21744876585007`.

The selected policy has the best evidence-to-complexity ratio and preserves
YAGNI: it changes one existing decision gate and nothing else.

## Participant boundary and invariants

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a non-`None` value. The other three public hooks remain unconditional
`None` delegates. The participant implementation remains entirely inside
`submission/response_strategies/`, standard-library-only, and package-valid.

The policy must remain read-only, deterministic, and fail-closed. It must not
use scenario names, hard-coded port or route identifiers, calendar dates,
seed-specific tables, tuned thresholds, files, environment variables, the
current directory, network access, subprocesses, wall-clock time, randomness,
or mutable module-level state. It must preserve the four exact public hook
signatures and must not import organizer-owned strategy or simulation modules.

The user's standing repository constraint overrides the general worktree
guidance: this experiment stays in the sole canonical folder
`/Users/noeflandre/wintersim-challenge-2026` and on the sole branch `main`.

## Exact policy change

Version 3 retains every v2 eligibility and timing condition:

- the shipment is new, has no bookings, and is still at its origin;
- a well-formed disruption is active under `start <= now < end`;
- the deterministic nominal shortest path is exactly one booking edge and
  intersects an active constraint;
- the deterministic safe shortest path contains at least two edges;
- all route, disruption, graph, fleet, speed, distance, and arithmetic inputs
  are valid;
- `hold_hours` and `detour_hours` are positive and finite; and
- `hold_hours < detour_hours` at full precision.

The sole behavior change is the transfer-complexity gate. Count adjacent pairs
in the safe path whose `route` objects differ by identity. Return `False` only
when this count is at least two. Therefore the safe path must involve at least
three service boardings. A path with zero or one route change delegates by
returning `None` without mutation.

No new estimator, configurable value, helper module, mutation, cache, logging,
or instrumentation is part of the candidate.

## Failure and data flow

The existing v2 data flow remains unchanged: derive active constraints, build
nominal and safe graphs, choose deterministic shortest-distance paths, validate
the new route-change count, estimate hold and detour times, and return either
the exact boolean `False` or `None`.

Missing relationships, malformed collections, invalid or non-finite values,
ambiguous disruption state, incomplete paths, and narrow runtime data-shape
errors delegate without mutation. Unexpected programmer errors remain visible;
the public hook must not add a broad `Exception` or `BaseException` catch.

## TDD contract

Strict RED-GREEN-refactor evidence is required before any operational run.

The RED test commit must add a synthetic one-transfer case that expects `None`
and fails against accepted v2 specifically because v2 returns `False`. Existing
qualifying, boundary, equality, malformed-state, deterministic-tie,
immutability, public-signature, and forbidden-capability coverage must remain.
The positive qualifying fixture is updated to require two route changes so that
the test suite proves v3 still activates.

The real ignored Round 1 integration test must derive a qualifying active
window and origin/destination pair from organizer runtime objects without
hard-coded names, require at least two route changes, prove the hook returns
`False`, prove a one-transfer synthetic case delegates, and prove complete
observable immutability for both outcomes.

After the expected RED is captured and committed, the minimum implementation
replaces the existing “at least one route change” gate with “at least two route
changes.” Focused GREEN, the full unit and integration suites, Ruff, Ty, mypy,
coverage, sync, smoke, and deterministic packaging must all pass before launch.

## Fixed experiment identity

- starting commit: `87faba27f7b56764cfac50384c935b67296c4817`;
- accepted v2 participant SHA-256:
  `144493d651d0eb967dc8725a34997d118b22ce3db116ca5126699bb8ea2b743c`;
- accepted v2 cumulative loss: `19.828803374740612`;
- accepted v2 ATT SHA-256:
  `d381b087f8d67124a8078b5afc795f5b59b08db90148614b43dcfdf351e7ac48`;
- accepted v2 mean ATT: `20.415972222222222` days;
- accepted v2 snapshot:
  `.challenge/round1/results/recovery_aware_direct_service_hold_v2_20260809/ATT_By_Statistics_Interval.csv`;
- round/scenario: `round1` / `create_with_disruption`;
- organizer seed: `2026`; process environment: `PYTHONHASHSEED=0`;
- warm-up: 140 days;
- measured horizon: 360 days;
- reporting interval: 5 days;
- required numbered ATT periods: 72;
- exact run command:
  `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`;
- ignored candidate evidence directory:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/`;
- ignored aggregate record:
  `experiments/results/round1_multi_transfer_recovery_hold_v3_20260810.json`.

The sole acceptance expression is:

```text
candidate_cumulative_loss < 19.828803374740612 - 1e-9
```

It is applied to all 72 periods at full precision. Mean ATT is descriptive
only. Equality, worsening, a crash, stale or incomplete output, a non-finite
value, an invalid period count, or any failed gate is rejection.

## Preflight, run, evidence, and decision

Before launch, require a clean single-worktree/single-branch repository; locked
`uv` resolution; Ruff format and lint; Ty; mypy; non-integration coverage at
least 90.00%; all integration tests; participant/runtime byte identity; Round 1
smoke; two byte-identical compliant packages; clean restricted-material scans;
a freshly verified v2 score, hash, and 72-period snapshot; and proof that no
simulator is running.

Pin candidate HEAD, strategy/runtime hashes, package hash and members, accepted
v2 evidence, and stale Output hash and mtime. Run exactly one managed full
candidate with the fixed command, monitoring until exit, Day 360, Period 72,
explicit completion, and a fresh ATT write. No code, test, policy, threshold,
or documentation correction is allowed after launch and before the decision.

Before scoring or synchronization, copy the fresh ATT and raw log to the fixed
ignored evidence directory. Record hashes, sizes, mtimes, mean ATT, all period
values, complete scorer JSON, better/equal/worse counts versus accepted v2,
delta, relative change, runtime, and decision. Commit an evidence-limited
tracked experiment report.

If accepted, retain v3 and rerun every final gate. If rejected or invalid,
preserve and document the result first, then revert the candidate integration,
implementation, and RED-test commits in reverse order with `git revert`. Sync
the restored accepted v2 strategy, restore its pinned ATT bytes, verify the
exact v2 hash and score, and rerun every final gate. Design, plan, and result
history remain. No second candidate, parameter tuning, submission, push, merge,
pull request, or history rewrite is part of this experiment.
