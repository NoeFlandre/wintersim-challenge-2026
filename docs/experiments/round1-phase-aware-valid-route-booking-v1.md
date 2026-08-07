# Round 1 phase-aware valid-route booking v1

**Status:** PRE-RUN REVIEW COMPLETE — FULL RUN AUTHORIZED

## Pre-run review record

The candidate was reviewed before any full simulation. The implementation and
tests are committed as `93101d5`, `91b4e22`, and `8e0a286`; the review removed
unused state and replaced broad exception handling with explicit fail-closed
exception sets required by the submission contract. The RED unit tests first
failed against the no-op adapter, then the GREEN suite passed on the real Round
1 context. The final preflight passed locked dependency checks, Ruff format and
lint, Ty, mypy, 201 non-integration tests with 92.41% coverage, the integration
suite (Round 1 contract passed; Round 0-only checks skipped because its source
is not present in this isolated clone), runtime byte comparison, smoke, two
identical participant-only packages, restricted-material scans, and a clean
process check.

The pinned fallback was independently rescored immediately before launch:
`period_count=72`, cumulative resilience loss
`20.436668751255972`, ATT SHA-256
`c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`.
Candidate strategy SHA-256 is
`0f3129792dbefb18239ba2349942e2aa59de9b622a098424ce2618fe95943de9`.
No full run has started at this checkpoint. Exactly one full candidate run is
authorized under the fixed contract below; no tuning or second run is allowed.

## Hypothesis

During active disruptions, the next service opportunity can dominate a small
sailing-distance difference. The organizer fallback chooses the shortest
nominal-distance path among valid routes but does not estimate the next vessel
phase. A phase-aware path that still obeys every fallback disruption exclusion
may reduce TEU-weighted Average Transport Time.

## Exact candidate policy

Only `UserStrategy.assign_associated_bookings` is overridden, and only while a
valid disruption plan is active. The candidate mirrors the organizer's rules:

- closed berth ports are excluded;
- active congested legs are excluded;
- an alternative route is usable only when its disruption key matches the
  active key and it has deployed vessels;
- original routes remain eligible.

It enumerates the same contiguous route-slice edges as the organizer, then
assigns each edge an estimated cost consisting of nominal distance divided by
the route's fastest deployed-vessel speed plus the earliest nominal wait for a
deployed vessel on that route to reach the edge's departure port. Current vessel
segment/berth position and cyclic route order are read without mutation. A
vessel awaiting its first release uses the route's configured weekday and the
fixed seven-day headway. Dijkstra selects the minimum estimated total; exact
ties retain edge/context order.

The path is fully validated before any mutation. Booking installation snapshots
old shipment and reverse-route references and rolls back all touched state on
failure. Any malformed state, non-finite value, missing route/vessel position,
inactive disruption, empty queue, or no complete path returns `None` so the
organizer fallback remains authoritative. The other three hooks return `None`.

The submitted code is standard-library-only, deterministic, read-only except
for the validated booking installation, and contains no organizer imports at
module import, I/O, environment access, network, subprocess, wall-clock, seed,
port-name, route-ID, or mutable cross-run state.

## Fixed run contract

- round: `round1`
- scenario: `create_with_disruption`
- seed: `2026`
- warm-up: `140` days
- measured horizon: `360` days
- ATT interval: `5` days; required rows: `72`
- environment: `PYTHONHASHSEED=0`
- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- fallback loss: `20.436668751255972`
- fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- fallback snapshot:
  `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`
- acceptance: `candidate_loss < 20.436668751255972 - 1e-9`
- candidate evidence:
  `.challenge/round1/results/phase_aware_valid_route_booking_v1_20260807/`
- ignored aggregate:
  `experiments/results/round1_phase_aware_valid_route_booking_v1_20260807.json`

## Mandatory protocol

RED tests must fail against the untouched no-op adapter before implementation.
GREEN tests must cover phase ordering, route continuity, disruption filtering,
deterministic ties, malformed fail-closed behavior, no mutation on delegation,
transactional rollback, package imports, and a real Round 1 context. All lock,
sync, Ruff, Ty, mypy, coverage, integration, sync/cmp, smoke, deterministic
package, restricted-material, process, and diff gates must pass before the one
full run. Preserve the fresh CSV and raw log before scoring or restoration.

On equality, worsening, invalid output, crash, incomplete output, or failed
gate: commit this result record, revert only candidate code/tests in reverse
order, synchronize the no-op adapter, restore the pinned ATT bytes, re-score
the exact fallback, rerun final gates, and do not try another candidate in this
experiment.

## Full-run result (recorded before restoration)

The single authorized run completed with exit code 0. The log contains
`Simulation Progress: Day 360 / 360`, Period 72 (Days 356–360),
`Simulation completed`, and the CSV output path. The simulation clock runtime
was `01:12:10` (started `2026-08-07T15:52:40+02:00`, finished
`2026-08-07T17:04:52+02:00`).

- candidate ATT SHA-256:
  `6b32c789cbd5f13bdcbaf1066c868bf1aba84fa10dc6aaa71d46ee418cf26aa4`
- candidate mean ATT: `20.694444444444443` days
- period count: `72`
- candidate cumulative resilience loss: `24.21744876585007`
- pinned fallback loss: `20.436668751255972`
- delta: `+3.780780014594098` (`+18.499981873815628%`)
- periods better/equal/worse than fallback: `8 / 0 / 64`
- raw log SHA-256:
  `af2952c37bb08ac49343a5ea189f03192fc2bb119bba722800a41c6b927fbe47`

The strict acceptance rule is not met, so the candidate is **REJECTED**. The
fresh ATT CSV and raw log were preserved before any restoration under
`.challenge/round1/results/phase_aware_valid_route_booking_v1_20260807/`; the
ignored aggregate is
`experiments/results/round1_phase_aware_valid_route_booking_v1_20260807.json`.
The candidate was materially worse despite eight improved periods; its route
phase estimate did not compensate for the accumulated degradation across the
other 64 periods. Fallback restoration and final gates remain pending in this
checkpoint.

## Rejection and restoration

The candidate was rejected under the strict threshold. Its implementation and
candidate-only tests were reverted in reverse commit order (`f341ad3`,
`f3a2a19`, `e812ff2`, `b6e36b6`, `6a44019`); the design, pre-run review, result
record, and ignored evidence remain. The Round 1 runtime was synchronized from
the no-op participant adapter and the pinned fallback ATT bytes were copied
back before rescoring.

Post-restoration verification:

- participant/runtime `user_strategy.py` SHA-256:
  `b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`
- active ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- restored score: `20.436668751255972`, `period_count=72`
- no second candidate, tuning, rerun, submission archive, or publication was
  performed

The final post-restoration gates passed with the no-op fallback active:

- `uv lock --check` and locked all-group sync
- Ruff format/check, Ty, and mypy
- 188 non-integration tests, 90.93% coverage (minimum 90%)
- one Round 1 integration test passed; six Round 0-only integrations skipped
  because this isolated experiment clone contains no Round 0 source
- Round 1 smoke: `SMOKE_OK`
- two deterministic participant-only packages, both SHA-256
  `82b075e6d6a7513ebbc26f4b1b8384b86bba4892681c88f1f33efec21db298a1`
- restricted-material scans, diff hygiene, and no-active-simulation check

The active output was rescored after the smoke gate and remains exactly
`20.436668751255972` with ATT SHA
`c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`.
The candidate evidence remains private and ignored; the tracked report is the
only result record.
