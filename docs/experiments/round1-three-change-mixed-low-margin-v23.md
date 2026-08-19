# Round 1 three-change mixed low-margin delegation v23

**Status: DESIGN FROZEN — no candidate implementation or full run yet.**

V23 tests one narrow subtraction from the accepted Round 1 v3 recovery-hold
control. The exact policy, alternatives, tests, one-run protocol, and restore
steps are in the [design](../superpowers/specs/2026-08-19-round1-three-change-mixed-low-margin-v23-design.md)
and [plan](../superpowers/plans/2026-08-19-round1-three-change-mixed-low-margin-v23.md).

## Frozen control and acceptance

- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / interval: `140` / `360` / `5` days;
- required ATT periods: `72`;
- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control loss: `19.084638612143134`;
- strict acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Candidate evidence is private/ignored under
`.challenge/round1/results/three_change_mixed_low_margin_v23_20260819/`, with
aggregate `experiments/results/round1_three_change_mixed_low_margin_v23_20260819.json`.
No push, submission, archive publication, tuning, duplicate, or second
candidate belongs to this experiment.

## Audit gate

Before RED or candidate execution, the fresh identity-free audit must evaluate
50 valid disruption midpoints and all 19,000 demand observations on disposable
contexts. It must compare v3 and v23 on the same observations, preserve
context order, and prove no mutation, model advancement, or Output write. It
must reproduce 48 v3 holds and record every control-only v23 delegation,
including full-precision timing margin and first-route headway. A no-op or
malformed-only candidate is a no-go and consumes no full run.

