# Round 1 multi-TEU v3 hold suppression v22

**Status: REJECTED — candidate run complete; v3 control restored.**

V22 is a separately named experiment from the accepted v3 control. It tests
whether existing v3 holds for multi-TEU cargo create more queue/capacity cost
than their direct-delay benefit. The complete policy, alternatives, gates, and
rejection procedure are in the [spec](../superpowers/specs/2026-08-19-round1-multi-teu-v3-hold-suppression-v22-design.md)
and [plan](../superpowers/plans/2026-08-19-round1-multi-teu-v3-hold-suppression-v22.md).

## Frozen control and acceptance

- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control score: `19.084638612143134` over 72 periods;
- fixed Round 1 `create_with_disruption`, seed 2026, `PYTHONHASHSEED=0`,
  140-day warm-up, 360 measured days, 5-day intervals;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

## Evidence basis

V18 removed all one-TEU v3 holds and kept multi-TEU holds, scoring
`20.744602632173724`. Its immutable audit found 48 v3 holds, 48 one-TEU
control-only activations, and 48 two-TEU retained activations. V20 and V21
also produced materially worse results when adding multi-TEU holds. V22 tests
the unmeasured complement: keep one-TEU v3 holds and delegate multi-TEU v3
holds. These counts are reachability evidence, not a score prediction.

The fresh v22 audit is stored privately at
`.challenge/round1/results/multi_teu_v3_hold_suppression_v22_20260819/activation_audit.json`.
The audit was completed before implementation and the candidate was frozen
only after RED/GREEN and every pre-run gate passed.

## Fresh pre-code audit

The identity-free audit passed before implementation using 50 valid disruption
midpoints and all 19,000 demand observations. It reproduced 48 v3 control
holds, 48 candidate one-TEU holds, zero candidate two-TEU holds, and 48
control-only two-TEU cases. It observed `no_mutation: true`, no model advance,
no Output write, and unchanged control ATT metadata. The immutable audit JSON
SHA-256 is
`6314bb30c4c57dd7d745f47f75bc20a443eb4ecde83f14d8df4d4f876bf7f1da`.

## Full-run result (2026-08-19)

The one authorized full run used the manifest-pinned command with
`PYTHONHASHSEED=0` and completed successfully at Day 360 / Period 72. The
fresh ATT (Average Transport Time) CSV and raw log were preserved before
scoring or restoration.

- candidate ATT SHA-256: `ed0e19de9a725c9577767f8a3f592e8f8bca4ba1b1796ab7a50c27f8a0f9021e`;
- mean ATT: `20.816111111111113` days;
- candidate cumulative resilience loss: `26.25449609374837`;
- control loss: `19.084638612143134`;
- delta: `+7.169857481605236` (`+37.55807884247853%`);
- period comparison: 0 better, 0 equal, 72 worse;
- raw-log SHA-256: `4761e2da101e14c163076780d05402c32f8b6a76f80a7a328ed140b4b2aced56`.

Decision: **REJECTED**. The candidate was materially worse than the frozen
v3 control and did not satisfy the strict acceptance rule. Complete machine-
readable evidence is in
`experiments/results/round1_multi_teu_v3_hold_suppression_v22_20260819.json`.

## Restoration and final state

The candidate implementation and RED tests were reverted in this order:

- `a1193e0` reverts the v22 implementation;
- `bfb4d60` reverts the v22 RED tests.

The participant runtime was synchronized to the accepted v3 control. The
restored strategy SHA-256 is
`f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`; the
active control ATT SHA-256 is
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`, and a
fresh score re-check is `19.084638612143134` over 72 periods.

Final gates passed after restoration: `uv lock --check`, locked `uv sync`,
Ruff format and lint, Ty on tracked source, mypy, 227 non-integration tests
with 90.84% coverage, 8 integration tests, Round 1 smoke, and two identical
deterministic packages (SHA-256 `a88fa1f534049cec96ffdf7d0204b2dc1fa3d685ceb438d9cecf45b4fcc5eef3`).
Restricted-material scans passed, no simulation process remains, and the
working tree is clean. The branch is `main`, ahead of `origin/main` by the
local experiment commits and not yet pushed.
