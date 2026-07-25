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

## Current strategy: safe recovery shuttle experiment

Three methods delegate to the organizer fallback without mutation:

- `select_vessel_for_berth`
- `assign_associated_bookings`
- `adjust_bookings_before_cargo_handling`

`create_alternative_service_routes` implements the standard alternative-route
creation, reservation, switching, and post-disruption restoration lifecycle
inside the participant file. If an active disruption leaves an affected
original service route without a complete safe alternative, it adds a
temporary recovery shuttle over the largest safely connected subset of that
route's ports. The shuttle uses only existing, non-disrupted legs and may take
one empty vessel when it reaches the shuttle start port.

This self-contained implementation is required by the submission packager:
participant code may import documented maritime entity classes, but it may not
depend on organizer-owned `response_strategies` implementation files that are
absent from the archive.

The policy is deterministic and derives every decision from the runtime
context. It contains no port names, route IDs, dates, tuned thresholds,
randomness, I/O, or mutable cross-run state.

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
