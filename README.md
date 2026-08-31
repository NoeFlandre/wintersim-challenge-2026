# wintersim-challenge-2026

A public-safe, reproducible participant workspace for the
[Winter Simulation Conference (WSC) 2026 Simulation Challenge](https://meetings.informs.org/wordpress/wsc2026/simulation-challenge/).

> **Public/private boundary.** This repository contains **only** participant-owned
> tooling, tests, strategy code, derived aggregate descriptions, and links to
> public organizer documentation. The organizer's simulation software, input
> datasets, and output datasets are **not** part of this repository. They live
> only in your local, git-ignored `.challenge/` directory after you bootstrap
> them from a private copy of the official archive. Never commit, copy, or
> redistribute organizer source or data.

## Tracked checkout vs git history (public-release status)

The current `HEAD` tree contains no organizer software or data: the organizer
ZIP, extracted source tree, derived outputs, and submission archives are absent
from the current tree and excluded by `.gitignore`.

Reachable local history also contains neither the archive path
`SimulationChallenge2026_Py_Round0.zip` nor the restricted blob
`3f5be8fecbcc829753785c4da55c69c89c44629e`. Verified by:

```bash
git rev-list --objects --all | grep -i SimulationChallenge2026_Py_Round0.zip
git rev-list --objects --all | grep 3f5be8fecbcc829753785c4da55c69c89c44629e
git ls-files | grep -E '\.zip|/Output/|/Input/|main\.py|default_strategy\.py'
```

Each of these commands returns no matches.

The coordinated owner-authorized history purge and force-push that removed
those restricted objects from reachable local history has been completed.

> **Residual warning.** Old local clones, pre-purge forks, and any GitHub
> dangling, cache, or fork objects that captured the prior history may
> still contain the restricted ZIP and blob. Treat any pre-purge clone as
> not-public-safe until its own reachable objects are re-verified. The
> tracked checkout and reachable local history are public-safe; clones and
> forks are not under the maintainers' control.

## Challenge purpose

Teams build response strategies for a maritime shipping disruption simulation.
The objective is to minimize **Cumulative Resilience Loss** (derived from
Average Transport Time) across disrupted scenarios while preserving simulation
integrity. See the tracked public documents in [`docs/`](docs/):
[`WSC-2026-Simulation-Challenge-Brief.pdf`](docs/WSC-2026-Simulation-Challenge-Brief.pdf)
and
[`WSC-2026-Simulation-Challenge-Tech-Document.pdf`](docs/WSC-2026-Simulation-Challenge-Tech-Document.pdf),
and the paraphrased rules in [`docs/challenge-rules.md`](docs/challenge-rules.md).

## Current status

- **Round 0** (warm-up / practice): not scored. **Round 0 must never be packaged
  or submitted.** Its controlled experiments and evidence remain documented
  under `docs/experiments/` as background only.
- **Round 1:** the organizer archive is privately bootstrapped at
  `.challenge/round1/source/`. Eighteen controlled experiments have valid scores
  and one earlier attempt was incomplete. The first nine scored candidates were
  rejected; recovery-aware direct-service hold v2 beat the fallback, and the
  multi-transfer refinement v3 improved the active best to
  `19.084638612143134`. This is `6.615707068353528%` below the
  `20.436668751255972` fallback. See
  [`docs/round1-readiness.md`](docs/round1-readiness.md) and the latest
  [`Round 1 port-involved margin-guard report`](docs/experiments/round1-port-involved-margin-guard-v11.md).
  That latest v11 trial scored `20.548930262023504`, was rejected as worse than
  v3, and left the accepted v3 strategy active.
- **Round 1 official window:** August 1-23, 2026 (20% weight).
- **Round 2:** September 1-23, 2026 (30% weight).
- **Hidden round:** October 1-23, 2026 (50% weight).

Round 2 is now bootstrapped locally from the organizer's newly released
archive. Its source and outputs stay private under `.challenge/round2/`, while
the public setup and compliance notes live in
[`docs/round2-readiness.md`](docs/round2-readiness.md). The Round 2 notice
requires normal event-driven logistics, forbids bypassing event logic, and
allows additional dependencies only when their installation and runtime use
are documented. Only a short wiring smoke check has run; no Round 2 strategy
or full simulation has been run yet.

The current `UserStrategy` keeps three decisions delegated to the organizer.
For new cargo only, it may wait for a disrupted one-booking direct service when
that service is estimated to recover and deliver sooner than a fragmented safe
detour requiring at least three service boardings. Simpler safe detours remain
delegated to the organizer. The first controlled Round 0 experiment was
completed and rejected because it increased Cumulative Resilience Loss by
22.12%; see [`docs/experiments/round0-first-result.md`](docs/experiments/round0-first-result.md).
Round 1's preceding no-safe congestion-tail booking experiment produced a
`25.80681018404835` loss against the `20.436668751255972` fallback, worse by
`26.27699014039333%`, and was rejected under the strict improvement rule; its
candidate evidence remains preserved in the ignored results directory.

- The preceding Round 1 carried-TEU berth-priority experiment produced the exact
  fallback loss `20.436668751255972` and byte-identical ATT, so it was rejected
  by strict equality; its candidate ATT, log, and scorer JSON remain in the
  ignored results directory.
- The accepted Round 1 multi-transfer recovery-hold experiment produced
  `19.084638612143134` over all 72 periods, improving the preceding accepted
  v2 result by `3.7529484181856874%`. Its ATT SHA-256 is
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
  the tested v3 candidate remains active.
- The latest Round 1 pure-congestion exclusion experiment scored
  `22.38757990186231` against the active v3 control
  `19.084638612143134` and was rejected; its ignored candidate evidence is
  preserved in the v9 results directory.
- The latest Round 1 port-closure exclusion experiment retained v3 holds only
  for pure leg-congestion constraints and delegated port-involved holds. It
  scored `22.096980694905298` against the active v3 control
  `19.084638612143134` and was rejected; its candidate ATT and log remain in
  the ignored v10 results directory, and v3 was restored byte-for-byte.
- The latest Round 1 port-involved margin-guard experiment delegated only
  low-margin port-involved v3 holds when the timing advantage was below one
  safe-route headway. Its single full run scored `20.548930262023504` against
  the active v3 control, `7.672619218205541%` worse, so it was rejected. The
  candidate ATT and log remain in the ignored v11 evidence directory, and v3
  was restored byte-for-byte with score `19.084638612143134`.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for dependency and lockfile management.
- Python 3.11 or newer. The local default is pinned to **3.12**
  (see `.python-version`); all first-party and submission code stays
  Python 3.11 compatible.

## Setup

From the repository root:

```bash
# Install dev + simulation dependency groups (simulation reproduces the
# organizer's runtime requirements without tracking the organizer's package).
uv sync --locked --group dev --group simulation

# Bootstrap a local round source from its private archive copy. The archive is
# verified against the SHA-256 pinned in config/rounds.toml before extraction.
uv run wsc2026 bootstrap --round round1 \
  --archive .challenge/downloads/SimulationChallenge2026_Py_Round1.zip

# Overlay participant response_strategies onto the selected round's source tree.
uv run wsc2026 sync --round round1

# Run a very short smoke simulation (a few days) to validate imports/wiring.
uv run wsc2026 smoke --round round1
```

Bootstrap extracts into the selected git-ignored `.challenge/<round>/source/`
tree and never modifies the source archive.

## Day-to-day commands

### Test, lint, typecheck

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src/wsc2026_tools submission
uv run pytest -m "not integration" --cov=src/wsc2026_tools --cov=submission --cov-report=term-missing --cov-fail-under=90
```

Integration tests require the local Round 0 source and are excluded from CI:

```bash
uv run pytest -m integration -q
```

### Scoring

Reproduce the dashboard's Cumulative Resilience Loss from two ATT-per-period
CSVs (scenario and baseline):

```bash
uv run wsc2026 score --scenario-att Output/scenario_att_by_period.csv \
                    --baseline-att Output/baseline_att_by_period.csv
# add --json for full-precision JSON including per-period values
```

### Packaging a submission

> **Round 0 must never be submitted.** The packager rejects Round 0.

```bash
uv run wsc2026 package --team YourTeam --round 1
```

This builds a deterministic ZIP under `dist/submissions/` containing a single
top-level directory with only the allowlisted participant-owned files, prints
its path, SHA-256, size, and member list, and never uploads anything.

> **Filename-order discrepancy (must confirm with organizers).** The current
> challenge website names archives `Round1_TeamName.zip` (round first), while the
> technical document PDF names them `TeamName_Round1.zip` (team first). This
> tooling uses the website's **`Round<N>_TEAM.zip`** order. **Confirm the
> required order with the organizers before your first real submission.**

## Full simulation runs

Full runs (the configured warm-up plus the measured experiment) are
**intentionally long** and are **excluded from CI**. They require a deliberate
experiment contract and review before starting:

```bash
uv run wsc2026 run --round round1 --full
```

Outputs are written inside the selected round's ignored extracted workspace.
Never start a full run from an unreviewed strategy or use Round 0 as a
submission.

## Submission boundary

Only files under [`submission/response_strategies/`](submission/response_strategies/)
are participant-owned and may enter a submission archive. See its
[README](submission/response_strategies/README.md) for the runtime restrictions
(standard-library-only, no network/subprocess/filesystem/cwd/wall-clock/unseeded
randomness/mutable global state) and supported Python version.

## Architecture summary

The workspace separates three concerns:

1. **Public participant workspace** (tracked): dev CLI under `src/wsc2026_tools/`,
   submission code under `submission/response_strategies/`, tests, config, docs.
2. **Ignored organizer workspace** (local only): `.challenge/<round>/source/`
   holds the verified, extracted organizer tree that the simulation actually
   runs against.
3. **Ignored outputs**: `dist/submissions/` and `experiments/results/`.

Data flow: **bootstrap** (verify + extract) -> **sync** (overlay participant
strategy) -> **smoke** / **run** (short or full simulation) -> **score**
(resilience loss) -> **package** (compliant archive). See
[`docs/architecture.md`](docs/architecture.md).

## Links

- Official challenge page: <https://meetings.informs.org/wordpress/wsc2026/simulation-challenge/>
- Brief: [`docs/WSC-2026-Simulation-Challenge-Brief.pdf`](docs/WSC-2026-Simulation-Challenge-Brief.pdf)
- Technical document: [`docs/WSC-2026-Simulation-Challenge-Tech-Document.pdf`](docs/WSC-2026-Simulation-Challenge-Tech-Document.pdf)
- Rules summary: [`docs/challenge-rules.md`](docs/challenge-rules.md)

## License and contributing

MIT License (c) NoeFlandre. See [`LICENSE`](LICENSE) and
[`CONTRIBUTING.md`](CONTRIBUTING.md).
