# Architecture

## Two workspaces, one repository

The workspace deliberately separates the **public participant workspace** from
the **ignored organizer workspace**.

### Public participant workspace (tracked, redistributable)

- `src/wsc2026_tools/` - the development-only CLI. Not part of any submission.
  - `paths.py` - repo-root-relative path helpers and strict `rounds.toml`
    loading (fail closed; no "allow unverified" escape).
  - `artifacts.py` - verified, atomic, safe archive extraction.
  - `overlay.py` - copies allowlisted participant files onto the organizer tree.
  - `scoring.py` - reproduces the dashboard's Cumulative Resilience Loss.
  - `packaging.py` - builds compliant submission archives.
  - `cli.py` - argparse entry point (`wsc2026 ...`) and the smoke/full runners.
- `submission/response_strategies/` - the **complete participant-owned
  submission surface**. Only files here may enter a submission archive.
- `config/rounds.toml` - public round metadata (archive filename, published
  SHA-256, marker paths). No organizer source or prose.
- `tests/` - unit tests (synthetic) and integration tests (require local source).
- `docs/` - public documentation and the publicly-distributed PDFs.

### Ignored organizer workspace (local only, never redistributed)

- `.challenge/<round>/source/` - the verified, extracted organizer tree that the
  simulation actually runs against.
- `.challenge/downloads/` - local copies of challenge archives.
- `dist/submissions/` - generated submission archives.
- `experiments/results/` - local experiment results.

## Why submission code is separate from dev tooling

Submission code runs inside the organizer's framework at evaluation time, where
neither `src/wsc2026_tools` nor the project's dependencies are guaranteed to
exist. Keeping `submission/response_strategies` physically and logically
separate ensures:

- The submission stays standard-library-only and self-contained.
- Dev tooling can use any dependencies without polluting the submission.
- The packager can enforce a strict allowlist of what ships.

## Data flow

```
bootstrap  ->  sync  ->  smoke (short) / run --full (long)  ->  score  ->  package
```

1. **bootstrap** verifies the archive SHA-256, safely extracts into
   `.challenge/<round>/source`, and validates structural marker paths.
2. **sync** overlays the participant `response_strategies` onto the extracted
   tree without touching organizer-owned files.
3. **smoke** runs a few simulation days in a subprocess (with `PYTHONPATH` set
   to the round root and `o2despy/`) to catch import/wiring/immediate runtime
   failures. **run --full** invokes the organizer's full `run_simulation`
   (no dashboard).
4. **score** computes Cumulative Resilience Loss from two ATT-per-period CSVs.
5. **package** builds a deterministic, compliant archive under
   `dist/submissions/`.

All paths in the CLI resolve relative to the repository root, never to the
current working directory, so commands behave identically from any directory.

## Why the fallback strategy is the initial baseline

The shipped `UserStrategy` returns `None` from every method, delegating to the
organizer fallback without mutating any input. This establishes a known,
unmodified baseline that:

- Proves the wiring works end to end (the smoke test exercises it).
- Gives a reference Cumulative Resilience Loss to compare future strategies
  against.
- Avoids any premature, unreviewed optimization.

## Why full simulations are manual

A full run includes a 140-day warm-up plus the experiment and can take on the
order of an hour. It is intentionally excluded from CI and gated behind
`run --full` so it cannot start accidentally.

## Future strategy modules

Future response-strategy algorithms, helpers, and participant-owned data will
be introduced **only** as part of an approved, tested strategy, under
`submission/response_strategies/`. No empty placeholder modules, caches,
databases, plugin systems, or optimization frameworks are added speculatively.
