# Round 1 disruption-weighted booking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate one self-contained `assign_associated_bookings` policy that chooses the shortest predicted sailing-time path while retaining safe handling of active closed ports and disruption recovery.

**Architecture:** Keep the public four-hook `UserStrategy` adapter intact and delegate three hooks. Add private, standard-library-only routing helpers in the participant module: active-plan extraction, closed-port filtering, route-edge construction, time-dependent leg-duration estimation, deterministic Dijkstra, and atomic booking installation. The helper layer must read runtime objects only and install bookings only after a complete path is validated.

**Tech Stack:** Python 3.11+, `uv`, pytest/pytest-cov, Ruff, `ty`, mypy, the local organizer Round 1 runtime for integration/full-run validation.

---

## Task 1: Create the candidate experiment contract

**Files:**
- Create: `docs/experiments/round1-disruption-weighted-booking-v1.md`

- [ ] **Step 1: Write the tracked contract before candidate code.**

  Record the hypothesis, one-hook scope, return semantics, no-I/O/no-state
  invariants, fixed Round 1 run identity, fallback score/hash/period count,
  strict acceptance expression, ignored evidence paths, one-run rule, and exact
  reject/revert/restore procedure. State that this document is a pre-run
  contract and that the full simulation is not yet authorized.

- [ ] **Step 2: Self-review the contract.**

  Run `rg -n "TBD|TODO|FIXME|placeholder" docs/experiments/round1-disruption-weighted-booking-v1.md` and `git diff --check`. Fix every ambiguity before committing.

- [ ] **Step 3: Commit the contract.**

  Run:

  ```bash
  git add docs/experiments/round1-disruption-weighted-booking-v1.md
  git commit -m "docs: contract Round 1 disruption-weighted booking experiment"
  ```

## Task 2: Add focused RED tests for the candidate behavior

**Files:**
- Modify: `tests/unit/test_user_strategy_contract.py`
- Create: `tests/unit/test_disruption_weighted_booking.py`
- Create: `tests/integration/test_round1_disruption_weighted_booking.py`

- [ ] **Step 1: Add a synthetic graph fixture and behavior assertions.**

  Use `types.SimpleNamespace` or small test-only classes, not organizer
  imports. Cover an active disruption with (a) a short congested direct edge
  versus a longer safe edge, (b) no safe edge, and (c) a disruption that ends
  during the predicted leg. Assert the chosen booking route/segments, exact
  booking sequence, reverse reference, and current index.

- [ ] **Step 2: Add fail-closed and determinism assertions.**

  Cover inactive plans, closed-port exclusion, equal-cost context-order ties,
  malformed context/shipment/route/speed/clock values, no path, and the
  guarantee that delegation and failed planning leave every input unchanged.
  Keep the three untouched hooks and exact signatures covered by the existing
  contract tests.

- [ ] **Step 3: Add the real Round 1 integration check.**

  Follow the existing namespace-isolation helpers used by
  `tests/integration/test_active_disruption_gate.py`. Skip with an actionable
  message when `.challenge/round1/source` is absent. Construct the real
  disruption context, select one demand with a valid origin/destination, call
  the participant hook at a runtime-relative active timestamp, and assert a
  valid chain or documented fail-closed delegation without mutating unrelated
  context collections.

- [ ] **Step 4: Run the focused tests and capture genuine RED.**

  Run:

  ```bash
  UV_CACHE_DIR=/private/tmp/wsc-uv-cache uv run pytest tests/unit/test_disruption_weighted_booking.py tests/unit/test_user_strategy_contract.py -q
  ```

  Expected: collection succeeds and the new active-policy assertions fail
  because the baseline `assign_associated_bookings` returns `None`. Fix test
  fixtures—not production code—until the failure is specifically behavioral.

- [ ] **Step 5: Commit only the RED tests.**

  Run:

  ```bash
  git add tests/unit/test_user_strategy_contract.py tests/unit/test_disruption_weighted_booking.py tests/integration/test_round1_disruption_weighted_booking.py
  git commit -m "test: specify disruption-weighted Round 1 booking policy"
  ```

## Task 3: Implement the minimum participant policy (GREEN)

**Files:**
- Modify: `submission/response_strategies/user_strategy.py`

- [ ] **Step 1: Implement active-plan and route-edge helpers.**

  Use only standard-library imports already permitted in the submission. Read
  `context.disruption_plans`, identify active close-berth plans and active
  congested-leg plans using `datetime.min` plus the supplied offsets, and
  derive a deterministic disruption key. Enumerate context-order service-route
  segments without scenario names or IDs. Exclude routes whose matching
  alternative disruption key is stale or has no deployed vessel. Exclude edges
  that enter, leave, or pass through a closed port; do not exclude congested
  legs merely because they are slowed.

- [ ] **Step 2: Implement time-dependent duration and deterministic Dijkstra.**

  Select a deterministic valid deployed-vessel speed per route. Estimate each
  physical leg's duration from distance/speed, charging the active multiplier
  until each plan ends and normal speed afterward. Run Dijkstra in context port
  order; compute an edge's cost at `now + current_elapsed` so recovery timing is
  represented. Reject non-finite/non-positive values and overflow by returning
  `None`.

