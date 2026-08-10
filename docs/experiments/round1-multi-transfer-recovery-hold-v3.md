# Round 1 multi-transfer recovery hold v3

## Status

**PRE-RUN APPROVED.** The participant policy, RED-GREEN contract, and complete
preflight are committed. No full candidate simulation has run and no
performance result is claimed.

## Hypothesis

The accepted recovery-aware direct-service hold v2 policy improved cumulative
resilience loss from `20.436668751255972` to `19.828803374740612`, but 25 of
its 72 period ATT values were worse than the no-op fallback. Version 2 held new
cargo whenever an interrupted one-booking direct service was estimated to
recover and deliver sooner than a safe detour containing at least one service
change.

A read-only topology audit found both simple one-change safe paths and more
fragmented paths with at least two service changes among v2-eligible static
observations. Version 3 tests whether delegating the simpler one-change cases
while retaining only the fragmented cases removes harmful holds without losing
the accepted policy's principal benefit. The audit establishes structural
activation only; it is not causal evidence or a performance result.

## Exact candidate policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a non-`None` value. The other three hooks remain unconditional `None`
delegates.

Version 3 retains the complete accepted v2 implementation except for one
eligibility gate. It still requires:

- a new shipment at a distinct origin with no existing booking chain;
- a well-formed active disruption under `start <= now < end`;
- a deterministic nominal shortest path containing exactly one booking edge;
- that nominal edge to intersect an active constraint;
- a complete deterministic safe shortest path;
- positive finite route, fleet, speed, distance, recovery, and timing data;
- `hold_hours < detour_hours` at full precision.

The candidate counts adjacent safe-path edges whose service-route objects
differ by identity. It returns the exact boolean `False` only when that count
is at least two, meaning the safe path requires at least three service
boardings. Zero or one service change delegates with `None`.

The strategy is read-only, deterministic, standard-library-only, and
fail-closed. It contains no scenario name, hard-coded port or route ID,
calendar date, seed table, fitted threshold, file or environment access,
network, subprocess, wall-clock time, randomness, mutable module state, or
organizer-owned import. Both `False` and `None` outcomes leave all observed
runtime objects unchanged.

## Alternatives rejected before implementation

1. A one-headway numeric safety margin adds a debatable approximation and a
   new numeric policy boundary.
2. Live vessel-phase prediction is substantially more complex and resembles a
   previous phase-aware candidate that worsened loss to `24.21744876585007`.

The selected structural refinement is smaller, generalizable, and does not
fit a value to this seed.

## TDD evidence

- approved design: `2207213`;
- executable plan: `d8bcad8`;
- RED contract: `d716ed6`;
- deterministic test formatting: `ee34432`;
- minimum participant implementation: `753e6bf`.

Against accepted v2, the focused RED run collected 40 tests and produced
exactly `1 failed, 39 passed`. The sole failure was
`test_one_transfer_safe_path_delegates_without_mutation`: accepted v2 returned
`False` where v3 requires `None`. This was a behavior failure, not a fixture,
collection, import, or runtime error.

After the one-line route-change gate and participant-owned wording changed,
the same focused selection produced `40 passed`. It includes:

- a positive two-transfer decision returning `False` without mutation;
- one-transfer, same-service, safe-direct, inactive, equality, malformed, and
  incomplete cases delegating without mutation;
- deterministic context-order path ties;
- exact public signatures and forbidden-capability/state checks;
- a real ignored Round 1 context with a derived active-window call whose safe
  path contains at least two service-route changes and whose complete observed
  state is unchanged.

Ruff format/lint, Ty, and mypy passed on the focused participant/test surface
after GREEN. The complete preflight remains required.

## Fixed control and run identity

- repository: sole canonical folder
  `/Users/noeflandre/wintersim-challenge-2026`;
- branch: sole branch `main`, per the user's standing constraint;
- candidate starting point: `87faba27f7b56764cfac50384c935b67296c4817`;
- accepted v2 participant SHA-256:
  `144493d651d0eb967dc8725a34997d118b22ce3db116ca5126699bb8ea2b743c`;
- accepted v2 cumulative loss: `19.828803374740612`;
- accepted v2 ATT SHA-256:
  `d381b087f8d67124a8078b5afc795f5b59b08db90148614b43dcfdf351e7ac48`;
- accepted v2 mean ATT: `20.415972222222222` days;
- accepted v2 snapshot:
  `.challenge/round1/results/recovery_aware_direct_service_hold_v2_20260809/ATT_By_Statistics_Interval.csv`;
- scenario: `create_with_disruption`;
- organizer seed: `2026`;
- process environment: `PYTHONHASHSEED=0`;
- warm-up: 140 days;
- measured horizon: 360 days;
- statistics interval: 5 days;
- required numbered periods: 72;
- exact full-run command:
  `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`;
