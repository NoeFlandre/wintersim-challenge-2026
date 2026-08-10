# Round 1 safe-departure opportunity gate v4 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run one controlled Round 1 experiment testing whether limiting the accepted v3 recovery hold to recovery waits no longer than the first safe service's live headway strictly improves cumulative resilience loss below `19.084638612143134`.

**Architecture:** Preserve the complete accepted v3 route graph, disruption, recovery, path-selection, service-time, and multi-transfer machinery. Add one fail-closed eligibility comparison inside `_should_hold`, prove the boundary and real-context activation through RED -> GREEN tests, then execute exactly one fixed full run and apply the precommitted accept-or-restore rule.

**Tech Stack:** Python 3.11-compatible standard-library participant code; `uv`; pytest/pytest-cov; Ruff; Ty; mypy; the repository `wsc2026` CLI; ignored organizer Round 1 runtime.

---

## Repository constraint

Execute only in `/Users/noeflandre/wintersim-challenge-2026` on the sole local
branch `main`. The user's explicit one-folder/one-branch requirement overrides
generic worktree guidance. Do not create another branch, worktree, clone, or
source folder. Do not push, upload, email, or submit anything.

The approved design is
`docs/superpowers/specs/2026-08-10-round1-safe-departure-opportunity-gate-v4-design.md`.
Its exact policy, current control, and one-run decision boundary are
authoritative.

### Task 1: Establish the v4 RED contract

**Files:**
- Move and modify: `tests/unit/test_round1_multi_transfer_recovery_hold_v3.py` -> `tests/unit/test_round1_safe_departure_opportunity_gate_v4.py`
- Move and modify: `tests/integration/test_round1_multi_transfer_recovery_hold_v3_real_context.py` -> `tests/integration/test_round1_safe_departure_opportunity_gate_v4_real_context.py`

- [ ] **Step 1: Rename the accepted v3 contracts without changing behavior**

Use Git-aware renames, then update only the module docstrings and the dynamic
participant module name to say `safe-departure opportunity gate v4`. Do not
edit `submission/` yet.

- [ ] **Step 2: Add explicit synthetic boundary contracts**

Add these tests immediately after the existing positive synthetic test. The
fixture's first safe route has cycle distance `120` and deployed speed `10`,
so its exact headway is `12` hours. At day `14.5`, recovery is exactly 12
hours away; at day `14.0`, it is 24 hours away. The remaining two safe routes
keep the detour much longer than the hold estimate.

```python
def test_recovery_wait_equal_to_safe_first_headway_can_hold_without_mutation() -> None:
    context, now, shipment, _ = _qualifying_fixture(
        safe_distances=(60.0, 1000.0, 1000.0)
    )
    before = _freeze((context, shipment))

    result = _decision(context, now, shipment)

    assert result is False
    assert _freeze((context, shipment)) == before


def test_recovery_wait_beyond_safe_first_headway_delegates_without_mutation() -> None:
    context, _, shipment, _ = _qualifying_fixture(
        safe_distances=(60.0, 1000.0, 1000.0)
    )
    now = ANCHOR + dt.timedelta(days=14.0)
    before = _freeze((context, shipment))

    result = _decision(context, now, shipment)

    assert result is None
    assert _freeze((context, shipment)) == before
```

The existing default qualifying fixture proves the strictly-below-headway
case because its recovery wait is 12 hours and its first safe headway is 200
hours. Keep its full no-mutation assertion.

- [ ] **Step 3: Extend malformed-state coverage for the first safe profile**

Add this mutation to the existing parameterized malformed-state test and add
the matching ID `zero-first-safe-speed` in the same position:

```python
lambda context, shipment, items: setattr(
    items["safe_a"].deployed_vessels[0].vessel_class,
    "sailing_speed",
    0.0,
),
```

The expected result remains `None` with a byte-for-byte equivalent object
snapshot.

- [ ] **Step 4: Make the real-context test prove both sides of the gate**

Replace the three-fraction sampler with daily active-window midpoints derived
only from runtime plan timing:

