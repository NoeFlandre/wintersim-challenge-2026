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

## Current strategy: v23 mixed three-change low-margin delegation

Three hooks return `None` and delegate completely to the organizer fallback.
During an active disruption, `assign_associated_bookings` keeps the accepted v3
recovery hold (`False`) except for one narrower case. It delegates (`None`) only
when the v3 hold already qualifies, the matching disruption has one congested
leg and one closed port, the safe shortest route has exactly three service-route
changes, and the hold-versus-detour timing margin is strictly smaller than the
first safe route's live full headway. Equality and every other case retain the
v3 hold or delegate as v3 dictates.

The strategy does not create or edit bookings. It reads runtime topology,
disruption windows, vessel speeds, and service-route headways, makes a
full-precision comparison, and otherwise preserves the v3 decision. Missing or
ambiguous data delegates without mutation. No performance result is claimed
until the pre-registered full experiment finishes.

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
