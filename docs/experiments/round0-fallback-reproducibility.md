# Round 0 fallback reproducibility audit

**Date:** 2026-07-20
**Branch:** `codex/challenge-foundation`
**Strategy baseline commit:** `3cae539` (revert of the transfer-aware
routing experiment; active `UserStrategy` is the no-op organizer-fallback
adapter). Current repository HEAD is a later commit that adds documentation on
top of this baseline.

## Purpose

This audit records what the current checkout actually reproduces when the
organizer fallback strategy (all four `UserStrategy` methods returning `None`)
is run end to end on Round 0. It is a reproducibility/integrity check. It is
**not** an optimization attempt and introduces no strategy code.

## Result summary

| Result | Cumulative Resilience Loss | ATT SHA-256 | Periods | Runtime |
| --- | ---: | --- | ---: | ---: |
| Historical reference (documented) | 18.276620672293834 | `ed4f274f827959ce4261303996bbde035aa784f7b7d070b9bbdf6bea1c7cbb03` | 72 | — |
| Current-checkout run #1 | 18.673577819840556 | `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658` | 72 | 33:53 |
| Current-checkout run #2 | 18.673577819840556 | `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658` | 72 | 33:47 |

## Conclusion

- The current checkout is **locally deterministic**: run #1 and run #2 produced
  byte-identical ATT files (`10234375...`) and identical scores
  (`18.673577819840556`) across two consecutive full runs (140-day warm-up +
  360 measured days, five-day statistics intervals, seed `2026`).
- The historically documented fallback result
  (`ed4f274f...`, `18.276620672293834`) is **not reproduced in the current
  checkout/environment**. This is recorded as an evidence discrepancy; it is
  not claimed to be fraudulent or wrong. The historical value was the reference
  against which the two rejected experiments were evaluated at the time and
  must be preserved as historical evidence.
- The newly reproduced result is labeled precisely as the
  **"current-checkout locally reproduced fallback"** and is **not** presented
  as the universal or official challenge fallback. Future experiments run in
  this exact checkout should compare against `18.673577819840556` unless the
  environment/source discrepancy is later resolved.

## Environment information

- Repository default: Python **3.12.2** (`.python-version` = `3.12`),
  `uv 0.11.16`.
- Submission/tooling targets: `requires-python = ">=3.11"`, `target-version =
  py311` (`pyproject.toml`).
- Verification also executed under an isolated **CPython 3.11.15** environment
  (`UV_PROJECT_ENVIRONMENT=/tmp/wsc2026-pause-py311`, project
  `wintersim-challenge-2026`): mypy, 187 unit tests, and smoke all passed.
- Key dependency in the resolved lock: `numpy 2.4.6`.

## Bounded integrity checks performed

1. `submission/response_strategies/user_strategy.py` is the no-op adapter;
   all four required methods (`select_vessel_for_berth`,
   `create_alternative_service_routes`, `assign_associated_bookings`,
   `adjust_bookings_before_cargo_handling`) return `None` and do not mutate
   inputs.
2. The organizer-side synchronized copy
   (`.challenge/round0/source/response_strategies/user_strategy.py`) is
   byte-identical to the submission copy.
3. Seed (`2026`), warm-up (`140`), measured days (`360`), interval size (`5`),
   and the disruption scenario (`create_with_disruption`, measurement-relative
   disruption offsets) are correct and unchanged in the current tree.
4. All required input CSVs are present
   (`.challenge/round0/source/Input/`:
   `ports.csv`, `service_routes.csv`, `route_segments.csv`, `demand_matrix.csv`,
   `vessel_classes.csv`, `route_plan.csv`).
5. No overlapping full simulation was active during either run; only one
   `wsc2026 run --full` process existed at a time.
6. The **baseline** ATT SHA-256
   (`2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`)
   matches the documented authoritative baseline hash exactly, so the input
   baseline is identical to the historical run even though the fallback
   scenario output is not.
