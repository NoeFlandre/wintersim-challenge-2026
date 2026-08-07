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

## Full-run result

The one authorized run completed normally. The raw log contains
`Simulation Progress: Day 360 / 360`, `Period Result Output: Period 72
(Days 356-360)`, `Simulation completed`, and the CSV output path. The organizer
reported a simulation-clock runtime of `00:51:15`. A shell-wrapper variable
named `status` was rejected by zsh after the simulation had already completed,
so no synthetic `UV_EXIT` line was appended; the simulation completion markers,
fresh output, and clean process exit were independently verified.

The fresh output and log were copied before scoring or restoration under:
`.challenge/round1/results/congested_direct_booking_v1_20260807/`.

- candidate ATT SHA-256:
  `e28a9d812053f7673635cc5b050a69e11f2a81dc00764f2992879894d284f033`
- raw log SHA-256:
  `849cc505846465f57a063d866a3d7c0dfb2adc23b61f30b106bd7b3674a0babc`
- candidate mean ATT: `20.738194444444439` days
- period count: `72`
- candidate cumulative resilience loss: `24.888361755688166`
- pinned fallback loss: `20.436668751255972`
- delta: `+4.451693004432194` (`+21.782870088153%`)
- periods better/equal/worse than fallback: `8 / 19 / 45`

The strict acceptance rule is not met. The candidate is **REJECTED**: allowing
exact affected origin/destination pairs onto congested direct legs materially
increased cumulative loss despite improving eight periods. The complete scorer
JSON is preserved in the ignored evidence directory as `score.json`.

## Rejection and restoration

The candidate implementation and candidate-only tests are reverted in reverse
order after this result record is committed. The design and result report stay
tracked; the candidate ATT, score JSON, and raw log remain private ignored
evidence. The no-op participant adapter is then synchronized back into the
private Round 1 source, the pinned fallback ATT bytes are restored, and the
fallback is re-scored exactly before final gates are run. No second candidate,
tuning, or duplicate full run is authorized in this experiment.

Restoration commits are `0b5be5a` (boundary-test revert), `320dfed`
(implementation revert), and `0930ea0` (RED-test revert), applied newest to
oldest. The private runtime was synchronized from the no-op adapter and the
pinned fallback snapshot was copied back before this verification.

Post-restoration state:

- participant and runtime `user_strategy.py` SHA-256:
  `b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`
- active ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- active fallback score: `20.436668751255972`, `period_count=72`
- no active Round 1 simulation or probe process

Final gates passed with the no-op fallback active:

- `uv lock --check` and locked all-group offline sync
- Ruff format/check, Ty, and mypy
- 188 non-integration tests, 90.93% coverage (minimum 90%)
- 7 integration tests
- Round 1 smoke: `SMOKE_OK`
- two deterministic participant-only packages, both SHA-256
  `a0b0db0871fee15dc540ed72f70cad8e72fee0263a54b9edc6d16f11c0d5dfcc`
- package members only `response_strategies/README.md` and
  `response_strategies/user_strategy.py`
- restricted-material scans, diff hygiene, and clean Git status

No second candidate, tuning, submission archive, publication, history rewrite,
or remote push was performed in this isolated experiment worktree.
