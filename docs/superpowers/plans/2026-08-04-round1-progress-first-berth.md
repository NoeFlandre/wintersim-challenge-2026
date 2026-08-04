# Round 1 progress-first berth priority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and evaluate exactly one package-valid Round 1 berth-selection hypothesis that prefers vessels able to progress immediately during a mixed active disruption queue, while preserving the pinned fallback everywhere else.

**Architecture:** Keep `UserStrategy` as the public adapter and put the read-only policy in one small participant-owned helper. The helper derives active disruption identity from runtime object references, classifies each vessel's next physical leg, and reuses the fallback's normalized ranking only among progress-capable vessels. Any malformed or ambiguous state delegates with `None`; no organizer code, constants tied to the scenario, or mutable state enters the package.

**Tech Stack:** Python 3.11+, `uv`, pytest, Ruff, `ty`, mypy, the repository's `wsc2026` CLI, and the ignored Round 1 organizer source only for local integration verification.

---

### Task 1: Isolate the experiment and commit its contract

**Files:**
- Create: `docs/experiments/round1-progress-first-berth-v1.md`
- Modify: none outside the new report

- [ ] **Step 1: Create the worktree from the approved main commit**

Run from the repository root:

```bash
git status --short --branch
git worktree add /private/tmp/wsc-round1-progress-first-berth-v1 -b codex/round1-progress-first-berth-v1 main
cp -R /Users/noeflandre/wintersim-challenge-2026/.challenge/round1 /private/tmp/wsc-round1-progress-first-berth-v1/.challenge/round1
```

The new worktree must start clean. The copied `.challenge` tree is ignored and must never be staged.

- [ ] **Step 2: Record the precommitted experiment contract**

Create `docs/experiments/round1-progress-first-berth-v1.md` with this exact contract before strategy code is changed:

```markdown
# Round 1 progress-first berth priority v1

Status: PRE-RUN REVIEW

Hypothesis: during an active disruption, a berth queue containing both a vessel
whose next physical leg is blocked and a vessel whose next leg can progress can
reduce propagation by selecting the progress-capable vessel. Among eligible
vessels use the existing fallback ranking (40% waiting time, 30% carried TEU,
20% capacity, 10% handling-workload penalty), with queue order as the tie-break.

Policy: return a vessel only for that mixed active-disruption case. Return
`None` for inactive/no-disruption queues, empty queues, all-progress queues,
all-blocked queues, ambiguous/malformed inputs, and all other hooks.

No scenario names, ports, routes, dates, seeds, tuned thresholds, I/O,
randomness, organizer imports, mutation, or mutable module state are allowed.

Fixed run: `create_with_disruption`, Round 1, seed 2026, 140 warm-up days,
360 measured days, 5-day ATT interval, 72 periods, `PYTHONHASHSEED=0`.
Candidate command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`.
Pinned fallback: loss `20.436668751255972`, ATT SHA-256
`c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`.
Acceptance: `candidate_loss < 20.436668751255972 - 1e-9`; equality is rejection.

Evidence: `.challenge/round1/results/progress_first_berth_v1_20260804/` and
`experiments/results/round1_progress_first_berth_v1_20260804.json` (ignored).
Exactly one candidate run is authorized. A rejected or invalid candidate is
documented, reverted with `git revert`, synchronized back to the no-op adapter,
and the pinned fallback ATT is restored before final gates.
```

- [ ] **Step 3: Commit the contract**

```bash
git add docs/experiments/round1-progress-first-berth-v1.md
git commit -m "docs: define Round 1 progress-first berth experiment"
```

### Task 2: Specify the policy with RED tests

**Files:**
- Create: `tests/unit/test_round1_progress_first_berth.py`
- Modify: `tests/unit/test_overlay.py`
- Modify: `tests/unit/test_packaging.py`

- [ ] **Step 1: Add behavior tests against `UserStrategy`**

The unit test module must construct tiny duck-typed ports, berths, legs,
segments, plans, vessels, vessel classes, and shipments. It must include these
assertions (the baseline must fail the mixed-queue assertions because it returns
`None`):

```python
def test_mixed_active_queue_returns_original_progress_vessel_by_fallback_rank():
    blocked, progress, context, port, berths, now, waits = make_mixed_case()
    result = UserStrategy.select_vessel_for_berth(
        context, port, [blocked, progress], berths, now, waits
    )
    assert result is progress

