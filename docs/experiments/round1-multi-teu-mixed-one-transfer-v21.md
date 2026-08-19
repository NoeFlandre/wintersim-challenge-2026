# Round 1 multi-TEU mixed one-transfer recovery hold v21

**Status: DESIGN FROZEN — activation audit passed; no candidate code or full
simulation has started.**

This report freezes one candidate from the accepted v3 control. The design is
in [`the specification`](../superpowers/specs/2026-08-19-round1-multi-teu-mixed-one-transfer-v21-design.md)
and [`the implementation plan`](../superpowers/plans/2026-08-19-round1-multi-teu-mixed-one-transfer-v21.md).

## Control and acceptance

- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control score: `19.084638612143134` over 72 periods;
- fixed configuration: Round 1 `create_with_disruption`, seed `2026`,
  `PYTHONHASHSEED=0`, 140-day warm-up, 360 measured days, five-day interval;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

## Frozen hypothesis

V12's mixed leg-plus-port one-transfer extension was close to v3 but added
harmful small-cargo decisions. V18 showed that the runtime's TEU size is a
valid structural distinction. V21 therefore preserves all v3 holds and adds
the v12 one-transfer case only when `teu_size > 1`. Exact one TEU, malformed,
non-finite, and non-positive sizes delegate.

The strongest failure mode is queue/capacity pressure from the added multi-TEU
holds. Activation is not a score prediction.

## Pre-code activation audit

The read-only audit used fresh real contexts at 50 identity-free disruption
midpoints and all 19,000 demands. It evaluated v3, one-TEU candidate, and
two-TEU candidate decisions with complete per-object before/after snapshots.
It reported:

- v3 holds: `48`;
- one-TEU candidate holds: `0`;
- two-TEU candidate holds: `54`;
- candidate-only two-TEU holds: `6`;
- candidate-only annual-TEU proxy: `38,880`;
- two-TEU control-only holds: `0`;
- `no_mutation: true`, `model_advanced: false`, and unchanged Output ATT.

The formal audit was written atomically to
`.challenge/round1/results/multi_teu_mixed_one_transfer_v21_20260819/activation_audit.json`.
Its SHA-256 is
`a3002388d5befa1bd38dcb0f06efaf6264d5f3604ea90acd6310c141f7415b6d`.
It contains no organizer identities or source material.

## TDD and pre-run contract

RED must fail only because untouched v3 delegates neither the new multi-TEU
mixed one-transfer case nor the exact-one-TEU boundary. GREEN must be the
minimum participant-only implementation, with all inherited v3 behavior and
read-only invariants retained. All protocol gates, package checks, and a
non-overwriting launch manifest are required before the one full run.

If the run is rejected or invalid, evidence is preserved first, the result is
committed, v21 code/tests are reverted in reverse order, and v3's participant
files and pinned ATT are restored and re-scored. No tuning or second run is
allowed inside v21.
