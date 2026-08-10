# Round 1 multi-transfer recovery hold v3 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one controlled Round 1 experiment that tests whether restricting the accepted recovery-hold policy to safe paths with at least two service-route changes strictly improves the current best cumulative resilience loss of `19.828803374740612`.

**Architecture:** Preserve the accepted v2 graph, disruption, recovery, and service-time machinery. Change only its structural eligibility gate from one route change to two, prove the behavior through synthetic and real-context tests, then execute exactly one fixed full run and apply the precommitted accept-or-revert rule.

**Tech Stack:** Python 3.11-compatible standard-library participant code; `uv`; pytest/pytest-cov; Ruff; Ty; mypy; the repository `wsc2026` CLI; ignored organizer Round 1 runtime.

---

## Repository constraint

The user's explicit one-folder/one-branch requirement overrides the generic
worktree guidance. Execute only in
`/Users/noeflandre/wintersim-challenge-2026` on `main`. Do not create another
branch, worktree, clone, or source folder.

### Task 1: Establish the v3 RED contract

**Files:**
- Move and modify: `tests/unit/test_round1_recovery_aware_direct_service_hold_v2.py` -> `tests/unit/test_round1_multi_transfer_recovery_hold_v3.py`
- Move and modify: `tests/integration/test_round1_recovery_hold_v2_real_context.py` -> `tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py`

- [ ] **Step 1: Change the positive synthetic fixture to use two transfers**

Replace the safe-path portion of `_qualifying_fixture` with three distinct
routes and expose all objects to existing mutation tests:

```python
def _qualifying_fixture(
    *,
    safe_distances: tuple[float, float, float] = (1000.0, 1000.0, 1000.0),
) -> tuple[SimpleNamespace, dt.datetime, SimpleNamespace, dict[str, Any]]:
    origin = _port("Origin")
    transfer_a = _port("Transfer A")
    transfer_b = _port("Transfer B")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route(
        "safe-a", [origin, transfer_a, origin], [safe_distances[0], safe_distances[0]]
    )
    safe_b = _route(
        "safe-b", [transfer_a, transfer_b, transfer_a], [safe_distances[1], safe_distances[1]]
    )
    safe_c = _route(
        "safe-c", [transfer_b, destination, transfer_b], [safe_distances[2], safe_distances[2]]
    )
    plan = _leg_plan(_leg(nominal))
    context = SimpleNamespace(
        ports=[origin, transfer_a, transfer_b, destination],
        service_routes=[nominal, safe_a, safe_b, safe_c],
        disruption_plans=[plan],
    )
    shipment = _shipment(origin, destination)
    now = ANCHOR + dt.timedelta(days=14.5)
    return context, now, shipment, {
        "origin": origin,
        "transfer": transfer_a,
        "transfer_a": transfer_a,
        "transfer_b": transfer_b,
        "destination": destination,
        "nominal": nominal,
        "safe_a": safe_a,
        "safe_b": safe_b,
        "safe_c": safe_c,
        "plan": plan,
    }
```

Update the equality test to call
`_qualifying_fixture(safe_distances=(40.0, 40.0, 80.0))`. With one vessel at
speed 10, the three first-boarding plus sailing estimates total exactly 32
hours, equal to the fixed hold estimate.

- [ ] **Step 2: Add the behavior that must fail against accepted v2**

Add this synthetic contract and retain the complete before/after snapshot:

```python
def test_one_transfer_safe_path_delegates_without_mutation() -> None:
    origin = _port("Origin")
    transfer = _port("Transfer")
    destination = _port("Destination")
    nominal = _route("nominal", [origin, destination, origin], [100.0, 100.0])
    safe_a = _route("safe-a", [origin, transfer, origin], [1000.0, 1000.0])
    safe_b = _route("safe-b", [transfer, destination, transfer], [1000.0, 1000.0])
    context = SimpleNamespace(
        ports=[origin, transfer, destination],
        service_routes=[nominal, safe_a, safe_b],
        disruption_plans=[_leg_plan(_leg(nominal))],
    )
    shipment = _shipment(origin, destination)
    before = _freeze((context, shipment))

    decision = _decision(context, ANCHOR + dt.timedelta(days=14.5), shipment)

    assert decision is None
    assert _freeze((context, shipment)) == before
```

