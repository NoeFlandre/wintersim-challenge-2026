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

## Current strategy: organizer fallback with berth-priority override

Three of the four hooks still delegate to the organizer fallback
(`create_alternative_service_routes`, `assign_associated_bookings`,
`adjust_bookings_before_cargo_handling`). They always return `None`.

The fourth hook, `select_vessel_for_berth`, implements a Smith-style
**TEU-delay-per-berth-hour priority** with the fixed 3-hour berthing
overhead:

- For each waiting vessel, compute predicted `handled_teu` (discharge + greedy
  load) and `affected_teu` (carried + greedy load) using only the organizer's
  berth-handling contract (`qc_count = max(1, int(loa / 55))`,
  `service_hours = 3.0 + handled_teu / (qc_count * 45)`).
- Occupied-capacity calculation mirrors the organizer's
  `VesselBeingServed._calc_occupied_teu` exactly: route-excluded cargo does
  not occupy capacity.
- Rank by exact cross multiplication of
  `numerator = affected_teu * qc_count` vs
  `denominator = 135 * qc_count + handled_teu`. Zero-handled vessels still
  consume the fixed 3-hour berthing time and use the same ratio path. Ties
  preserve the input `waiting_vessels` order.
- Returns one of `waiting_vessels` or `None`. Never returns `False`. Never
  mutates any input.
- Invalid inputs (missing/non-numeric/non-finite/zero/negative TEU,
  missing vessel class, missing route, non-finite LOA, nonpositive
  capacity) raise narrow expected exceptions that the public selector
  catches and uses to delegate with `None`. No broad `except Exception`
  is used.

Cargo age is intentionally excluded; the metric weights ATT per TEU, so the
marginal one-hour cost of delaying one TEU is constant. The full hypothesis,
mathematical justification, and reviewer-gate notes live in
`docs/experiments/round0-teu-delay-smith-priority-v1.md`. **No performance
simulation, scoring, or second candidate may be run before reviewer approval.**

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