```python
def _candidate_times(context: Any) -> tuple[dt.datetime, ...]:
    times: set[dt.datetime] = set()
    for plan in context.disruption_plans:
        start_days = getattr(plan, "start_offset_days", None)
        duration_days = getattr(plan, "duration_days", None)
        if (
            isinstance(start_days, (int, float))
            and not isinstance(start_days, bool)
            and math.isfinite(start_days)
            and isinstance(duration_days, (int, float))
            and not isinstance(duration_days, bool)
            and math.isfinite(duration_days)
            and duration_days > 0
        ):
            for offset in range(math.ceil(duration_days)):
                midpoint = start_days + offset + 0.5
                if midpoint < start_days + duration_days:
                    times.add(dt.datetime.min + dt.timedelta(days=midpoint))
    return tuple(sorted(times))
```

Add a helper that derives the accepted-v3 eligibility metrics without calling
the candidate decision:

```python
def _v3_eligible_metrics(
    participant: Any,
    context: Any,
    now: dt.datetime,
    demand: Any,
) -> tuple[float, float] | None:
    state = participant._active_state(context, now)
    if state is None:
        return None
    graphs = participant._graphs(context, state)
    if graphs is None:
        return None
    nominal = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[0]
    )
    safe = participant._shortest_path(
        context, demand.origin_port, demand.destination_port, graphs[1]
    )
    if nominal is None or safe is None or len(nominal) != 1 or len(safe) < 2:
        return None
    route_changes = sum(
        left.route is not right.route
        for left, right in zip(safe, safe[1:], strict=False)
    )
    if route_changes < 2:
        return None
    recovery = participant._edge_constraint_recovery(nominal[0], state)
    nominal_hours = participant._path_service_hours(nominal)
    detour_hours = participant._path_service_hours(safe)
    safe_first_profile = participant._route_profile(safe[0].route)
    if (
        recovery is None
        or nominal_hours is None
        or detour_hours is None
        or safe_first_profile is None
    ):
        return None
    wait_hours = max(0.0, (recovery - now).total_seconds() / 3600.0)
    hold_hours = wait_hours + nominal_hours
    if not all(
        math.isfinite(value) and value > 0.0
        for value in (hold_hours, detour_hours, safe_first_profile.headway_hours)
    ):
        return None
    if hold_hours >= detour_hours:
        return None
    return wait_hours, safe_first_profile.headway_hours
```

Replace the old single-qualifying search with a scan that requires at least
one case on each side of the new boundary and asserts no mutation for every
candidate call:

```python
    found_retained_hold = False
    found_long_wait_delegation = False
    for now in times:
        context = scenario_builders.create_with_disruption()
        DefaultStrategy.create_alternative_service_routes(context, now)
        for index, demand in enumerate(context.demands):
            metrics = _v3_eligible_metrics(participant, context, now, demand)
            if metrics is None:
                continue
            shipment = Shipment(
                index=index,
                teu_size=1,
                demand=demand,
                current_storage_port=demand.origin_port,
                generated_time=now,
            )
            before = _snapshot(context, shipment)
            decision = participant.UserStrategy.assign_associated_bookings(
                context, now, shipment
            )
            assert _snapshot(context, shipment) == before
            wait_hours, safe_first_headway = metrics
            if wait_hours <= safe_first_headway:
                assert decision is False
                found_retained_hold = True
            else:
                assert decision is None
                found_long_wait_delegation = True
            if found_retained_hold and found_long_wait_delegation:
                break
        if found_retained_hold and found_long_wait_delegation:
            break

    assert found_retained_hold
    assert found_long_wait_delegation
```

Keep the existing outside-window `None` and no-mutation proof.

- [ ] **Step 5: Run focused RED and inspect the failure cause**

Run:

```bash
uv run pytest \
  tests/unit/test_round1_safe_departure_opportunity_gate_v4.py \
  tests/integration/test_round1_safe_departure_opportunity_gate_v4_real_context.py \
  -q -vv
```

Require the synthetic long-wait assertion to fail because accepted v3 returns
`False` where v4 requires `None`. The real-context long-wait assertion may
also fail for the same missing gate. Collection errors, fixture errors, a
dormant real-context scan, or unrelated failures invalidate RED and must be
fixed before proceeding.

- [ ] **Step 6: Commit tests while they are still RED**

Stage the two renamed test paths and the two removed v3 paths, then commit:

