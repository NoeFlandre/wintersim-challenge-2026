# Round 1 pending alternative-route vessel activation design

## Decision

Run exactly one Round 1 candidate that changes only
`UserStrategy.select_vessel_for_berth`. During an active disruption, the hook
will select the first waiting vessel (in the framework-provided queue order)
that is empty and has a valid pending alternative service route whose first
leg departs from the berth's port. Every other situation delegates with
`None`.

The hypothesis is that the organizer fallback may reserve an empty vessel for
an alternative route but then choose a different vessel at the berth. Giving
that pending-route vessel a berth at its route's actual departure port should
activate the already-created alternative without changing route construction,
booking assignment, carried cargo, or the fallback policy elsewhere. This is a
narrow test of a concrete gap observed in the real Round 1 context, not a
general berth-priority rewrite.

## Evidence and constraints

The current Round 1 no-op control is pinned to cumulative resilience loss
`20.436668751255972`, 72 five-day ATT periods, and ATT SHA-256
`c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`.
Earlier Round 1 experiments that changed in-transit booking or broad initial
booking choices were worse, while progress-first berth selection produced a
byte-identical result. A static inspection of the organizer fallback found
that active Day-60 and Day-125 disruptions reserve an empty pending vessel for
an S2 or S6 alternative route. This candidate targets only activation of that
existing reservation and leaves the fallback ranking untouched when no pending
route is ready.

The participant code must remain inside the permitted
`submission/response_strategies` surface, use only the Python standard library,
avoid organizer imports and scenario constants, and perform no I/O,
subprocesses, environment reads, wall-clock reads, randomness, mutation, or
mutable module-level state. It must return the original vessel object or
`None`; it must never construct routes or alter context, queues, vessels,
bookings, legs, or plans.

## Exact policy

1. Determine whether `current_time` is inside any context disruption plan. A
   plan is active for the interval anchored at `datetime.min` plus
   `start_offset_days`, inclusive at the start and exclusive at the end. Any
   missing, non-numeric, non-finite, overflowing, or otherwise malformed plan
   makes that plan ineligible; malformed input must fail closed to `None`.
2. Iterate `waiting_vessels` exactly once in its supplied order.
3. A vessel is eligible only when `carried_shipments` is empty, its
   `pending_assigned_service_route` is present, that route has at least one
   segment, and the segment with the lowest `sequence_index` has an
   `associated_leg` whose `departure_port is port`.
4. Return the first eligible original vessel. If the queue is empty,
   iteration fails, no plan is active, no vessel matches, or any candidate is
   malformed, return `None` without mutation.
5. `create_alternative_service_routes`, `assign_associated_bookings`, and
   `adjust_bookings_before_cargo_handling` remain unconditional `None` hooks.

The policy is deterministic because it uses only the supplied queue order and
explicit segment sequence. Identity comparison for the departure port avoids
accidentally matching an unrelated object with an equal label.

## Validation and acceptance

RED tests must fail against the no-op baseline for an active matching vessel.
GREEN tests must cover start/end boundaries, queue-order ties, carried vessels,
wrong ports, missing/malformed routes and plans, no mutation, object identity,
the inactive gate, and preservation of the four-hook signature contract. An
ignored integration test must load the participant file by path alongside the
real Round 1 organizer context and exercise a real active plan without relying
on the organizer package namespace.

Before execution, lock/sync, Ruff format/lint, `ty`, mypy, non-integration
coverage (at least 90%), integration tests, Round 1 sync and byte comparisons,
smoke, deterministic packaging twice, restricted-material scans, and process
checks must pass. Only then may the one fixed run be started:

```text
PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full
```

The run uses `create_with_disruption`, seed 2026, 140 warm-up days, 360
measured days, five-day ATT intervals, and must finish at Period 72/Day 360.
The candidate is accepted only if
`candidate_loss < 20.436668751255972 - 1e-9`. Equality, worsening, a crash,
incomplete output, a non-72-period CSV, or any failed gate is rejection. The
candidate ATT and log must be copied to the ignored evidence directory
`.challenge/round1/results/pending_alt_activation_v1_20260807/` before any
score-based restoration; the ignored aggregate is
`experiments/results/round1_pending_alt_activation_v1_20260807.json`.

On rejection, preserve all evidence, record the exact result, revert only the
candidate implementation/tests/allowlist changes with `git revert`, sync and
restore the pinned no-op Round 1 runtime and ATT, re-score the fallback to the
exact pinned value, and repeat the final gates. Do not tune, run a second
candidate, alter the threshold, publish organizer material, or retain an
archive. On acceptance, keep the candidate, document the same evidence, and
run the final gates without a second run.
