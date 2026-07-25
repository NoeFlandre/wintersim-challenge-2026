# response_strategies

This directory is the **complete participant-owned submission surface** for the
WSC 2026 Simulation Challenge. Per the challenge rules, only files in this
directory are considered for evaluation.

## What is here

- `user_strategy.py` - the participant `UserStrategy` adapter that the
  organizer framework imports and calls during simulation events.
- `transshipment_readiness.py` - the standard-library-only implementation of
  the reviewed Round 0 transshipment-readiness barrier candidate.

## What is intentionally absent

Organizer files such as `default_strategy.py`, `strategy_validation.py`, and
the package `__init__.py` are **not** included here. They live only inside the
local, ignored organizer tree under `.challenge/` and are overlaid at runtime
by the `wsc2026 sync` command. Never copy organizer source into this directory.

## Current strategy: Transshipment Readiness Barrier v1

Only `select_vessel_for_berth` may override the organizer fallback. It delegates
to `transshipment_readiness.py`, which may select one original waiting vessel
as a temporary buffer when conservative route, capacity, event-readiness, and
TEU-hour checks all pass. Every invalid, ambiguous, disrupted, non-finite, or
non-positive case returns `None`. The other three hooks remain unconditional
fallback delegations.

This candidate has not been performance-simulated or accepted. Its status is
`PRE_RUN_REVIEW`, and operational execution requires separate reviewer approval.

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