Accepted v2 must fail this assertion as `False is None`; a collection error or
fixture error is not an acceptable RED.

- [ ] **Step 3: Keep all existing tests meaningful under the three-route fixture**

Change loops that mark safe alternatives from `(safe_a, safe_b)` to
`(safe_a, safe_b, safe_c)`. Change the closed-port positive case to three
distinct safe routes. Extend the same-service indirect case through both
transfer ports. Rebuild `_tie_fixture` with equal-distance three-route X and Y
branches: fast distances `(40, 40, 80)` at speed 10 and slow distances
`(40, 40, 80)` at speed 1. Context port order must still select which tied
branch wins, producing `None` for the exact-equality fast branch and `False`
for the slower branch.

- [ ] **Step 4: Strengthen the real Round 1 integration assertion**

Rename the dynamic module to
`wsc_round1_multi_transfer_recovery_hold_v3_participant`. Before accepting a
real `False` decision, derive the same safe graph and assert its adjacent route
change count is at least two:

```python
state = participant._active_state(context, now)
assert state is not None
graphs = participant._graphs(context, state)
assert graphs is not None
safe_path = participant._shortest_path(
    context,
    demand.origin_port,
    demand.destination_port,
    graphs[1],
)
assert safe_path is not None
route_changes = sum(
    left.route is not right.route
    for left, right in zip(safe_path, safe_path[1:], strict=False)
)
if decision is False:
    assert route_changes >= 2
```

Keep the real-context no-mutation snapshot and outside-window delegation proof.

- [ ] **Step 5: Run the focused suite and capture RED**

Run:

```bash
uv run pytest tests/unit/test_round1_multi_transfer_recovery_hold_v3.py \
  tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py -q -vv
```

Expected: exactly the one-transfer delegation test fails because accepted v2
returns `False`; every other test passes.

- [ ] **Step 6: Commit RED tests only**

```bash
git add tests/unit/test_round1_multi_transfer_recovery_hold_v3.py \
  tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py \
  tests/unit/test_round1_recovery_aware_direct_service_hold_v2.py \
  tests/integration/test_round1_recovery_hold_v2_real_context.py
git commit -m "test: specify multi-transfer recovery hold policy"
```

Record the commit SHA and exact RED counts in the experiment report later.

### Task 2: Implement the minimum v3 policy

**Files:**
- Modify: `submission/response_strategies/user_strategy.py`
- Modify: `submission/response_strategies/README.md`

- [ ] **Step 1: Replace only the route-change eligibility check**

In `_should_hold`, replace the v2 `any(...)` test with:

```python
    route_change_count = sum(
        left.route is not right.route
        for left, right in zip(safe_path, safe_path[1:], strict=False)
    )
    if route_change_count < 2:
        return False
```

Do not change graph construction, path selection, disruption recovery,
headways, sailing-time estimation, comparison arithmetic, exception handling,
or any public signature.

- [ ] **Step 2: Update participant-owned descriptions**

Change the module and `assign_associated_bookings` docstrings plus
`submission/response_strategies/README.md` to say the safe detour must require
at least two service-route changes (at least three service boardings). Do not
claim performance before the full run.

- [ ] **Step 3: Run focused GREEN**

Run the same focused command from Task 1. Expected: every selected unit and
integration test passes, including the previously RED one-transfer contract.

- [ ] **Step 4: Run fast static checks**

```bash
uv run ruff format --check submission tests
uv run ruff check submission tests
uv run ty check submission
uv run mypy submission
```

Expected: all exit zero with no diagnostics.

- [ ] **Step 5: Commit the implementation**

```bash
git add submission/response_strategies/user_strategy.py \
  submission/response_strategies/README.md
git commit -m "feat: hold only multi-transfer disruption detours"
```

### Task 3: Create the tracked pre-run experiment record

**Files:**
- Create: `docs/experiments/round1-multi-transfer-recovery-hold-v3.md`

- [ ] **Step 1: Write the pre-run record**

Copy the approved policy, invariants, fixed run identity, baseline evidence,
acceptance expression, RED/GREEN evidence, candidate commits, ignored evidence
paths, one-run rule, and exact rejection/revert procedure from the approved
specification. Mark the decision `PRE-RUN`; do not predict an improvement.

- [ ] **Step 2: Verify and commit the record**

