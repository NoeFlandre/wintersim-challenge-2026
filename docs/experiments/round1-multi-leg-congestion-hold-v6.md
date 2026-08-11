# Round 1 multi-leg congestion hold v6

## Status

**PRE-RUN GATES COMPLETE — one candidate simulation is authorized by this
contract; it has not started.** This file is the tracked contract for one
separately named candidate experiment. It will be updated with immutable run,
score, and restoration evidence only after the corresponding steps complete.

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

The saved audit has SHA-256
`d514c34cfeccb32a574b552d333c7643cd3fa8fd9e495586b737ec3d4d4b60b5`.

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

RED tests failed only because v3 delegated the qualifying candidate-only
contexts: the focused unit/real-context selection reported 2 expected failures
and 4 passing controls. The RED contract is commit `134a859`.

The minimum participant implementation is commit `9dcce2a`; the participant
README correction is `a64a22e`. Focused GREEN reported 46 passing tests. The
candidate strategy SHA-256 is
`65531d8f2df02177998c32040555b478b211a7031ab59ab4ccd9304dd44eff00`, and the
participant/runtime strategy and README files are byte-identical.

The complete preflight passed before any full simulation:

- `uv lock --check`: passed; 29 packages resolved;
- `uv sync --locked --all-groups`: passed; 29 resolved and 25 checked;
- Ruff format/check: passed (23 files formatted, all checks passed);
- `ty check src/wsc2026_tools submission`: passed;
- mypy over `src/wsc2026_tools submission`: passed, 8 files;
- non-integration tests: 232 passed, 9 deselected, true branch coverage
  `90.88%` (the fixed gate is at least `90.00%`);
- integration tests: 9 passed;
- Round 1 sync and byte comparison for both participant files: passed;
- Round 1 smoke: `SMOKE_OK` and `smoke: OK`;
- two validation packages: byte-identical SHA-256
  `fbda567c8c0d61d8ed3fbecd614953324fd89fa6908ecdecd54f31e3c78552eb`,
  6,141 bytes, containing only the participant README and strategy;
- accepted v3 control freshly rescored to
  `19.084638612143134` over 72 periods;
- control and active Output ATT bytes: identical SHA-256
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`,
  1,262 bytes, stale mtime epoch `1786468847`;
- authoritative Round 1 baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- `git diff --check`, one-worktree/one-branch layout, restricted-material
  scans, clean tracked status, and no-live-simulator proof: passed.

The non-overwriting launch manifest will be written at
`.challenge/round1/results/multi_leg_congestion_hold_v6_20260811/pre_run_manifest.json`
after this pre-run record is committed. It will pin the full launch HEAD,
strategy/runtime hashes, package hash and members, control/baseline evidence,
stale Output metadata, fixed configuration, commands, gate results, and the
exact acceptance expression.

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

## Full-run result

Exactly one candidate simulation ran from the frozen launch HEAD
`8091b6eda8ba0bfef0ee472786a255d7755e4cd0` with the fixed command and
configuration. The managed process exited `0`; the raw log contains Period 72
(Days 356–360), Output Simulation Day 360, and `Simulation completed.`. The
organizer-reported simulation runtime was `00:27:26`.

Before scoring or any restoration, the fresh ATT bytes and raw log were copied
to the predeclared ignored evidence directory:

- candidate ATT SHA-256:
  `12ddb90c5cdd3cf7a13f1c7945e5f3e13edefd72cc77939d7ffef36f92f12511`;
- candidate ATT size/mtime: 1,262 bytes / epoch `1786473016`;
- numbered periods: 72;
- candidate mean ATT: `20.4675` days;
- raw log SHA-256:
  `00b5985477ea6a5f4a030fffd0b1fe724f20c19165b6a4b1fa57aecdbafbd35c`.

The source ATT and preserved candidate snapshot were byte-identical at
preservation time. No second simulation, replay, tuning, or duplicate process
was launched.

## Score and decision

The official scorer evaluated only the preserved candidate ATT against the
authoritative Round 1 baseline and reported 72 periods and cumulative
resilience loss `20.810481217905384`. The accepted v3 control is
`19.084638612143134`, so the exact delta is `+1.72584260576225`, or
`+9.043098173544317%` (worse). The candidate ATT was better in 17 periods,
equal in 28, and worse in 27 than v3; the candidate mean was also higher
(`20.4675` vs `20.3675` days).

The frozen gate is false:

```text
20.810481217905384 < 19.084638612143134 - 1e-9
```

**Decision: REJECTED.** This rejects the exact multi-leg pure-congestion
one-transfer extension in the fixed public Round 1 scenario and seed. It does
not prove that every structurally similar policy is harmful under hidden
scenarios. The complete scorer JSON is preserved at
`experiments/results/round1_multi_leg_congestion_hold_v6_20260811.json`, and
the candidate ATT, log, and score JSON remain ignored private evidence.

## Rejection and restoration

The rejection record was committed before any restore. Candidate commits were
reverted in the declared reverse order:

- `26df110` reverted the participant README update `a64a22e`;
- `c26d28b` reverted the v6 implementation `9dcce2a`;
- `863e962` reverted the v6 RED tests `134a859`.

The accepted v3 participant files were synchronized from the tracked source,
and the pinned v3 ATT snapshot was copied byte-for-byte back to the active
Round 1 Output. Independent verification then reported:

- participant/runtime strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- active and pinned v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- active Output re-score: `19.084638612143134` over 72 periods;
- no candidate, replay, tuning, or restoration simulation was run.

All final gates passed after restoration:

- locked uv check/sync, Ruff format/check, Ty, and mypy;
- 227 non-integration tests with true branch coverage `90.84%`;
- 8 integration tests;
- Round 1 sync and byte identity for both participant files;
- one-day smoke: `SMOKE_OK`, with the restored ATT hash unchanged;
- two final participant-only packages byte-identical at SHA-256
  `a88fa1f534049cec96ffdf7d0204b2dc1fa3d685ceb438d9cecf45b4fcc5eef3`,
  5,923 bytes;
- `git diff --check`, one-worktree/one-branch layout, restricted-material
  scans, clean tracked status, and no-live-simulator proof.

The v6 candidate ATT, raw log, score JSON, activation audit, aggregate, and
pre-run manifest remain ignored private evidence. No push, merge, pull request,
submission archive, upload, or history rewrite occurred.
