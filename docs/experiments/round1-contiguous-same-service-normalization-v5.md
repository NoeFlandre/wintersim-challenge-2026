# Round 1 contiguous same-service normalization v5

## Status

**PRE-RUN DESIGN FROZEN — no candidate simulation has started.** This report
is the tracked contract for one candidate run under the autonomous experiment
goal. It records the exact control, hypothesis, activation audit, tests,
preflight, decision rule, and restoration procedure.

## Hypothesis

The accepted v3 policy already avoids long safe detours when a disrupted
nominal service is estimated to recover sooner. Its implementation treats a
nominal shortest path with more than one booking edge as ineligible, even when
all adjacent edges use the same service-route object. In the real topology,
six identity-free observations had exactly that shape and would still prefer a
recovery hold under the existing timing comparison. Normalizing this contiguous
same-service path should protect those cargo flows without broadening the policy
to genuine multi-service transfers.

The strongest failure case is that a same-route multi-edge booking can encode a
real operational transfer or otherwise be semantically different from a single
booking; in that case the extension can add harmful holds. The full scorer, not
the audit, will decide.

## Exact candidate

Only `assign_associated_bookings` may return `False`; the other three hooks
remain unconditional `None` delegates. The candidate preserves all v3 gates:
new unbooked shipment, distinct origin/destination, active well-formed
disruption, deterministic shortest paths, safe path with at least two route
changes, complete finite positive route/fleet/timing data, and strict
`hold_hours < detour_hours`.

The only eligibility change is that a nominal path is accepted when it is
non-empty and either has one edge or has multiple edges whose route objects are
all identical. Recovery is the latest matching active constraint across every
nominal edge. Any mixed-route multi-edge nominal path delegates. The strategy
is read-only, deterministic, standard-library-only, fail-closed, and free of
scenario identities, I/O, randomness, wall-clock access, mutable globals, and
organizer imports.

## Fresh activation audit

The audit used a fresh `create_with_disruption()` context per derived timestamp,
called the organizer fallback route-preparation helper only as setup, then
evaluated all demand objects in context order without advancing the model or
writing Output. It sampled the midpoint of each integer day inside every valid
disruption window (50 timestamps, 19,000 demand-time observations).

- v3 control activations: 48;
- proposed candidate activations: 54;
- candidate-only activations: 6;
- candidate-only annual-TEU exposure proxy: 7,776;
- every candidate-only shape: nominal path 2 edges, safe path 3 edges, 2 safe
  route changes;
- observed mutation: none.

These are structural activation and exposure observations, not score
predictions. The ignored JSON audit is retained at
`.challenge/round1/results/contiguous_same_service_normalization_v5_20260811/activation_audit.json`.

## Fixed control and run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- layout: one worktree, one local branch (`main`), no push or publication;
- control: accepted v3 multi-transfer recovery hold;
- control loss: `19.084638612143134` over 72 periods;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- scenario: `create_with_disruption`;
- organizer seed: `2026`;
- `PYTHONHASHSEED`: `0`;
- warm-up: 140 days;
- measured horizon: 360 days;
- ATT interval: 5 days;
- required numbered periods: 72;
- candidate ATT evidence: `.challenge/round1/results/contiguous_same_service_normalization_v5_20260811/ATT_By_Statistics_Interval.csv`;
- candidate aggregate: `experiments/results/round1_contiguous_same_service_normalization_v5_20260811.json`;
- candidate log: `.challenge/round1/results/contiguous_same_service_normalization_v5_20260811/full_run.log`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

The active Output ATT is stale control evidence until a fresh completed run
writes it. Candidate bytes must be copied before scoring, sync, smoke, or
restoration.

## TDD and preflight

RED tests must demonstrate same-service multi-edge activation, later-edge
recovery, mixed-route delegation, malformed/inactive delegation, unchanged v3
behavior, no mutation, and real-context candidate-only activation. GREEN is
the minimum participant implementation. The required gates are locked uv
resolution/sync, Ruff format/lint, Ty, mypy, true non-integration coverage of
at least 90%, integration tests, Round 1 sync and byte comparison, smoke, two
byte-identical participant-only packages, restricted-material scans, one clean
worktree/branch, and no live simulator.

## Pre-run verification record

