# Round 1 congestion-only direct booking experiment

## Goal

Evaluate one participant-owned cargo-routing policy that may use an active
congested physical leg as a single direct booking when no berth closure is
active, avoiding a potentially longer safe detour and transshipment.

## Evidence and hypothesis

The pinned Round 1 no-op fallback has cumulative resilience loss
`20.436668751255972` over 72 five-day periods. The fallback excludes every
active congested leg from initial booking paths. The controlled Round 1
experiments already tried broad disruption-weighted and phase-aware path
replacement; both changed many shipments and were materially worse. A narrower
policy is warranted: only exact origin-to-destination traffic whose endpoints
are the two ports of an active congested leg may use that one leg, and only
when no active berth closure exists anywhere in the context. All other calls
delegate unchanged to the organizer fallback.

The falsifiable hypothesis is that, during a congestion-only tail window, the
extra sailing time on a direct leg is lower than the waiting and handling cost
of a safe multi-leg detour. The policy is intentionally conservative: it does
not alter cargo whose origin/destination is not an exact affected-leg pair,
does not run while any berth is closed, and requires an original route with a
deployed vessel to contain the target leg.

## Exact policy boundary

Only `UserStrategy.assign_associated_bookings` may return a non-`None` value.
For every active plan, the helper validates finite timing and a positive
multiplier. It collects active congested target legs (`multiplier > 1`) and
active berth closures. If any active closure is present, if no active
congested leg is valid, or if runtime state is malformed, it returns `None`.

For an exact endpoint match (`shipment.demand.origin_port is leg.departure_port`
and `destination_port is leg.arrival_port`), it chooses the first deterministic
original service-route segment in `context.service_routes` whose leg is the
target leg and whose route has at least one deployed vessel. It installs one
complete `Booking` covering that segment and returns `True`. The booking is
installed transactionally: all old reverse references and shipment fields are
restored if any mutation fails. If no valid matching route exists, it returns
`None`.

The other three hooks remain unconditional `None`. No organizer fallback code
is imported, and the participant code uses only the standard library plus the
runtime `Booking` class loaded lazily after planning. The policy must be
deterministic, read-only until the validated installation, free of I/O,
network, subprocess, environment, wall-clock, randomness, mutable global
state, port names, route IDs, dates, seeds, and tuned numeric thresholds.

## TDD and validation design

RED tests must fail against the no-op adapter for:

- active congestion-only exact endpoint matching returns `True` and creates a
  complete one-segment booking;
- active closure, inactive plans, non-matching endpoints, malformed plans,
  missing/deployed-empty routes, and ambiguous target legs delegate with
  `None` and no mutation;
- exact active-window boundaries use `start <= now < end`;
- old shipment and reverse-route references remain consistent after success;
- an injected installation failure rolls every mutation back;
- the four public signatures and the three untouched hooks remain valid.

The minimal implementation must make the focused suite GREEN, then pass the
real Round 1 context integration test, lock/sync, Ruff, Ty, mypy, coverage,
integration, sync/cmp, smoke, deterministic package, restricted-material,
diff, and process gates. The full run is not authorized until the contract and
pre-run review are committed.

## Fixed candidate contract

- branch: `codex/round1-congested-direct-booking-v1`
- round: `round1`
- scenario: `create_with_disruption`
- seed: `2026`
- `PYTHONHASHSEED=0`
- warm-up: `140` days
- measured horizon: `360` days
- ATT interval: `5` days
- required periods: `72`
- candidate command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- acceptance expression (full precision, no rounding):
  `candidate_loss < 20.436668751255972 - 1e-9`
- candidate evidence directory (ignored):
  `.challenge/round1/results/congested_direct_booking_v1_20260807/`
- ignored aggregate: `experiments/results/round1_congested_direct_booking_v1_20260807.json`

The fresh candidate CSV and raw log must be copied and hashed before any
restore or scoring command can overwrite `Output/`. Record byte size, mtime,
header, 72-period count, mean ATT, full scorer JSON, per-period comparison,
runtime log hash, package hash, and package members.

## One-candidate and restoration rule

Exactly one complete candidate run is allowed after pre-run authorization. A
crash, incomplete output, invalid period count, equality, worsening score, or
failed final gate is rejection. On rejection, preserve evidence, commit the
result report, revert only candidate code/tests in reverse order with
`git revert`, synchronize the no-op adapter, restore the pinned fallback ATT
bytes, re-score exactly to the pinned loss, and rerun every final gate. Do not
tune, rerun, try a second candidate in this experiment, publish organizer
material, submit an archive, push/merge/PR, or rewrite history.
