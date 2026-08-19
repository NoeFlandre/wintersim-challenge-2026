# Round 1 equal-distance one-transfer tie v27 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test one narrowly isolated half of v25 by installing only exact-distance safe paths that reduce two service-route changes to one, while preserving the accepted v3 hold and submission boundary.

**Architecture:** Extend the existing participant-only `user_strategy.py` with deterministic pure path-analysis helpers and a transactional booking installer. Keep the four-hook public surface unchanged; only the initial-booking hook may claim a decision. Use a real-context integration contract and a private 19,000-observation audit before the full run.

**Tech Stack:** Python 3.11-compatible standard library participant code, `uv`, Ruff, Ty, mypy, pytest/coverage, and the existing WSC CLI.

---

### Task 1: Commit the frozen experiment contract

**Files:**
- Create: `docs/superpowers/specs/2026-08-19-round1-equal-distance-one-transfer-tie-v27-design.md`
- Create: `docs/superpowers/plans/2026-08-19-round1-equal-distance-one-transfer-tie-v27.md`
- Create: `docs/experiments/round1-equal-distance-one-transfer-tie-v27.md`

- [ ] **Step 1: Record the contract**

Record the v3 strategy/ATT/baseline hashes, score `19.084638612143134`, exact
acceptance expression, fixed Round 1 command/configuration, private evidence
paths, v27 policy, audit result, one-run rule, and reverse-order restoration.
Do not include organizer source, input rows, or names in tracked docs.

- [ ] **Step 2: Self-review the documents**

Run:

```bash
rg -n 'TODO|TBD|FIXME' docs/superpowers/specs/2026-08-19-round1-equal-distance-one-transfer-tie-v27-design.md docs/superpowers/plans/2026-08-19-round1-equal-distance-one-transfer-tie-v27.md docs/experiments/round1-equal-distance-one-transfer-tie-v27.md
git diff --check
```

Expected: no placeholders and no whitespace errors. Confirm the design names
one hook, one `2→1` policy delta, and no `1→0` behavior.

- [ ] **Step 3: Commit the contract**

```bash
git add docs/superpowers/specs/2026-08-19-round1-equal-distance-one-transfer-tie-v27-design.md docs/superpowers/plans/2026-08-19-round1-equal-distance-one-transfer-tie-v27.md docs/experiments/round1-equal-distance-one-transfer-tie-v27.md
git commit -m "docs: define round1 equal-distance one-transfer tie v27"
```

### Task 2: Add the RED behavior contract

**Files:**
- Create: `tests/unit/test_round1_equal_distance_one_transfer_tie_v27.py`
- Modify: `tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py`

- [ ] **Step 1: Write the failing tests before production code**

Build a synthetic topology with one disrupted nominal edge, a fallback safe
path of three booking edges/two route changes, and an exact-distance safe path
of two booking edges/one route change. Assert that the untouched v3 adapter
returns `None` where v27 requires `True`, installs only the two tied-path
bookings, and leaves fallback route references empty. Add the nearest negative
case where the only improvement is `1→0`; it must remain `None`. Also cover a
non-tie, v3 `False` hold precedence, malformed/duplicate ports, unavailable
Booking constructor, append failure rollback, exact public signatures, and
mutation-free delegation.

Use a test-only `Booking` module injected through `sys.modules`; never import
the organizer module in tracked participant code or tests outside that test
fixture. Keep the new test module name unique to avoid pytest import collisions.

- [ ] **Step 2: Run RED and capture the intended failure**

```bash
uv run pytest tests/unit/test_round1_equal_distance_one_transfer_tie_v27.py -q
```

Expected: collection succeeds; only the new `2→1` installation assertions
fail because untouched v3 delegates. Fixture, signature, malformed, and
rollback tests must not fail for unrelated reasons. Fix the test fixture if
collection or setup fails; do not write production code yet.

- [ ] **Step 3: Add the real-context contract**

Extend the existing real-context sweep so `True` is accepted only when the
candidate installs a complete chain. For every other decision, compare a full
context/shipment snapshot before and after. Assert the audit-derived `2→1`
shape is observed and the v3 `False` holds remain unchanged. Do not advance a
model or write Output in the integration test.

- [ ] **Step 4: Commit RED**

```bash
git add tests/unit/test_round1_equal_distance_one_transfer_tie_v27.py tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py
git commit -m "test: define round1 one-transfer tie v27 contract"
```

### Task 3: Implement the minimum participant policy

**Files:**
- Modify: `submission/response_strategies/user_strategy.py`
- Modify: `submission/response_strategies/README.md`

- [ ] **Step 1: Add pure path helpers**

Add the smallest helpers needed to:

```python
def _path_distance(path): ...
def _route_change_count(path): ...
def _fewer_transfer_equal_path(context, origin, destination, edges, fallback_path): ...
```

The solver must restrict candidates to exact shortest-distance paths, use
context/edge order for deterministic ties, reject malformed/non-finite graph
data, and return `None` on uncertainty. It must never mutate runtime objects.

- [ ] **Step 2: Add transactional installation**

Validate contiguity and segment bounds, construct all `Booking` objects before
publishing references, snapshot every touched route list, then publish the
shipment chain and reverse references. On anticipated constructor or append
failure restore the shipment and every touched route exactly and return
`None`; never return `True` after a partial install.

- [ ] **Step 3: Wire the exact `2→1` gate**

Keep `_should_hold(context, now, shipment)` first and unchanged. Only if it
returns false, compute the fallback safe path and tied minimum-change path.
Require exactly `fallback_changes == 2` and `candidate_changes == 1`; otherwise
delegate `None`. Preserve unconditional `None` in the other three hooks.

