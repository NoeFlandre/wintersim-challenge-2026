# Round 1 TEU-delay Smith-priority berth scheduling v2

Status: PRE-RUN REVIEW — one candidate run is not authorized until every gate
below passes.

## Hypothesis

The organizer berth fallback mixes waiting time, carried TEU, vessel capacity,
and a handling-workload penalty. During an active disruption, the metric is a
TEU-weighted average transport time, so the queue should first serve the vessel
that releases the greatest amount of TEU-weighted downstream work per unit of
berth occupancy. A Smith-style ratio that includes the organizer's fixed
three-hour berthing overhead may reduce the waiting component of ATT without
changing routes or bookings.

## Exact candidate policy

Only `UserStrategy.select_vessel_for_berth` is overridden. The policy is active
only while at least one well-formed disruption plan contains the current time.
For every waiting vessel it mirrors the organizer's cargo-handling inputs:

- carried TEU, including cargo continuing beyond the current port;
- TEU scheduled to discharge at the current segment;
- greedily predicted eligible loading TEU at the next segment, bounded by
  remaining vessel capacity;
- the organizer's crane count `max(1, int(loa / 55))`.

The ratio is:

```text
(affected TEU × crane count) /
(handled TEU + 135 × crane count)
```

The denominator is proportional to handling hours plus the fixed three-hour
berthing duration (`3 × 45` TEU-hours per crane). The candidate returns the
original vessel with the greatest exact cross-multiplied ratio. Equal ratios
keep waiting-queue order. Malformed inputs, inactive disruptions, and empty
queues return `None`, delegating to the organizer fallback. The other three
hooks always return `None`.

The implementation is read-only, deterministic, standard-library-only, and
contains no scenario names, hard-coded ports/dates/seeds, I/O, network,
subprocesses, environment reads, wall-clock calls, randomness, or mutable
module-level state.

## Fixed run contract

- round: `round1`
- scenario: `create_with_disruption`
- seed: `2026`
- warm-up: `140` days
- measured horizon: `360` days
- ATT interval: `5` days; required rows: `72`
- environment: `PYTHONHASHSEED=0`
- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- fallback snapshot:
  `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`

Accept only when the complete candidate scorer result satisfies, without
rounding:

```text
candidate_loss < 20.436668751255972 - 1e-9
```

## Evidence and rejection protocol

The candidate CSV and raw log must be copied to the ignored evidence directory
`.challenge/round1/results/teu_delay_smith_priority_v2_20260807/` before any
restoration. Record the CSV hash/size/mtime, 72-period count and mean, full
scorer JSON, per-period better/equal/worse counts, run-log hash, package hash
and members, and the exact decision in this report and an ignored aggregate
JSON under `experiments/results/`.

Equality, worsening, a crash, an incomplete run, a non-72-row CSV, or any
failed final gate is rejection. On rejection, preserve the evidence, record
the result, revert candidate-only code/tests, synchronize the no-op adapter,
restore the pinned fallback bytes, re-score exactly to the pinned loss, and
rerun every final gate. Do not tune, rerun, try a second candidate, submit,
rewrite history, or publish organizer material.

## Pre-run gates

Before the one full candidate run: RED tests must fail against the no-op
baseline and GREEN tests must pass after implementation; the real Round 1
integration contract must pass; `uv lock --check`, locked `uv sync`, Ruff
format/check, `ty`, mypy, non-integration coverage at least 90%, integration
tests, sync/cmp, smoke, deterministic packaging twice, restricted-material
scans, diff hygiene, and process checks must all pass. No full run is allowed
until this stop point has been reviewed.

## Pre-run review record

- RED focused tests: 3 failures against the no-op baseline (expected).
- GREEN focused tests: 16 passed; real Round 1 integration: 1 passed.
- Non-integration suite: 206 passed, 8 integration tests deselected;
  coverage `91.77%`.
- Full integration suite: 8 passed.
- `uv lock --check`: passed; locked dependency resolution: 29 packages.
- Ruff format/check, `ty`, and mypy: passed.
- Round 1 sync/cmp and smoke: passed (`SMOKE_OK`).
- Two deterministic packages: SHA-256
  `9963b0f50d0e76286e526f858df7edf1e72fa335a505f92dde0b0b394358339c`;
  members are only `README.md` and `user_strategy.py`.
- Candidate strategy SHA-256:
  `22042a18a0f9c62b7471be4ea02a95f6644f220f7b47185c22843667ae5c2d66`.
- Pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`.
- Restricted-material and diff checks: passed; no matching simulation process
  is running.

This is the final stop point before the single candidate full run. The run is
authorized only under the fixed command and acceptance rule above.

## Candidate result (2026-08-07)

The authorized command was executed exactly once with `PYTHONHASHSEED=0`. The
process exited `0` after a reported simulation runtime of `00:25:05`. The raw
log contains all 72 period markers, `Output Simulation Day: 360`,
`Simulation completed.`, and the output-directory marker.

- candidate cumulative resilience loss: `20.436668751255972`
- pinned fallback cumulative resilience loss: `20.436668751255972`
- delta: `0.0`
- candidate ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- candidate ATT: 72 periods, mean `20.450972222222223` days, 1,262 bytes
- candidate versus fallback periods: 0 better, 72 equal, 0 worse
- run-log SHA-256:
  `ef8ba418898f37863a0c34fd2eb30a0ea6771ada2a93e746d7cec789caa480ab`
- candidate package SHA-256:
  `9963b0f50d0e76286e526f858df7edf1e72fa335a505f92dde0b0b394358339c`

Decision: **REJECTED — strict equality**. The acceptance rule requires a
strict improvement below the fallback by more than `1e-9`; the candidate ATT
CSV is byte-identical to the pinned fallback and therefore demonstrates no
measurable change.

Private ignored evidence is preserved in
`.challenge/round1/results/teu_delay_smith_priority_v2_20260807/` (ATT CSV,
raw log, score JSON, and candidate package). The machine-readable aggregate is
`experiments/results/round1_teu_delay_smith_priority_v2_20260807.json`.

The candidate implementation and tests must now be reverted in reverse order;
the no-op participant adapter and pinned fallback output must be restored and
all final gates rerun. No second run, tuning, submission, or publication is
authorized.

## Post-rejection restoration

The candidate-only implementation and tests were reverted with Git in reverse
order. The participant adapter was synchronized from the no-op submission
(`b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`), and the
pinned fallback ATT bytes were restored from the pre-run fallback evidence.
The restored ATT SHA is
`c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`; scoring
the restored output again returned `20.436668751255972` over 72 periods.

The candidate evidence remains private and ignored. No second simulation,
tuning, replay, submission archive, or organizer-material publication was
performed.

Post-restoration verification passed: `uv lock --check`; locked dependency
sync from the existing cache; Ruff format/check; `ty`; mypy; 188
non-integration tests with 90.93% coverage; 7 integration tests; Round 1
sync/cmp; smoke (`SMOKE_OK`); and restricted-material/diff/process checks.
Two fallback packages were byte-identical at SHA-256
`82b075e6d6a7513ebbc26f4b1b8384b86bba4892681c88f1f33efec21db298a1`, with
only `README.md` and `user_strategy.py` members. The working tree is clean.