```bash
git diff --check
git add docs/experiments/round1-multi-transfer-recovery-hold-v3.md
git commit -m "docs: record multi-transfer hold pre-run contract"
```

### Task 4: Run every preflight gate and pin launch evidence

**Files:**
- Create ignored: `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/pre_run_manifest.json`

- [ ] **Step 1: Run locked quality and test gates**

Run in failure-on-first-error order:

```bash
uv lock --check
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run ty check src/wsc2026_tools submission
uv run mypy src/wsc2026_tools submission
uv run pytest -m "not integration" \
  --cov=src/wsc2026_tools --cov=submission \
  --cov-report=term-missing --cov-fail-under=90
uv run pytest -m integration -q
```

True coverage must be at least `90.00%`; rounded output below the configured
threshold is rejection.

- [ ] **Step 2: Synchronize and validate the actual Round 1 runtime**

```bash
uv run wsc2026 sync --round round1
cmp submission/response_strategies/user_strategy.py \
  .challenge/round1/source/response_strategies/user_strategy.py
uv run wsc2026 smoke --round round1
cmp submission/response_strategies/user_strategy.py \
  .challenge/round1/source/response_strategies/user_strategy.py
```

Require `SMOKE_OK`, exit zero, and byte identity after smoke.

- [ ] **Step 3: Validate deterministic packaging twice**

Run `uv run wsc2026 package --team NoeFlandre --round 1` twice. Copy each
generated archive to a fresh `/tmp` directory before the next invocation,
compare them with `cmp`, calculate both SHA-256 hashes, and inspect both member
lists with `unzip -Z1`. Require byte identity and only the required top-level
folder containing `response_strategies/README.md` and
`response_strategies/user_strategy.py`. Move the generated validation archive
out of the repository; never submit or upload it.

- [ ] **Step 4: Verify the accepted control and repository safety**

Require:

```text
control score = 19.828803374740612
control periods = 72
control ATT SHA-256 = d381b087f8d67124a8078b5afc795f5b59b08db90148614b43dcfdf351e7ac48
```

Use the scorer against
`.challenge/round1/source/Output/Baseline_ATT_By_Statistics_Interval.csv`.
Also require `git diff --check`, a clean `git status --short`, exactly one
worktree, exactly one branch (`main`), no restricted tracked/reachable object,
and no tracked ZIP, `Input/`, `Output/`, organizer `main.py`, or
`default_strategy.py`.

- [ ] **Step 5: Prove no simulator is live and write the manifest**

Inspect the process list for `wsc2026 run` and the Round 1 organizer `main.py`.
Ignore only the process-inspection command itself. Abort before launch if any
real simulator exists.

Atomically write the ignored pre-run JSON with: schema version, UTC timestamp,
candidate HEAD, strategy/runtime SHA-256, `cmp` result, package SHA/members,
control score/hash/mean/periods/snapshot, active Output hash/size/mtime,
configuration, exact acceptance expression, gate results, and no-live-process
proof. Refuse to overwrite an existing manifest.

- [ ] **Step 6: Commit the pre-run gate record**

Append exact preflight evidence to the tracked experiment report and commit:

```bash
git add docs/experiments/round1-multi-transfer-recovery-hold-v3.md
git commit -m "docs: approve multi-transfer hold full run"
```

Require a clean status before launch.

### Task 5: Execute exactly one full candidate run

**Files:**
- Create ignored: `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/full_run.log`
- Create ignored: `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`

- [ ] **Step 1: Recheck launch identity immediately before execution**

Recheck HEAD, strategy/runtime hashes and byte identity, control snapshot hash,
stale Output hash/mtime, clean Git status, and no live simulator. Any mismatch
stops the experiment before launch.

- [ ] **Step 2: Launch the sole candidate**

Execute the fixed command once, with output streamed to the fixed ignored log:

```bash
PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full
```

Do not edit code, tests, docs, the threshold, or the policy after launch.

- [ ] **Step 3: Monitor the same managed process**

Poll the existing process/session at intervals shorter than 60 seconds. Report
elapsed time, latest measured day/period, and liveness. Never start a duplicate.
Require exit code zero plus explicit `Simulation completed.`, simulation Day
360, Period 72 (Days 356-360), and a fresh Output ATT mtime/write.

- [ ] **Step 4: Preserve output before any score, sync, smoke, or restore**

