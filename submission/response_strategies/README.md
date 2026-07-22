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

## Current strategy: temporal lower-bound safe routing during active disruptions (v1)

Round 0 experiment candidate.

The candidate overrides `assign_associated_bookings` only when **all** of
the following are true:

1. At least one disruption plan is currently active
   (``start <= now < end`` anchored at ``datetime.min``).
2. The shipment's nominal distance-shortest path over **original** service
   routes touches at least one currently active closed port or congested leg.
3. Every active disrupted resource touched by that path has its earliest
   physically possible encounter at or after that plan's recovery time,
   using the documented optimistic lower-bound model:
   - transfer, berth, and cargo-handling waits are zero;
   - each leg is sailed at 1.05x the fastest valid sailing speed among the
     original route's currently deployed vessels;
   - disruption multipliers are ignored;
   - an encounter at exactly the recovery instant is safe because the
     active interval is end-exclusive.
4. A complete valid nominal booking chain exists.

When all conditions hold, the candidate atomically installs the chain and
returns exactly ``True``. Otherwise, it returns exactly ``None`` without
mutating any reachable state. The candidate never returns ``False``.

The other three hooks (`select_vessel_for_berth`,
`create_alternative_service_routes`, `adjust_bookings_before_cargo_handling`)
remain unconditional ``None`` delegates to the organizer fallback.

The hypothesis, exact one-hook scope, lower-bound model, atomic-mutation
contract, full-run configuration, acceptance rule, and rejection/restoration
procedure are documented in
`docs/experiments/round0-temporal-safe-routing-v1.md`.

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
