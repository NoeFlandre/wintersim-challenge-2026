# response_strategies

This directory is the **complete participant-owned submission surface** for the
WSC 2026 Simulation Challenge. Per the challenge rules, only files in this
directory are considered for evaluation.

## What is here

- `user_strategy.py` - the participant `UserStrategy` adapter that the
  organizer framework imports and calls during simulation events.

## What is intentionally absent

Organizer files such as `default_strategy.py`, `strategy_validation.py`, and
the package `__init__.py` are **not** included here. They live only inside the
local, ignored organizer tree under `.challenge/` and are overlaid at runtime
by the `wsc2026 sync` command. Never copy organizer source into this directory.

## Current strategy: v25 equal-distance route tie-break experiment

Three hooks return `None` and delegate completely to the organizer fallback.
The booking hook preserves the v3 recovery hold for a newly generated shipment.
Otherwise, during an active disruption, it may install a complete booking chain
only when the fallback's disruption-safe shortest path has exactly the same
total sailing distance as another safe path with strictly fewer service-route
changes. The path is derived from the live context and installed only after all
segments and booking objects are validated; any uncertainty delegates without
mutation.

The strategy reads runtime topology and active disruption state, uses exact
full-precision distance equality, and preserves deterministic context-order
tie-breaking when no strictly better transfer count exists. It uses only
standard-library code plus the organizer's runtime `maritime_data_context`
`Booking` class, has no filesystem/network/randomness/clock access, and keeps
all temporary state inside a call. No performance result is claimed until the
pre-registered full experiment finishes.

## Submission boundary

Only files from this directory may enter a submission archive built by
`wsc2026 package`. The packager rejects organizer code, inputs, outputs, tests,
caches, and development tooling.

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