- candidate evidence directory:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/`;
- aggregate evidence:
  `experiments/results/round1_multi_transfer_recovery_hold_v3_20260810.json`.

The sole acceptance expression is:

```text
candidate_cumulative_loss < 19.828803374740612 - 1e-9
```

It applies to all 72 periods at full precision. Mean ATT is descriptive only.
Equality, worsening, crash, stale or incomplete output, non-finite values,
wrong period count, or a failed gate is rejection.

## Mandatory pre-run gate

Before launch, require locked `uv` resolution; Ruff format and lint; Ty; mypy;
non-integration coverage of at least 90.00%; every integration test; synchronized
participant/runtime byte identity; Round 1 smoke; two byte-identical compliant
packages; current control hash/score/period proof; clean tracked and reachable
restricted-material scans; one worktree; one branch; a clean Git status; and
proof that no simulator is live.

An ignored, non-overwriting manifest must pin candidate HEAD, strategy/runtime
hashes, package hash and member list, accepted v2 evidence, stale Output hash
and mtime, fixed configuration, acceptance expression, and gate results. No
full run is permitted until this tracked report records the exact successful
preflight.

## Pre-run verification record

The full preflight completed on 2026-08-10 before any candidate launch. The
reviewed code/test/report-parent HEAD was
`63138bb459486b32655c2c91ee86936d69e4bdea`. The final launch HEAD is the
documentation commit containing this record and is pinned separately in the
ignored non-overwriting manifest.

- participant strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- synchronized Round 1 strategy SHA-256: the same `f04bda9d...` value;
- participant/runtime strategy comparison: byte-identical before and after
  smoke;
- `uv lock --check`: 29 packages resolved;
- `uv sync --locked --all-groups`: 29 packages resolved and 25 checked;
- Ruff format: 21 files already formatted;
- Ruff lint: all checks passed;
- Ty over `src/wsc2026_tools` and `submission`: all checks passed;
- mypy over the same participant/dev surfaces: 8 files, no issues;
- non-integration suite: 227 passed, 8 deselected;
- true branch coverage: `90.84%`, above the fixed `90.00%` gate;
- real integration suite: 8 passed, 227 deselected;
- Round 1 sync: exactly `README.md` and `user_strategy.py` synchronized;
- one-day Round 1 smoke: `SMOKE_OK` and `smoke: OK`;
- two validation-only Round 1 packages: byte-identical SHA-256
  `5f63fce47a5dc3e5b84cc66660b7772826bdc9b169466796f9d0e327b6068d19`,
  5,907 bytes each;
- package members only:
  `Round1_NoeFlandre/response_strategies/README.md` and
  `Round1_NoeFlandre/response_strategies/user_strategy.py`;
- generated validation archive moved outside the repository to the private
  temporary package-evidence directory; it was not submitted or uploaded;
- accepted v2 control freshly rescored to exactly `19.828803374740612` over 72
  periods;
- accepted v2 snapshot and active stale Output were byte-identical SHA-256
  `d381b087f8d67124a8078b5afc795f5b59b08db90148614b43dcfdf351e7ac48`;
- exact decimal control mean ATT:
  `20.41597222222222222222222222` days;
- stale active Output: 1,262 bytes, mtime epoch `1786269649`;
- `git diff --check`, one-worktree/one-branch checks, and tracked/reachable
  restricted-material scans: clean;
- process inspection found no live WSC run or organizer Round 1 `main.py`
  process (only the inspection command itself matched).

The preflight did not run a full simulation, score candidate output, tune any
parameter, build a second candidate, push, merge, open a pull request, upload,
or submit anything.

## One-run and decision procedure

Exactly one managed full candidate run is permitted. After launch, no code,
test, documentation, policy, or threshold change may precede the decision. The
same process must be monitored to explicit exit zero, Day 360, Period 72, and
`Simulation completed.` A duplicate or tuning run is forbidden.

The raw log and fresh ATT bytes must be copied to the precommitted ignored
evidence directory before scoring, synchronization, smoke, or restoration.
Scoring uses the complete official formula and authoritative Round 1 baseline.

If accepted, v3 remains active and all final gates are rerun. If rejected or
invalid, the result report is committed first; candidate implementation,
formatting, and RED-test commits are reverted in reverse order with `git
revert`; accepted v2 is synchronized; its pinned ATT is restored byte-for-byte
and rescored; and all final gates are rerun. Design, plan, and result history
remain.

No second candidate, tuning, submission, upload, push, merge, pull request, or
history rewrite is part of this experiment.
