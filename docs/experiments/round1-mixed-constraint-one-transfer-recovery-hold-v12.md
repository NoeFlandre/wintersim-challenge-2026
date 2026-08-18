# Round 1 mixed-constraint one-transfer recovery hold v12

**Status: PRE-RUN REVIEW / NO FULL RUN AUTHORIZED.**

This record freezes one candidate from the accepted Round 1 multi-transfer
recovery-hold v3 control. The private activation audit, RED/GREEN TDD, and all
pre-run gates passed. No full simulation has been authorized by this record.

## Frozen hypothesis and policy

The candidate preserves every v3 hold and adds only this case: a new shipment
whose nominal shortest path is one disrupted booking edge, whose safe shortest
path requires exactly one service-route change, whose nominal edge matches both
an active congested-leg and an active closed-port constraint, and whose unchanged
v3 recovery-plus-direct estimate is strictly faster than the safe detour. Pure
leg-only and port-only one-transfer cases delegate. A qualifying decision is
read-only and returns `False`; all other states delegate with `None`.

The strongest failure mode is that the compound one-transfer cases are still
harmful because the static estimate omits queues, capacity, and event-history
effects. The official cumulative resilience loss over all required periods is
the sole decision metric.

## Control and fixed configuration

- public base HEAD: `8b708f3e488c346743a5cdc467f46b819501e10d`;
- canonical layout: one checkout, one worktree, branch `main`;
- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / interval: `140` / `360` / `5` days;
- required numbered periods: exactly `72`;
- control strategy SHA-256: `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT: `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- control ATT SHA-256: `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- freshly verified control loss: `19.084638612143134`;
- authoritative baseline ATT SHA-256: `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- acceptance expression: `candidate_loss < 19.084638612143134 - 1e-9`.

## Required audit and implementation gates

Before RED, a private audit must reproduce the historical v3 activation count
under the identity-free 50-timestamp/19,000-observation protocol and find at
least one exact mixed leg-and-port one-transfer candidate-only activation with
strict finite timing advantage and no mutation or Output write. A dormant or
semantically mismatched candidate is a NO-GO and consumes no run.

The audit passed on 2026-08-18 with:

- `50` derived timestamps and `19,000` demand-time observations;
- `48` v3 control activations and `54` v12 candidate activations;
- `6` candidate-only activations, all exactly one safe route change with
  matching kinds `{"leg", "port"}`;
- candidate-only annual-TEU exposure proxy `19,440` (repeated observations,
  not unique volume);
- zero control-only activations;
- finite, strictly positive timing margins for every candidate-only case;
- complete observed state unchanged and Output ATT metadata unchanged;
- no model advancement and no Output write.

Ignored evidence: `.challenge/round1/results/mixed_constraint_one_transfer_recovery_hold_v12_20260818/activation_audit.json`
(SHA-256 `fe43717342f48d514ec9cae172b4282213751d7c0b828eba20c83005f1f3fa98`).
The audit is structural reachability evidence only and does not predict the
official score.

After the audit, RED tests must fail only for missing candidate behavior. GREEN
may change only the participant strategy and README; the shared constraint
matching helper must preserve v3 recovery semantics. The full test, coverage,
integration, sync, smoke, deterministic packaging, restricted-material, and
clean-state gates are mandatory.

## Implementation and verification record

- design/specification commit: `b469b6e`;
- RED test commit: `0b1dfbe` (the untouched v3 implementation failed only the
  exact mixed leg-and-port one-transfer expectation; retained and negative
  cases passed);
- GREEN implementation commit: `da80d03`;
- candidate strategy SHA-256:
  `384b30a43a6cf0dbf39fb45df9ee21c1ff97b220f09adda4471638b592172ccd`;
- participant and Round 1 runtime strategy files are byte-identical;
- participant and Round 1 runtime README files are byte-identical.

The implementation is limited to the participant strategy and README. It adds
one shared matching helper, preserves v3 graph/recovery/timing behavior, and
returns `False` only for the exact mixed one-transfer case; all other hooks and
non-qualifying states still delegate with `None`. It has no mutable module
state, identity/date/index lookup, organizer imports, output writes, or model
advancement.

