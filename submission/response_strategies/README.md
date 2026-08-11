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

## Current strategy: contiguous same-service recovery hold v5

Three hooks return `None` and delegate completely to the organizer fallback.
During an active disruption, `assign_associated_bookings` may return `False`
for a newly generated shipment only when all of the following are derived from
the live context: its nominal shortest route is one disrupted service or a
contiguous multi-edge path on one service route, the currently safe shortest
route needs at least two changes between services (at least three service
boardings), and the nominal service is estimated to recover and deliver sooner
than that detour. Recovery is taken from every nominal edge, so a later edge is
not ignored.

The strategy does not create or edit bookings. It reads runtime topology,
disruption windows, vessel speeds, and service-route headways, makes a
full-precision comparison, and otherwise delegates. Missing or ambiguous data
also delegates without mutation. The v5 full-run result is recorded in the
public experiment report after the one pre-registered candidate run; no output
is used to tune this policy.

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
