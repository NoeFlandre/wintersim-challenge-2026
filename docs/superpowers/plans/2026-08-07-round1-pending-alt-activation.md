# Pending Alternative-Route Vessel Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test exactly one narrow Round 1 berth-selection policy that activates
an already-reserved empty vessel at the first port of its pending alternative
service route during an active disruption, then evaluate it once against the
pinned no-op fallback.

**Architecture:** Keep the participant surface in
`submission/response_strategies/user_strategy.py`. Use two private,
read-only helpers for disruption-window and pending-route inspection. Preserve
the three other hooks as `None`, and never import organizer code or mutate
runtime objects. Work in the isolated worktree
`/private/tmp/wsc-round1-pending-alt-activation-v1`; the organizer source and
outputs remain ignored/private.

**Tech Stack:** Python 3.11+, `uv`, pytest/pytest-cov, Ruff, `ty`, mypy, and the
repository `wsc2026` CLI with the local ignored Round 1 source for integration
and one full-run validation.

---

## 1. Freeze the contract before code

- [x] Create `docs/superpowers/specs/2026-08-07-round1-pending-alt-activation-design.md` with the hypothesis, exact policy, pinned fallback, strict acceptance expression, evidence paths, and rejection/restore rules.
- [x] Create this implementation plan with concrete commands and review stops.
- [x] Inspect the diff and run a temporary-marker search over the new documents. Remove every ambiguity and run `git diff --check`.
- [x] Commit only the spec and plan as `docs: define Round 1 pending alternative activation experiment`.

## 2. RED: specify observable behavior

- [x] Add `tests/unit/test_pending_alt_activation.py` using small local fakes for plans, ports, legs, ordered segments, routes, and vessels. The tests must assert:
  - an active matching vessel returns the exact original object;
  - queue order wins when multiple vessels match;
  - the start boundary is active and the end boundary is inactive;
  - inactive/no-plan contexts delegate;
  - carried vessels, missing routes, empty routes, wrong departure ports, missing sequence/leg fields, malformed plans, and malformed queues fail closed;
  - input lists, route segments, vessel fields, and context plans are unchanged;
  - the other three hooks still return `None` and all required signatures remain exact.
- [x] Run the focused tests against the untouched no-op adapter. Capture genuine RED failures caused by the expected matching case, not fixture/import errors.
- [x] Commit the RED tests as `test: specify pending alternative activation policy`.

## 3. GREEN: implement the smallest valid strategy

- [x] In `submission/response_strategies/user_strategy.py`, update the module/class documentation and add only standard-library imports needed for `datetime` and `Any`.
- [x] Implement `_has_active_disruption(context, now)` with `datetime.min` anchoring, inclusive-start/exclusive-end comparisons, and fail-closed handling of malformed numeric/overflow input.
- [x] Implement `_pending_route_starts_at_port(vessel, port)` with empty-carried check, lowest `sequence_index`, associated-leg lookup, identity comparison, and fail-closed handling. Do not sort or mutate the route's segment collection.
- [x] Make `select_vessel_for_berth` return the first eligible original waiting-vessel object only when the active gate is true; otherwise return `None`. Do not inspect or modify available berths or waiting-time scores.
- [x] Keep the three remaining hooks unconditional `None` and do not add new files to the package allowlist.
- [x] Run focused tests, then Ruff format/lint, `ty`, and mypy. Fix only behavior or typing defects required by the contract.
- [x] Commit the implementation as `feat: activate pending alternative route vessels`.

## 4. Real integration and coverage

- [x] Add `tests/integration/test_round1_pending_alt_activation.py`, marked `integration`, that skips clearly if `.challenge/round1/source` is absent. Load the participant module by absolute file path, construct the real `scenario_builders.create_with_disruption()` context, choose a timestamp inside an actual disruption plan using `datetime.min`, and exercise a real port/route/vessel-shaped pending alternative without importing the participant package into the organizer namespace.
- [x] Assert returned identity, active/inactive boundary behavior, carried-vessel delegation, and a before/after snapshot of context, routes, vessels, and plans.
- [x] Run focused unit+integration tests and the complete non-integration coverage command with `--cov-fail-under=90`; add only meaningful branch tests if needed.
- [x] Commit integration/coverage corrections as `test: verify pending alternative activation in Round 1 context`.

## 5. Pre-run review and gates (no simulation yet)

- [x] Write `docs/experiments/round1-pending-alt-activation-v1.md` with status `PRE-RUN REVIEW`, the fixed hypothesis/policy, prior evidence, run identity, pinned fallback score/hash, evidence locations, and the exact acceptance/rejection rule.
- [x] Review source, tests, docs, and the complete diff. Verify no scenario constants, organizer imports, I/O, mutable globals, random/time/environment access, package-surface expansion, or untracked organizer files.
- [x] Run all preflight commands from the spec: `uv lock --check`; locked `uv sync --all-groups`; Ruff format/check; `ty`; mypy; non-integration coverage; integration tests; `uv run wsc2026 sync --round round1`; `cmp` for strategy and README; Round 1 smoke; deterministic package twice; restricted-material scans; `git diff --check`; and a no-process check.
- [x] Verify the active fallback ATT hash and score exactly match the pinned control, record the strategy SHA, package SHA/member list, and test outputs in the report.
- [x] Commit the reviewed PRE-RUN report. Stop and inspect this commit before launching the full run.

## 6. Exactly one candidate run and evidence preservation

- [x] Start exactly one fixed run with `PYTHONHASHSEED=0`, redirecting stdout/stderr to `/tmp/wsc_round1_pending_alt_activation_v1_20260807.log`. Poll at most every 30 seconds; do not edit code, tune parameters, or start another process while it runs.
- [x] Require exit 0 and log markers for Period 72, Day 360, simulation completion, and CSV output. If any is absent, reject without inventing a score.
- [x] Immediately copy the candidate ATT CSV and run log into `.challenge/round1/results/pending_alt_activation_v1_20260807/` and hash them before invoking the scorer.
- [x] Score only the preserved candidate against the pinned Round 1 baseline, compute period count/mean and better/equal/worse counts, and write the ignored aggregate JSON. Commit the tracked report with exact outcome before restoration.

## 7. Apply the strict decision and finish cleanly

- [x] Accept only a strict improvement below `20.436668751255972 - 1e-9`; otherwise label `REJECTED` and state equality/worsening precisely.
- [x] For rejection, `git revert` candidate-only implementation/test commits in reverse order, synchronize the no-op adapter, restore the pinned fallback ATT from the ignored control snapshot, re-score exact equality, and rerun every final gate. Keep the experiment report and ignored evidence; do not run a second candidate.
- [x] For acceptance, retain the implementation and run every final gate without a second simulation.
- [x] Update `README.md`, `docs/round1-readiness.md`, and `docs/challenge-overview.html` only after the result, adding the fourth Round 1 experiment with plain-language outcome and link. Do not publish private evidence or organizer files.
- [x] Commit final documentation with a Conventional Commit message, verify `git status`, branch history, restricted scans, active runtime SHA, ATT SHA, and score.
- [x] Copy ignored evidence/aggregate from this worktree into the root checkout before removing the worktree. Reconcile the final result onto the single `main` checkout, rerun the final verification there, and leave a clean, resumable state. Push only if the user explicitly requests publication; otherwise report the exact local branch/commit and safe handoff boundary.