- [ ] **Step 3: Install bookings atomically after planning.**

  Validate the complete path first. Only then remove stale reverse references,
  replace `shipment.associated_bookings`, append new `Booking` objects to both
  sides, set the minimum sequence index, and return `True`. If anything is
  malformed or no path exists, return `None` before mutation so the organizer
  fallback remains authoritative.

- [ ] **Step 4: Run focused GREEN tests and all submission checks.**

  Run the focused tests, then:

  ```bash
  UV_CACHE_DIR=/private/tmp/wsc-uv-cache uv run ruff format --check .
  UV_CACHE_DIR=/private/tmp/wsc-uv-cache uv run ruff check .
  UV_CACHE_DIR=/private/tmp/wsc-uv-cache uv run ty check src/wsc2026_tools submission
  UV_CACHE_DIR=/private/tmp/wsc-uv-cache uv run mypy src/wsc2026_tools submission
  ```

  Resolve implementation defects without weakening tests or adding unrelated
  abstractions. The integration check must pass or skip only because Round 1
  organizer source is unavailable.

- [ ] **Step 5: Commit minimal GREEN implementation.**

  Run:

  ```bash
  git add submission/response_strategies/user_strategy.py
  git commit -m "feat: choose disruption-weighted initial booking paths"
  ```

## Task 4: Mandatory preflight and packaging review (no full run yet)

**Files:**
- Modify: `docs/experiments/round1-disruption-weighted-booking-v1.md`

- [ ] **Step 1: Run the full non-operational gates.**

  Run lock/sync, Ruff format/check, `ty`, mypy, non-integration coverage with
  `--cov-fail-under=90`, all integration tests, restricted-material scans, and
  `git diff --check`. Do not launch the full simulation from a failed gate.

- [ ] **Step 2: Synchronize and inspect the real runtime.**

  Run `uv run wsc2026 sync --round round1`, compare the participant strategy
  with the Round 1 source, and run `uv run wsc2026 smoke --round round1`.
  Confirm the submission module has no forbidden imports or I/O and that no
  candidate helper is missing from the package.

- [ ] **Step 3: Build the validation package twice.**

  Run `uv run wsc2026 package --team ValidationTeam --round 1` twice, compare
  bytes/SHA/member list, and verify only participant-owned allowlisted files
  are present. Move validation archives out of the repository's generated
  directory if needed.

- [ ] **Step 4: Record the pre-run review.**

  Update the experiment report with candidate commit/strategy hashes, gate
  outputs, package metadata, and explicit confirmation that no simulation has
  started. Commit the report. Stop for a human-readable review checkpoint
  before the long run.

## Task 5: Authorize and execute exactly one full candidate

**Files:**
- Modify: `docs/experiments/round1-disruption-weighted-booking-v1.md`
- Create (ignored): `.challenge/round1/results/disruption_weighted_booking_v1_20260807/`

- [ ] **Step 1: Pin run identity and process state.**

  Record candidate HEAD, strategy SHA, synchronized copy SHA, pinned fallback
  ATT hash/score, current Output ATT hash/mtime, and a clean process check. Use
  `PYTHONHASHSEED=0` and prove no other `wsc2026`/organizer process is running.

- [ ] **Step 2: Run one command only.**

  Run `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full` exactly once,
  redirecting to the precommitted ignored log. Monitor the same process every
  30–50 seconds until Period 72/Day 360/`Simulation completed`/exit 0. Never
  start a duplicate or change code/threshold after launch.

- [ ] **Step 3: Preserve fresh evidence before any restore.**

  Copy the fresh ATT CSV and log into the exact ignored evidence directory,
  record SHA/size/mtime/header/periods/mean, score against the authoritative
  baseline with `--json`, and compute per-period better/equal/worse counts.
  Create the ignored aggregate JSON and update the tracked report with the
  complete result and decision.

- [ ] **Step 4: Commit the result record before restoration.**

  Run `git add docs/experiments/round1-disruption-weighted-booking-v1.md && git commit -m "docs: record Round 1 disruption-weighted booking result"`.

## Task 6: Apply the acceptance gate and finish cleanly

- [ ] **Step 1: If accepted, retain the candidate and document exact evidence.**

  Acceptance is only the unrounded strict expression from the contract. Run
  every final gate again and do not claim submission readiness without package
  inspection and restricted scans.

- [ ] **Step 2: If rejected/equal/invalid, revert candidate code/tests.**

  Preserve evidence first. Revert the implementation and RED-test commits in
  reverse order with `git revert`; keep the contract and result report. Sync
  the no-op adapter from the restored submission, restore the pinned fallback
  ATT bytes from its ignored snapshot, and re-score to exactly
  `20.436668751255972`.

- [ ] **Step 3: Run every final gate fresh.**

  Repeat lock/sync, Ruff, `ty`, mypy, coverage, integration, Round 1 sync/cmp,
  smoke, deterministic packaging twice, ATT hash/score, diff hygiene,
  restricted-material scans, and process checks. Confirm the worktree is clean
  and no full-run process remains.

- [ ] **Step 4: Reconcile only after review.**

  Use the finishing-a-development-branch workflow: fast-forward the clean
  result to `main` only after verification, remove the temporary experiment
  worktree/branch, verify only `/Users/noeflandre/wintersim-challenge-2026`
  remains, and synchronize remote `main` if explicitly requested. Do not open a
  PR or submit an archive as part of this experiment.
