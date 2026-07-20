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

The current `HEAD` tree contains no organizer software or data: the
organizer ZIP, the extracted source tree, derived outputs, and submission
archives are excluded by `.gitignore` and have never been added in tracked
form on this branch.

However, reachable repository history **does contain**
`SimulationChallenge2026_Py_Round0.zip`. In particular:

* commit `f7d0c70` ("chore: add Round 0 challenge archive") added the
  organizer ZIP, and is an ancestor of both the current `HEAD` and
  `origin/main`.
* Commit `df6d53d` ("chore: establish public-safe uv workspace") is the
  point at which the ZIP was removed from the working tree and added to
  `.gitignore`, but the file remains in the history before that point.

Therefore the repository as currently published is **not** public-safe in
its history. It must not be made public or merged as public-safe until an
owner authorizes and coordinates a history purge and a force-push that
removes `f7d0c70` and any later commit that re-introduced the ZIP. The
coding agent will not perform that destructive operation autonomously.

> **Public release and merge remain blocked pending owner-authorized history purge and coordinated force-push.**

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
  or submitted.** This workspace currently targets Round 0 for local
  bootstrapping, smoke testing, and baseline measurement only.
- **Round 1:** August 1-23, 2026 (20% weight).
- **Round 2:** September 1-23, 2026 (30% weight).
- **Hidden round:** October 1-23, 2026 (50% weight).

The current `UserStrategy` delegates every decision to the organizer fallback.
This is an intentional, known baseline; no optimization has been performed yet.

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

# Bootstrap the local Round 0 source from your private copy of the archive.
# The archive is verified against its published SHA-256 before extraction.
uv run wsc2026 bootstrap --round round0 --archive /path/to/SimulationChallenge2026_Py_Round0.zip

# Overlay participant response_strategies onto the bootstrapped source tree.
uv run wsc2026 sync --round round0

# Run a very short smoke simulation (a few days) to validate imports/wiring.
uv run wsc2026 smoke --round round0
```

Bootstrap extracts into the git-ignored `.challenge/round0/source/` tree and
never modifies the source archive.

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

Full runs (140-day warm-up plus the experiment) are **intentionally long** and
are **excluded from CI**. They require an explicit confirmation flag so an
hour-long run cannot start accidentally:

```bash
uv run wsc2026 run --round round0 --full
```

Outputs are written inside the ignored extracted workspace / experiment area.

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