```bash
git commit -m "test: specify safe-departure opportunity gate v4"
```

Record the commit SHA, failing test names, and exact focused counts for the
experiment report.

### Task 2: Implement the minimum GREEN policy

**Files:**
- Modify: `submission/response_strategies/user_strategy.py`
- Modify: `submission/response_strategies/README.md`
- Test: `tests/unit/test_round1_safe_departure_opportunity_gate_v4.py`
- Test: `tests/integration/test_round1_safe_departure_opportunity_gate_v4_real_context.py`

- [ ] **Step 1: Add only the approved fail-closed headway gate**

In `_should_hold`, after validating `recovery` and before the final decision,
derive the first safe route profile with the existing helper. The relevant
portion must become:

```python
    recovery = _edge_constraint_recovery(nominal_path[0], state)
    if recovery is None:
        return False
    safe_first_profile = _route_profile(safe_path[0].route)
    if safe_first_profile is None:
        return False
    nominal_hours = _path_service_hours(nominal_path)
    detour_hours = _path_service_hours(safe_path)
    if nominal_hours is None or detour_hours is None:
        return False
    wait_hours = max(0.0, (recovery - now).total_seconds() / 3600.0)
    if wait_hours > safe_first_profile.headway_hours:
        return False
    hold_hours = wait_hours + nominal_hours
    if not all(math.isfinite(value) and value > 0.0 for value in (hold_hours, detour_hours)):
        return False
    return hold_hours < detour_hours
```

Do not modify graph construction, path selection, route-change counting,
recovery selection, service-time arithmetic, exception handling, public
signatures, or any non-target hook.

- [ ] **Step 2: Update participant-owned descriptions without claiming a result**

Update the module docstring, `assign_associated_bookings` docstring, and
`submission/response_strategies/README.md` so they explain that a qualifying
multi-transfer detour is declined only when recovery is no more than one live
headway of the detour's first safe service. State that the rule is read-only,
deterministic, and fail-closed. Mark performance as unmeasured until the full
run.

- [ ] **Step 3: Run focused GREEN**

Run the same focused command from Task 1. Require every selected unit and
integration test to pass, including the two assertions that were RED.

- [ ] **Step 4: Run static checks on the changed surface**

```bash
uv run ruff format --check submission tests
uv run ruff check submission tests
uv run ty check submission
uv run mypy submission
```

All commands must exit zero without ignored diagnostics.

- [ ] **Step 5: Commit the minimal implementation**

Stage only the participant strategy and README, then commit:

```bash
git commit -m "feat: gate recovery holds by safe-service headway"
```

### Task 3: Create the tracked pre-run contract

**Files:**
- Create: `docs/experiments/round1-safe-departure-opportunity-gate-v4.md`

- [ ] **Step 1: Write the PRE-RUN experiment record**

Record the approved hypothesis, alternatives, exact policy, current v3
control score/hash/snapshot, fixed run identity, acceptance expression,
RED/GREEN commits and outputs, evidence paths, one-run rule, and exact
accept-or-restore procedure. Mark it `PRE-RUN`; do not predict performance.

- [ ] **Step 2: Verify and commit the record**

Run `git diff --check`, search the report for stale v2 thresholds and
unmeasured performance claims, then commit:

```bash
git commit -m "docs: record safe-departure gate pre-run contract"
```

### Task 4: Run every preflight gate and pin launch identity

**Files:**
- Modify: `docs/experiments/round1-safe-departure-opportunity-gate-v4.md`
- Create ignored: `.challenge/round1/results/safe_departure_opportunity_gate_v4_20260810/pre_run_manifest.json`

- [ ] **Step 1: Run locked quality and test gates in fail-fast order**

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

Require true branch coverage at least `90.00%`; a displayed rounded value does
not override the command's exit status. Any failure stops before launch.

- [ ] **Step 2: Synchronize and smoke the actual Round 1 runtime**

```bash
uv run wsc2026 sync --round round1
cmp submission/response_strategies/user_strategy.py \
  .challenge/round1/source/response_strategies/user_strategy.py
cmp submission/response_strategies/README.md \
  .challenge/round1/source/response_strategies/README.md
uv run wsc2026 smoke --round round1
cmp submission/response_strategies/user_strategy.py \
  .challenge/round1/source/response_strategies/user_strategy.py
```

