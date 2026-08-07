# Round 1 disruption-weighted booking v1

**Status:** pre-run review; candidate implementation is not yet authorized to
run the full simulation.

## Hypothesis

The Round 1 organizer fallback removes every currently congested sailing leg
from its initial-booking graph. That can make cargo wait for recovery even when
the slowed leg is the only available connection or is faster than a long safe
detour. A policy that compares predicted sailing duration, including the
runtime disruption multiplier and recovery time, may reduce transport-time
backlog without changing the simulator.

## Exact candidate scope

Only `UserStrategy.assign_associated_bookings` is overridden. The other three
hooks return `None` and delegate to the organizer fallback.

During an active disruption, the candidate keeps closed ports as hard
exclusions, but permits congested legs and chooses a complete booking path by
predicted sailing duration. The estimate uses runtime route vessel speed,
active disruption-plan multipliers, and the end of a disruption when a leg
crosses that boundary. Existing deployed alternative routes are considered
only when their active disruption key matches. Ties use deterministic context
order.

The candidate returns `None` without mutation when there is no active
disruption, no valid path, or any malformed/ambiguous runtime object. It
validates the entire chain before replacing any booking references. It uses
only standard-library imports and no organizer imports, filesystem/network/
subprocess/environment/wall-clock access, randomness, or mutable module state.

## Starting control

- Starting branch: `main`
- Starting commit: `fe8235b`
- Starting strategy SHA-256:
  `b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`
- Round: `round1`
- Scenario: `create_with_disruption`
- Seed: `2026`
- Warm-up: 140 days
- Measured horizon: 360 days
- ATT interval: 5 days
- Required period count: 72
- Process environment: `PYTHONHASHSEED=0`
- Pinned fallback cumulative loss: `20.436668751255972`
- Pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- Pinned fallback snapshot:
  `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`

The historical Round 0 score is not a Round 1 threshold.

## Acceptance and evidence

Accept only if the complete candidate score satisfies, without rounding:

```text
candidate_loss < 20.436668751255972 - 1e-9
```

The one authorized candidate run must write a fresh 72-period ATT CSV. Before
any score-based restore, preserve the CSV, raw run log, SHA-256, byte size,
mtime, header, period count, mean ATT, full-precision scorer JSON, per-period
better/equal/worse counts, package hash, and package members in:

`.challenge/round1/results/disruption_weighted_booking_v1_20260807/`

The ignored aggregate record is:

`experiments/results/round1_disruption_weighted_booking_v1_20260807.json`

## Rejection and restoration

Equality, worsening, a crash, incomplete output, a non-72-period CSV, or any
failed gate is rejection. Preserve evidence and commit this report before
restoring anything. Revert candidate implementation and test commits in
reverse order with `git revert`; retain this contract and the result record.
Synchronize the restored no-op adapter from `submission/`, restore the pinned
fallback ATT bytes from its ignored snapshot, and re-score to exactly
`20.436668751255972`. Run every final gate again. Do not tune, rerun, try a
second candidate, submit an archive, push/merge/open a PR, or rewrite history
as part of this experiment.

## Pre-run gate

The full run is not authorized until RED tests have been observed, GREEN tests
and integration checks pass, lock/sync, Ruff, `ty`, mypy, coverage (minimum
90%), packaging twice, sync/cmp, smoke, restricted-material, diff, and process
checks all pass, and the candidate identity/fallback identity are pinned in a
review update to this file.

## Pre-run review (2026-08-07)

No full simulation, replay, or candidate output has been launched from this
branch. The candidate commits are:

- `ae6f26f` — RED behavior tests (five active-policy failures, collection
  successful);
- `5549168` — minimal weighted-booking implementation;
- `6776e8c` — reject invalid zero disruption multipliers;
- `82cb2cc` — behavior-focused fail-closed/rollback coverage tests.

The candidate HEAD is `82cb2cc1f50c3c2e6154aa0476f52099f3445230`, and both the
tracked submission and synchronized Round 1 runtime strategy have SHA-256
`e14952f60c152c3d9ef540dd2420c4ef907d9ad497931aeed0ca41b3f1a33b38`. The
pre-run Output ATT is the pinned fallback SHA
`c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`; its
fresh re-score has 72 periods and cumulative loss
`20.436668751255972`.

Verified gates before authorization:

