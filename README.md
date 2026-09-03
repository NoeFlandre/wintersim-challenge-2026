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
are documented.

Ten Round 2 experiments are complete. Every experiment, its behavioural delta,
activation statistics, score, per-period comparison and decision is tabulated in
the [Round 2 experiment ledger](docs/experiments/round2-ledger.md).

The first eight experiments all tuned one binary predicate: whether to hold new
cargo at its origin during a disruption. The accepted
[v1 port-closure hold](docs/experiments/round2-port-closure-one-transfer-full-headway-v1.md)
reached `35.1039547178493`; relaxing or tightening its margin lost every time.

The last two changed the architecture and are both accepted:

- [v9 time-aware booking assignment](docs/experiments/round2-time-aware-booking-v9.md)
  stops delegating routing to the organizer's distance-based shortest path and
  builds the booking chain itself, minimising estimated transport time. Score
  `20.248013560766417`, an improvement of `42.320%`.
- [v10 full-headway boarding cost](docs/experiments/round2-full-headway-boarding-v10.md)
  charges one full headway per boarding rather than half, a correction derived
  from [measuring the cost model against realized transit
  time](docs/experiments/round2-cost-model-fidelity.md). Score
  `14.897068731156086`, a further `26.427%`.

The active Round 2 strategy therefore scores `14.897068731156086`, which is
`57.56%` below the `35.1039547178493` that opened the round. Its ATT SHA-256 is
`4f22259de77c2e77477ba21f0f7c36c988ee9c5e80cca425984fe65aa0ad6eb4`, reproduced
byte-identically by two independent full runs.

The current `UserStrategy` keeps three decisions delegated to the organizer and
owns one: the initial booking chain for newly generated cargo. It selects the
chain with the least estimated transport time, computed from live runtime state
(sailing time at current leg multipliers, one full headway per service route
boarded, and the simulation's fixed berthing time per intermediate port call).
It fails closed to the organizer fallback on closed destinations, paths that can
only cross a congested leg, disruption-alternative or vessel-less routes, and
any malformed or ambiguous data. Round 0 and Round 1 evidence remains as
background only; see the ledger and per-experiment reports for the full record.

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
