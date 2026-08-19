# Round 1 multi-TEU missed-connection buffer v20 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test one bounded, capacity-aware extension of the accepted v3 recovery hold and leave either an accepted v20 or fully restored v3 state.

**Architecture:** Keep the existing participant module and its v3 topology/timing pipeline. Add one pure helper for the smallest unique safe-route headway and one final multi-TEU branch after the unchanged v3 comparison. No booking or organizer object is mutated.

**Tech Stack:** Python 3.11+, uv, pytest, Ruff, ty, mypy, standard library only in submission code.

---

### Task 1: Freeze the experiment and prove RED

**Files:**
- Modify: `tests/unit/test_round1_multi_transfer_recovery_hold_v3.py`
- Modify: `tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py`

- [ ] Add `teu_size: int = 1` to the synthetic shipment helper and store it on the fixture object.
- [ ] Add focused tests asserting: v3 equality still delegates for one TEU; the same case returns `False` for two TEU; exact buffered equality delegates; non-integer, boolean, missing, and non-positive sizes delegate when only the extension could act; existing v3 strict holds remain `False` independent of size; all decisions are mutation-free.
- [ ] Add a real-context integration assertion that finds at least one same-context pair where one TEU delegates and two TEU returns `False`, with complete state snapshots unchanged.
- [ ] Run:
  `UV_CACHE_DIR=/tmp/wsc-uv-cache-v17 uv run pytest tests/unit/test_round1_multi_transfer_recovery_hold_v3.py tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py -q`.
  Expected: only the new multi-TEU candidate assertions fail against v3.
- [ ] Commit the RED contract without implementation.

### Task 2: Implement the minimum GREEN policy

**Files:**
- Modify: `submission/response_strategies/user_strategy.py`
- Modify: `submission/response_strategies/README.md`

- [ ] Add `_minimum_path_headway_hours(path)` that visits safe-path routes in encounter order, validates each with `_route_profile`, and returns the minimum finite positive unique-route headway or `None`.
- [ ] Preserve the existing strict `hold_hours < detour_hours` return. Only after it is false, require a non-boolean `numbers.Integral` TEU size greater than one and test the strict buffered comparison. Guard the sum against non-finite values.
- [ ] Keep all four public signatures exact, all other hooks as `None`, and all paths mutation-free.
- [ ] Update the participant README with the frozen v20 rule and no performance claim.
- [ ] Run the focused suite until GREEN, then Ruff and both type checkers.
- [ ] Commit the minimum implementation separately from RED.

### Task 3: Formal activation evidence

**Files:**
- Create ignored: `.challenge/round1/results/multi_teu_missed_connection_buffer_v20_20260819/activation_audit.py`
- Create ignored: `.challenge/round1/results/multi_teu_missed_connection_buffer_v20_20260819/activation_audit.json`
- Create: `docs/experiments/round1-multi-teu-missed-connection-buffer-v20.md`

- [ ] Run a non-overwriting audit over the 50 derived timestamps and 19,000 demand-time observations with fresh contexts.
- [ ] Require 48 v3 control holds, 48 one-TEU candidate holds, 59 two-TEU candidate holds, exactly 11 two-TEU candidate-only decisions, zero control-only decisions, unchanged Output, no mutation, and no model advancement.
- [ ] Record definition/hash, timestamps, observations, shapes, exposure proxy, limitations, and candidate identity in ignored JSON.
- [ ] Record only aggregate, non-restricted evidence in the tracked experiment report.

### Task 4: Preflight and immutable manifest

**Files:**
- Create ignored: `.challenge/round1/results/multi_teu_missed_connection_buffer_v20_20260819/pre_run_manifest.json`

- [ ] Run locked uv check/sync, Ruff format/lint, ty, mypy, non-integration branch coverage at least 90%, integration tests, Round 1 sync/cmp, direct smoke, and deterministic package twice.
- [ ] Freshly re-score the pinned v3 ATT to `19.084638612143134` over 72 periods; verify the pinned/active control SHA and baseline SHA.
- [ ] Verify one worktree, only local `main`, clean tracked status, restricted-material scans, and no live simulator.
- [ ] Freeze exact HEAD, participant/runtime/README/package hashes, member list, control/baseline hashes, stale Output size/mtime/hash, fixed command, and strict decision expression in a non-overwriting ignored manifest.

### Task 5: Run exactly once and decide

**Files:**
- Create ignored: `.challenge/round1/results/multi_teu_missed_connection_buffer_v20_20260819/full_run.log`
- Create ignored: `.challenge/round1/results/multi_teu_missed_connection_buffer_v20_20260819/ATT_By_Statistics_Interval.csv`
- Create ignored: `.challenge/round1/results/multi_teu_missed_connection_buffer_v20_20260819/score.json`
- Create ignored: `experiments/results/round1_multi_teu_missed_connection_buffer_v20_20260819.json`
- Modify: `docs/experiments/round1-multi-teu-missed-connection-buffer-v20.md`

- [ ] Revalidate the manifest byte-for-byte immediately before launch; any mismatch cancels the run.
- [ ] Launch only the frozen command once and monitor the same process to exit.
- [ ] Require exit 0, Day 360, Period 72, `Simulation completed`, and a fresh ATT write.
- [ ] Copy/hash the raw log and fresh ATT before any other operational command.
- [ ] Score the preserved ATT over exactly 72 periods and apply only `candidate_loss < 19.084638612143134 - 1e-9`.
- [ ] Record hashes, runtime, mean ATT, period comparison, exact loss/delta, and decision; commit the result before restoration.

### Task 6: Accept or restore, verify, and pause

**Files:**
- Modify on rejection via `git revert`: candidate code/tests/README only
- Modify: `docs/experiments/round1-multi-teu-missed-connection-buffer-v20.md`

- [ ] If accepted, keep v20 active. If rejected, revert candidate commits in reverse order, sync v3, restore its pinned ATT bytes, and re-score exactly.
- [ ] Run the complete final gate set, verify deterministic package contents, clean Git status, restricted-material absence, and no live process.
- [ ] Commit only the final tracked documentation correction if needed. Do not push, submit, tune, or run again. Pause with the exact result and final active strategy.