def test_mixed_active_queue_preserves_fallback_rank_among_progress_vessels():
    blocked, low, high, context, port, berths, now, waits = make_ranked_case()
    result = UserStrategy.select_vessel_for_berth(
        context, port, [blocked, low, high], berths, now, waits
    )
    assert result is high

def test_inactive_all_progress_and_all_blocked_delegate():
    case = make_cases_at_active_and_inactive_boundaries()
    assert UserStrategy.select_vessel_for_berth(*case.inactive) is None
    assert UserStrategy.select_vessel_for_berth(*case.all_progress) is None
    assert UserStrategy.select_vessel_for_berth(*case.all_blocked) is None

def test_start_is_inclusive_and_end_is_exclusive():
    case = make_mixed_case()
    assert UserStrategy.select_vessel_for_berth(*case.at_start) is case.progress
    assert UserStrategy.select_vessel_for_berth(*case.at_end) is None

def test_closed_arrival_berth_and_congested_next_leg_are_blocked():
    case = make_mixed_case_with_both_blockers()
    assert UserStrategy.select_vessel_for_berth(*case.args) is case.progress

def test_exact_score_tie_uses_original_queue_order_and_identity():
    case = make_tied_case()
    assert UserStrategy.select_vessel_for_berth(*case.args) is case.first_progress

def test_malformed_disruption_or_route_delegates_without_mutation():
    case = make_malformed_case()
    before = case.snapshot()
    assert UserStrategy.select_vessel_for_berth(*case.args) is None
    assert case.snapshot() == before

def test_public_contract_and_other_hooks_remain_delegating():
    assert UserStrategy.create_alternative_service_routes(object(), object()) is None
    assert UserStrategy.assign_associated_bookings(object(), object(), object()) is None
    assert UserStrategy.adjust_bookings_before_cargo_handling(object(), object(), object()) is None