Copy the fresh `ATT_By_Statistics_Interval.csv` byte-for-byte into the fixed
ignored result directory. Record source/copy SHA-256, size, mtime, header,
numbered period count, and mean ATT. Require identical bytes, 72 periods, and
finite values.

### Task 6: Score once and apply the fixed decision rule

**Files:**
- Create ignored: `experiments/results/round1_multi_transfer_recovery_hold_v3_20260810.json`
- Modify: `docs/experiments/round1-multi-transfer-recovery-hold-v3.md`

- [ ] **Step 1: Score the preserved candidate**

Run `wsc2026 score --json` on the preserved candidate ATT against the
authoritative Round 1 baseline ATT. Record complete scorer JSON, full-precision
cumulative loss, all period losses, mean ATT, ATT SHA, runtime, and 72-period
validation.

- [ ] **Step 2: Compare directly with accepted v2**

Compare all 72 ATT values against the pinned v2 snapshot and record
better/equal/worse counts, absolute delta, and relative percentage. Apply only:

```text
candidate_cumulative_loss < 19.828803374740612 - 1e-9
```

Equality is rejection. Do not round, retune, or run another candidate.

- [ ] **Step 3: Preserve aggregate evidence and document the decision**

Write the ignored aggregate JSON without overwriting existing evidence. Update
the tracked report with evidence-limited language, all required hashes and
times, exact decision, and forbidden-action confirmation. Commit before any
rejection restoration:

```bash
git add docs/experiments/round1-multi-transfer-recovery-hold-v3.md
git commit -m "docs: record multi-transfer hold result"
```

- [ ] **Step 4A: If accepted, retain v3**

If the expression is true, keep candidate code/tests active. Update `README.md`
and `docs/challenge-overview.html` with the new best score, delta, and a concise
plain-language experiment entry. Do not push or submit.

- [ ] **Step 4B: If rejected or invalid, restore accepted v2**

If the expression is false, revert the implementation commit and RED-test
commit in reverse order using separate `git revert --no-edit` operations. Do
not revert the design, plan, pre-run, or result-report commits. Then:

1. synchronize the restored v2 submission into Round 1;
2. copy the verified pinned v2 ATT snapshot back to active Output;
3. require the restored participant SHA
   `144493d651d0eb967dc8725a34997d118b22ce3db116ca5126699bb8ea2b743c`;
4. require the restored ATT SHA
   `d381b087f8d67124a8078b5afc795f5b59b08db90148614b43dcfdf351e7ac48`;
5. re-score exactly `19.828803374740612` over 72 periods; and
6. update public docs only to record the rejected experiment, leaving v2 as
   the named active best.

### Task 7: Run final verification and leave a clean state

**Files:**
- Modify when needed: `README.md`
- Modify when needed: `docs/challenge-overview.html`
- Modify: `docs/experiments/round1-multi-transfer-recovery-hold-v3.md`

- [ ] **Step 1: Commit final documentation**

Run `git diff --check`, inspect the full diff, then commit with either
`docs: publish accepted multi-transfer hold result` or
`docs: finalize rejected multi-transfer hold result`.

- [ ] **Step 2: Rerun every final gate from fresh state**

Repeat locked sync, Ruff format/lint, Ty, mypy, non-integration coverage,
integration tests, Round 1 sync/cmp, smoke/cmp, deterministic packaging twice,
active ATT hash and score, restricted-material scans, one-worktree/one-branch
checks, no-live-simulator check, `git diff --check`, and clean Git status.

- [ ] **Step 3: Audit completion against the approved design**

Verify every spec invariant and deliverable directly: one candidate only, one
full run only, no post-launch policy change, preserved raw evidence, 72 periods,
full-precision decision, correct active strategy/output after acceptance or
rejection, participant-only package, no restricted material, and no push,
merge, PR, upload, submission, or history rewrite.

- [ ] **Step 4: Report the result**

Report branch/HEAD, candidate and restoration commits, strategy/package/ATT/log
hashes, fixed configuration, runtime, score, mean, delta, relative change,
period comparison, decision, evidence paths, all final gates, clean Git state,
and forbidden-action confirmation. Mark the persistent goal complete only if
the retained candidate strictly beats `19.828803374740612`; otherwise keep the
larger multi-experiment goal active after this experiment ends cleanly.
