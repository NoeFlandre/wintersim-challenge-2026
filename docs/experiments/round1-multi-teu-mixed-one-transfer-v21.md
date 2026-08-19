# Round 1 multi-TEU mixed one-transfer recovery hold v21

**Status: REJECTED — candidate run complete; control restoration in progress.**

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

## Run result

The candidate passed the frozen pre-run gates and exactly one full run was
launched with `PYTHONHASHSEED=0` and the pinned Round 1 command. It exited `0`
and the raw log contains Period 72 (Days 356–360), Output Simulation Day 360,
`Simulation completed.`, and a fresh CSV write. The fresh ATT and raw log were
copied into the ignored evidence directory before scoring or restoration.

- candidate strategy SHA-256: `196f49c741b8906806d4fbde52ed680c1e6a228d752c0d35947ba810e6b47c34`;
- candidate ATT SHA-256: `adbd031f37d1ba8722561760cf155be315e10836ea3185f31233bef5077c1a79`;
- candidate ATT: `20.57236111111111` mean days across exactly 72 numbered rows;
- candidate cumulative resilience loss: `22.39069050026446`;
- pinned v3 control loss: `19.084638612143134`;
- delta: `+3.306051888121326` (`+17.31578875514049%`);
- period comparison: `16` better, `21` equal, `35` worse than control;
- decision: **REJECTED** because the candidate is strictly worse than the
  unchanged control under `candidate_loss < 19.084638612143134 - 1e-9`;
- evidence aggregate:
  `experiments/results/round1_multi_teu_mixed_one_transfer_v21_20260819.json`;
- raw log SHA-256:
  `6323a51534e8581cca8c572dbe96a43a7f48f93ff5d44f88a55c26fccfa52b0f`.

The result is evidence about this exact multi-TEU mixed one-transfer policy.
It does not prove that every cargo-size policy is harmful. The candidate-only
activation audit was valid, but its six structural activations did not predict
the official score.
