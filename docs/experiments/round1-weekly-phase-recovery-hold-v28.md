# Round 1 weekly-phase recovery hold v28

**Status: PRE-RUN REVIEW — implementation and structural audit passed; full run not yet started.**

## Purpose

This is one separately named experiment from the accepted Round 1 v3 control.
It tests a single additive refinement to the v3 initial-booking hold. The
experiment must remain one candidate and one full run; no tuning or duplicate
run is allowed.

## Frozen control

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and one branch: `main`;
- current control: accepted multi-transfer recovery hold v3;
- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control loss: `19.084638612143134` over 72 periods;
- baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`.

## Hypothesis and exact delta

The v3 estimate uses half a derived headway and can delegate even when the
organizer's declared weekly release phase makes the direct recovery hold faster
than the multi-transfer safe detour. The candidate keeps every existing v3
hold and adds `False` only when all v3 topology/recovery prerequisites hold,
v3 itself would delegate, and a read-only phase walk using each route's
`start_day_of_week` yields:

```text
recovery_wait + phase_nominal_service_time < phase_safe_service_time
```

Phase timing adds sailing time from deployed-vessel mean speed and the next
weekly release wait at each route transition. Invalid or uncertain data
delegates. No booking is installed by the participant and the other three
hooks remain `None` delegates.

## Structural exploration

A read-only exploratory audit over the existing helper-derived 50 valid
midpoints and 19,000 demand observations found nine phase-positive cases where
v3 delegates, and one v3 hold that a phase replacement would suppress. The
selected additive policy preserves all 48 v3 holds and therefore does not use
the replacement's suppression. The exploratory result is reachability evidence
only; it does not predict the official score. A post-GREEN audit must repeat the
same sample with the actual candidate hook, prove no mutation/Output write, and
record immutable evidence before any run.

The actual candidate-hook audit completed before preflight using the same fresh
contexts, all demands in context order, and a Git-loaded v3 control:

- candidate strategy SHA-256: `dfe4613546480aee8015d172e91e27e1e9303872395006f6c321c6c80822f299`;
- 19,000 observations over 50 timestamps;
- candidate activations: `57`;
- preserved v3/control activations: `48`;
- candidate-only activations: `9`;
- control-only activations: `0`;
- candidate-only annual-TEU exposure proxy: `6,852`;
- shape counts: safe edges/route changes `3/2` (`2`), `4/2` (`3`),
  `5/3` (`4`);
- `no_mutation: true`, `model_advanced: false`, `output_written: false`;
- active Output remained byte-identical to the pinned v3 ATT
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.

Private machine-readable evidence is
`.challenge/round1/results/weekly_phase_recovery_hold_v28_20260820/activation_audit.json`.
Activation is structural evidence only and is not a score prediction.

## TDD and implementation record

- RED contract commit: `0331398`;
- formatting-only test correction: `bdbba87`;
- GREEN implementation commit: `a077ee9`;
- candidate strategy SHA-256:
  `dfe4613546480aee8015d172e91e27e1e9303872395006f6c321c6c80822f299`;
- focused v28 plus v3 contract tests: `42 passed`;
- focused Ruff format/lint, Ty, and mypy: passed.

The candidate changes only participant code, participant README, and the
candidate tests. It adds no organizer import, external capability, mutable
state, booking mutation, or other hook behavior.

## Pre-run gate record

After synchronization, the complete preflight passed before any full run:

- participant/runtime strategy SHA-256: `dfe4613546480aee8015d172e91e27e1e9303872395006f6c321c6c80822f299`;
- participant/runtime README SHA-256:
  `ce2cbc5f3b9b667015d5acd98d5df41486d556c61f091e188a11a990c6408421`;
- `uv lock --check`: passed (29 packages);
- `uv sync --locked --all-groups`: passed (29 resolved, 25 checked);
- Ruff format/check: passed;
- Ty: passed;
- mypy: passed (8 source files);
- non-integration tests/branch coverage: `230 passed, 8 deselected`,
  `90.41%` true branch coverage;
- integration tests: `8 passed, 230 deselected`;
- Round 1 sync and byte comparison: passed;
- Round 1 smoke: `SMOKE_OK`;
- deterministic participant-only package twice: SHA-256
  `86ea4f2783918dfa49fa354107dbc988a8bf547541f443d745318ffdeb0ae694`,
  6,380 bytes, members only
  `Round1_V28Validation/response_strategies/README.md` and
  `Round1_V28Validation/response_strategies/user_strategy.py`;
- active Output after smoke remained the pinned control ATT SHA
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`,
  1,262 bytes;
- authoritative baseline ATT SHA:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- fresh control re-score: `19.084638612143134`, exactly 72 periods;
- `git diff --check`, clean Git state, one worktree/branch, restricted scans,
  and no-live-simulator checks: passed.

The non-overwriting launch manifest is created only after this documentation
commit and pins the final launch HEAD, hashes, package, control, stale Output,
audit, run command, evidence paths, and threshold. A mismatch cancels launch.

## Run contract

- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / interval: `140` / `360` / `5` days;
- required numbered periods: `72`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`;
- candidate evidence directory:
  `.challenge/round1/results/weekly_phase_recovery_hold_v28_20260820/`;
- ignored aggregate:
  `experiments/results/round1_weekly_phase_recovery_hold_v28_20260820.json`.

The fresh ATT and raw log must be preserved before scoring, synchronization,
smoke, packaging, or restoration. Equality, worsening, invalid/incomplete
output, a crash, or any failed gate is rejection. Rejection requires a result
commit, reverse-order Git reverts of only v28 code/tests, v3 synchronization,
byte-identical pinned ATT restoration, exact control re-score, and all final
gates. No push, merge, PR, upload, submission, history rewrite, tuning, or
second candidate is authorized.

## TDD and implementation boundary

RED tests must fail only because the untouched v3 implementation does not add
the phase-positive decision. GREEN must add the smallest standard-library-only
helpers and preserve v3 behavior and fail-closed validation. Tests must cover
phase boundaries, invalid values, route transitions, mutation-free delegation,
existing v3 holds, exact signatures, and package restrictions. The full run is
not authorized until the actual-hook audit, all quality gates, deterministic
participant-only packaging, fresh v3 control score, and immutable launch
manifest are green.
