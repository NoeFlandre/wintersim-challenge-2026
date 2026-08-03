# response_strategies

This directory is the **complete participant-owned submission surface** for the
WSC 2026 Simulation Challenge. Per the challenge rules, only files in this
directory are considered for evaluation.

## What is here

- `user_strategy.py` - the participant `UserStrategy` adapter that the
  organizer framework imports and calls during simulation events.
- `deferred_rebooking.py` - a participant-owned, standard-library-only helper
  for the Round 1 future-only in-transit rebooking policy.

## What is intentionally absent

Organizer files such as `default_strategy.py`, `strategy_validation.py`, and
the package `__init__.py` are **not** included here. They live only inside the
local, ignored organizer tree under `.challenge/` and are overlaid at runtime
by the `wsc2026 sync` command. Never copy organizer source into this directory.

## Current strategy: deferred future-only rebooking

Three methods in `UserStrategy` return `None`, delegating to the organizer
fallback. The in-transit hook returns `False` only when all active disruption
impacts are downstream of the vessel's current segment; direct impacts and
invalid state still delegate. The helper never mutates organizer objects.

## Submission boundary

Only files from this directory may enter a submission archive built by
`wsc2026 package`. The packager allowlists the two participant Python modules
and this README; it rejects organizer code, inputs, outputs, tests, caches, and
development tooling.

## Runtime restrictions

Submission code runs under the organizer framework and must be:

- Python 3.11+ compatible (the repo targets 3.11; the local default is 3.12).
- Standard-library imports only, plus documented organizer modules such as
  `maritime_data_context` or `simulation_model` that are available on the
  evaluation runtime `PYTHONPATH`.
- Free of network calls, subprocesses, filesystem access, environment-variable
  reads, current-working-directory assumptions, wall-clock time, unseeded
  randomness, and mutable cross-run global state.

Do not import development tooling from `src/wsc2026_tools`; that package is for
the local CLI only and is not present at evaluation time.