Pre-run verification passed:

- `uv lock --check` and locked `uv sync --all-groups`;
- Ruff format and lint;
- Ty and mypy;
- non-integration tests: `233 passed, 9 deselected`, branch coverage
  `90.82%` (the configured `>=90%` gate);
- integration tests: `9 passed`;
- one-day Round 1 smoke: `SMOKE_OK`;
- two deterministic packages, each containing only
  `response_strategies/README.md` and `response_strategies/user_strategy.py`,
  with SHA-256
  `d9c523274aea6d97ff95b3ea0708c40f49531b863c3d79b2cdb4b79087c7a720`;
- active Output ATT remains byte-identical to the pinned v3 control
  (`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`),
  with 72 numbered periods and mean ATT `20.3675` days;
- restricted-material scans and `git diff --check` are clean.

The non-overwriting pre-run manifest is written after this report commit in
the ignored evidence directory and pins the reviewed HEAD, hashes, audit
proof, package, control, and exact fixed-run contract.

## Evidence and authorization

Private audit and, only if a later run is authorized, candidate evidence belong
under `.challenge/round1/results/mixed_constraint_one_transfer_recovery_hold_v12_20260818/`;
the aggregate belongs under
`experiments/results/round1_mixed_constraint_one_transfer_recovery_hold_v12_20260818.json`.
No candidate ATT, score, run log, or result exists at this freeze point. No push,
merge, PR, upload, submission, history rewrite, tuning, or second candidate is
part of this experiment. The workflow must stop after the pre-run manifest for
senior review before any full simulation.

## Full-run outcome

Senior authorization was received for exactly one full run from HEAD
`5779152696ecbf73d61f2dcfc933b6d7bad10c71`. The first literal invocation did
not reach the simulator because the default uv cache was permission-blocked;
that launch-failure log is preserved separately. The one simulation was then
started with the same manifest-pinned command and `UV_CACHE_DIR` moved to the
already validated temporary cache. No strategy, seed, horizon, or threshold
changed, and no duplicate simulation was launched.

The run completed with exit `0` and the required markers: Period 72, Day 360,
`Simulation completed.`, and a fresh CSV write. The preserved evidence is:

- ATT snapshot:
  `.challenge/round1/results/mixed_constraint_one_transfer_recovery_hold_v12_20260818/ATT_By_Statistics_Interval.csv`;
  SHA-256 `095fbaefba3e9049d2e1e80947bc34631a9d601ac0411ba33c05ba11d3043646`;
- completed raw log:
  `.challenge/round1/results/mixed_constraint_one_transfer_recovery_hold_v12_20260818/full_run.log`;
  SHA-256 `3239c49e1136e1bac52f315ebda10dd70ac2fb66d35a69a87235d6909090786a`;
- launch-failure log:
  `.challenge/round1/results/mixed_constraint_one_transfer_recovery_hold_v12_20260818/launch_failure_default_uv_cache.log`;
  SHA-256 `428110c146046e897b3cda61be7243c9c56c1389651ce31de39877a203f84c2a`;
- score aggregate:
  `experiments/results/round1_mixed_constraint_one_transfer_recovery_hold_v12_20260818.json`;
  SHA-256 `28a4c6dedc194a66e5862dd826030b4fcb276f916a86a47de112566c6556f591`.

The scorer reported exactly 72 periods and cumulative resilience loss
`19.313383619092`. Against the pinned accepted control
`19.084638612143134`, the delta is `+0.22874500694886635` (`+1.19858181020688%`).
The candidate ATT was better in 26 periods, equal in 20, and worse in 26; the
official cumulative score still governs. The strict rule
`candidate_loss < 19.084638612143134 - 1e-9` therefore rejects this candidate.

**Decision: REJECTED.** The candidate must not remain active, and no tuning or
second run is authorized. The frozen v3 restoration procedure follows this
record.
