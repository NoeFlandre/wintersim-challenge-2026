# OrtolanForever — WSC 2026 Round 2

This directory contains the participant-owned response strategy submitted by
team **OrtolanForever** for Round 2 of the WSC 2026 Simulation Challenge.

## Strategy

The strategy owns three decisions: the initial booking chain for newly
generated cargo (`assign_associated_bookings`), whether to leave an in-transit
chain alone when a disruption appears after the cargo has sailed
(`adjust_bookings_before_cargo_handling`), and whether to move vessels between
services in response to a disruption
(`create_alternative_service_routes`). Berth selection is delegated to the
organizer's default implementation.

The organizer's fallback selects a booking chain by minimising **sailing
distance**. Distance ignores how often each service actually departs, so the
fallback will buy a marginally shorter route at the price of an extra
transshipment — and a transfer costs, on average, half of the next service's
headway. This strategy instead minimises **estimated transport time**, built
entirely from the live simulation context:

- sailing time per leg is `sailing_distance` divided by the mean speed of the
  route's currently deployed vessels, multiplied by the congestion multiplier
  **only while that congestion is still in force**. A slowdown is temporary, so
  a leg the cargo will not reach until after it clears is costed at normal
  speed; a slowdown whose end cannot be established is assumed permanent;
- boarding a service costs one full `headway`, where
  `headway = route cycle hours / deployed vessel count`. Cargo loads only onto
  a vessel whose next segment matches the booking's departure segment, so
  departures on a given segment are one headway apart. A full headway rather
  than the textbook half is used because cargo is loaded only if it is already
  waiting when a vessel begins its port call, and because the simulation's ±5%
  sailing variation makes vessels bunch, which lifts the mean wait for a random
  arrival above half a headway;
- each intermediate port call inside a single booking costs the simulation's
  fixed three-hour berthing time.

The chain is chosen by a shortest-path search over `(port, service route)`
states, so each change of service is charged its own boarding wait. Two
consecutive bookings never use the same service route.

The strategy declines and lets the organizer decide whenever:

- the shipment is not newly generated cargo, or origin and destination match;
- a port whose berths are all unavailable has **no readable reopening time**.
  A closure is temporary, so when its end can be established from the active
  disruption plans the port stays usable and the estimate charges the wait
  until it reopens, delaying the rest of that ride by the same amount; cargo
  bound for it is booked rather than held. The reopening time is trusted only
  when the plan arithmetic and the live berth state agree, so an unexpected
  simulation epoch, a malformed plan, or a missing plan all fall back to
  treating the port as impassable;
- the only available path would cross a congested leg. Congested legs are
  used when a congestion-free path also exists and the congested one is still
  faster, but never as the sole option;
- a service route is not the rotation its service is currently running, or
  has no deployed vessels — booking either could be orphaned when the fleet
  moves;
- any runtime value is missing, malformed, non-finite, ambiguous, or the
  destination is unreachable.

Bookings are constructed only after the complete chain has been validated and
are then registered in one pass, so no partially booked shipment can be left
behind.

## Runtime guarantees

- Compatible with Python 3.11 and newer.
- Deterministic: no randomness, no wall clock, no iteration order that depends
  on object identity or hashing, and integer-only tie-breaks.
- Uses only the Python standard library plus `Booking`, `Segment` and
  `ServiceRoute` from the organizer's `maritime_data_context`, which the
  organizer's own interface documentation directs a custom strategy to create.
- Changes no berth, disruption, demand, shipment, or clock state. The only
  state it writes is the booking chain and the fleet's rotation assignment,
  both of which the interface exists to set.
- Performs no network, subprocess, filesystem, environment, or wall-clock
  access, and keeps no state between calls.

The organizer's framework supplies the remaining simulation components at
evaluation time. This archive intentionally contains only the participant
strategy and this explanation.

## Keeping an in-transit chain

When a disruption appears after cargo is already at sea, the organizer replans
the rest of its journey by sailing distance, refusing the disrupted ports and
legs outright, and discharges the cargo at its current port whenever the
rebuild does not continue on the service it is already riding. Staying aboard
and waiting the disruption out is often faster.

This strategy therefore returns a decision to change nothing whenever every
affected shipment on the arriving vessel is at least as well off keeping its
booked chain, judged by the same cost model — the remaining chain walked from
the current port with closure waits and congestion priced, against the fastest
path the model can find from there. The alternative is costed with no wait to
board its first service, so a chain is kept only when it beats even the most
favourable rebuild.

The hook never mutates a booking, route, vessel, or berth. Anything uncertain
returns `None`, which restores the organizer's own replanning exactly.

## Running each service on its fastest rotation

The organizer's fallback answers a disruption by building an avoiding route
from existing legs and reserving **one** vessel from each affected service onto
it. That is the worst of both worlds: the original rotation still crawls
through the slowdown and has lost a share of its departures, while the new
route runs a single vessel around its whole cycle.

Nothing in the organizer's validation limits a new rotation to one vessel, so
this strategy moves the **whole service** instead, under one rule:

> Move an entire service onto a detour around a slowdown when the detour still
> calls every port the rotation calls and its cycle is strictly shorter than
> the rotation's cycle at the multipliers now in force.

The detour is built by replacing each slowed leg `A -> B` with the fastest path
`A -> ... -> B` over existing legs that no disruption touches. Only insertions
are made, so every port is still called, in the same order, and the rotation
stays a connected cycle. Because both cycles are measured at the same speed,
comparing their multiplier-stretched distances is exactly comparing their cycle
hours, and a service that moves keeps its full vessel count: its headway
improves as well as its sailing time.

Three safety rules bound the change:

- **A shut port is never routed around.** A closure is a wait, not a reason to
  stop calling somewhere; dropping the call would abandon the cargo booked
  there. A rotation with a closed port anywhere on it is left alone entirely.
- **Only an empty vessel moves, and only where it stands.** A vessel joins
  another rotation only when it is carrying nothing and the rotation calls the
  port it is at, so it resumes from there. No cargo is loaded, discharged,
  moved, or completed by this hook.
- **A rotation is never left without vessels while cargo is still booked on
  it.** The last vessel stays until no unfinished shipment holds a booking on
  that rotation. New cargo is offered only the rotation each service is
  actually running, which is what lets the one being left behind drain.

When the slowdown lifts, the same rule points the service back at its nominal
rotation and the fleet returns the same way, one empty vessel at a time. With
no slowdown in force, or with no detour worth taking, nothing is created and
the fleet stays exactly as deployed.