```

The actual fixture builders must use `datetime.min + timedelta(days=...)`,
object identity for `target_leg` and closed `target_berth.port`, finite numeric
metrics, and immutable snapshots of all input fields. Do not import organizer
modules in the participant test fixture.

- [ ] **Step 2: Add allowlist regression tests before adding the helper**

Extend overlay and packaging tests so the expected participant names are:

```python
EXPECTED = {"user_strategy.py", "README.md", "progress_first_berth.py"}
assert set(copied) == EXPECTED
assert set(member_names) == {f"response_strategies/{name}" for name in EXPECTED}
```

The tests must also continue rejecting any unallowlisted file.

- [ ] **Step 3: Run focused RED checks and fix only test defects**

```bash
uv run pytest tests/unit/test_round1_progress_first_berth.py -q
uv run pytest tests/unit/test_overlay.py tests/unit/test_packaging.py -q
```

Expected: the new mixed-queue assertions fail because the no-op adapter
returns `None`; there must be no collection errors. Commit only the tests:

```bash
git add tests/unit/test_round1_progress_first_berth.py tests/unit/test_overlay.py tests/unit/test_packaging.py
git commit -m "test: specify progress-first berth behavior"
```

### Task 3: Implement the minimum participant policy and reach GREEN

**Files:**
- Create: `submission/response_strategies/progress_first_berth.py`
- Modify: `submission/response_strategies/user_strategy.py`
- Modify: `submission/response_strategies/README.md`
- Modify: `src/wsc2026_tools/overlay.py`
- Modify: `src/wsc2026_tools/packaging.py`
- Modify: tests that assert the allowlists

- [ ] **Step 1: Add the helper with a small, read-only public function**

Implement `choose_progress_capable_vessel(context, waiting_vessels,
current_time, waiting_since_by_vessel)` in
`progress_first_berth.py`. It must:

1. return `None` for an empty queue, missing/invalid `context.disruption_plans`,
   invalid timestamps, or no active disruption;
2. compute active plans with `start <= current_time < end`, where `start` is
   `datetime.min + timedelta(days=plan.start_offset_days)`;
3. treat `plan.multiplier > 1` with a non-`None` target leg as a blocked next
   leg, and `plan.close_berth` with a non-`None` target berth as a blocked
   arrival port, comparing objects by identity;
4. call each vessel's `get_next_segment()` without mutating it, inspect
   `segment.associated_leg` and that leg's `arrival_port`, and delegate if any
   required value is ambiguous;
5. return `None` unless at least one vessel is blocked and one is progress-capable;
6. reproduce the fallback's normalized score over the complete queue, then
   select the highest-scoring progress-capable vessel using `-index` as the
   tie-break, returning the original object;
7. validate numeric values with `math.isfinite`, catch only expected shape/value
   errors (`AttributeError`, `KeyError`, `IndexError`, `TypeError`, `ValueError`,
   `OverflowError`), and never catch `BaseException` or `Exception` broadly;
8. contain no filesystem, network, subprocess, environment, clock, random,
   mutable module-level object, or organizer import.

Use `datetime` and `math` from the standard library only. Keep all helper
functions private except the one called by `user_strategy.py`.

- [ ] **Step 2: Wire only `select_vessel_for_berth`**

Add a relative import and replace only that method body with:

```python
return choose_progress_capable_vessel(
    maritime_data_context,
    waiting_vessels,
    current_time,
    waiting_since_by_vessel,
)
```

Leave the other three methods as unconditional `return None` delegates and
preserve the exact public signature.

- [ ] **Step 3: Add the helper to the two explicit submission allowlists**

Add the exact filename `progress_first_berth.py` to
`ALLOWED_OVERLAY_FILES` and `ALLOWED_PARTICIPANT_FILES` (or the equivalent
constants already used by each module), and update their explanatory docstrings
to say that participant modules are copied/package-checked explicitly.

- [ ] **Step 4: Update participant README**

Document that only the berth hook makes the narrow mixed active-disruption
decision, that all other cases delegate, and that the helper is packaged with
the adapter. Do not include organizer implementation or private input data.

- [ ] **Step 5: Run focused GREEN checks and commit**

```bash
uv run pytest tests/unit/test_round1_progress_first_berth.py tests/unit/test_overlay.py tests/unit/test_packaging.py -q
uv run ruff format submission/response_strategies/progress_first_berth.py submission/response_strategies/user_strategy.py tests/unit/test_round1_progress_first_berth.py
uv run ruff check submission/response_strategies tests/unit/test_round1_progress_first_berth.py
uv run ty check submission/response_strategies
```

All focused tests must pass before the implementation commit:

```bash
git add submission/response_strategies src/wsc2026_tools/overlay.py src/wsc2026_tools/packaging.py tests
git commit -m "feat: prioritize progress-capable vessels during disruptions"
```

### Task 4: Validate real context and perform the full preflight

**Files:**
- Create: `tests/integration/test_round1_progress_first_berth_runtime.py`

- [ ] **Step 1: Add a skipped-safe real-context integration test**

Load the ignored Round 1 `create_with_disruption` scenario only when the local
source exists. Find a real active disruption plan and real route segments,
construct a waiting queue from real vessel objects without changing their
fields, call the helper, and assert the result is either `None` or one of the
original queue objects. Snapshot each vessel's route, current segment, carried
shipments, and all plan fields before and after; assert identical snapshots.
Skip with a clear reason when `.challenge/round1/source` is absent. Do not
write outputs or alter the organizer tree.

- [ ] **Step 2: Run all preflight gates before any candidate run**

```bash
uv lock --check
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run ty check src/wsc2026_tools submission tests
uv run mypy src/wsc2026_tools submission
uv run pytest -m "not integration" --cov=src/wsc2026_tools --cov=submission --cov-report=term-missing --cov-fail-under=90
uv run pytest -m integration -q
uv run wsc2026 sync --round round1
cmp submission/response_strategies/user_strategy.py .challenge/round1/source/response_strategies/user_strategy.py
cmp submission/response_strategies/progress_first_berth.py .challenge/round1/source/response_strategies/progress_first_berth.py
uv run wsc2026 smoke --round round1
uv run wsc2026 package --team ValidationTeam --round 1
uv run wsc2026 package --team ValidationTeam --round 1
```

Hash the two package archives and compare member lists byte-for-byte. Confirm
only the three allowlisted participant files are present, no simulation/probe
process is running, `git diff --check` is clean, and restricted-material scans
find neither the organizer ZIP path nor its known blob. If any gate fails,
stop and correct it before the run.

- [ ] **Step 3: Commit the real-context test and contract corrections**

```bash
git add tests/integration/test_round1_progress_first_berth_runtime.py docs/experiments/round1-progress-first-berth-v1.md
git commit -m "test: validate progress-first berth on Round 1 context"
```

### Task 5: Execute, preserve, and score exactly one candidate

**Files:**
- Ignored evidence: `.challenge/round1/results/progress_first_berth_v1_20260804/`
- Ignored aggregate: `experiments/results/round1_progress_first_berth_v1_20260804.json`

- [ ] **Step 1: Pin the run identities and verify the fresh-run preconditions**

Record the candidate branch HEAD, submission/helper SHA-256 values, fallback
ATT SHA and score, fallback period count, active Output mtime/SHA, and process
list. Confirm the synchronized private copies are byte-identical. Do not start
the run if any value differs from the contract.

- [ ] **Step 2: Run the single fixed candidate and monitor it**

```bash
PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full > /tmp/wsc_round1_candidate_progress_first_berth_20260804.log 2>&1
```

While it runs, inspect progress at intervals under 60 seconds using `ps` and
the log's period markers. Do not edit code, stop/restart it, tune thresholds,
or launch another simulation. Completion requires `Period Result Output:
Period 72`, `Simulation completed.`, and exit code 0.

- [ ] **Step 3: Preserve raw output before scoring or restoration**

Copy the fresh ATT CSV and raw log into the ignored evidence directory. Record
the CSV SHA-256, byte count, 72 numbered periods, mean ATT, full scorer JSON,
package SHA/member list, timestamps, and the exact command in the aggregate
JSON. Never overwrite the pinned fallback snapshot.

- [ ] **Step 4: Score and apply the fixed gate**

Score the preserved candidate against the Round 1 baseline ATT with the CLI.
Compare full-precision cumulative loss to `20.436668751255972 - 1e-9`, count
periods better/equal/worse than the pinned fallback, and record the result
without rounding. A crash, stale/missing CSV, wrong period count, or equality
is rejection.

### Task 6: Document, restore, verify, and reconcile

**Files:**
- Modify: `docs/experiments/round1-progress-first-berth-v1.md`
- Modify: `README.md`
- Modify: `docs/round1-readiness.md`
- Modify: `docs/challenge-overview.html` if its Round 1 experiment table is stale

- [ ] **Step 1: Record the immutable result before changing code**

Add candidate score, ATT hash/mean/period count, runtime, period comparison,
decision, evidence paths, package metadata, and every gate result to the report.
State explicitly that only one candidate was run.

- [ ] **Step 2: Reject safely unless the strict gate is met**

For a rejected or invalid candidate, commit the result report first, then use
`git revert` in reverse order for the implementation, RED tests, and any
candidate-only allowlist changes. Keep the experiment contract/report. Run
`uv run wsc2026 sync --round round1`, verify all four hooks are no-op, restore
the pinned fallback ATT from
`.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`,
and re-score it exactly to `20.436668751255972`. Never manually reconstruct
the fallback or run a second candidate.

- [ ] **Step 3: Run final gates after restoration**

Repeat lock/sync, Ruff, `ty`, mypy, full non-integration coverage, integration,
Round 1 smoke, deterministic package twice, sync/cmp, restricted scans,
`git diff --check`, process checks, and `git status`. Confirm the active ATT
hash/score is the pinned fallback and the worktree is clean.

- [ ] **Step 4: Reconcile the approved result onto the sole main checkout**

Copy only ignored candidate evidence and the restored fallback Output into
`/Users/noeflandre/wintersim-challenge-2026`, fast-forward `main` to the
experiment branch, remove the temporary worktree and branch only after all
needed commits are reachable, verify there is one worktree and one local
branch, then push `main` and verify `git rev-parse main` equals
`origin/main`. Do not publish organizer source, ZIPs, outputs, or private
input/history. Leave no running process.

- [ ] **Step 5: Commit and hand off the clean state**

```bash
git add docs README.md
git commit -m "docs: record Round 1 progress-first berth experiment"
git push origin main
```

The final report must include the exact branch/HEAD, candidate and fallback
hashes/scores, decision, evidence locations, restored state, all gate results,
remote verification, and a statement that no second candidate, tuning,
submission, merge, or history rewrite occurred.
