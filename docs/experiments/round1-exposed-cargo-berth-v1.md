# Round 1 exposed-cargo berth priority v1

**Status: PRE-RUN REVIEW — no candidate simulation has started.**

## Review checkpoint

This is one isolated experiment from the clean Round 1 fallback at
`b4ce07b4dbfec0edc6dc2954c4bdd3a4b375e8da`, on branch
`codex/round1-exposed-cargo-berth-v1`. The design is committed in
`docs/superpowers/specs/2026-08-07-round1-exposed-cargo-berth-design.md`.

The single hypothesis is to prioritize the waiting vessel carrying the largest
positive **exposed-TEU × waiting-hours** backlog while a disruption is active.
Exposed cargo is read-only classified from the remaining booking segment slice
when it touches an active congested leg or a closed-berth port. Inactive,
unexposed, tied, missing, or malformed state delegates with `None` to the
organizer fallback. No route, booking, cargo, vessel assignment, or context
mutation is performed. The other three hooks remain no-op delegates.

This is intentionally narrower than the rejected global age-weighted berth
policy, which reordered all congested queues and worsened Round 0, and the
Round 1 progress-first and Smith policies, which produced byte-identical ATT.
The candidate acts only on an observable disruption-related TEU backlog.

### Candidate commits and identity

- `2066fa6` — experiment design/specification
- `1b6d4a8` — RED unit contract tests (expected failures against no-op)
- `5dec22b` — RED real Round 1 integration test (expected failure)
- `43371be` — minimal participant implementation
- `7f67f0f` — fail-closed and documentation correction
- `34a5f28` — meaningful boundary tests for coverage
- candidate HEAD: `34a5f28`
- candidate `submission/response_strategies/user_strategy.py` SHA-256:
  `890ba96df070e70622ec83ca0247493451d65d4000ef4a3ec678f45473e26172`

The RED unit run failed only in the two new behavior assertions after the
fixture correction; the remaining seven initial assertions passed. The RED
real-runtime integration test failed because the untouched adapter returned
`None`. GREEN focused behavior is now `27 passed`, and the real Round 1
integration test passes with the candidate.

## Fixed run identity and acceptance

- round/scenario: `round1` / `create_with_disruption`
- seed: `2026`; `PYTHONHASHSEED=0`
- warm-up: `140` days
- measured horizon: `360` days
- ATT interval: `5` days; required periods: `72`
- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback cumulative resilience loss:
  `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- acceptance expression (full precision, strict):
  `candidate_loss < 20.436668751255972 - 1e-9`

The fallback snapshot is
`.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`.
The active pre-run Output CSV matches that snapshot byte-for-byte, has 72
periods, and re-scores to the pinned loss. Its current 1,262-byte mtime is
recorded as stale-state evidence; it is not candidate evidence.

Candidate evidence must be copied before any scoring, synchronization, smoke,
or restoration overwrites Output:

- ignored ATT/log/score directory:
  `.challenge/round1/results/exposed_cargo_berth_v1_20260807/`
- ignored aggregate:
  `experiments/results/round1_exposed_cargo_berth_v1_20260807.json`

## Pre-run gates completed

- `uv lock --check`: passed (29 packages resolved)
- `uv sync --locked --all-groups`: passed
- `uv run ruff format --check .`: passed (21 files)
- `uv run ruff check .`: passed
- `uv run ty check src/wsc2026_tools submission`: passed
- `uv run mypy src/wsc2026_tools submission`: passed
- non-integration suite: `215 passed, 8 deselected`; coverage `91.32%`
  (true coverage, above the 90% minimum)
- integration preflight: `2 passed, 6 expected Round 0 skips` in this
  Round 1-only worktree; the real Round 1 candidate integration test passed
- Round 1 `sync` and participant/runtime `cmp`: passed
- Round 1 smoke: `SMOKE_OK`
- two validation packages: byte-identical SHA-256
  `7fc0fbbdfaea8856aae68f6edb4a8945f2ac8d9ab63400d84e6115cce432cbb6`
- package members: only
  `Round1_ValidationTeam/response_strategies/README.md` and
  `Round1_ValidationTeam/response_strategies/user_strategy.py`
- `git diff --check`: passed; worktree clean
- tracked/reachable restricted-material scans: no matches
- no `wsc2026`, organizer `main.py`, or other simulator process is running

## Authorization boundary

All pre-run gates are green and the fallback identity is pinned. The next
action may be exactly one monitored full candidate run. No simulation has run
for this candidate at this checkpoint. After start, do not modify code, tune a
threshold, rerun, launch a second candidate, or change the acceptance rule.

Monitor the one managed process until Day 360, Period 72, explicit completion,
and a fresh CSV. Preserve the raw log and ATT bytes first, then score the full
72 periods. Equality, worsening, crash, incomplete output, invalid output, or
any failed gate is rejection; the candidate must be recorded, reverted in
reverse order with `git revert`, the no-op adapter synchronized, the pinned
fallback ATT restored and re-scored exactly, and all final gates rerun. No
organizer source, inputs, outputs, archives, or private evidence may enter Git
history or a submission archive.

## Candidate result (one run, 2026-08-07)

The authorized candidate command completed exactly once after the initial
pre-simulation uv-cache permission failure. The actual simulator process exited
`0` and the raw log contains `Simulation Progress: Day 360 / 360`, Period 72
(`Days 356-360`), `Simulation completed`, and `CSV written`. The organizer
reported simulation-clock runtime `00:42:45`.

The fresh output and raw log were preserved before scoring or restoration at
`.challenge/round1/results/exposed_cargo_berth_v1_20260807/`.

- candidate ATT SHA-256: `1d602005736ef7e1c0f85316a28aebbcff794aa1d81371ba84f4fa978f06345f`
- candidate ATT bytes: `1262`
- candidate periods: `72`
- candidate mean ATT: `20.545972222222222` days
- pinned fallback ATT SHA-256: `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- pinned fallback mean ATT: `20.450972222222223` days
- candidate cumulative resilience loss: `21.95177745845056`
- pinned fallback cumulative resilience loss: `20.436668751255972`
- delta: `+1.5151087071945888` (`+7.413677471782064%`)
- periods better/equal/worse than fallback: `17 / 20 / 35`
- raw-log SHA-256: `352cf272e066844f5eea57408c8e425e388e54e769d8bb2a155ead06d5a17802`

The strict acceptance expression is not met. The candidate is **REJECTED —
worse than fallback**. The machine-readable scorer output and aggregate remain
ignored/private alongside the ATT and raw log. The first launch attempt is
recorded only as an environment permission failure before any simulator
process; it is not a second candidate run.

## Rejection and restoration

The candidate result is committed before restoration. The candidate
implementation and candidate-only tests will be reverted in reverse order with
`git revert`; the design, pre-run review, result, and aggregate audit records
remain. The participant adapter will then be synchronized back to the no-op
fallback, the pinned fallback ATT bytes restored and re-scored exactly, and all
final gates rerun. No tuning, second candidate, submission, publication, or
history rewrite is permitted.
