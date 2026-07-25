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

## Current strategy: recovery-aware origin hold vs. disruption detour

The candidate is a single-hook change. `UserStrategy.assign_associated_bookings`
is the only method that returns a non-`None` value, and even then only `False`.

- `False` is returned only when waiting for the relevant disruption recovery
  is predicted to complete strictly earlier than the fallback's currently
  available safe detour. `False` means "no booking can currently be assigned
  (may cause retry/wait)" and uses the existing organizer retry lifecycle.
- `None` is returned in every other case (delegate to the organizer fallback).

The other three hooks always return `None`:

- `select_vessel_for_berth`
- `create_alternative_service_routes`
- `adjust_bookings_before_cargo_handling`

The candidate is read-only and self-contained. It does not create bookings,
routes, legs, vessels, or events. It does not mutate any organizer state. It
does not import organizer source.

## Submission boundary

Only files from this directory may enter a submission archive built by
`wsc2026 package`. The packager rejects organizer code, inputs, outputs, tests,
caches, and development tooling.

## Runtime restrictions

Submission code runs under the organizer framework and must be:

- Python 3.11+ compatible (the repo targets 3.11; the local default is 3.12).
- Standard-library imports only. The participant strategy imports
  `datetime`, `math`, and `typing` from the standard library; no third-party
  modules and no organizer modules are imported.
- Free of network calls, subprocesses, filesystem access, environment-variable
  reads, current-working-directory assumptions, wall-clock time, unseeded
  randomness, and mutable cross-run global state.

Do not import development tooling from `src/wsc2026_tools`; that package is for
the local CLI only and is not present at evaluation time.