- [ ] **Step 4: Run focused GREEN**

```bash
uv run pytest tests/unit/test_round1_equal_distance_one_transfer_tie_v27.py tests/unit/test_round1_multi_transfer_recovery_hold_v3.py -q
uv run pytest tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py -q
```

Expected: all v27 and retained-v3 tests pass, including real-context state
parity. Correct code or fixture assumptions, never expectations, if a test
fails.

- [ ] **Step 5: Run changed-surface quality checks and commit GREEN**

```bash
uv run ruff format submission/response_strategies tests/unit/test_round1_equal_distance_one_transfer_tie_v27.py tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py
uv run ruff check submission/response_strategies tests/unit/test_round1_equal_distance_one_transfer_tie_v27.py tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py
uv run ty check submission
uv run mypy submission
git add submission/response_strategies/user_strategy.py submission/response_strategies/README.md tests/unit/test_round1_equal_distance_one_transfer_tie_v27.py tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py
git commit -m "feat: install exact-distance one-transfer ties"
```

### Task 4: Complete the mandatory preflight

**Files:**
- Modify: `docs/experiments/round1-equal-distance-one-transfer-tie-v27.md`

- [ ] **Step 1: Run all gates**

```bash
uv lock --check
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run ty check src/wsc2026_tools submission
uv run mypy src/wsc2026_tools submission
uv run pytest -m "not integration" --cov=src/wsc2026_tools --cov=submission --cov-branch --cov-report=term-missing --cov-fail-under=90
uv run pytest -m integration -q
uv run wsc2026 sync --round round1
cmp submission/response_strategies/user_strategy.py .challenge/round1/source/response_strategies/user_strategy.py
cmp submission/response_strategies/README.md .challenge/round1/source/response_strategies/README.md
uv run wsc2026 smoke --round round1
uv run wsc2026 package --team ValidationTeam --round 1
uv run wsc2026 package --team ValidationTeam --round 1
git diff --check
```

Expected: every command exits zero, coverage is at least 90.00% unrounded,
smoke prints `SMOKE_OK`, and the two package archives are byte-identical and
contain only the two participant files. Move generated archives outside the
repository after hashing. Verify restricted history/path scans, one worktree,
sole `main`, clean tracked status, and no live simulator before launch.

- [ ] **Step 2: Freeze the non-overwriting manifest**

Write the ignored v27 manifest only after all gates pass. Pin candidate HEAD,
participant/runtime hashes and byte identity, package SHA/member list, v3 and
baseline ATT hashes/score/periods, stale Output metadata, exact command,
acceptance expression, evidence paths, and no-live-process proof. Refuse to
overwrite an existing manifest.

- [ ] **Step 3: Commit the pre-run documentation**

Record all gate outputs and manifest hash in the tracked v27 report, then:

```bash
git add docs/experiments/round1-equal-distance-one-transfer-tie-v27.md
git commit -m "docs: freeze round1 one-transfer tie v27 preflight"
```

### Task 5: Run one candidate and decide

**Files:**
- Modify: `docs/experiments/round1-equal-distance-one-transfer-tie-v27.md`
- Write ignored: `.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/full_run.log`
- Write ignored: `.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/ATT_By_Statistics_Interval.csv`

- [ ] **Step 1: Revalidate launch identities**

Immediately before launch, recheck manifest HEAD, strategy/runtime/package
hashes, v3 control and baseline hashes/score, stale Output metadata, clean
Git state, restricted scans, and no live process. Any mismatch cancels the run.

- [ ] **Step 2: Launch exactly once**

```bash
PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache-v27 \
uv run wsc2026 run --round round1 --full \
  > .challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/full_run.log 2>&1
```

Monitor this same process below 60 seconds until exit. Do not edit code,
restart, duplicate, tune, or score stale Output after launch.

- [ ] **Step 3: Preserve before scoring**

Require exit 0, Day 360, Period 72, `Simulation completed`, and a fresh CSV
write. Copy the fresh ATT to the predeclared evidence path before any sync,
smoke, package, restore, or other command that can overwrite Output. Hash and
validate exactly 72 numbered rows and finite ATT values.

- [ ] **Step 4: Score and apply the immutable gate**

Score the preserved ATT against the authoritative baseline and record full
precision, per-period better/equal/worse counts, mean ATT, delta, relative
change, and raw log/ATT hashes. Accept only:

```text
candidate_loss < 19.084638612143134 - 1e-9
```

### Task 6: Restore on rejection or finalize acceptance

- [ ] **Step 1: Record the result before cleanup**

Write the ignored aggregate and tracked result section without changing the
policy or threshold. If the candidate ties, worsens, crashes, or is invalid,
mark it rejected.

- [ ] **Step 2: Revert and restore on rejection**

Commit the rejection report, then `git revert` the GREEN and RED commits in
reverse order. Synchronize v3 from `submission/`, restore the pinned v3 ATT
snapshot byte-for-byte, and re-score exactly `19.084638612143134` over 72
periods. Never recreate the adapter by hand.

- [ ] **Step 3: Run final gates**

Repeat lock/sync, Ruff, Ty, mypy, coverage, unit/integration tests, sync/cmp,
smoke, deterministic package twice, restricted scans, `git diff --check`,
clean status, and no-live-process checks. Update the report with the restored
strategy/ATT hashes and final package members. Leave v3 active unless the
candidate strictly beats the control.
