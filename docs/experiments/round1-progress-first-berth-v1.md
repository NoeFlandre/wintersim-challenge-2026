# Round 1 progress-first berth priority v1

Status: PRE-RUN REVIEW

## Hypothesis

Round 1 has disruption windows in which a berth queue can contain vessels with
different immediate prospects. The organizer fallback ranks waiting time,
carried TEU, vessel capacity, and handling workload, but does not ask whether
the vessel's next physical leg or destination berth is currently blocked. This
candidate tests whether selecting a vessel that can make immediate progress,
while retaining the fallback ranking among those vessels, reduces downstream
congestion.

## Fixed policy

`UserStrategy.select_vessel_for_berth` examines the runtime context only during
an active disruption. A vessel is progress-capable when its next physical leg
is not an active congested leg and its next leg's arrival port has no active
closed berth. It is blocked when either condition is true.

The hook returns an original progress-capable waiting vessel only when the
queue contains at least one vessel in each class. It reproduces the organizer
fallback's normalized ranking over the complete queue and uses queue order for
an exact tie. Empty queues, inactive disruptions, all-progress/all-blocked
queues, malformed inputs, and every other hook return `None` so the organizer
fallback handles them.

The implementation is participant-owned, standard-library-only, read-only, and
contains no scenario names, ports, routes, dates, seeds, tuned thresholds,
randomness, I/O, organizer imports, or mutable module state.

## Fixed run contract

- Scenario: `create_with_disruption`
- Round: `round1`
- Seed: `2026`
- Warm-up: `140` days
- Measured horizon: `360` days
- ATT interval: `5` days
- Required periods: `72`
- Environment: `PYTHONHASHSEED=0`
- Candidate command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- Pinned fallback cumulative resilience loss: `20.436668751255972`
- Pinned fallback ATT SHA-256: `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- Acceptance expression: `candidate_loss < 20.436668751255972 - 1e-9`

Evidence is private and ignored under
`.challenge/round1/results/progress_first_berth_v1_20260804/`; the aggregate
record is `experiments/results/round1_progress_first_berth_v1_20260804.json`.
The candidate output must be copied there before any score-based restoration.

## TDD and gates

RED tests prove the no-op baseline delegates in the mixed queue and prove that
the new helper is rejected until explicitly added to both overlay and package
allowlists. GREEN tests cover active interval boundaries, closed-arrival and
congested-leg classification, fallback ranking and tie order, malformed
fail-closed behavior, object identity, no mutation, and the four-hook contract.
The ignored integration test uses real Round 1 objects and checks state
preservation.

Before the full run, lock/sync, Ruff, `ty`, mypy, non-integration coverage
(minimum 90%), integration, sync/cmp, Round 1 smoke, deterministic packaging
twice, restricted-material, diff, and process gates must all pass.

## Rejection and cleanup

Exactly one candidate full run is authorized. Equality, worsening, a crash,
incomplete output, a non-72-period CSV, or any failed runtime/package gate is
rejection. No tuning or second candidate is allowed.

For rejection, preserve the raw CSV, log, score, hashes, period statistics,
and package metadata first; commit this report; revert candidate code/tests and
candidate-only allowlist changes with `git revert`; synchronize the no-op
adapter; restore the pinned fallback ATT from
`.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`;
re-score it to the pinned loss; and repeat every final gate. No organizer
source, input, output, or archive may be tracked or published.

## Result

The candidate full run was executed exactly once on 2026-08-04 with the fixed
command and environment. It exited 0 and recorded all 72 period markers,
`Output Simulation Day: 360`, `Simulation completed.`, and
`CSV output written`. The simulator reported `00:34:14`.

- Candidate cumulative resilience loss: `20.436668751255972`
- Pinned fallback cumulative resilience loss: `20.436668751255972`
- Delta: `0.0` (`0.0%`)
- Strict gate: **rejected**; equality is not `< fallback - 1e-9`
- Candidate ATT SHA-256: `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- Candidate ATT periods: `72`
- Candidate mean ATT: `20.450972222222223` days across numbered rows
- Candidate vs fallback ATT: byte-identical; 0 periods better, 72 equal, 0 worse
- Candidate raw log SHA-256: `8029e7ef6ac048d0e59e6bfa3e20e3827ecd3aa692bb2030a6513ff029309019`
- Candidate package SHA-256: `6512645352e5f8e1c23a9837bd45d92ebef3fe836d344f2b74b7001749325fea`
- Candidate package members: `README.md`, `progress_first_berth.py`,
  `user_strategy.py` under `response_strategies/`

Raw evidence is retained privately under
`.challenge/round1/results/progress_first_berth_v1_20260804/`:
`ATT_By_Statistics_Interval.csv`, `run.log`, and `score.json`. The ignored
aggregate record is
`experiments/results/round1_progress_first_berth_v1_20260804.json`.

The experiment is **REJECTED — no measurable change**. The implementation and
candidate-only tests/allowlist changes must be reverted before the final gates;
the tracked contract and this result record remain as the audit trail.
