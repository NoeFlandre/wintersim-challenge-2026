# Round 1 selective cyclic terminal-return hold v14

**Status: PRE-RUN REVIEW — no full simulation authorized yet.**

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
