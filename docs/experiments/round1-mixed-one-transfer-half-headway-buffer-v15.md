# Round 1 mixed one-transfer half-headway-buffer recovery hold v15

**Status: REJECTED — complete; v3 restored.**

The accepted v3 policy holds only safe detours requiring at least two service
route changes. V12 added six mixed leg+port one-transfer cases and scored
`19.313383619092`, slightly worse than v3. The profile of those six cases shows
the same Shenzhen → Busan demand, with a positive hold-vs-detour margin from
`23.551818181818135` to `143.55181818181813` hours, while the first safe route
has a `154.76363636363635` hour headway. V15 adds only the subset with a
strict margin greater than half that headway. It preserves all v3 holds and
delegates all other states.

## Frozen policy

The only changed hook is `assign_associated_bookings`. In addition to every v3
condition, a new shipment may be held when:

1. the nominal shortest path is one disrupted direct edge;
2. the safe shortest path has exactly one service-route change;
3. the nominal edge matches both an active leg and active port constraint;
4. the v3 recovery-versus-detour estimate is strictly positive; and
5. `detour_hours - hold_hours > 0.5 * first_safe_route_headway_hours`.

The half-headway buffer is a conservative uncertainty margin: v3 already
models each service-route transition with half a headway, so a one-transfer
extension must have more than one such buffer before it overrides the
organizer's fallback. Equality delegates. Missing or invalid values delegate.
No v3 hold is removed. Other hooks remain unconditional delegates.

## Fixed control and acceptance

- checkout: `/Users/noeflandre/wintersim-challenge-2026`, one clean `main` worktree;
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
failed gate is rejection. Exactly one full simulation is allowed; no tuning or
second run belongs to v15. On rejection, revert the candidate and restore v3
participant, runtime, and ATT before final gates.

## Activation evidence

The preceding private v3 profile is retained at
`.challenge/round1/results/v3_activation_profile_v15_20260819/profile.json`.
The exact v15 oracle audit is
`.challenge/round1/results/mixed_one_transfer_half_headway_buffer_v15_20260819/activation_audit.py`;
its immutable JSON evidence is
`.challenge/round1/results/mixed_one_transfer_half_headway_buffer_v15_20260819/activation_audit.json`
(SHA-256
`f1e6cabaca4db9dbb91e30651b7b175d03e3877f1f9ab6215bb5958ad6149776`).
The audit must evaluate 50 valid timestamps and 19,000 demand observations on
disposable contexts. It reproduced 48 v3 holds, exposed exactly three
candidate-only activations with finite strict buffer margin, observed zero
control-only activations, and wrote no organizer Output (`no_mutation: true`,
`output_written: false`). A dormant or mismatched predicate is a NO-GO and
consumes no simulation.

## TDD and pre-run contract

The RED contract covered the mixed one-transfer case below, equality, below
and above the half-headway buffer, invalid headway data, and preservation of a
v3 multi-transfer hold. GREEN added only a local read-only guard with no
mutable module state, organizer imports, I/O, randomness, dates, identifiers,
or changes to other hooks. The candidate was synchronized only through the
participant-owned `README.md` and `user_strategy.py` files.

Before a full run, locked `uv` resolution/sync, Ruff, Ty, mypy, unit coverage
at least 90%, integrations, sync/cmp, one-day smoke, deterministic participant-
only packages, unchanged control score/ATT, restricted-material scans, clean
Git state, and no-live-process checks must pass. Freeze a non-overwriting
manifest with all hashes and the exact run command. Preserve raw log and ATT
before scoring or restoration. These gates passed before the run. No push,
merge, PR, upload, submission archive, history rewrite, or second candidate
was part of v15.

## Full-run result

The literal manifest command was attempted once and stopped before simulation
because the sandbox denied the default UV cache; the launch error is preserved
at `.challenge/round1/results/mixed_one_transfer_half_headway_buffer_v15_20260819/launch_failure_default_uv_cache.log`
(SHA-256 `428110c146046e897b3cda61be7243c9c56c1389651ce31de39877a203f84c2a`).
The one actual simulation used the same command with only `UV_CACHE_DIR` set to
a writable temporary cache. It exited `0`, reached Period 72 / Day 360, and
printed `Simulation completed.`. The raw log is preserved at
`.challenge/round1/results/mixed_one_transfer_half_headway_buffer_v15_20260819/full_run.log`
(SHA-256
`90420e57b38397a039a8476793b654ceea2f0ad2496ecb7f6e6c572f7abe87d3`). The
fresh ATT was copied before scoring to
`.challenge/round1/results/mixed_one_transfer_half_headway_buffer_v15_20260819/ATT_By_Statistics_Interval.csv`
(SHA-256
`112aa548445b940ad0510952fdc1af36785fb842afc4b0204bd9f0ad283930fd`).

| Metric | Candidate | v3 control |
| --- | ---: | ---: |
| Cumulative resilience loss | `21.713670841302392` | `19.084638612143134` |
| Difference vs control | `+2.629032229159258` | — |
| Mean ATT (72 periods, days) | `20.531388888888888` | `20.3675` |
| Periods better / equal / worse | `17 / 21 / 34` | — |

The strict acceptance rule was not met, so the candidate is **REJECTED**.
Complete machine-readable evidence is in
`.challenge/round1/results/mixed_one_transfer_half_headway_buffer_v15_20260819/result.json`.

## Restoration

The rejected implementation commit `aa8f8d6` was reverted without rewriting
history. The temporary v15 test was removed, participant and ignored runtime
files were synchronized back to v3, and the active ATT was restored from the
pinned v3 snapshot. Final active hashes are the v3 strategy
`f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`, v3
README `0590ba5bb34ffc9bf0e7f368b552f8f26c71eb7314a00fa221e0c5e8f4225595`, and
ATT `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.
The ignored candidate artifacts remain available for audit; no candidate
output is active.

## Final verification after restoration

After restoration, the repository passed `uv lock --check`, locked `uv sync`,
Ruff format and lint, Ty, mypy, the full suite (`235 passed`), non-integration
coverage (`227 passed`, `90.84%`), and the integration suite run serially
(`8 passed`). Round 1 smoke returned `SMOKE_OK`. Two participant-only package
runs were byte-identical (SHA-256
`a8caf7f755a880ceb239c774887f29a489f07d2fe3b51b7d84d60d6891d04747`) and
contained only `README.md` and `user_strategy.py`. The v3 ATT and runtime
hashes above remained unchanged after smoke and packaging. Restricted-history
and tracked-path scans were clean, no simulation process remained, and the
working tree is clean on `main`.
