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

## Current strategy: multi-transfer recovery-hold experiment

Three hooks return `None` and delegate completely to the organizer fallback.
During an active disruption, `assign_associated_bookings` may return `False`
for a newly generated shipment only when all of the following are derived from
the live context: its normal shortest route is one disrupted direct service,
the currently safe shortest route needs exactly two changes between services
(exactly three service boardings), and the direct service is estimated to
recover and deliver sooner than that detour. A safe route with three or more
changes delegates to the organizer fallback.

The strategy does not create or edit bookings. It reads runtime topology,
disruption windows, vessel speeds, and service-route headways, makes a
full-precision comparison, and otherwise delegates. Missing or ambiguous data
also delegates without mutation. No performance result is claimed until the
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
