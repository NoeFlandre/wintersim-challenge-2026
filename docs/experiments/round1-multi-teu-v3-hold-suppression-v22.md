# Round 1 multi-TEU v3 hold suppression v22

**Status: DESIGN FROZEN — no candidate code or full simulation has started.**

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

The fresh v22 audit must be stored privately at
`.challenge/round1/results/multi_teu_v3_hold_suppression_v22_20260819/activation_audit.json`.
No simulation is authorized until RED/GREEN and every pre-run gate pass.

## Fresh pre-code audit

The identity-free audit passed before implementation using 50 valid disruption
midpoints and all 19,000 demand observations. It reproduced 48 v3 control
holds, 48 candidate one-TEU holds, zero candidate two-TEU holds, and 48
control-only two-TEU cases. It observed `no_mutation: true`, no model advance,
no Output write, and unchanged control ATT metadata. The immutable audit JSON
SHA-256 is
`6314bb30c4c57dd7d745f47f75bc20a443eb4ecde83f14d8df4d4f876bf7f1da`.
