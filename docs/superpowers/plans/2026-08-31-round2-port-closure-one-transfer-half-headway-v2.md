# Round 2 Port-Closure One-Transfer Half-Headway v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and evaluate one conservative, identity-free half-headway extension to the accepted Round 2 port-closure recovery hold while preserving a clean fallback on rejection.

**Architecture:** Keep the existing `UserStrategy.assign_associated_bookings` graph and timing helpers unchanged. Replace only the exact-one-route-change port-closure margin boundary, leaving the accepted full-headway cases and every other hook delegated or unchanged. Use synthetic contracts plus a real ignored-context activation audit, then one frozen full simulation.

**Tech Stack:** Python 3.11+, standard library participant code, `uv`, pytest/coverage, Ruff, Ty, mypy, and the repository's `wsc2026` CLI.

---

### Task 1: Add the RED behavioral contract

**Files:**
- Modify: `tests/unit/test_round2_port_closure_one_transfer_v1.py`
- Create: `tests/integration/test_round2_port_closure_half_headway_v2_real_context.py`

- [ ] **Step 1: Add focused unit assertions before production changes**

Extend the existing fixture-based unit module with these behaviors:

```python
def test_half_headway_port_closure_one_transfer_holds() -> None:
    context, now, shipment, _ = _one_transfer_fixture((157.0, 157.0))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is False


def test_half_headway_equality_delegates() -> None:
    distance = 470.0 / 3.0
    context, now, shipment, _ = _one_transfer_fixture((distance, distance))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None


def test_below_half_headway_delegates() -> None:
    context, now, shipment, _ = _one_transfer_fixture((156.0, 156.0))

    assert UserStrategy.assign_associated_bookings(context, now, shipment) is None
```

The existing full-headway, pure-leg, mixed-constraint, malformed, and
multi-transfer tests remain unchanged and cover retained behavior. If the
exact-equality fixture is affected by floating-point rounding, derive the
expected boundary from the same helper calculations and choose the nearest
representable distance whose computed margin is exactly no greater than half
the computed headway; do not weaken the production comparison.

- [ ] **Step 2: Add the real Round 2 integration contract**

Create an integration test that skips when `round2` source is absent, clears
organizer namespaces before import, loads the participant file by absolute
path, and evaluates fresh `create_with_disruption()` contexts at every integer
day midpoint in every valid disruption window. For every demand, construct a
new origin-waiting `Shipment`, snapshot all observed context and shipment
state, and evaluate the current participant hook. Reproduce the candidate
oracle using participant pure helpers: one nominal edge, at least two safe
edges, exactly one route change, matching constraint kinds exactly `{"port"}`,
finite positive timing values, and `0.5 * max_headway < margin <= max_headway`.
Require at least one such candidate-only observation, require the hook to
return `False` for it, require all before/after snapshots to match, and assert
that the organizer Output ATT path's `(exists, size, sha256, mtime_ns)` tuple
is unchanged. Also retain one out-of-window call that returns `None` without
mutation.

- [ ] **Step 3: Run the focused RED selection**

Run:

```bash
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run pytest \
  tests/unit/test_round2_port_closure_one_transfer_v1.py \
  tests/integration/test_round2_port_closure_half_headway_v2_real_context.py -q
```

Expected result: collection/import succeeds; the new half-headway-above-bound
unit and real candidate-only assertion fail because the unchanged control
delegates below the full-headway threshold; unrelated existing tests pass.

- [ ] **Step 4: Commit only the RED contract**

```bash
git add tests/unit/test_round2_port_closure_one_transfer_v1.py \
  tests/integration/test_round2_port_closure_half_headway_v2_real_context.py
git commit -m "test: define round2 half-headway recovery hold"
```

### Task 2: Implement the minimal participant policy

**Files:**
- Modify: `submission/response_strategies/user_strategy.py` at `_should_hold`
- Modify: `submission/response_strategies/README.md`

- [ ] **Step 1: Change only the frozen comparison**

In the exact-one-route-change, port-only branch, preserve every preceding
guard and replace only:

```python
return max_headway is not None and margin > max_headway
```

with:

```python
return max_headway is not None and margin > 0.5 * max_headway
```

Keep the strict comparison, finite-value checks, `None` delegation, and all
v3/multi-transfer behavior. Update the module docstring and participant README
to say that the accepted Round 2 policy now uses a strict half-headway margin
for the port-closure-only one-transfer extension. Do not add configuration,
new hooks, organizer imports, I/O, state, or dependencies.

- [ ] **Step 2: Run the same selection GREEN**

```bash
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run pytest \
  tests/unit/test_round2_port_closure_one_transfer_v1.py \
  tests/integration/test_round2_port_closure_half_headway_v2_real_context.py -q
```

Expected result: all focused unit and real-context tests pass, including
immutability and candidate-only activation.

- [ ] **Step 3: Run changed-surface static checks**

```bash
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run ruff format --check submission tests/unit tests/integration
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run ruff check submission tests/unit tests/integration
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run ty check src/wsc2026_tools submission
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run mypy src/wsc2026_tools submission
```

- [ ] **Step 4: Commit the minimal GREEN implementation**

```bash
git add submission/response_strategies/user_strategy.py submission/response_strategies/README.md
git commit -m "feat: extend round2 closure hold to half headway"
```

### Task 3: Freeze the real activation audit and experiment contract

**Files:**
- Create ignored: `.challenge/round2/results/port_closure_one_transfer_half_headway_v2_20260831/activation_audit.py`
- Create ignored: `.challenge/round2/results/port_closure_one_transfer_half_headway_v2_20260831/activation_audit.json`
- Modify: `docs/experiments/round2-port-closure-one-transfer-half-headway-v2.md`

