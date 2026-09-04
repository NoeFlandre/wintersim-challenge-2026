# OrtolanForever — WSC 2026 Round 2

This directory contains the participant-owned response strategy submitted by
team **OrtolanForever** for Round 2 of the WSC 2026 Simulation Challenge.

## Strategy

The strategy owns exactly one decision: the initial booking chain for newly
generated cargo (`assign_associated_bookings`). The other three decision points
are delegated to the organizer's default implementation.

The organizer's fallback selects a booking chain by minimising **sailing
distance**. Distance ignores how often each service actually departs, so the
fallback will buy a marginally shorter route at the price of an extra
transshipment — and a transfer costs, on average, half of the next service's
headway. This strategy instead minimises **estimated transport time**, built
entirely from the live simulation context:

- sailing time per leg is `sailing_distance * sailing_time_multiplier` divided
  by the mean speed of the route's currently deployed vessels, so an active
  congestion multiplier is priced rather than merely avoided;
- the wait to board the **first** service is read from where that route's
  vessels actually are: each deployed vessel is walked forward around the
  rotation (half of its current leg if at sea, half a berthing time if already
  alongside, then a leg plus a port call per further segment) and the earliest
  departure any of them offers is used. A service whose vessel is about to
  arrive is therefore preferred over an identical one whose vessel has just
  left. If a route's vessels cannot all be located, that route falls back to
  the headway expectation rather than being dropped;
- the wait to board each **later** service costs one full `headway`, the
  reciprocal of the combined departure rate of the deployed vessels
  (`1 / sum of 1 / cycle hours per vessel`, which equals
  `cycle hours / vessel count` whenever the vessels share a speed). Phase
  information about a connection days ahead has decayed, so a full headway
  rather than the textbook half is used: cargo loads only if it is already
  waiting when a vessel begins its port call, and the simulation's ±5% sailing
  variation makes vessels bunch, which lifts the mean wait for a random arrival
  above half a headway;
- each intermediate port call inside a single booking costs the simulation's
  fixed three-hour berthing time.

The chain is chosen by a shortest-path search over `(port, service route)`
states, so each change of service is charged its own boarding wait. Two
consecutive bookings never use the same service route.

The strategy declines and lets the organizer decide whenever:

- the shipment is not newly generated cargo, or origin and destination match;
- a port has berths and none of them is available — it is not booked as an
  arrival or an intermediate call, and a closed destination is delegated so the
  organizer's wait-and-retry keeps control;
- the only available path would cross a congested leg. Congested legs are
  used when a congestion-free path also exists and the congested one is still
  faster, but never as the sole option;
- a service route is an organizer-created disruption alternative, or currently
  has no deployed vessels — booking either could be orphaned when the
  organizer restores vessels at recovery;
- any runtime value is missing, malformed, non-finite, ambiguous, or the
  destination is unreachable.

Bookings are constructed only after the complete chain has been validated and
are then registered in one pass, so no partially booked shipment can be left
behind.

## Runtime guarantees

- Compatible with Python 3.11 and newer.
- Deterministic: no randomness, no wall clock, no iteration order that depends
  on object identity or hashing, and integer-only tie-breaks.
- Uses only the Python standard library plus `Booking` from the organizer's
  `maritime_data_context`, which the organizer's own interface documentation
  directs a custom strategy to create.
- Read-only apart from the booking chain the interface requires it to create:
  it changes no route, vessel, berth, disruption, or simulation state.
- Performs no network, subprocess, filesystem, environment, or wall-clock
  access, and keeps no state between calls.

The organizer's framework supplies the remaining simulation components at
evaluation time. This archive intentionally contains only the participant
strategy and this explanation.
