# Round 1 weekly-phase recovery hold v28 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one read-only, additive weekly-departure-phase recovery hold to the accepted Round 1 v3 strategy and validate it through one controlled full run.

**Architecture:** Keep the existing v3 graph and recovery helpers. Add a small phase-time helper that walks an already-selected path, adds the next configured weekly release wait at each route transition, and returns `None` on malformed data. The booking hook first preserves v3's result, then evaluates the phase predicate only for v3 delegations; no booking mutation is added.

**Tech Stack:** Python 3.11+, standard library participant code, pytest, uv, Ruff, Ty, mypy, and the repository WSC CLI.

---

### Task 1: Add the frozen RED contract

**Files:**
- Create: `tests/unit/test_round1_weekly_phase_recovery_hold_v28.py`
- Modify: `docs/experiments/round1-weekly-phase-recovery-hold-v28.md`

- [ ] **Step 1: Write tests before production code**

  Build the existing lightweight route/shipment fixtures used by
  `tests/unit/test_round1_multi_transfer_recovery_hold_v3.py`. Add tests for:

  - a phase-positive v3 delegation returning `False` without mutation;
  - a phase-negative delegation remaining `None`;
  - an existing v3 hold remaining `False` even when phase timing is negative;
  - exact weekly phase boundary (`start_day_of_week == current fractional day`)
    and a one-microsecond-after boundary;
  - invalid, boolean, NaN, infinity, and out-of-range phase values delegating;
  - route transitions using context order and preserving all public signatures;
  - inactive disruption and malformed graph state delegating unchanged.

- [ ] **Step 2: Run the focused RED selection**

  Run:

  ```bash
  env -u PYTHONPATH UV_CACHE_DIR=/tmp/wsc-v28-cache uv run --no-sync pytest -q tests/unit/test_round1_weekly_phase_recovery_hold_v28.py
  ```

  Expected result: the phase-positive behavior fails because the untouched v3
  strategy returns `None`; the control, boundary, and mutation assertions must
  otherwise collect and pass. Fix fixtures if the failure is a collection or
  type error, then rerun until the intended behavior is the only failure.

- [ ] **Step 3: Commit the RED contract**

  ```bash
  git add tests/unit/test_round1_weekly_phase_recovery_hold_v28.py docs/experiments/round1-weekly-phase-recovery-hold-v28.md
  git commit -m "test: define weekly phase recovery hold v28 contract"
  ```

### Task 2: Implement the minimal phase predicate

**Files:**
- Modify: `submission/response_strategies/user_strategy.py`
- Modify: `submission/response_strategies/README.md`

- [ ] **Step 1: Add a pure route-release wait helper**

  Implement a helper that validates `route.start_day_of_week` as a finite,
  non-boolean number in `[0.0, 7.0)`, computes the current Monday-based
  fractional weekday from a supplied `datetime`, and returns the next weekly
  release wait in hours. It must not read the clock or mutate anything.

- [ ] **Step 2: Add a phase-aware path-time helper**

  Walk the existing `_Edge` tuple in order. Reuse `_route_profile` for sailing
  speed. At each first edge or route-identity transition, add the validated
  release wait at `now + accumulated_hours`; then add edge sailing time. Reject
  malformed/non-finite/non-positive values by returning `None`.

- [ ] **Step 3: Extend `_should_hold` additively**

  Keep the current v3 predicate and return `True` immediately when it holds.
  If v3 delegates but all topology and recovery prerequisites are available,
  compute phase-aware nominal and safe times and return `True` only when the
  full-precision recovery-plus-phase-nominal value is strictly below the
  phase-safe value. Otherwise return `False`.

- [ ] **Step 4: Update participant documentation only for this policy**

  State that v3 holds are preserved and the additive phase extension uses
  `start_day_of_week` read-only; retain the standard-library and fail-closed
  restrictions. Do not add configuration or unrelated refactors.