- [ ] **Step 1: Run a fresh, non-mutating activation audit**

Use disposable real contexts at all 166 valid integer-day midpoints and every
demand in context order. Set up default alternative routes only on each fresh
context, never advance a model, never call the full-run entry point, and never
write Output. Evaluate the independent v3 oracle and the frozen half-headway
predicate on the same observation set. Snapshot context and shipment state
around every participant call. Atomically create the ignored JSON and refuse
overwrites. Record schema version, exact candidate-definition hash, counts,
anonymous shape/boundary counts, annual-TEU exposure proxy, hashes, and
`no_mutation=true`, `model_advanced=false`, `output_written=false`.

Expected structural result from the pre-code audit: 76 additional candidate-only
observations beyond the accepted full-headway policy, all port-only one-change
cases, with exposure proxy 163,600. These are activation evidence, not a score
prediction; if the implementation audit disagrees, stop and correct tests/code
before any full run.

- [ ] **Step 2: Run every preflight gate before launch**

```bash
UV_CACHE_DIR=/tmp/wsc-uv-cache uv lock --check
UV_CACHE_DIR=/tmp/wsc-uv-cache uv sync --locked --all-groups
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run ruff format --check .
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run ty check src/wsc2026_tools submission
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run mypy src/wsc2026_tools submission
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run pytest -m "not integration" \
  --cov=src/wsc2026_tools --cov=submission --cov-branch \
  --cov-report=term-missing --cov-fail-under=90
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run pytest -m integration -q
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run wsc2026 sync --round round2
cmp submission/response_strategies/user_strategy.py \
  .challenge/round2/source/response_strategies/user_strategy.py
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run wsc2026 smoke --round round2
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run wsc2026 package --team ValidationTeam --round 2
UV_CACHE_DIR=/tmp/wsc-uv-cache uv run wsc2026 package --team ValidationTeam --round 2
git diff --check
```

Compare package bytes/hashes and members; only the participant README and
strategy may be present. Scan tracked/reachable history for restricted material
and confirm one clean `main` worktree and no live WSC process.

- [ ] **Step 3: Freeze a non-overwriting pre-run manifest**

Record the exact launch HEAD, participant/runtime hashes and byte identity,
package hash/members, fresh accepted-control ATT and score, authoritative
baseline hash, stale active Output metadata, audit hash, run configuration,
command, evidence paths, strict acceptance expression, and one-candidate/no-
tuning rule in the ignored experiment directory. Do not launch if any identity
or gate differs from the tracked report.

### Task 4: Execute, score, and decide exactly one candidate

**Files:**
- Create ignored: `.challenge/round2/results/port_closure_one_transfer_half_headway_v2_20260831/full_run.log`
- Create ignored: `.challenge/round2/results/port_closure_one_transfer_half_headway_v2_20260831/ATT_By_Statistics_Interval.csv`
- Create ignored: `.challenge/round2/results/port_closure_one_transfer_half_headway_v2_20260831/score.json`
- Modify: `docs/experiments/round2-port-closure-one-transfer-half-headway-v2.md`

- [ ] **Step 1: Launch only the frozen command**

```bash
PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache \
  uv run wsc2026 run --round round2 --full \
  > .challenge/round2/results/port_closure_one_transfer_half_headway_v2_20260831/full_run.log 2>&1
```

Monitor that exact process below 60-second intervals. Require exit 0, Period
72, Day 360, `Simulation completed.`, and a fresh ATT write. Never edit code,
change the threshold, or start a duplicate run.

- [ ] **Step 2: Preserve evidence before any overwriting command**

Copy the fresh Output ATT and raw log into the predeclared ignored directory,
record byte size/mtime/header/SHA-256, and verify exactly 72 numbered periods
before scoring. Do this before sync, smoke, packaging, or restoration.

- [ ] **Step 3: Score and apply the immutable gate**

Score the preserved ATT with the repository scorer against the Round 2
authoritative baseline. Record full-precision loss, per-period values,
mean ATT, better/equal/worse counts versus the accepted control, and hashes.
Accept only:

```text
candidate_loss < 35.1039547178493 - 1e-9
```

Equality, worsening, invalid output, incomplete run, or a failed gate is
rejection. Update the tracked report only with observed evidence.

### Task 5: Retain or restore and finish cleanly

- [ ] **Step 1: If accepted, retain the candidate**

Keep the candidate active, re-run all final gates, re-score its active ATT,
build the deterministic package twice, update the report and public Round 2
readiness summary, and leave `main` clean with no live simulator. Do not push,
merge, submit, or upload.

- [ ] **Step 2: If rejected or invalid, restore the exact control**

Commit the result report before changing code. Revert only this experiment's
implementation and RED-test commits in reverse order with `git revert`, sync
the accepted v1 participant strategy, restore the pinned accepted-control ATT
bytes, re-score exactly `35.1039547178493`, and rerun every lock, format, lint,
Ty, mypy, coverage, integration, sync/cmp, smoke, package, restricted-history,
process, diff, and Git-cleanliness gate. Keep all ignored candidate evidence
and tracked design/result history. Do not attempt a second candidate or tuning.

- [ ] **Step 3: Write the final evidence-limited report**

Include branch/HEAD, candidate and control hashes, package hash/members, run
markers, score/delta/relative change, period comparison, decision, evidence
paths, restoration proof when applicable, every gate result, restricted scan,
clean state, and actions not taken. Distinguish activation evidence from
causal performance evidence.