The preflight completed before any candidate simulation on launch HEAD
`5dfb1035cf39f08198e3dc34b8492712d004b41a`. The non-overwriting manifest is
`.challenge/round1/results/contiguous_same_service_normalization_v5_20260811/pre_run_manifest.json`
with SHA-256
`9c71e6ae7a71e37c19f4cf8241722b9db23b12af39362b741d1bf805d9a77e21`.

- candidate and synchronized runtime strategy: byte-identical,
  SHA-256 `96c0820c3b2c2567213847afe6ea735bc665505e1d1e254003ccbc069f5a2fc8`;
- control ATT snapshot and stale active Output: byte-identical,
  SHA-256 `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`,
  1,262 bytes;
- authoritative Round 1 baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- `uv lock --check` and `uv sync --locked --all-groups`: passed;
- Ruff format/check, Ty, and mypy: passed;
- non-integration suite: 229 passed, 9 deselected, true branch coverage
  `90.96%`;
- integration suite: 9 passed;
- Round 1 sync and participant/runtime comparison: passed;
- Round 1 smoke: `SMOKE_OK` and `smoke: OK`;
- two validation packages: byte-identical SHA-256
  `2f80bc6760c1429cf6516f3f8761af53fa492d28785334688bf258567ae19b81`,
  containing only the participant README and strategy;
- tracked/reachable restricted-material scans, `git diff --check`, clean Git
  status, one-worktree/one-branch layout, and no live simulator: passed.

No full run, candidate Output write, scoring of candidate bytes, tuning,
second candidate, package submission, push, merge, PR, or history rewrite had
occurred at this stop point.

## One-run decision and restoration

Exactly one full candidate run is allowed. After launch no code, tests,
thresholds, documentation, or policy may change. A crash, timeout, missing
fresh ATT, wrong period count, equality, worsening score, or failed gate is
rejection. If rejected, preserve ignored evidence and commit this result,
revert candidate implementation/test commits with `git revert`, synchronize
the accepted v3 strategy, restore the pinned v3 ATT snapshot byte-for-byte,
re-score it at `19.084638612143134`, and rerun all final gates. No second
candidate, tuning, submission archive, push, merge, PR, or history rewrite is
authorized by this report.

## Full-run result

Exactly one candidate simulation ran from launch HEAD
`b504f0351ecfabced7b9d257651206d524c69f59` with the frozen configuration. The
managed process exited `0`; the raw log contains `Period Result Output: Period
72 (Days 356-360)`, `Output Simulation Day: 360`, and `Simulation completed.`.
The organizer reported simulation runtime `00:24:56`.

- candidate strategy SHA-256:
  `96c0820c3b2c2567213847afe6ea735bc665505e1d1e254003ccbc069f5a2fc8`;
- candidate ATT SHA-256:
  `25827e3da6af17a54f54be88eedfa42924222ce9199f500236e4b5ae902d5f0b`;
- candidate ATT size: 1,262 bytes;
- numbered periods: 72;
- candidate mean ATT: `20.56986111111111` days;
- full-run log SHA-256:
  `b233d6b464ac81c82e1eb021a646783a23a6815ce9d328bd5a0fb5f580edb5d5`.

The fresh ATT and raw log were copied into the ignored evidence directory
before scoring, synchronization, smoke, or restoration.

## Score and decision

The official scorer, using the preserved candidate ATT and the authoritative
Round 1 baseline, reported 72 periods and cumulative resilience loss
`22.392546553745177`. The accepted v3 control is
`19.084638612143134`, so the exact delta is `+3.3079079416020427` and the
relative change is `+17.33282986819197%` (worse).

The candidate ATT was better in 12 periods, equal in 26, and worse in 34 than
the control. Mean ATT is descriptive only; the unchanged acceptance expression
was:

```text
22.392546553745177 < 19.084638612143134 - 1e-9
```

It is false. **Decision: REJECTED.** The aggregate scorer record is preserved
in ignored `experiments/results/round1_contiguous_same_service_normalization_v5_20260811.json`.

The result establishes that this exact same-service extension degraded the
fixed Round 1 scenario. It does not prove that every contiguous same-route
path is harmful in another scenario or seed.

## Rejection and restoration

This result record is committed before any restoration. The candidate code,
README, and candidate-only tests will be reverted in reverse order with
`git revert`; the accepted v3 strategy will then be synchronized, its pinned
ATT snapshot restored byte-for-byte, and its score rechecked at exactly
`19.084638612143134`. All final gates will be rerun. No tuning, duplicate run,
second candidate, package submission, push, merge, PR, or history rewrite is
part of this experiment.
