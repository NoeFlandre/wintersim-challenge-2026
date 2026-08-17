# Round 1 port-closure exclusion v10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and evaluate one participant-only v10 rule that delegates v3 recovery holds whenever a matching closed-port disruption intersects the nominal direct edge, while retaining pure-leg holds.

**Architecture:** Keep the existing read-only v3 graph, timing, and fail-closed helpers. Add one pure classifier for matching active constraint kinds and one early delegation gate inside `_should_hold`; do not change any route, timing, mutation, or non-target hook behavior. Behavioral tests extend the existing v3 synthetic contract and real Round 1 context integration test.

**Tech Stack:** Python 3.11+, standard library participant code, pytest, uv, Ruff, Ty, mypy, the repository WSC CLI, and ignored organizer Round 1 runtime only for integration/audit/full-run evidence.

---

### Task 1: Commit the frozen experiment contract

**Files:**
- Create: `docs/superpowers/specs/2026-08-17-round1-port-closure-exclusion-v10-design.md`
- Create: `docs/superpowers/plans/2026-08-17-round1-port-closure-exclusion-v10.md`
- Create: `docs/experiments/round1-port-closure-exclusion-v10.md`

- [ ] **Step 1: Record the contract**

  Record the v3 control hashes, 50-timestamp/19,000-observation audit, 26
  port-involved control-only activations, `21,126` annual-TEU exposure proxy,
  exact policy, evidence paths under
  `.challenge/round1/results/port_closure_exclusion_v10_20260817/`, scorer
  threshold, and reverse-order restoration procedure.

- [ ] **Step 2: Self-review the documents**

  Run `rg -n 'TODO|TBD|placeholder|20\.436|fallback_control_seed0'` over the
  three new files. Remove every stale fallback value and ensure the contract
  says no full run is allowed until preflight and the non-overwriting manifest
  pass.

- [ ] **Step 3: Commit the frozen design**

  ```bash
  git add docs/superpowers/specs/2026-08-17-round1-port-closure-exclusion-v10-design.md \
    docs/superpowers/plans/2026-08-17-round1-port-closure-exclusion-v10.md \
    docs/experiments/round1-port-closure-exclusion-v10.md
  git commit -m "docs: freeze round1 port closure exclusion v10"
  ```

### Task 2: Add the RED behavioral contract

**Files:**
- Modify: `tests/unit/test_round1_multi_transfer_recovery_hold_v3.py`
- Modify: `tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py`

- [ ] **Step 1: Add synthetic mixed-constraint RED tests**

  Add a fixture using the existing `_qualifying_fixture`, append a matching
  `_berth_plan` for the nominal edge's intermediate port alongside the existing
  `_leg_plan`, and assert the public hook returns `None` with the complete
  `_freeze((context, shipment))` snapshot unchanged. Add a synthetic
  port-involved multi-transfer case with the same assertion. Add a companion
  pure-leg assertion that still returns `False` so the candidate cannot remove
  the v9-proven subset.

- [ ] **Step 2: Add the real-context RED test**

  Sample the existing identity-free active-window timestamps. For each fresh
  context, run the organizer route-preparation helper, construct a shipment for
  each demand, and use the existing private `_should_hold`/graph helpers only
  to locate a v3 hold whose matching constraint-kind set contains `port`.
  Assert the public candidate call returns `None` and the complete real-context
  snapshot is unchanged. Do not print organizer names or IDs.

- [ ] **Step 3: Run the focused RED selection**

  ```bash
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run pytest -q \
    tests/unit/test_round1_multi_transfer_recovery_hold_v3.py \
    tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py
  ```

  Expected result against untouched v3: only the new mixed/port delegation
  assertions fail; existing v3 controls and mutation checks pass. If collection
  or fixtures fail, fix the test harness before implementing code.

- [ ] **Step 4: Commit RED**

  ```bash
  git add tests/unit/test_round1_multi_transfer_recovery_hold_v3.py \
    tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py
  git commit -m "test: specify round1 port closure exclusion v10"
  ```

### Task 3: Implement the minimum participant policy

**Files:**
- Modify: `submission/response_strategies/user_strategy.py`
- Modify: `submission/response_strategies/README.md`

- [ ] **Step 1: Add the classifier before changing the decision**

  Add a read-only helper immediately after `_edge_constraint_recovery`:

  ```python
  def _edge_constraint_kinds(edge: _Edge, state: _ActiveState) -> tuple[str, ...]:
      leg_ids = {id(leg) for leg in edge.legs}
      arrival_names = {
          name
          for name in (_port_name(port) for port in (*edge.intermediate_ports, edge.arrival))
          if name is not None
      }
      return tuple(
          sorted(
              {
                  constraint.kind
                  for constraint in state.constraints
                  if (
                      constraint.kind == "leg"
                      and constraint.target_identity in leg_ids
                  )
                  or (
                      constraint.kind == "port"
                      and constraint.arrival_name in arrival_names
                  )
              }
          )
      )
  ```

- [ ] **Step 2: Add the one frozen gate**

  Immediately after the existing `route_change_count < 2` delegation in
  `_should_hold`, add:

  ```python
      if _edge_constraint_kinds(nominal_path[0], state) != ("leg",):
          return False
  ```

  This preserves only pure-leg v3 holds; all mixed/port-involved or malformed
  unmatched cases delegate through the existing `return False` -> public `None`
  path. Do not alter timing, graph, route-change, exception, or hook code.

- [ ] **Step 3: Update participant README**

  State that v10 retains the accepted v3 hold only for direct edges affected
  solely by congested legs and delegates when a matching closed port is present;
  keep all submission/runtime restrictions unchanged.

