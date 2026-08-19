# Round 1 equal-distance one-transfer tie v27

## Status

**PRE-TDD AUDIT GO — no candidate code or full simulation has run.**

This experiment is a separately named, single-candidate trial from the
accepted v3 control. The design and implementation plan are:

- [`design`](../superpowers/specs/2026-08-19-round1-equal-distance-one-transfer-tie-v27-design.md);
- [`plan`](../superpowers/plans/2026-08-19-round1-equal-distance-one-transfer-tie-v27.md).

## Frozen control and gate

- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required numbered periods: `72`;
- accepted v3 strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- accepted v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control loss: `19.084638612143134`;
- strict acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Candidate evidence is private/ignored under
`.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/`,
with aggregate
`experiments/results/round1_equal_distance_one_transfer_tie_v27_20260819.json`.
No tuning, duplicate, second candidate, push, submission, or history rewrite
is authorized within this experiment.

## Hypothesis and exact delta

V25 combined exact-distance safe-path reductions of `1→0` and `2→1` route
changes and scored `21.779788584660977`. V27 isolates only the `2→1` shape:
preserve all v3 `False` recovery holds, then install a complete booking chain
only when the fallback safe path has exactly two adjacent service-route
changes and an exact-distance alternative has exactly one. The `1→0` shape,
all non-ties, all other route-change counts, and uncertain/malformed state
delegate `None`.

The candidate is participant-only, deterministic, standard-library-only, and
must install transactionally with complete rollback on anticipated failure.
The other three hooks remain unconditional `None` delegates.

## Pre-code activation audit

The fresh identity-free audit used 50 valid disruption midpoints and every
Round 1 demand (19,000 observations) on disposable contexts. It reproduced 48
v3 holds and found 50 candidate-only `2→1` opportunities, with annual-TEU
exposure proxy `22,150`. It found no candidate `1→0` behavior. Complete state
snapshots were unchanged (`no_mutation: true`), no model advanced, and Output
was not written. This is structural reachability evidence, not a score
prediction.

Ignored audit JSON:
`.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/activation_audit.json`

Audit SHA-256:
`e31f0582870f0ed6fa02b6ff2d929d1ec8a928736b1ba5ec9a4799b05329abd6`.

## Next gate

RED tests must be added and observed against untouched v3. Only after valid
RED, minimal GREEN, all quality/integration/package/smoke gates, a fresh v3
control score check, and a non-overwriting launch manifest may the single full
Round 1 run start. The candidate ATT and raw log must be preserved before
scoring or restoration. Rejection requires a report-first Git revert, v3
synchronization, byte-identical ATT restoration, exact re-score, and all final
gates.
