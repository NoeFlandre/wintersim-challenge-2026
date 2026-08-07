# Round 1 congestion-only direct booking v1

**Status:** PRE-RUN REVIEW COMPLETE — FULL RUN AUTHORIZED

## Review checkpoint

This experiment was designed from a read-only audit of the public repository,
the private Round 1 runtime contract, the official challenge materials, and the
earlier Round 1 results. The candidate is isolated on branch
`codex/round1-congested-direct-booking-v1`; no full simulation has started at
this checkpoint. The design contract is recorded in
`docs/superpowers/specs/2026-08-07-round1-congested-direct-booking-design.md`.

The RED tests were committed as `af308b9` and failed against the untouched
no-op adapter (2 expected failures, 6 passes). The candidate implementation is
`7750edc`, and the additional fail-closed boundary coverage is `ff8ca8e`.
Focused tests are green (`31 passed`), the real Round 1 context integration
test is green, and the implementation review found no mutation, import,
determinism, or challenge-scope violation. The candidate strategy SHA-256 is
`761f83f3a461373b6308cf3e7a0ac6224aea3315f5dfcdbf33408decefa90918`.

## Hypothesis

The fallback excludes every active congested leg from initial booking paths.
For an exact origin-to-destination pair matching a congested leg, a direct
booking may avoid the waiting and transshipment cost of the safe detour. The
policy is deliberately narrow: it acts only during an active congestion-only
window, only for the exact affected endpoints, only on an original route with
a deployed vessel, and never while any berth closure is active. Every other
case delegates to the organizer fallback.

## Exact participant policy

Only `UserStrategy.assign_associated_bookings` may return a non-`None` value.
It validates finite positive disruption timing and multipliers, collects active
congested target legs, and fails closed on malformed runtime state. For an
exact endpoint match it selects the first deterministic original-route segment
containing that leg and installs one complete `Booking` for that segment. The
installation snapshots shipment and reverse-route references and restores them
on any expected failure. The three other hooks remain unconditional `None`.

The code uses only standard-library modules plus the runtime `Booking` class
loaded lazily. It has no file/network/subprocess/environment/wall-clock access,
randomness, tuned dates or names, mutable module state, organizer fallback
imports, or changes outside the participant adapter at runtime.

## Fixed run contract

- round: `round1`
- scenario: `create_with_disruption`
- seed: `2026`
- `PYTHONHASHSEED=0`
- warm-up: 140 days
- measured horizon: 360 days
- ATT interval: 5 days; required periods: 72
- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback cumulative loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- strict acceptance: `candidate_loss < 20.436668751255972 - 1e-9`
- candidate evidence directory (ignored):
  `.challenge/round1/results/congested_direct_booking_v1_20260807/`
- aggregate evidence (ignored):
  `experiments/results/round1_congested_direct_booking_v1_20260807.json`

## Pre-run gates

All gates below passed before the full run was authorized:

- locked dependency resolution and offline all-group sync
- Ruff format/check, Ty, and mypy
- 219 non-integration tests with 91.87% coverage (minimum 90%)
- 8 integration tests passed
- participant/runtime `user_strategy.py` byte comparison passed
- Round 1 smoke returned `SMOKE_OK`
- two participant-only packages were byte-identical, each SHA-256
  `6e41fdbd71bc5a93ed96d046209ad89aed1e3bd199eda725dbcda3fd2a3bebd1`
- package members were only `response_strategies/README.md` and
  `response_strategies/user_strategy.py`
- restricted-material history/path scans, diff check, and no-active-WSC-process
  check passed
- the fallback snapshot matched the active Output byte-for-byte and rescored
  to the pinned loss before this checkpoint

Exactly one full candidate run is authorized now. No tuning, duplicate run,
second candidate, threshold change, organizer-material publication, archive
submission, history rewrite, or remote push is part of this run.

## Protocol after the run

The raw log and fresh ATT CSV must be copied and hashed before any scoring,
smoke, synchronization, or restoration can overwrite `Output/`. The candidate
will be accepted only on a strict full-score improvement with 72 valid periods.
On equality, worsening, invalid output, crash, incomplete output, or a failed
post-run gate, the candidate must be recorded, its candidate code/tests
reverted in reverse order, the no-op adapter synchronized, the pinned fallback
ATT restored and re-scored exactly, and every final gate rerun. Only the
tracked report and design record remain public; all raw organizer-derived
evidence stays ignored and local.