- [ ] **Step 4: Run focused GREEN and static checks**

  ```bash
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run pytest -q \
    tests/unit/test_round1_multi_transfer_recovery_hold_v3.py \
    tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run ruff format --check submission tests
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run ruff check submission tests
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run ty check src/wsc2026_tools submission
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run mypy src/wsc2026_tools submission
  ```

  Expected focused GREEN: every synthetic and real mixed/port delegation test,
  pure-leg retention test, inherited v3 test, and mutation test passes.

- [ ] **Step 5: Commit the implementation**

  ```bash
  git add submission/response_strategies/user_strategy.py submission/response_strategies/README.md
  git commit -m "feat: exclude port closure recovery holds"
  ```

### Task 4: Record activation evidence and review the candidate

**Files:**
- Create ignored: `.challenge/round1/results/port_closure_exclusion_v10_20260817/activation_audit.json`

- [ ] **Step 1: Write the audit record atomically and refuse overwrites**

  Record schema version, round, control/candidate strategy hashes, identity-free
  sample rule, 19,000 observations, control activations `48`, candidate
  activations `22`, control-only activations `26`, exposure `21,126`, shape
  counts, `no_mutation: true`, and the limitation that activation is not score
  evidence. Keep the file ignored and never copy organizer source into tracked
  paths.

- [ ] **Step 2: Review the candidate diff**

  Confirm only participant code/README and intended tests changed, the public
  signatures remain exact, no forbidden imports/state/I/O appeared, and the
  candidate gate is exactly one classifier plus one delegation branch.

### Task 5: Run the complete preflight and freeze launch identities

**Files:**
- Modify: `docs/experiments/round1-port-closure-exclusion-v10.md`
- Create ignored: `.challenge/round1/results/port_closure_exclusion_v10_20260817/pre_run_manifest.json`

- [ ] **Step 1: Run all required gates**

  ```bash
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv lock --check
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv sync --locked --all-groups
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run ruff format --check .
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run ruff check .
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run ty check src/wsc2026_tools submission
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run mypy src/wsc2026_tools submission
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run pytest -m 'not integration' --cov=src/wsc2026_tools --cov=submission --cov-branch --cov-report=term-missing --cov-fail-under=90
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run pytest -m integration -q
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run wsc2026 sync --round round1
  cmp submission/response_strategies/user_strategy.py .challenge/round1/source/response_strategies/user_strategy.py
  cmp submission/response_strategies/README.md .challenge/round1/source/response_strategies/README.md
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run wsc2026 smoke --round round1
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run wsc2026 package --team ValidationTeam --round 1
  UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 uv run wsc2026 package --team ValidationTeam --round 1
  git diff --check
  ```

- [ ] **Step 2: Verify control and safety identities**

  Re-score the pinned v3 ATT to `19.084638612143134`, record its SHA and stale
  Output metadata, verify the candidate/runtime strategy hash and package
  member list, prove one worktree/`main`, no live simulator, and no restricted
  tracked/reachable archive/blob/path.

- [ ] **Step 3: Commit the immutable pre-run report**

  Record the exact candidate strategy SHA, package hashes, all gate results,
  launch HEAD, command, evidence destinations, and acceptance expression in the
  tracked report. Write a non-overwriting manifest only after those values
  match. Commit with:

  ```bash
  git add docs/experiments/round1-port-closure-exclusion-v10.md
  git commit -m "docs: record v10 pre-run verification"
  ```

### Task 6: Execute exactly one candidate run

- [ ] **Step 1: Recheck launch state**

  Confirm the committed HEAD, strategy/runtime byte identity, pinned control
  hash, stale Output mtime/hash, empty candidate evidence destinations, clean
  Git status, and no live `wsc2026`/organizer process.

- [ ] **Step 2: Launch and monitor the one process**

  ```bash
  PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache-0817 \
    uv run wsc2026 run --round round1 --full 2>&1 | tee /tmp/wsc_v10_full_run.log
  ```

  Poll the same managed session below 60 seconds until explicit Day 360,
  Period 72, `Simulation completed`, and fresh CSV markers. Do not edit code,
  change thresholds, or start another run after launch.

- [ ] **Step 3: Preserve evidence before any overwrite**

  Copy the fresh ATT and log to the predeclared ignored v10 directory, verify
  byte identity, SHA-256, 72 numbered periods, finite values, header, size,
  mtime, and mean ATT before invoking score, sync, smoke, or restoration.

### Task 7: Score, decide, and leave a clean state

- [ ] **Step 1: Score the preserved candidate**

  Run `uv run wsc2026 score --scenario-att .challenge/round1/results/port_closure_exclusion_v10_20260817/ATT_By_Statistics_Interval.csv --baseline-att .challenge/round1/source/Output/Baseline_ATT_By_Statistics_Interval.csv --json`, save the full JSON in the ignored aggregate, and compute candidate/control better/equal/worse counts.

- [ ] **Step 2: Apply the immutable decision**

  Accept only if `candidate_loss < 19.084638612143134 - 1e-9`. On acceptance,
  retain v10 and run final gates. On rejection/equality/invalidity, commit the
  result report first, revert the implementation and RED commits in reverse
  order, synchronize v3, restore the pinned v3 ATT snapshot, re-score exact,
  and rerun all final gates. Never manually recreate the strategy.

- [ ] **Step 3: Final verification**

  Run lock/sync, Ruff, Ty, mypy, branch coverage, all integration tests,
  sync/cmp, smoke, deterministic package twice, control score/hash, restricted
  scans, diff check, clean status, one-worktree/`main`, and no-live-process.
  Update README, `docs/round1-readiness.md`, and `docs/challenge-overview.html`
  with the v10 result and current scored-count only after the decision is final.
