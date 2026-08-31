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
  port-closure recovery-hold strategy; Round 1 evidence remains separate.
- The accepted experiment is documented in
  [`round2-port-closure-one-transfer-full-headway-v1.md`](experiments/round2-port-closure-one-transfer-full-headway-v1.md).
- Its cumulative resilience loss is `35.1039547178493`, compared with the
  fresh v3 control `35.50366097019303` (a `1.125817%` improvement).

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
