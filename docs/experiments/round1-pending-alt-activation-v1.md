# Round 1 pending alternative-route vessel activation v1

Status: PRE-RUN REVIEW

## Hypothesis

When the organizer fallback detects an active disruption, it can reserve an
empty vessel for a disruption-avoiding alternative route. The fallback berth
score does not explicitly prefer that reserved vessel when it is waiting at
the route's first port. Selecting the first such vessel in the existing berth
queue may activate the already-built alternative sooner, without changing
route construction, booking assignment, carried cargo, or the fallback policy
elsewhere.

This is deliberately narrower than the rejected booking and general
progress-priority experiments. It changes only
`select_vessel_for_berth`, and only when an active disruption and a valid
pending-route match are both observable.

## Fixed policy

During an active disruption, inspect `waiting_vessels` in the supplied order.
Return the original first vessel that has no carried shipments, has a pending
alternative route with at least one segment, and whose lowest-sequence segment
starts at the supplied `port` by object identity. Return `None` for inactive or
malformed plans, empty/malformed queues, carried vessels, missing/empty routes,
wrong ports, or no match. The other three hooks remain unconditional `None`.

The implementation is standard-library-only, deterministic, read-only, and
contains no organizer imports, scenario names, dates, seeds, thresholds,
randomness, I/O, environment reads, wall-clock reads, or mutable global state.

## TDD and review evidence

- RED focused run against the untouched no-op adapter: 5 expected matching/
  active-boundary/mutation tests failed; 27 existing and negative-case tests
  passed.
- GREEN focused run: 32 tests passed.
- Real Round 1 integration checks: 2 passed. They construct the organizer's
  `create_with_disruption()` context, use its real route/segment/vessel objects,
  and verify identity plus context-state preservation.
- Non-integration coverage: 209 passed, 9 integration tests deselected,
  91.39% total (minimum 90%).
- Commits: `5158cf6` contract/spec/plan, `57d06af` RED tests,
  `84d0dc9` GREEN implementation, `53645aa` real integration tests.

## Fixed run contract

- Round: `round1`
- Scenario: `create_with_disruption`
- Seed: `2026`
- Warm-up: `140` days
- Measured horizon: `360` days
- ATT interval: `5` days
- Required periods: `72`
- Candidate command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- Candidate evidence directory:
  `.challenge/round1/results/pending_alt_activation_v1_20260807/`
- Ignored aggregate:
  `experiments/results/round1_pending_alt_activation_v1_20260807.json`

The pinned no-op fallback was verified immediately before this review:

- Cumulative resilience loss: `20.436668751255972`
- ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- Period count: `72`
- Active output and pinned fallback snapshot: byte-identical
- Participant and synchronized Round 1 runtime strategy SHA-256:
  `93c7d3b5f8f90751fe72c72b8ab18182dd2745a9fa522b244bcfe44787a7e815`

Acceptance is strict:

```text
candidate_loss < 20.436668751255972 - 1e-9
```

Equality, worsening, a crash, incomplete Day-360 output, or a non-72-period
CSV is rejection. The historical Round 0 score is not a Round 1 threshold.

## Pre-run gates

All required gates passed before this report was committed:

- `uv lock --check` and `uv sync --locked --all-groups`
- Ruff format/check, `ty check src/wsc2026_tools submission`, and mypy
- Non-integration coverage command at 91.39%
- Full integration suite: 9 passed
- Round 1 sync and byte comparisons for `user_strategy.py` and `README.md`
- Round 1 smoke: `SMOKE_OK`
- Two deterministic `ValidationTeam` packages with identical SHA-256
  `6e40ff8cb88edcdaa2b4eaa3651d65bcbc8e0a8e337c629b0d7cfcbb58e18510`;
  members are only `README.md` and `user_strategy.py` under
  `response_strategies/`
- Restricted-history/tracked-file scans: no organizer archive, restricted
  blob, input, output, `main.py`, or `default_strategy.py`
- `git diff --check` clean and no active simulator process

No full simulation has run for this candidate at the time of this review.
Exactly one full candidate run is authorized after this commit. No tuning,
second candidate, threshold change, or organizer-material publication is
permitted.

## Result

To be filled only after the single run has completed, its CSV and log have
been preserved, and the candidate has been scored. On rejection, the candidate
implementation/tests will be reverted, the pinned no-op strategy and ATT will
be restored, and every final gate will be repeated.