Require `SMOKE_OK`, exit zero, and byte identity after smoke. Confirm the
accepted stale Output ATT hash remains
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.

- [ ] **Step 3: Validate deterministic packaging twice**

Create a fresh private `/tmp` directory. Run
`uv run wsc2026 package --team NoeFlandre --round 1` twice, moving each
generated archive into that directory before the next run. Require identical
SHA-256 hashes, `cmp` equality, and identical `unzip -Z1` lists containing
only one top-level directory with:

```text
response_strategies/README.md
response_strategies/user_strategy.py
```

Move any remaining validation archive out of the repository. Never submit or
upload it.

- [ ] **Step 4: Re-prove the accepted control and safety boundary**

Score the accepted v3 snapshot against
`.challenge/round1/source/Output/Baseline_ATT_By_Statistics_Interval.csv` and
require exactly 72 periods and `19.084638612143134`. Require its SHA-256 to be
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.

Also require:

- `git diff --check` and a clean `git status --short`;
- one `git worktree list` entry and only local branch `main`;
- no live `wsc2026 run`, organizer `main.run_simulation`, or matching Round 1
  simulator process;
- no tracked or reachable organizer archive/blob;
- no tracked ZIP, `Input/`, `Output/`, organizer `main.py`, or
  `default_strategy.py`.

- [ ] **Step 5: Commit the tracked pre-run gate record**

Append the exact outputs, candidate hashes, package hash/members, control
re-score, and gate counts to the report. Commit:

```bash
git commit -m "docs: approve safe-departure gate full run"
```

Require a clean status. This commit is the immutable candidate launch HEAD.

- [ ] **Step 6: Write the ignored pre-run manifest atomically**

Refuse to overwrite an existing manifest. Write a schema-versioned JSON object
containing exact observed values for:

```text
created_at_utc
launch_head
strategy_sha256
runtime_strategy_sha256
strategy_runtime_cmp
package_sha256
package_members
control_score
control_period_count
control_att_sha256
control_snapshot
stale_output_sha256
stale_output_size
stale_output_mtime_ns
scenario
seed
pythonhashseed
warmup_days
measured_days
interval_days
expected_periods
run_command
acceptance_expression
quality_gate_results
no_live_process_evidence
```

Use a temporary sibling and atomic rename. Parse the finished JSON back,
validate every required key and hash, and require `git status --short` remains
clean because the directory is ignored.

### Task 5: Execute and monitor exactly one full candidate

**Files:**
- Create ignored: `.challenge/round1/results/safe_departure_opportunity_gate_v4_20260810/full_run.log`
- Create ignored: `.challenge/round1/results/safe_departure_opportunity_gate_v4_20260810/ATT_By_Statistics_Interval.csv`

- [ ] **Step 1: Recheck launch identity immediately before execution**

Recheck HEAD against the manifest, strategy/runtime hashes and `cmp`, control
snapshot, stale Output hash/size/mtime, clean status, and no live simulator.
Any mismatch stops before consuming the run.

- [ ] **Step 2: Launch the sole candidate once**

Record an ISO UTC start timestamp, then launch exactly:

```bash
PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full
```

Stream both stdout and stderr to the fixed ignored log while preserving the
real simulator exit status. Do not edit code, tests, docs, policy, threshold,
manifest, or configuration after launch.

- [ ] **Step 3: Monitor only the launched process**

Poll the same managed process/session at intervals no longer than 60 seconds.
Report elapsed time, latest day/period marker, and liveness. Never launch a
duplicate. On exit, record finish UTC and require:

```text
exit code 0
Simulation Day 360
Period Result Output: Period 72 (Days 356-360)
Simulation completed.
```

Require the source ATT file to have a fresh mtime relative to the manifest.

- [ ] **Step 4: Preserve fresh evidence before any score or state-changing command**

Copy the fresh source ATT byte-for-byte to the fixed ignored candidate path.
Record source and copy SHA-256, size, mtime, header, numbered row count, and
mean ATT. Require byte equality, exactly 72 numbered periods, finite values,
and two expected organizer summary rows. Record the full log SHA-256 and
terminal markers. Do not run sync, smoke, or restoration first.

