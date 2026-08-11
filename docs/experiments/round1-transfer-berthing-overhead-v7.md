# Round 1 transfer-berthing overhead v7

**Status: REJECTED — complete; accepted v3 control restored and final gates
passed.**

The full contract, hypothesis, activation evidence, fixed run identity,
acceptance rule, TDD requirements, and restoration procedure are recorded in
[`the design specification`](../superpowers/specs/2026-08-11-round1-transfer-berthing-overhead-v7-design.md)
and [`the executable plan`](../superpowers/plans/2026-08-11-round1-transfer-berthing-overhead-v7.md).

This report will be extended only with preflight, one-run evidence, the strict
decision, and final restoration or acceptance gates. No post-run tuning is
permitted.

## Pre-run verification record

The reviewed launch HEAD is `952772be3a48447170faea5c74c0f6bdcc52070c` on the
sole local `main` branch. The participant strategy and synchronized Round 1
runtime copy are byte-identical at SHA-256
`be8f36acb3d8c2ee6cb8fcd7c03d805e2ee5dbc7eb93c95b5cf6c0bd21d85e64`.

The non-overwriting ignored manifest is
`.challenge/round1/results/transfer_berthing_overhead_v7_20260811/pre_run_manifest.json`
(SHA-256
`268dc441ddd7a14f2a50a236bd207aac7e963d15a383ce14be4373c9d1f7282a`). It
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

## Full-run result (exactly one candidate run)

The frozen command was run exactly once:

```text
PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache-0811 uv run wsc2026 run --round round1 --full
```

The first log write was observed at `2026-08-11T20:55:10+0200`; the process
completed at `2026-08-11T21:37:11+0200`. The simulator reported runtime
`00:41:31`, exit code `0`, Period 72 (Days 356-360), simulation day 360,
`Simulation completed.`, and the expected CSV output path. The complete log
is preserved privately at
`.challenge/round1/results/transfer_berthing_overhead_v7_20260811/full_run.log`
with SHA-256
`2e7ecbf8551b199c01819d315f9a2015fed72ce2c4806e6eafd31fecf53f4f83`.

The candidate CSV was preserved before scoring at
`.challenge/round1/results/transfer_berthing_overhead_v7_20260811/ATT_By_Statistics_Interval.csv`.
It contains 72 numbered periods, is 1,262 bytes, and has SHA-256
`0e4cfe00a9fab8d16076e615bed32f167b36d69296f1f6363f684d396a75a90f`.
Its mean ATT (Average Transport Time) is `20.50819444444444` days.

Scoring against the authoritative Round 1 baseline produced:

- cumulative resilience loss: `21.428353158559474`;
- period count: `72`;
- accepted v3 control: `19.084638612143134`;
- delta versus control: `+2.34371454641634` (`+12.2806%`);
- versus the control ATT, 20 periods improved, 18 were equal, and 34 were
  worse (maximum per-period increase `1.56` days).

The immutable acceptance rule is
`candidate_loss < 19.084638612143134 - 1e-9`. The candidate is therefore
**REJECTED**; it is materially worse than the accepted v3 control. The raw
scorer JSON is preserved in the same ignored result directory.

No tuning, second candidate, or additional simulation was authorized.

## Restoration and final verification

Because the candidate failed the strict gate, its participant changes were
reverted in reverse dependency order:

- `cf7d913` reverts v7 test formatting;
- `ae02d18` reverts the v7 participant README change;
- `0b0c1bb` reverts the v7 implementation and real-context integration test;
- `bd8e565` reverts the v7 RED test contract.

The accepted v3 participant strategy is active again. Round 1 was synchronized
and the participant/runtime copies are byte-identical at strategy SHA-256
`f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`. The
active ATT was restored from the pinned v3 snapshot, not regenerated; its
SHA-256 is `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.
Re-scoring it against the Round 1 baseline produced exactly
`19.084638612143134` over 72 periods.

Post-restoration gates all passed:

- locked `uv` check and all-group synchronization;
- Ruff format (21 files), Ruff lint, `ty check src/wsc2026_tools submission`,
  and mypy (8 source files);
- full pytest: 235 passed;
- non-integration coverage: 227 passed, 8 deselected, 90.84% true branch
  coverage (minimum 90%);
- integration tests: 8 passed;
- Round 1 sync and byte comparison;
- Round 1 smoke: `SMOKE_OK`, with the restored strategy and ATT still
  byte-identical afterward;
- two deterministic participant-only packages, both SHA-256
  `a88fa1f534049cec96ffdf7d0204b2dc1fa3d685ceb438d9cecf45b4fcc5eef3`,
  5,923 bytes, containing only the participant README and
  `user_strategy.py`;
- `git diff --check` and restricted-material scans;
- no live simulator or probe process.

The candidate evidence remains private and ignored under
`.challenge/round1/results/transfer_berthing_overhead_v7_20260811/`. No
submission archive, push, merge, PR, or history rewrite was performed. This
experiment is closed; no further run is authorized by this report.
