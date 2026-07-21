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

## Current strategy

`UserStrategy` deliberately delegates `select_vessel_for_berth`,
`create_alternative_service_routes`, and `assign_associated_bookings` to the
organizer fallback (each returns `None`).

`adjust_bookings_before_cargo_handling` is also a no-op when no disruption is
active (returning `None` so the fallback may perform in-transit replanning).
While at least one disruption is active, however, it returns `False` to tell
the caller "handled, do not run the organizer in-transit rebooking fallback".
The active call makes **no mutation whatsoever** on the context, routes,
legs, segments, bookings, shipments, vessel assignment, vessel carried
shipments, vessel segment/berth, or any other object reachable from the
arguments.

The exact rationale, hypothesis, and acceptance rules are documented in
`docs/experiments/round0-in-transit-rebooking-suppression-v1.md`.

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