- [ ] **Step 5: Run focused GREEN checks**

  ```bash
  env -u PYTHONPATH UV_CACHE_DIR=/tmp/wsc-v28-cache uv run --no-sync pytest -q tests/unit/test_round1_weekly_phase_recovery_hold_v28.py tests/unit/test_round1_multi_transfer_recovery_hold_v3.py
  env -u PYTHONPATH UV_CACHE_DIR=/tmp/wsc-v28-cache uv run --no-sync ruff format --check submission tests/unit/test_round1_weekly_phase_recovery_hold_v28.py
  env -u PYTHONPATH UV_CACHE_DIR=/tmp/wsc-v28-cache uv run --no-sync ruff check submission tests/unit/test_round1_weekly_phase_recovery_hold_v28.py
  env -u PYTHONPATH UV_CACHE_DIR=/tmp/wsc-v28-cache uv run --no-sync ty check submission
  env -u PYTHONPATH UV_CACHE_DIR=/tmp/wsc-v28-cache uv run --no-sync mypy submission
  ```

- [ ] **Step 6: Commit the implementation**

  ```bash
  git add submission/response_strategies/user_strategy.py submission/response_strategies/README.md
  git commit -m "feat: add weekly phase recovery hold v28"
  ```

### Task 3: Prove real-context activation and freeze the run

**Files:**
- Create ignored: `.challenge/round1/results/weekly_phase_recovery_hold_v28_20260820/activation_audit.py`
- Create tracked: `docs/experiments/round1-weekly-phase-recovery-hold-v28.md` updates

- [ ] **Step 1: Run the actual-hook audit**

  Use fresh contexts at every helper-derived valid disruption midpoint and
  every demand in context order. Compare the candidate to a control module
  loaded from the pre-v28 strategy object; require 50 timestamps, 19,000
  observations, 48 preserved v3 holds, at least one candidate-only phase hold,
  no candidate suppression of v3, unchanged context/shipment snapshots, and
  unchanged Output ATT metadata. Write an atomic, refuse-overwrite JSON record
  with hashes and limitations.

- [ ] **Step 2: Run all mandatory preflight gates**

  Run lock/sync, Ruff format/check, Ty, mypy, non-integration coverage with the
  unrounded `>=90.00%` threshold, integration tests, Round 1 sync/cmp, smoke,
  deterministic package twice with member inspection, diff/restricted scans,
  and a no-live-process check. Freshly re-score v3 and record its ATT/hash and
  stale Output metadata.

- [ ] **Step 3: Freeze a non-overwriting launch manifest**

  Pin candidate HEAD, participant/runtime hashes, package hashes/members,
  control/baseline hashes and score, audit hash/counts, stale Output, exact
  command, evidence paths, and strict acceptance expression. Stop if any pin
  differs.

### Task 4: Execute one run and decide

- [ ] **Step 1: Launch exactly once**

  ```bash
  env -u PYTHONPATH PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-v28-cache uv run --no-sync wsc2026 run --round round1 --full > .challenge/round1/results/weekly_phase_recovery_hold_v28_20260820/full_run.log 2>&1
  ```

  Monitor the same process below 60 seconds until exit, Day 360, Period 72,
  `Simulation completed`, and a fresh ATT write. Do not edit code or rerun.

- [ ] **Step 2: Preserve and score before any overwrite**

  Copy the fresh ATT to the predeclared evidence directory, record bytes/hash,
  validate 72 finite periods, and run `wsc2026 score --json` against the pinned
  baseline. Record per-period better/equal/worse counts and full precision.

- [ ] **Step 3: Apply the frozen threshold**

  Accept only `candidate_loss < 19.084638612143134 - 1e-9`. Equality or any
  worsening is rejection. Commit the result before any restoration.

### Task 5: Restore or retain and verify

- [ ] **Step 1: If rejected or invalid, revert only v28 code/tests**

  Revert the implementation commit, then the RED test commit in reverse order;
  retain design, plan, audit, and result records. Synchronize v3 from the
  restored participant files and restore the pinned v3 ATT snapshot byte-for-
  byte. Never recreate it manually.

- [ ] **Step 2: Run final gates and clean-state checks**

  Re-run lock/sync, Ruff, Ty, mypy, coverage, integration, sync/cmp, smoke,
  deterministic packaging twice, exact v3 score/hash, diff check, restricted
  scans, one-worktree/one-branch check, and no-live-process check.

- [ ] **Step 3: Update the result report**

  Record branch/HEAD, strategy hashes, audit, package members/hash, run markers,
  candidate and control scores, decision, evidence paths, revert/restore
  commits, final gates, and forbidden-action confirmation. Leave `main` clean.
