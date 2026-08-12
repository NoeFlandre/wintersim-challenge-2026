# Round 1 pure-congestion transfer hold v8

**Status: PRE-RUN VERIFIED — no candidate simulation has started.**

This report records one candidate experiment from the accepted v3 control. The
full hypothesis, activation audit, fixed identities, strict acceptance rule,
and restoration procedure are in the
[`design specification`](../superpowers/specs/2026-08-12-round1-pure-congestion-transfer-hold-v8-design.md)
and [`implementation plan`](../superpowers/plans/2026-08-12-round1-pure-congestion-transfer-hold-v8.md).

The participant code must remain under `submission/response_strategies/`; the
ignored organizer source, input, output, and candidate evidence must never be
tracked or packaged. The one-candidate/no-tuning rule is immutable.

## Implementation review before launch

The hypothesis was implemented with strict RED→GREEN TDD and reviewed before
any operational run:

- RED: the new pure-congestion one-transfer behavior failed exactly as
  intended (`1 failed, 41 passed`); the failure was the missing `False`
  decision, not a fixture or infrastructure error.
- GREEN: the focused unit and real-context integration checks passed (`43
  passed`), including a candidate-only activation, closed-berth and
  multi-physical-leg delegation, and complete state immutability.
- The candidate changes are limited to the participant strategy and its
  behavioral tests. No organizer source, input, output, random seed, mutable
  cross-run state, dependency, or submission boundary was changed.

The candidate participant and synchronized runtime are byte-identical at
SHA-256 `4f170eeb12ebb3b20fa5c83d11dcdb21663ae6764e2fe10936df1ec456f28686`.

## Pre-run verification

The complete launch preflight passed on 2026-08-12 before the run was
authorized:

- `uv lock --check` and `uv sync --locked --all-groups` passed.
- Ruff format/check, Ty, and mypy passed.
- Non-integration tests passed (`229 passed, 9 deselected`) with true branch
  coverage `90.45%` (minimum `90%`).
- Integration tests passed (`9 passed, 229 deselected`).
- Round 1 sync and participant-file `cmp` passed; the one-day smoke check
  returned `SMOKE_OK`.
- Two participant-only `ValidationTeam` packages were byte-identical, with
  SHA-256 `26b719ad276bed9326fa1805a3c1c431f433a98115ded4fea825fcceb2d3f1a7`.
  Each archive contains only `response_strategies/README.md` and
  `response_strategies/user_strategy.py`.
- The active output remained the pinned v3 control before launch: ATT
  SHA-256 `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`,
  72 periods, and score `19.084638612143134` against the authoritative Round 1
  baseline ATT SHA-256
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`.
- Restricted-material, diff-hygiene, branch/worktree, and live-process checks
  were clean.

The exact run identity was frozen: `PYTHONHASHSEED=0`, seed `2026`, Round 1
`create_with_disruption`, 140-day warm-up, 360 measured days, 5-day ATT
intervals, and one command only:

```text
UV_CACHE_DIR=/tmp/wsc-uv-cache-0812 uv run wsc2026 run --round round1 --full
```

The strict acceptance rule is immutable:
`candidate_loss < 19.084638612143134 - 1e-9`. The candidate ATT and raw log
must be copied to the ignored v8 evidence directory before scoring, syncing,
smoke, or restoration. If the candidate is equal, worse, or fails, its result
will be committed first, then only the v8 implementation/test commits will be
reverted, v3 will be synchronized and restored from its pinned ATT snapshot,
and every final gate will be rerun.

## Full-run result

The one authorized full run was launched from HEAD
`57b388697a92db691c53d78359ffbdc85f0a7ccd` with the frozen command and ran to
completion without interruption:

- `Simulation Progress: Day 360 / 360` and `Period Result Output: Period 72`
  were present in the raw log.
- `Simulation completed.` and `CSV output written` were present; the command
  exited `0`. No Round 1 simulator process remained afterward.
- Simulation-reported runtime was `00:28:58`.
- The preserved raw log is
  `.challenge/round1/results/pure_congestion_transfer_hold_v8_20260812/full_run.log`
  (SHA-256 `4fee7a02ff78e79ede825d9f0a802a6c5c578c75004e2929738072d1901ebbf7`).
- The preserved candidate ATT is
  `.challenge/round1/results/pure_congestion_transfer_hold_v8_20260812/ATT_By_Statistics_Interval.csv`
  (72 numbered rows, SHA-256
  `7392bc6f3508c03ea23841e9eaf12d9bd759d7cb1d6a14058694ca709112de20`).

Scoring that preserved file against the authoritative Round 1 baseline
(`2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`) produced
cumulative resilience loss `20.229520673897987`. Compared with the pinned v3
control `19.084638612143134`, the delta is `+1.1448820617548527` (`+5.99897%`),
so the candidate is **REJECTED** by the immutable rule
`candidate_loss < 19.084638612143134 - 1e-9`.

Against the byte-preserved v3 ATT, the candidate was better in 4 periods, equal
in 50, and worse in 18. The candidate ATT was not substituted for the control.
The ignored aggregate record is
`experiments/results/round1_pure_congestion_transfer_hold_v8_20260812.json`.

The next required action is the documented rejection path: commit this result,
revert only the v8 implementation/test commits, synchronize the v3 participant,
restore its pinned ATT bytes, re-score the active output, and rerun the final
quality, integration, packaging, safety, and clean-state gates.

## Rejection restoration and final state

The result was committed before restoration. Candidate-only commits
`9d0fe30`, `253ba62`, and `95f641e` were then reverted in reverse dependency
order; the frozen design, pre-run, and result records remain in history. The
active participant is again the accepted v3 strategy:

- `submission/response_strategies/user_strategy.py` and the synchronized Round
  1 runtime are byte-identical at SHA-256
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`.
- The active ATT was restored by copying the pinned v3 snapshot, is
  byte-identical at SHA-256
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`, and
  re-scores to `19.084638612143134` over 72 periods.
- The candidate ATT and raw log remain preserved only in the ignored v8
  evidence directory; no candidate output was substituted for the control.

Final gates after restoration all passed: lock check and locked sync; Ruff
format/check; Ty; mypy; non-integration tests (`227 passed, 8 deselected`, true
branch coverage `90.84%`); integration tests (`8 passed, 227 deselected`);
Round 1 sync and `cmp`; `SMOKE_OK`; two deterministic participant-only
packages (final SHA-256
`a88fa1f534049cec96ffdf7d0204b2dc1fa3d685ceb438d9cecf45b4fcc5eef3`); diff
hygiene; restricted-material scans; one worktree on `main`; and no live WSC
process. The experiment is complete and rejected; v3 remains the active best.
