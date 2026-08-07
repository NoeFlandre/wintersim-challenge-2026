# Round 1 disruption-weighted booking design

## Goal

Test one general Round 1 cargo-routing policy that can improve the official
Cumulative Resilience Loss without changing the simulator, scorer, or any
organizer-owned file.

## Evidence and decision

The restored Round 1 no-op adapter delegates to the organizer fallback and is
the pinned control. Two prior Round 1 experiments were rejected: suppressing
future-only in-transit replanning was materially worse, and a progress-first
berth policy produced byte-identical output. The fallback's initial-booking
policy always removes every currently congested leg from its candidate graph,
even when that leg is the only available connection or a short, mildly delayed
connection is faster than waiting for recovery. That is the single assumption
tested here.

## Candidate policy

Only `UserStrategy.assign_associated_bookings` is changed. The other three
hooks continue returning `None` and delegate to the organizer fallback.

When no disruption is active, the hook returns `None` without reading or
mutating runtime state. During an active disruption:

1. Closed berths/ports remain hard exclusions; a booking edge may not pass
   through a currently closed port.
2. Congested sailing legs remain eligible. Each edge is scored by predicted
   sailing duration, not raw distance. The estimate uses the selected route's
   deployed-vessel speed and the active disruption plans for the physical legs.
3. If a disruption ends while a predicted leg is in progress, the estimate
   charges the multiplier only until the plan's end and normal speed afterward.
4. A deterministic, context-order Dijkstra search chooses the lowest predicted
   completion time across valid booking edges. Existing, deployed alternative
   routes are considered only when their runtime disruption key matches the
   active plans, matching the organizer's availability boundary.
5. The shipment's existing booking references are changed only after a complete
   path has been found and validated. The returned chain contains contiguous
   route segments, correct sequence indices, reverse route references, and a
   valid current booking index.

If the context, shipment, route, speed, disruption clock, or graph is missing or
malformed, or no valid path exists, the hook returns `None` and lets the
organizer fallback decide. It never partially mutates state.

## Explicit non-goals and compliance

- No port names, route IDs, dates, seed-specific tables, tuned thresholds, or
  historical score constants in submission code.
- No organizer imports, filesystem/network/subprocess/environment access,
  wall-clock calls, randomness, or mutable module/global state.
- No changes outside the participant submission surface except tests, public
  documentation, and development-only experiment records.
- No output/scorer manipulation and no second candidate or parameter sweep.

## Test design

RED tests will prove that the no-op baseline delegates for inactive/malformed
inputs but cannot handle a valid active graph. GREEN tests will cover:

- effective-duration choice between a shorter congested leg and a longer safe
  detour;
- a congested direct path when no safe path exists;
- recovery during a leg;
- closed-port exclusion and deterministic ties;
- complete booking/reverse-reference construction;
- no mutation on delegation, malformed input, and no-path paths;
- exact four-hook signatures and standard-library-only imports.

An integration test will construct the real Round 1 disruption context and
verify a valid active booking assignment without relying on hard-coded
participant code names. The full run remains blocked until all gates pass.

## Fixed run contract

- Round: `round1`
- Scenario: `create_with_disruption`
- Seed: `2026`
- Warm-up: 140 days
- Measured horizon: 360 days
- ATT interval: 5 days, exactly 72 periods
- Environment: `PYTHONHASHSEED=0`
- Pinned fallback loss: `20.436668751255972`
- Pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- Acceptance: `candidate_loss < 20.436668751255972 - 1e-9`
- Candidate evidence directory:
  `.challenge/round1/results/disruption_weighted_booking_v1_20260807/`

Exactly one full candidate run is authorized. Its raw output is preserved
before scoring or restoration. Equality, worsening, invalid output, crashes,
or failed gates are rejection. Rejection requires a tracked report, reverse
`git revert` of candidate code/tests, synchronization of the no-op adapter,
byte restoration of the pinned fallback ATT, exact re-score, and fresh final
gates. No push, merge, PR, submission, or history rewrite is part of this
experiment contract.
