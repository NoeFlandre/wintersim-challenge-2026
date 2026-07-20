# Contributing

This repository is a participant workspace for the WSC 2026 Simulation
Challenge. These notes keep the workspace compliant and reproducible.

## Hard rules

- **Never commit organizer source or data.** Organizer software, inputs, and
  outputs live only in the git-ignored `.challenge/` tree. Do not copy them into
  tracked files, tests, fixtures, docs, or CI artifacts.
- **Round 0 is never submitted.** The packager rejects it.
- **Submission code stays standard-library-only** (plus documented organizer
  modules available at runtime). No network, subprocess, filesystem,
  environment, cwd, wall-clock, unseeded randomness, or mutable cross-run global
  state.
- **Do not push, force-push, rewrite history, or submit anything** without
  explicit owner approval. The restricted Round 0 archive still exists in prior
  git history and needs owner-authorized public-history purging.

## Workflow

We follow strict red-green-refactor TDD for every behavioral unit:

1. Write one focused failing test; run it; confirm it fails for the right reason.
2. Implement the minimum code to pass.
3. Run the exact test, then the module; refactor only while green.
4. Commit the coherent increment.

## Local checks before pushing

```bash
uv lock --check
uv sync --locked --group dev --group simulation
uv run ruff format --check .
uv run ruff check .
uv run mypy src/wsc2026_tools submission
uv run pytest -m "not integration" --cov=src/wsc2026_tools --cov=submission --cov-report=term-missing --cov-fail-under=90
```

Integration tests require the local Round 0 source and are excluded from CI:

```bash
uv run pytest -m integration -q
```

## Tooling layout

- Dev CLI: `src/wsc2026_tools/` (run via `uv run wsc2026 ...`).
- Submission surface: `submission/response_strategies/`.
- Tests: `tests/unit` (synthetic, fast) and `tests/integration` (need local
  source; marked `integration`).

## Adding strategy code

Only add modules under `submission/response_strategies/` as part of an approved,
tested strategy. When you do, extend the allowlists in `overlay.py` and
`packaging.py` deliberately, and keep submission imports within the allowed set
(standard library, participant modules, documented organizer modules).