### Task 6: Score once and apply the immutable decision rule

**Files:**
- Create ignored: `experiments/results/round1_safe_departure_opportunity_gate_v4_20260810.json`
- Modify: `docs/experiments/round1-safe-departure-opportunity-gate-v4.md`

- [ ] **Step 1: Score only the preserved candidate**

Run:

```bash
uv run wsc2026 score \
  --scenario-att .challenge/round1/results/safe_departure_opportunity_gate_v4_20260810/ATT_By_Statistics_Interval.csv \
  --baseline-att .challenge/round1/source/Output/Baseline_ATT_By_Statistics_Interval.csv \
  --json
```

Require a finite score and exactly 72 periods. Record the complete JSON at full
precision.

- [ ] **Step 2: Compare directly with accepted v3**

Compare all 72 numbered ATT values with
`.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`.
Record better/equal/worse counts, candidate-minus-control delta, and relative
percentage. Apply only:

```text
candidate_cumulative_loss < 19.084638612143134 - 1e-9
```

Equality is rejection. Do not round, reinterpret, tune, or launch another v4
candidate.

- [ ] **Step 3: Preserve aggregate evidence and commit the decision before restoration**

Atomically create the ignored aggregate JSON without overwriting. Include the
manifest identity, timestamps, command, exit status, log/ATT hashes, score,
all period losses, mean, 72-period validation, v3 comparison, exact decision
expression, boolean decision, and evidence paths.

Update the tracked report with evidence-limited language and commit:

```bash
git commit -m "docs: record safe-departure gate result"
```

- [ ] **Step 4A: If accepted, retain v4 and update the public current best**

If the expression is true, keep v4 code/tests active. Update `README.md`,
`docs/round1-readiness.md`, `docs/challenge-overview.html`, and the participant
README with the new score, exact delta/percentage, hashes, and a simple
explanation. Do not claim hidden-seed generalization. Commit with:

```bash
git commit -m "docs: publish accepted safe-departure gate result"
```

- [ ] **Step 4B: If rejected or invalid, restore accepted v3 exactly**

If the expression is false, preserve and commit the result first. Revert the
implementation commit, then the RED-test commit, using separate
`git revert --no-edit` operations. Do not revert the design, plan, pre-run, or
result records. Then:

1. synchronize restored v3 into Round 1;
2. restore the pinned v3 ATT snapshot byte-for-byte to active Output;
3. require restored participant/runtime strategy SHA-256
   `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
4. require restored ATT SHA-256
   `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
5. re-score exactly `19.084638612143134` over 72 periods;
6. update the report with restoration evidence; and
7. do not attempt a second v4 candidate.

### Task 7: Run final verification and leave a clean state

**Files:**
- Modify if needed: `docs/experiments/round1-safe-departure-opportunity-gate-v4.md`
- Modify on acceptance: `README.md`
- Modify on acceptance: `docs/round1-readiness.md`
- Modify on acceptance: `docs/challenge-overview.html`

- [ ] **Step 1: Run the complete final gate against the retained policy**

Run the same lock, sync, Ruff, Ty, mypy, non-integration coverage, integration,
sync/cmp, smoke/cmp, deterministic-package, scorer, diff, restricted-material,
single-worktree, single-branch, and no-live-process checks from Task 4. Move the
validation package out of the repository.

- [ ] **Step 2: Audit evidence consistency**

Parse the manifest and aggregate JSON. Recompute every ATT/log/strategy hash,
period count, mean, score, delta, percentage, and decision. Require the tracked
report and public current-best docs to agree with the retained code and active
Output. Verify no organizer material or ignored evidence became tracked.

- [ ] **Step 3: Commit only genuine final documentation corrections**

If final verification requires a tracked correction, stage only the affected
documentation and commit with a precise Conventional Commit message. Do not
create an empty commit.

- [ ] **Step 4: Report the exact final state**

Require a clean `main`, no live simulator, and no push/submission. Report
launch/result commits, candidate score and hashes, strict decision, retained
strategy, evidence paths, gate counts, and whether the next experiment remains
necessary. The overall goal is complete only if the retained candidate score
is strictly below `19.084638612143134 - 1e-9`.
