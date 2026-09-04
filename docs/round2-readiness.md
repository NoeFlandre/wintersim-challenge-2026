# Round 2 readiness

**Status:** organizer archive downloaded, checksum-verified, bootstrapped,
synchronized, and smoke-tested. The first Round 2 experiment is complete and
accepted; Round 1 remains unchanged.

## Organizer notice

The Round 2 archive was received on 2026-08-31. The notice establishes these
rules:

- Put every evaluated modification under `response_strategies/`.
- Do not modify or bypass the simulation model's event logic. A strategy must
  use the normal logistics process; it must not complete shipments early or
  move them to another port without the required transportation steps.
- Additional third-party packages are allowed only when the submission
  documents their dependencies, installation, and evaluation-environment run
  procedure.

The organizer's notice is authoritative if it differs from this repository's
summary or tooling.

## Private local archive

The archive is kept outside Git in the ignored organizer workspace:

```text
.challenge/downloads/SimulationChallenge2026_Py_Round2.zip
.challenge/round2/source/
```

Verified archive SHA-256:

```text
ab2d8a03ae83f5c1a8e5dcd2658d8f5df8710b202f241189d69dc7c197295013
```

The extracted source is organizer material. Never track, publish, or include
it in a submission archive.

## Round separation

- Round 1's participant strategy, package, reports, and private evidence remain
  unchanged.
- Round 2 has its own ignored source tree at `.challenge/round2/source/` and
  its own ignored results area at `.challenge/round2/results/`.
- The tracked `submission/response_strategies/` directory remains the sole
  participant submission surface. It now contains the accepted Round 2
  time-aware booking strategy; Round 1 evidence remains separate.
- Every Round 2 experiment is tabulated in the
  [experiment ledger](experiments/round2-ledger.md).
- The active strategy is the accepted
  [v15 timed congestion](experiments/round2-timed-congestion-v15.md),
  built on the accepted
  [v14 fair in-transit cost](experiments/round2-in-transit-fair-cost-v14.md),
  built on the accepted
  [v13 in-transit keep veto](experiments/round2-in-transit-keep-veto-v13.md),
  built on the accepted
  [v12 timed port closures](experiments/round2-timed-port-closure-v12.md),
  built on the accepted
  [v10 full-headway boarding cost](experiments/round2-full-headway-boarding-v10.md)
  and [v9 time-aware booking assignment](experiments/round2-time-aware-booking-v9.md).
- Its cumulative resilience loss is `10.347110679813037` over 72 periods,
  `70.52%` below the `35.1039547178493` reached by the earlier hold-based v1
  policy. The v1 control was reproduced bit for bit in the current environment
  before the comparison.
- Candidates are additionally required to hold up on held-out scenarios they
  were not developed against. v12 improves the harsher `shifted` scenario by
  `10.32%`; the in-transit intervention improves the gentler `mild` scenario by
  `0.74%`; and timed congestion improves `mild` by `15.79%`, against only
  `0.034%` on Round 2, whose congestion windows are too long for it to bite.

## Verified archive structure

The Round 2 archive contains the expected runtime components: `main.py`,
`simulation_model/`, `maritime_data_context/`, `scenario_builders/`,
`o2despy/`, `response_strategies/`, `Input/`, and the baseline ATT output.
The checksum and required marker paths are registered in
`config/rounds.toml`; bootstrap must fail closed if either changes.

The synchronized Round 2 runtime passes the short smoke check (`SMOKE_OK`).
The accepted Round 2 candidate completed one full 140-day warm-up plus
360-day measured run and was scored over 72 five-day periods. Its private ATT,
log, control, and manifests remain under `.challenge/round2/results/`.

## Commands

Run from the repository root:

```bash
uv sync --locked --group dev --group simulation
uv run wsc2026 bootstrap --round round2 \
  --archive .challenge/downloads/SimulationChallenge2026_Py_Round2.zip
uv run wsc2026 sync --round round2
uv run wsc2026 smoke --round round2
```

Before any full run, follow the experiment protocol in
`.agents/skills/running-wsc-experiments/` and obtain a separate review of the
hypothesis, tests, package, compliance checks, and acceptance gate. A Round 2
submission may contain only participant-owned files under
`response_strategies/`.
