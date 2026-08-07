# Round 1 no-safe congestion-tail direct booking v2

**Status: PRE-RUN REVIEW — no operational run authorized yet**

## Review checkpoint

This is one isolated Round 1 candidate, based on the fallback audit and the
rejected broad direct-booking trial. The candidate changes only
`submission/response_strategies/user_strategy.py`; no organizer source,
inputs, outputs, or archive is tracked. The design contract is committed in
[`2026-08-08-round1-no-safe-congestion-direct-v2-design.md`](../superpowers/specs/2026-08-08-round1-no-safe-congestion-direct-v2-design.md).

The RED contract tests were committed in `1a94a13` and initially failed
against the no-op adapter (the two expected behavior failures were the exact
no-safe-path direct-booking cases). The implementation, corrected cyclic test
fixture, boundary coverage, and real Round 1 integration check are committed
in `d0084b3`. The candidate strategy SHA-256 is
`b8e31e031511a13fb97af175aa512b17ce85786e1e59c3569d129c997f418983`.

Focused unit and real-context checks are green: `23 passed`. The broader
non-integration coverage gate is `210 passed, 8 deselected, 90.74%` (minimum
90%). Ruff and mypy are clean; the complete preflight below remains a required
review gate before synchronization or a full run.

## Hypothesis

The Round 1 fallback excludes every active congested sailing leg from initial
booking paths. During a congestion-only window before any berth closure, an
exact origin/destination pair can have no remaining safe booking path. The
fallback then leaves that shipment waiting until the disruption changes. The
previous broad direct-booking experiment allowed every exact affected pair
onto a slowed leg and scored `24.888361755688166`, far worse than the
`20.436668751255972` fallback. This candidate tests the narrower claim that
only the no-safe-path tail should receive a direct booking.

## Exact participant policy

At an initial booking decision, the candidate:

1. validates active disruption timing and collects active congested legs and
   closed-berth ports; malformed or ambiguous state delegates with `None`;
2. delegates whenever a berth closure is active or no valid congestion is
   active;
3. requires the shipment demand endpoints to exactly match an active
   congested leg and finds a deployed original-route segment for that leg;
4. reconstructs the fallback-compatible deterministic contiguous graph,
   excluding active congested legs and closed ports and admitting only original
   routes plus matching deployed alternatives; a complete safe path delegates
   unchanged;
5. when no safe path exists, installs one complete `Booking` for the original
   congested segment transactionally and returns `True`.

The other three hooks remain unconditional `None`. The code uses only standard
library modules plus the runtime `Booking` loaded lazily. It has no filesystem,
network, subprocess, environment, wall-clock, randomness, mutable module
state, route/port/date/seed tables, or organizer fallback import. Delegation
is read-only; installation restores shipment and reverse-route references on
expected failure. The real Round 1 integration test exercises the public hook
on the New Jersey → Cartagena congestion window before the Cartagena closure,
verifies the safe-path condition, and verifies that only the intended booking
relation is added.

## Fixed run contract

- branch: `codex/round1-no-safe-congestion-direct-v2`
- base: `3e9434974f16ea6df58ef5c24fecf268869620b2`
- round/scenario: `round1` / `create_with_disruption`
- seed: `2026`; `PYTHONHASHSEED=0`
- warm-up: `140` days; measured horizon: `360` days
- ATT interval: `5` days; required periods: `72`
- exact command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback cumulative loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- strict acceptance: `candidate_loss < 20.436668751255972 - 1e-9`
- candidate evidence directory (ignored):
  `.challenge/round1/results/no_safe_congestion_direct_v2_20260808/`
- ignored aggregate: `experiments/results/round1_no_safe_congestion_direct_v2_20260808.json`
- temporary full-run log: `/private/tmp/wsc2026-round1-no-safe-congestion-direct-v2/full_run.log`

The candidate must be run exactly once after all preflight gates pass. Equality,
worsening, a crash, incomplete output, an invalid period count, or any failed
gate is rejection. There will be no tuning, duplicate run, second candidate,
threshold change, submission, publication, push, merge, or history rewrite as
part of this experiment.

## Pre-run gates required before authorization

- locked dependency check and all-group `uv` sync;
- Ruff format/check, Ty, and mypy;
- non-integration pytest with unrounded coverage `>=90%`;
- all integration tests;
- Round 1 strategy sync and byte comparison;
- Round 1 smoke;
- two deterministic participant-only packages with allowlisted members;
- restricted-material history/path scans, diff check, and no-active-process
  check;
- fresh verification of the fallback ATT SHA and exact fallback score;
- a pre-run backup of the no-op runtime and pinned fallback ATT before sync.

Only after those checks are reviewed will one managed full run be launched and
monitored to explicit Day 360 / Period 72 / `Simulation completed` markers.
Fresh ATT and raw log evidence will be copied and hashed before any scoring or
restoration can overwrite the runtime output.

## Rejection and restoration procedure

For rejection, equality, crash, or incomplete output: preserve the candidate
CSV/log/score evidence first; commit this tracked result update; revert the
candidate implementation and candidate-only tests in reverse order with
`git revert`; synchronize the no-op adapter; restore the pinned fallback ATT
from the pre-run backup; rescore it to `20.436668751255972` with 72 periods;
and rerun every final gate. The design and result audit remain tracked; raw
organizer-derived evidence stays ignored and private.
