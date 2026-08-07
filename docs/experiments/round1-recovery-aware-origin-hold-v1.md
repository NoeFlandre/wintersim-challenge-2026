# Round 1 recovery-aware origin hold v1

**Status: PRE-RUN REVIEW — one full candidate run is authorized only after
this report and all gates are reviewed.**

## Hypothesis and fixed policy

During an active disruption, the organizer's fallback can choose a safe
detour even when waiting for the disrupted nominal service to recover would
finish sooner. For an origin shipment, this candidate estimates both options:

- wait until every active disruption on the nominal shortest-distance path has
  recovered, then use that nominal path; or
- use the currently safe shortest-distance path immediately.

It returns `False` (hold the shipment so the organizer's existing origin retry
mechanism waits) only when the first estimate is strictly shorter. It returns
`None` in every other case, delegating to the organizer fallback. It does not
write bookings, routes, vessels, events, globals, files, environment, or
random state; the other three hooks remain no-op.

The estimate uses only runtime objects: route segment distances, deployed
vessel speeds, half a route headway, active plan windows, and deterministic
port-order Dijkstra tie-breaking. It fails closed on malformed data and uses
only standard-library imports. No scenario names, dates, seed maps, thresholds,
or organizer imports are in the participant module.

## TDD and review evidence

- Design/spec committed before implementation:
  `docs/superpowers/specs/2026-08-07-round1-recovery-aware-origin-hold-design.md`.
- RED unit run against the no-op baseline: 2 expected policy failures and 7
  passing negative/unchanged-state tests.
- GREEN focused unit run: 9 policy tests passed; later fail-closed/helper tests
  raised the full non-integration run to 220 passing tests.
- Real-runtime integration uses `create_with_disruption()`, scans the actual
  scenario for a hold-eligible congestion case, verifies the public hook
  returns `False`, and verifies context/shipment immutability. Eight
  integration tests pass.
- The first integration fixture incorrectly assumed the first disruption had
  a safe alternate path. Investigation showed it legitimately had none and
  delegated; the fixture was corrected without changing strategy behavior.

## Fixed run contract and acceptance rule

- round: `round1`
- scenario: `create_with_disruption`
- seed: `2026`; `PYTHONHASHSEED=0`
- warm-up: `140` days; measured horizon: `360` days
- ATT interval: `5` days; required periods: `72`
- candidate command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- candidate evidence directory:
  `.challenge/round1/results/recovery_aware_origin_hold_v1_20260807/`
- ignored aggregate:
  `experiments/results/round1_recovery_aware_origin_hold_v1_20260807.json`
- pinned fallback cumulative loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- strict acceptance: `candidate_loss < 20.436668751255972 - 1e-9`

Equality, worsening, a crash, incomplete Day 360 output, or a CSV with any
period count other than 72 is rejection. No tuning or second candidate is
permitted in this experiment.

## Pre-run gates

All gates below passed in the isolated candidate worktree before a full run:

- `uv lock --check`; `uv sync --locked --all-groups`
- Ruff format/check; mypy (`8` source files)
- non-integration coverage command: `220` passed, `8` integration deselected,
  `91.84%` (minimum 90%)
- integration suite: `8` passed
- Round 1 sync and byte-identical participant/runtime strategy
  (`b16cd5dad07c345ec638aaa0ad9544dab2f8dc0d516a646d0413ae125e7d58af`)
- Round 1 smoke: `SMOKE_OK`
- two deterministic `RecoveryHoldValidation` packages, each containing only
  `README.md` and `user_strategy.py`, SHA-256
  `82a52694d8da1434090a44c93d6eababfde33e79421e1a3c74500a67e258d3c7`
- `git diff --check` clean and no active simulator process
- restricted archive/blob/path scans clean

The no-op runtime and fallback ATT were backed up before synchronization. The
full run has **not** started at this stop point. After the one run completes,
the fresh ATT and log must be copied to the evidence directory before scoring
or restoration; the result must then be recorded here and the candidate
reverted if it fails the strict gate.
