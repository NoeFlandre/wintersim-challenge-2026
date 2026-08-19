# Round 1 two-route-change-only recovery hold v17

**Status: PRE-RUN REVIEW — implementation and audit only; no full simulation
authorized yet.**

## Hypothesis

Accepted v3 holds new cargo when a disrupted direct service is estimated to
recover sooner than a safe detour requiring at least two service-route changes.
The v3 activation profile contains both two-change and three-change detours.
The three-change cases add another transfer and may create disproportionate
queue, capacity, and transshipment costs. V17 keeps the established two-change
holds and delegates only the three-change cases, isolating that structural
subset without changing the timing model or any other hook.

The official cumulative resilience loss remains the only performance metric;
the audit only establishes reachability and immutability.

## Exact policy

Only `assign_associated_bookings` changes. Preserve every v3 condition and
return `False` only when the safe shortest path has exactly two changes between
service-route objects. A safe path with three or more changes delegates with
`None`; zero or one change, malformed data, equality, inactive disruptions,
and all other hooks retain the existing v3 behavior. The guard is local,
read-only, deterministic, standard-library-only, fail-closed, and has no
mutable module state, I/O, randomness, dates, identifiers, or organizer
imports.

## Fixed control and acceptance

- checkout: `/Users/noeflandre/wintersim-challenge-2026`, one `main` worktree;
- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required periods: exactly `72`;
- v3 strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- v3 control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control loss: `19.084638612143134`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Equality, worsening, stale/invalid output, incomplete markers, mutation, or a
failed final gate is rejection. Exactly one full simulation is allowed; no
tuning, duplicate run, push, merge, PR, upload, submission, or history rewrite
belongs to v17. A rejection restores v3 participant files, runtime, and ATT.

## Activation audit

The immutable v3 profile evaluated 50 valid timestamps and 19,000 demand
observations, with 48 control holds. It records 34 two-change holds and 14
three-change holds. The v17 audit must reproduce those counts on disposable
contexts, select exactly the 34 two-change holds, delegate exactly 14
control-only three-change holds, observe no mutation or model advancement, and
write no organizer Output before implementation and before any run.
The immutable audit passed with SHA-256
`6221128668f10ea8ed6f5c9295bfc27af9862c981876904db09d2c0a1b1bb2b5`:
`19,000` observations, `48` control activations, `34` candidate activations,
`0` candidate-only, `14` control-only, `no_mutation: true`, and
`output_written: false`.

## TDD and gates

RED tests must fail only because v3 still returns `False` for a qualifying
three-change detour; the existing two-change hold and all v3 contracts remain
green. GREEN is the smallest route-change equality guard. Before any full run,
locked `uv` resolution/sync, Ruff, Ty, mypy, unit coverage at least 90%, serial
integrations, participant/runtime `cmp`, one-day smoke, deterministic
participant-only packages, unchanged control score/ATT, restricted-material
scans, clean Git state, and no-live-process checks must pass. Freeze a
non-overwriting manifest, preserve the raw log and fresh ATT before scoring,
and restore v3 before final gates on rejection.

## Evidence paths

Ignored v17 evidence belongs under
`.challenge/round1/results/two_route_change_only_v17_20260819/`; the aggregate
belongs under
`experiments/results/round1_two_route_change_only_v17_20260819.json`.
This record is updated with immutable audit, run, score, restoration, and
final-gate hashes only after each action.

## Full-run result

The one authorized full run used the frozen `round1` configuration and
completed successfully: the literal default-uv-cache launch failed before a
simulator started (log SHA-256
`428110c146046e897b3cda61be7243c9c56c1389651ce31de39877a203f84c2a`), then the
same command ran once with the predeclared writable `UV_CACHE_DIR`. The run
ended with exit `0`, Period `72` (Days `356-360`), Day `360`, and
`Simulation completed`.

The fresh candidate ATT was preserved before scoring at
`.challenge/round1/results/two_route_change_only_v17_20260819/ATT_By_Statistics_Interval.csv`
(SHA-256
`c051850daf539e76158ebd9fc6af1b114d38e70abef79d16dce7694bf543c5fc`). The raw
log is preserved at
`.challenge/round1/results/two_route_change_only_v17_20260819/full_run.log`
(SHA-256
`08c6c4df1befa7997b1b80b73318b009741d64fb8fdcd2be7f5d3a41766572a1`), with
simulation runtime `00:22:34`. The scorer accepted exactly `72` numbered
periods and returned cumulative resilience loss
`19.824783028123303`.

| Metric | Candidate | v3 control |
| --- | ---: | ---: |
| Cumulative resilience loss | `19.824783028123303` | `19.084638612143134` |
| Difference vs control | `+0.7401444159801684` | — |
| Relative change | `+3.878220756610151%` | — |
| Mean ATT (days) | `20.412222222222223` | `20.3675` |
| Periods better / equal / worse | `4 / 58 / 10` | — |

The strict rule was not met (`19.824783028123303` is not below
`19.084638612143134 - 1e-9`), so v17 is **REJECTED**. The exact policy
activated in the audit, but suppressing the 14 three-change v3 holds did not
improve the official score. This result does not establish why those holds
were harmful; it only rejects this frozen route-change subset.

The machine-readable result is retained in the ignored aggregate
`experiments/results/round1_two_route_change_only_v17_20260819.json`. The
candidate code and RED test must now be reverted and the pinned v3 participant,
runtime, and ATT restored before final verification.
