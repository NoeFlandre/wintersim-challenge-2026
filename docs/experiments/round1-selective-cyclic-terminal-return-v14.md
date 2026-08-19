# Round 1 selective cyclic terminal-return hold v14

**Status: REJECTED — full run complete and v3 control restored.**

V13 showed that suppressing every repeated-route safe path was too broad: it
removed 42 of the 48 v3 holds and scored `23.329445446758054`. V14 tests only
the smallest exposed subcase. It preserves every v3 decision except a safe
shortest path with exactly three edges and route identity pattern A → B → A
(exactly two route changes, returning to the first service route). That one
cyclic terminal-return case delegates to the organizer fallback; all other
states retain v3 behavior.

## Frozen control and acceptance

- checkout: `/Users/noeflandre/wintersim-challenge-2026`, one clean `main` worktree;
- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required period count: exactly `72`;
- v3 participant SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- v3 control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control loss: `19.084638612143134`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Equality, worsening, invalid/stale output, incomplete completion markers,
failed gates, or mutation is rejection. A rejected candidate is reverted and
the v3 participant, runtime, and ATT are restored before final gates. This
experiment permits exactly one full run, with no tuning or retry after a real
simulator has started.

## Read-only activation audit

The ignored audit
`.challenge/round1/results/selective_cyclic_terminal_return_v14_20260819/activation_audit.py`
evaluated the exact predicate on fresh disposable contexts at 50 valid
timestamps and every demand (19,000 observations). It advanced no model and
did not write Output. Evidence:

- JSON: `.challenge/round1/results/selective_cyclic_terminal_return_v14_20260819/activation_audit.json`;
- audit result SHA-256:
  `6465e454a00884e4b6cfa321a8668c5527d3f712a11015f92ffb644bf306266c`;
- 48 v3 control activations;
- 44 candidate activations and 4 suppressed activations;
- all four suppressed cases are exactly `changes=2; safe_edges=3`, with the
  route sequence `Intra-EastAsia → Asia-Europe-NorthEurope → Intra-EastAsia`;
- every suppressed timing margin is finite and strictly positive;
- zero candidate-only activations;
- complete state and Output signatures unchanged (`no_mutation: true`);
- audit gate `go: true`.

The audit is structural exposure evidence, not a score prediction. The official
72-period cumulative loss remains the only acceptance metric.

## Implementation and gates

The participant boundary remains only
`submission/response_strategies/user_strategy.py` and its README, synchronized
into the ignored Round 1 runtime. Add one RED test that constructs a genuine
three-edge A → B → A safe path, proves the v3 control would hold it, and
expects the v14 public decision to delegate without mutation. Existing v3
qualifying, boundary, malformed-state, tie, public-hook, forbidden-capability,
and mutation tests must remain intact. GREEN is one local route-identity/length
guard after the existing v3 two-change guard; no mutable module state,
organizer imports, I/O, randomness, date/index lookup, or changes to other
hooks are allowed.

Before a run, require locked `uv` environment, Ruff format/lint, Ty and mypy,
unit coverage at least 90%, integration tests, one-day smoke, deterministic
packaging, participant/runtime byte identity, unchanged v3 control score and
ATT, restricted-material scans, clean diff, and a non-overwriting pre-run
manifest. Stop for review at that manifest. If the fixed run is authorized,
preserve its raw log and ATT before scoring or restoration, score exactly 72
periods, apply the strict threshold, document the result, and leave the v3
control active on rejection.

No push, merge, PR, upload, submission archive, history rewrite, or second
candidate is part of v14.

## Full-run outcome

The pre-run manifest was reviewed at HEAD `a7c003ab8bd5db869fe37dd586187abad58a657a`.
The literal launch again failed before simulator startup because the default uv
cache was unreadable; that log is preserved. The one actual simulator run used
the same fixed Round 1 command and configuration with the validated temporary
`UV_CACHE_DIR=/tmp/wsc-uv-cache-v14`. No strategy, seed, horizon, scenario,
threshold, or acceptance rule changed.

The run exited `0` with Period 72, Day 360, `Simulation completed`, and a fresh
CSV-write marker. Preserved evidence:

- candidate ATT:
  `.challenge/round1/results/selective_cyclic_terminal_return_v14_20260819/ATT_By_Statistics_Interval.csv`
  (SHA-256 `7f54b398140f2550685894c4c12113e879f72f10a304188e2a269e1225b128a7`);
- raw completed log:
  `.challenge/round1/results/selective_cyclic_terminal_return_v14_20260819/full_run.log`
  (SHA-256 `dc4e89858b02780847580496ce6b74364d4a9a50730f6386613ae2a6f47c1b5d`);
- pre-simulator launch failure:
  `.challenge/round1/results/selective_cyclic_terminal_return_v14_20260819/launch_failure_default_uv_cache.log`
  (SHA-256 `428110c146046e897b3cda61be7243c9c56c1389651ce31de39877a203f84c2a`);
- score aggregate:
  `experiments/results/round1_selective_cyclic_terminal_return_v14_20260819.json`.

The scorer reported cumulative resilience loss `22.564049197867078` over 72
periods. Against the pinned v3 control `19.084638612143134`, the delta is
`+3.4794105857239437` (`+18.231472214045862%`). The candidate ATT was better in
13 periods, equal in 26, and worse in 33. The strict acceptance rule rejects
the candidate.

**Decision: REJECTED.** Even the narrow four-activation A → B → A suppression
was harmful in aggregate. It must not be tuned or rerun as v14.

## Restoration checkpoint

The rejected implementation was reverted from commit `a7c003a`. The
candidate-only RED test was removed while this report and private evidence were
retained. Round 1 synchronization restored the accepted v3 participant and
runtime strategy files byte-identically (SHA-256
`f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`), and the
README copies are byte-identical. The active ATT was restored from the v3
snapshot with SHA-256
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.

No second candidate, tuning, rerun, submission, push, merge, or history rewrite
was performed. Final restoration verification passed:

- locked `uv` check/sync, Ruff format/lint, Ty, and mypy;
- non-integration tests: `227 passed, 8 deselected`, coverage `90.84%`;
- integration tests: `8 passed`;
- full smoke: `SMOKE_OK`;
- two deterministic packages, each containing only
  `response_strategies/README.md` and `response_strategies/user_strategy.py`,
  SHA-256 `3d2bf1aa4c829ae947df89807944359799c258931734365f6e7981cfb32f9aa5`;
- restored active ATT re-score: 72 periods,
  `19.084638612143134`, byte-identical to the pinned v3 control;
- restricted-material scans, `git diff --check`, participant/runtime hashes,
  and no-live-process check all passed;
- final Git working tree is clean on `main`.
