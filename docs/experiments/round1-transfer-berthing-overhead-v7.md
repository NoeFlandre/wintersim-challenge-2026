# Round 1 transfer-berthing overhead v7

**Status: PRE-RUN DESIGN FROZEN — no candidate simulation has started.**

The full contract, hypothesis, activation evidence, fixed run identity,
acceptance rule, TDD requirements, and restoration procedure are recorded in
[`the design specification`](../superpowers/specs/2026-08-11-round1-transfer-berthing-overhead-v7-design.md)
and [`the executable plan`](../superpowers/plans/2026-08-11-round1-transfer-berthing-overhead-v7.md).

This report will be extended only with preflight, one-run evidence, the strict
decision, and final restoration or acceptance gates. No post-run tuning is
permitted.

## Pre-run verification record

The reviewed launch HEAD is `7550dd676258239c6b3ebdd0f85d32db92c96f4f` on the
sole local `main` branch. The participant strategy and synchronized Round 1
runtime copy are byte-identical at SHA-256
`be8f36acb3d8c2ee6cb8fcd7c03d805e2ee5dbc7eb93c95b5cf6c0bd21d85e64`.

The non-overwriting ignored manifest is
`.challenge/round1/results/transfer_berthing_overhead_v7_20260811/pre_run_manifest.json`
(SHA-256
`5cd3b43f923e36e99a7e13ada3434d1386227539732272821137c034a3d12e2d`). It
pins the launch identities, fixed configuration, package member list, and all
preflight results.

Fresh preflight gates passed before any candidate simulation:

- locked `uv` lock check and all-group synchronization;
- repository Ruff format/check, `ty`, and mypy;
- 230 non-integration tests with true branch coverage `90.85%`;
- 9 integration tests;
- Round 1 sync and participant/runtime byte comparison;
- Round 1 smoke: `SMOKE_OK`;
- two deterministic participant-only packages, SHA-256
  `d4d29d400550871f3701292a225679a849d4fe13c708f78d44bbf839a04e1cda`,
  6,178 bytes, containing only the participant README and
  `user_strategy.py`;
- accepted v3 control snapshot and active Output byte-identical at
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`, and
  the control re-scored to `19.084638612143134` over 72 periods;
- restricted-material history/tracked-file scans, `git diff --check`, one
  worktree/one branch, clean tracked status, and no live simulator.

No full run, candidate score, tuning, restore, package submission, push,
merge, PR, or history rewrite has occurred at this checkpoint. Exactly one
candidate run is now permitted by this experiment contract.
