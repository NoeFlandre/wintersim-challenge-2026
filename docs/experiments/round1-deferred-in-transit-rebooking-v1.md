# Round 1 deferred in-transit rebooking v1

**Status:** rejected; fallback restored and all final gates green.

## Hypothesis

The organizer fallback re-plans every carried shipment as soon as any later
booking contains an active disruption. That can discharge cargo and create an
extra transshipment while the vessel is still on an unaffected segment. The
candidate will defer only those **future-only** re-plans: it will let the
current booking continue until the vessel's current segment or current port is
directly affected. When the current segment is directly affected, it delegates
to the organizer fallback so the existing disruption avoidance remains intact.

This is a single, general policy hypothesis. It uses the actual disruption
objects and route/booking relationships supplied at runtime; it does not use
port names, route IDs, dates, seed-specific tables, or tuned numeric margins.
The earlier Round 0 experiment that suppressed all in-transit rebooking was
worse than fallback, so this experiment deliberately preserves fallback
behavior for direct impacts and narrows only premature decisions.

## Exact scope and return contract

Only `UserStrategy.adjust_bookings_before_cargo_handling` is overridden. The
other three hooks return `None` and delegate to the organizer fallback.

- `None` means “delegate”; the hook must not mutate anything on that path.
- `False` means “handled with no re-plan”; the hook must not mutate anything.
- An active disruption is relevant only when a carried shipment's unfinished
  current or later bookings contain an active closed port or congested leg.
- If a relevant shipment's current segment/current port is directly affected,
  return `None` and let the fallback perform its normal re-plan.
- If relevant impacts are future-only for every affected shipment on the
  vessel, return `False` and preserve all bookings and vessel state.
- Any missing, ambiguous, malformed, or non-finite runtime relationship
  delegates (`None`) rather than guessing.

The implementation must use standard-library-only imports, no I/O, no
environment or process access, no randomness, no mutable module state, and no
organizer imports. It must preserve object identity and deterministic context
order. It may read runtime objects but must not mutate them.

## TDD and evidence requirements

RED tests must cover inactive/no-impact delegation, future-only suppression,
direct-impact delegation, mixed-impact delegation, closed-port boundaries,
invalid-state fail-closed behavior, signature/static-method compatibility, and
state immutability. The RED commit must fail because the current no-op returns
`None` for the future-only case. The minimum implementation then makes all
focused tests GREEN, followed by the real Round 1 smoke/integration and full
preflight gates.

## Fixed run identity and controls

- scenario: `create_with_disruption`
- seed: `2026`
- warm-up: `140` days
- measured horizon: `360` days
- statistics interval: `5` days
- required period count: `72`
- process environment: `PYTHONHASHSEED=0` (used for both control and candidate)
- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`

The fresh no-op Round 1 control completed at Period 72 before this contract
was committed. Its exact reference is:

- cumulative resilience loss: `20.436668751255972`
- ATT SHA-256: `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- mean ATT: `20.451` days
- period count: `72`
- ignored snapshot: `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`
- ignored run log: `.challenge/round1/results/fallback_control_seed0_20260803/run.log`

An earlier unpinned control is retained separately as diagnostic evidence; it
has the same ATT bytes in this checkout. The historical Round 0 value is not
used as the Round 1 threshold.

## Acceptance rule and evidence paths

Accept only if the candidate's complete scorer result satisfies, without
rounding:

```text
candidate_cumulative_loss < 20.436668751255972 - 1e-9
```

The candidate ATT must contain exactly 72 numbered periods and be copied before
any restore to:

`.challenge/round1/results/deferred_in_transit_rebooking_v1_20260803/ATT_By_Statistics_Interval.csv`

The full log and JSON score belong in that same ignored result directory and
`experiments/results/round1_deferred_in_transit_rebooking_v1_20260803.json`.
Record SHA-256, byte size, mtime, mean ATT, full-precision score, per-period
comparison counts/delta, and the package hash/member list.

## Rejection and restoration

Equality, worsening, a crash, an incomplete output, a failed validation gate,
or a non-72-period CSV is rejection. Preserve raw ignored evidence first, then
record the result, revert the candidate implementation/tests in reverse order
with `git revert`, synchronize the no-op adapter to the private Round 1 source,
restore the pinned fallback ATT bytes, and re-score to exactly
`20.436668751255972`. Do not recreate the adapter manually and do not attempt
another candidate or tune any threshold.

## Candidate result (2026-08-03)

The one authorized candidate run completed end to end. No second candidate,
rerun, tuning, or code change was made after it started.

- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- scenario: `create_with_disruption`
- seed: `2026`
- runtime: `00:19:29`
- completion: Period 72 (Days 356-360), `Simulation completed`, `UV_EXIT=0`
- candidate ATT SHA-256:
  `e8538b171a9ff34a8131ffaa1b09e1bb3cc964c85af2d7727d7f1c0b4af2eef3`
- candidate ATT bytes: `1262`
- candidate mean ATT: `20.63625` days across 72 numbered periods
- candidate cumulative resilience loss: `23.38738245924171`
- pinned fallback cumulative resilience loss: `20.436668751255972`
- delta versus fallback: `+2.950713707985738` (`+14.438330159872%`)
- candidate periods lower/equal/higher than fallback ATT: `20 / 21 / 31`
- decision: **REJECTED**; the strict gate requires a score below
  `20.436668751255972 - 1e-9`
- candidate snapshot:
  `.challenge/round1/results/deferred_in_transit_rebooking_v1_20260803/ATT_By_Statistics_Interval.csv`
- candidate run log:
  `.challenge/round1/results/deferred_in_transit_rebooking_v1_20260803/run.log`
- run-log SHA-256:
  `7dbb25638f9f33103157b96a8698ed0fcbb93956c0f26bc24be5a468c455391f`
- scorer JSON:
  `.challenge/round1/results/deferred_in_transit_rebooking_v1_20260803/score.json`

The candidate was materially worse than the paired no-op control. The
candidate snapshot and raw log are retained as ignored, private evidence; the
implementation is not eligible for submission.

## Post-rejection restoration

The candidate implementation and its tests were reverted in reverse order.
The experiment contract, result record, and `ty` development-tool dependency
were retained. The private Round 1 runtime was synchronized from the restored
no-op submission, and the active ATT was restored byte-for-byte from the
verified control snapshot:

- restored ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- restored score: `20.436668751255972` across 72 periods
- active strategy: the four-hook no-op adapter
- candidate evidence remains under the ignored result directory above

## Final verification

After restoration, the worktree is clean and no simulation, probe, or replay
process remains. The final gates passed:

- `uv lock --check` and `uv sync --locked --all-groups`
- Ruff format/check, `ty check src/wsc2026_tools submission`, and mypy
- non-integration tests: `188 passed, 7 deselected`, coverage `90.93%`
- integration tests: `1 passed, 6 expected Round-0-source skips`
- Round 1 smoke: `SMOKE_OK`
- synchronized submission/runtime `user_strategy.py` SHA-256:
  `b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`
- two final package builds were byte-identical:
  `5efe04447fcf268f3e692fd48a026d3f32ee0b374d63a77f5b0826e868256aa9`
- final package members: `response_strategies/README.md` and
  `response_strategies/user_strategy.py` only
- restricted-material history/path scans and `git diff --check`: clean

## One-candidate and publication rules

Exactly one candidate full run is authorized after the pre-run review. No
second idea, parameter sweep, partial-run substitution, post-result code
change, submission archive, push, merge, pull request, or history rewrite is
allowed as part of this experiment. Organizer archives, source, input, and
output remain ignored/private and must not enter Git history or the package.
