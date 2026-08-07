# Round 1 empty alternative-route reservation v1

**Status:** PRE-RUN REVIEW COMPLETE — FULL RUN AUTHORIZED

## Review checkpoint

This experiment was designed from a read-only audit of the public repository,
the private Round 1 runtime contract, the official challenge materials, and
the previous Round 1 results. It is isolated on branch
`codex/round1-empty-alternative-reservation-v1`, based on sanitized commit
`8b13491`. No full simulation or scoring run has started for this candidate.
The design contract is recorded in
`docs/superpowers/specs/2026-08-07-round1-empty-alternative-reservation-design.md`.

The RED tests were committed as `fa05fe0` and failed against the untouched
no-op adapter (2 expected failures, 12 passes). Boundary and real-runtime
integration coverage is committed as `744d2ab`; the participant implementation
is `551d4b5`. The focused policy suite is green (`28 passed`), the complete
non-integration suite is green (`216 passed`, 91.18% coverage), and the
integration suite is green (`8 passed`). The candidate participant SHA-256 is
`fd42434a16a8cfb8bf50026cc1673124ce6b67a88d24c7643843513fd5b81c31`.

## Hypothesis

The organizer fallback reserves the first eligible vessel from each disrupted
source route for an already-built alternative route, even when that vessel is
carrying cargo. A carrying vessel cannot activate its pending alternative until
it becomes empty. If another vessel on the same source route is empty and has
no pending reservation, moving only the pending reservation can make the safe
alternative available sooner without changing route construction or bookings.

## Exact participant policy

Only `UserStrategy.create_alternative_service_routes` may return a non-`None`
value. It derives the current disruption key from active, well-formed runtime
plans. When no valid active key exists, when no matching existing alternative
route exists, or when the state is malformed, it returns `None` so the
organizer fallback owns route creation and lifecycle cleanup.

For each matching alternative in `context.service_routes` order, the policy
requires exactly one pending vessel assigned to the alternative's original
source route and carrying at least one shipment. It then searches that source
route's deployed vessels in their existing order for a different vessel still
assigned to the source route, with no pending reservation and no carried
shipments. It clears the old pending pointer, assigns the alternative pointer
to the empty vessel, and returns `True` if at least one replacement succeeds.
It makes at most one deterministic replacement per alternative. Existing
stale pending reservations are detected first and delegated to the organizer
fallback for cleanup. Pointer writes are transactional; a failed write is
rolled back.

The strategy never creates or deletes routes, legs, or vessels; changes deployed
lists or assigned routes; edits bookings or cargo; imports organizer strategy
code; or uses I/O, network, subprocesses, environment state, wall-clock time,
randomness, or mutable module-level state. The other three hooks remain
unconditional `None`.

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
  `.challenge/round1/results/empty_alternative_reservation_v1_20260807/`
- aggregate evidence (ignored):
  `experiments/results/round1_empty_alternative_reservation_v1_20260807.json`

## Pre-run gates

All gates below passed before the full run was authorized:

- `uv lock --check` and locked all-group offline dependency sync
- Ruff format/check, Ty, and mypy
- 216 non-integration tests with 91.18% coverage (minimum 90%)
- 8 integration tests passed
- participant/runtime `user_strategy.py` byte comparison passed
- Round 1 smoke returned `SMOKE_OK`
- two participant-only packages were byte-identical, each SHA-256
  `ea02982f52444c33c98563acb71058a2a042bb14ca79864dd230baaba59d4ba0`
- package members were only `response_strategies/README.md` and
  `response_strategies/user_strategy.py`
- restricted-material history/path scans, diff check, and no-active-WSC-process
  check passed
- the fallback snapshot matched active `Output/` byte-for-byte and rescored to
  the pinned loss with 72 periods before this checkpoint

Exactly one full candidate run is authorized now. No tuning, duplicate run,
second candidate, threshold change, organizer-material publication, archive
submission, history rewrite, or remote push is part of this experiment.

## Protocol after the run

The raw log and fresh ATT CSV must be copied and hashed before any scoring,
smoke, synchronization, or restoration can overwrite `Output/`. The candidate
is accepted only on a strict full-score improvement with 72 valid periods. On
equality, worsening, invalid output, crash, incomplete output, or a failed gate,
the candidate must be recorded, its candidate code/tests reverted in reverse
order with `git revert`, the no-op adapter synchronized, the pinned fallback
ATT restored and re-scored exactly, and every final gate rerun. Only the
tracked report and design record remain public; raw organizer-derived evidence
stays ignored and local.

**Current state:** pre-run review complete; the one full candidate run is
authorized but has not yet started.
