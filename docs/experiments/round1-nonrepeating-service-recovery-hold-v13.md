# Round 1 non-repeating-service recovery hold v13

**Status: REJECTED — full run complete and v3 control restored.**

This experiment is a narrow subtraction from the accepted Round 1 v3 control.
It keeps v3's existing direct-disruption, safe-detour, route-change, recovery,
and timing rules. It changes only the decision for a safe detour that reuses the
same deployed service-route object later in the path (for example, service A →
service B → service A). Such a cyclic detour is delegated to the organizer
fallback because it can reserve vessels and create a fragmented route without
being a genuinely new service sequence.

## Frozen control and acceptance rule

- checkout: `/Users/noeflandre/wintersim-challenge-2026`, one `main` worktree;
- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required period count: exactly `72`;
- accepted v3 participant SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- pinned v3 control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control cumulative resilience loss: `19.084638612143134`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Equality, worsening, stale or invalid output, incomplete logs, a failed gate,
or any mutation of the organizer state is rejection. On rejection the v3
participant, synchronized runtime, and ATT must be restored before the final
verification gates. No tuning or second run belongs to this experiment.

## Why this candidate was selected

Earlier broad one-transfer additions and broad port/leg exclusions worsened the
official score. The v3 policy currently holds every safe path with at least two
service-route changes when the estimated recovery hold is faster. The fresh
read-only audit found that most v3 activations are specifically cyclic paths:
the safe path uses the same route object more than once. Removing only those
holds targets the known cyclic-detour failure mode while retaining all other
v3 decisions.

## Read-only activation audit (before implementation)

The ignored audit at
`.challenge/round1/results/nonrepeating_service_recovery_hold_v13_20260819/activation_audit.py`
evaluated the candidate oracle on disposable contexts only. It advanced no
model and did not write organizer Output. Evidence is in
`.challenge/round1/results/nonrepeating_service_recovery_hold_v13_20260819/activation_audit.json`
(SHA-256 `9d4df57e156e23d3c377aadf201b84111b3a687ce3525cacb2b460128e07f21a`).

Results:

- `50` valid disruption timestamps and `19,000` demand-time observations;
- `48` v3 control holds;
- `6` candidate holds remain;
- `42` v3 holds are delegated by the candidate, all with a repeated route;
- `35,970` repeated-route annual-TEU exposure proxy (repeated observations,
  not unique volume);
- zero candidate-only activations;
- complete context/shipment/Output signatures unchanged;
- Output ATT remained byte-identical to the v3 control;
- `go: true` under the audit's structural reachability gate.

This is exposure evidence, not a score prediction. The official score from one
fixed full run remains the only acceptance metric.

## Implementation and verification contract

Participant changes are limited to
`submission/response_strategies/user_strategy.py` and its synchronized Round 1
runtime copy, plus the explanatory README. Add a small RED test proving that a
safe A → B → A path delegates while the existing non-repeating qualifying
fixture still returns `False`; retain mutation, malformed-state, boundary, and
public-hook tests. The GREEN change must be a local, deterministic identity
check in `_should_hold`, with no mutable module state, organizer imports, I/O,
randomness, date/index lookup, or changes to other hooks.

Before any full run, require locked `uv` environment, Ruff format/lint, Ty or
mypy as configured, unit coverage at the repository threshold, integration
tests, one-day smoke, deterministic package hashes, participant/runtime
byte-identity, the unchanged v3 control ATT and score, restricted-material
scans, clean diff, and a non-overwriting pre-run manifest. Stop for review at
that manifest. If authorized, run exactly one fixed Round 1 full command with
`PYTHONHASHSEED=0`, preserve the fresh ATT and raw log before scoring or
restoration, score exactly 72 periods, then accept or reject using the rule
above. Document the result and leave the checkout clean with the v3 control
active.

No push, merge, PR, upload, submission archive, history rewrite, or additional
candidate is part of this experiment.

## Full-run outcome

The pre-run manifest was reviewed at HEAD `22e5eee6e88e846fe88d11f797a7a1bed4b94ed1`.
The literal command first failed before simulator startup because the default uv
cache was not readable; that launch-failure log is preserved. The one and only
simulator run then used the same fixed command and configuration with the
already validated temporary `UV_CACHE_DIR=/tmp/wsc-uv-cache-v13`. No seed,
horizon, scenario, strategy, threshold, or acceptance rule changed.

The run exited `0` and contains Period 72, Day 360, `Simulation completed`, and
the CSV-write marker. The preserved evidence is:

- candidate ATT:
  `.challenge/round1/results/nonrepeating_service_recovery_hold_v13_20260819/ATT_By_Statistics_Interval.csv`
  (SHA-256 `663682e55503f56c396927158d1c25974acd5f795367b312cc28e3711d9064d6`);
- raw completed log:
  `.challenge/round1/results/nonrepeating_service_recovery_hold_v13_20260819/full_run.log`
  (SHA-256 `8a5d83b5720a88349cc27e8922f1960e92fb8013cbaaaeed7599e65e3fd14b0e`);
- pre-simulator cache launch failure:
  `.challenge/round1/results/nonrepeating_service_recovery_hold_v13_20260819/launch_failure_default_uv_cache.log`
  (SHA-256 `428110c146046e897b3cda61be7243c9c56c1389651ce31de39877a203f84c2a`);
- score aggregate:
  `experiments/results/round1_nonrepeating_service_recovery_hold_v13_20260819.json`.

The scorer reported exactly 72 periods and cumulative resilience loss
`23.329445446758054`. Relative to the pinned v3 control
`19.084638612143134`, the delta is `+4.24480683461492` (`+22.249679409458184%`).
The candidate ATT was better in 12 periods, equal in 19, and worse in 41.
The strict acceptance expression therefore rejects this candidate.

**Decision: REJECTED.** The cyclic-path suppression removed 42 of the 48
structurally exposed v3 holds, but the official simulation shows that those
holds were beneficial in aggregate. This result must not be tuned or rerun as
the same experiment.

## Restoration checkpoint

The rejected implementation was reverted from commit `22e5eee`. The
candidate-only RED test was removed while this report and its private evidence
were retained. Round 1 synchronization restored the accepted v3 participant
and runtime strategy files byte-identically (SHA-256
`f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`); the
README copies are also byte-identical. The active ATT is restored from the v3
snapshot with SHA-256
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.

No second candidate, tuning, rerun, submission, push, merge, or history rewrite
was performed. Final static, unit, integration, smoke, packaging, restricted-
material, and clean-state gates must be rerun after this restoration before
pausing the experiment.