7. ATT is measured in **days**, not hours, in both the current checkout and
   the historical result. The simulation computes ATT internally in hours, but
   `main.py` divides it by 24.0 before writing each period row, so the CSV's
   approximately 18.8–21.3 values and `OverallMean` ≈ 20.34 are days. The
   documented historical "Mean ATT = 20.276666666666667" is on the same day
   scale. A unit/scale mismatch is therefore **ruled out** and is not an
   explanation for the SHA/score discrepancy. The cause of the discrepancy
   remains unresolved within this bounded audit. Plausible categories include a
   difference in the historical organizer source, inputs not covered by the
   baseline ATT hash, dependency/runtime state, or another unrecorded
   environmental difference — but none of these is proven here.
8. No stale participant helper or experiment artifact exists under the
   organizer `response_strategies/` directory (only `default_strategy.py`,
   `strategy_validation.py`, `README.md`, `user_strategy.py`).
9. `git status` is clean; `.challenge/` and `experiments/results/` are
   gitignored, so no organizer material is tracked.

## Private (ignored) evidence

Snapshots are local-only and must remain untracked:

- Run #1:
  `.challenge/round0/results/fallback_reproduction_current_checkout_run1/ATT_By_Statistics_Interval.csv`
  — SHA `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`
- Run #2:
  `.challenge/round0/results/fallback_reproduction_current_checkout_run2/ATT_By_Statistics_Interval.csv`
  — SHA `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`

The stale file `experiments/results/fallback_2026.json` remains unverified and
is **not** authoritative.

## Verification gates (all green)

- `uv lock --check` — ok
- `uv sync --locked --group dev --group simulation` — ok
- `uv run ruff format --check .` — 19 files formatted
- `uv run ruff check .` — all checks passed
- `uv run mypy src/wsc2026_tools submission` — no issues (8 files; also clean
  under Python 3.11)
- `uv run pytest -m "not integration" --cov-fail-under=90` — 187 passed,
  coverage 90.93% (also clean under Python 3.11)
- `uv run pytest -m integration -q` — 7 passed
- `uv run wsc2026 smoke --round round0` — SMOKE_OK
- Deterministic packaging: two `wsc2026 package --round 1 --team ValidationTeam`
  builds produced identical SHA `a0b0db0871fee15dc540ed72f70cad8e72fee0263a54b9edc6d16f11c0d5dfcc`
  with members `Round1_ValidationTeam/response_strategies/README.md` and
  `Round1_ValidationTeam/response_strategies/user_strategy.py` only.

## Resume point

- The active no-op organizer-fallback strategy implementation derives from
  revert commit `3cae539`, while the current repository HEAD includes this and
  later documentation commits. Do not reintroduce either rejected candidate.
- In this checkout, compare new candidates against the locally reproduced
  fallback `18.673577819840556` (SHA `10234375...`), labeled only as the
  current-checkout locally reproduced fallback, unless the discrepancy with the
  historical `ed4f274f...` / `18.276620672293834` is resolved first. Keep
  `18.276620672293834` and `ed4f274f...` as historical evidence.
- Open investigation (not performed here): reconcile the historical and
  current-checkout fallback outputs. Both report ATT in days, and two
  current-checkout runs are byte-identical, so any difference must lie in the
  historical environment/source rather than in a unit or scaling error. Do not
  modify organizer source to force a match.
- **Update 2026-07-22.** The coordinated owner-authorized history purge
  and force-push that removed the restricted Round 0 ZIP and the
  restricted blob (`3f5be8fecbcc829753785c4da55c69c89c44629e`) from
  reachable local history has been completed. `git rev-list --objects
  --all` and `git ls-files` contain neither the archive path nor the
  restricted blob. **Residual warning:** old local clones, pre-purge
  forks, and any GitHub dangling, cache, or fork objects that captured
  the prior history may still contain the restricted ZIP and blob. Treat
  any pre-purge clone as not-public-safe until its own reachable objects
  are re-verified.