- `uv lock --check` and `uv sync --locked --all-groups` passed;
- Ruff format/check, `ty check src/wsc2026_tools submission`, and mypy passed;
- non-integration suite: 200 passed, 8 integration deselected, 90.96% total
  coverage (minimum 90%);
- integration suite: 8 passed;
- `wsc2026 sync --round round1`, byte comparisons, and Round 1 smoke passed
  with `SMOKE_OK`;
- two validation packages are byte-identical, SHA-256
  `b8d4ff810acfa525e72ec0f43d37c1c14fda2d32908fca46228bfdbdbabb0bc6`, size
  5747 bytes, containing only `README.md` and `user_strategy.py`;
- `git diff --check`, tracked/reachable restricted-material scans, and the
  no-overlapping-simulator process check passed.

The one-candidate full-run authorization is now satisfied. The exact command
is `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`; after it starts,
no code, threshold, or process changes are permitted.

## Candidate run result (2026-08-07)

The single authorized run completed successfully from candidate HEAD
`28e34d87a0cb45661fa633e3d582a27e8d2694d5`, with no code or configuration
changes during execution. The log contains period 72 at day 360, a
`Simulation completed.` marker, and the CSV-output marker. The simulator
reported a runtime of `00:24:57`.

Evidence was preserved before scoring or restoration under:

`.challenge/round1/results/disruption_weighted_booking_v1_20260807/`

- Candidate ATT CSV: 1,262 bytes, SHA-256
  `3e156e67be60346179b5184fd723ce4099b5b36aa918f8b0d5cdf227f4830c9e`;
  72 numbered periods; mean ATT `20.877222222222223` days.
- Raw run log SHA-256:
  `9f58c3beee04deae8d33fe93d0c05e54e2cc29a353473c6337e6993645478a78`.
- Full scorer JSON is retained as `score.json` in the same evidence directory.
- The pre-run deterministic package SHA was
  `b8d4ff810acfa525e72ec0f43d37c1c14fda2d32908fca46228bfdbdbabb0bc6`;
  its only members were `response_strategies/README.md` and
  `response_strategies/user_strategy.py`.

The candidate cumulative resilience loss is
`27.025393118568292`. Against the pinned fallback loss
`20.436668751255972`, the exact delta is `+6.588724367312320` (`+32.239717967%`),
so the strict acceptance condition is not met. Comparing the 72 numbered ATT
rows with the pinned fallback snapshot, 10 were better, 16 equal, and 46
worse; candidate mean ATT was `20.877222222222223` days versus fallback mean
`20.450972222222223` days. Decision: **REJECTED**.

The candidate and raw evidence remain preserved for audit. Restoration is
deliberately recorded separately below and will not rerun the simulator.

## Rejection and fallback restoration (2026-08-07)

The strict gate rejected the candidate. The candidate implementation and its
tests were reverted in reverse order with these generated commits:

- `5f40ec7` reverted the fail-closed coverage tests;
- `0c489b9` reverted multiplier validation;
- `cf12b03` reverted the disruption-weighted booking implementation;
- `dfbb489` reverted the candidate behavior tests.

The experiment contract and evidence documentation were retained. The no-op
adapter was synchronized into the private Round 1 runtime, and the pinned
fallback ATT snapshot was copied back byte-for-byte. The restored strategy
SHA is `b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`,
and the active fallback ATT SHA is
`c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`.
The restored fallback re-scores to `20.436668751255972` over 72 periods.
No restoration simulation, second candidate, tuning, replay, submission, or
history rewrite was performed.

## Post-restore verification (2026-08-07)

All final gates passed after restoration:

- `uv lock --check` and `uv sync --locked --all-groups` passed;
- Ruff format/check, `ty check src/wsc2026_tools submission`, and mypy passed;
- non-integration tests: 188 passed, 7 integration deselected, 90.93% total
  coverage (minimum 90%);
- integration tests: 7 passed;
- Round 1 sync and byte comparisons passed; smoke returned `SMOKE_OK`;
- two validation packages were byte-identical, SHA-256
  `a0b0db0871fee15dc540ed72f70cad8e72fee0263a54b9edc6d16f11c0d5dfcc`,
  containing only `README.md` and `user_strategy.py`;
- `git diff --check` and restricted-material scans passed;
- no simulator/probe process remains;
- active fallback re-score has 72 periods and cumulative loss exactly
  `20.436668751255972`.

The branch is ready for clean handoff with the rejected candidate evidence
retained and the fallback runtime restored.
