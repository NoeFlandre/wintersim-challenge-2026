# Round 2: time-aware booking assignment (v9)

**Status: DESIGN — frozen before implementation.**

## Why a new architecture

Every Round 2 experiment so far (v1–v8) tuned one binary predicate: whether to
hold new cargo at its origin while a disruption is active. The accepted v1
policy gained `0.3997` (`1.13%`). Widening it (v2 half-headway, v3
three-quarter-headway, v7 upper-quartile half-headway) and narrowing it (v4
late-recovery, v6 TEU-dominance) both made the score worse, and the berth hook
(v5) produced a byte-identical ATT. That neighbourhood is exhausted: the hold
predicate is at a local optimum worth roughly 1% of the objective.

Stepping back, the incumbent never exercises the main power the organizer's
own interface grants. `assign_associated_bookings` is documented as:

> A custom strategy should create the required `Booking` objects, populate
> `shipment.associated_bookings` in sequence order, register each booking in
> its service route's `associated_bookings` collection, and set
> `shipment.current_booking_index`.

The incumbent only ever returns `False` (hold) or `None` (delegate). All actual
routing is therefore done by `DefaultStrategy`, which runs Dijkstra over
**sailing distance**. Distance is the wrong objective: it ignores service
frequency entirely.

## Measured diagnosis

A read-only audit built fresh disruption contexts, applied the runtime
disruption state exactly as `DisruptionManager` does, created the organizer's
alternative routes, and for every demand compared the default distance-optimal
booking path with a time-optimal path. Evidence is in the ignored directory
`.challenge/round2/results/audit_20260903/`.

- Across the 166 disruption days: 62,555 demand-time observations, of which
  **10,564 (16.9%)** have a strictly faster time-aware path. Median saving
  `53.7` hours; p90 `90.8` hours.
- On days with **no** active disruption the same defect is present:
  **70 of 380 demands (18.4%)** are improvable, and the TEU-weighted mean
  saving over *all* demands is `5.12` hours.

The defect is structural, not disruption-specific. Representative cases:

| OD | default path | time-optimal path | saving |
| --- | --- | --- | --- |
| Busan→Kaohsiung | S2 Busan→Shanghai, S4 Shanghai→Kaohsiung | S2 Busan→Kaohsiung | 52.1 h |
| Shanghai→Busan | S4 Shanghai→Kaohsiung, S2 Kaohsiung→Busan | S2 Shanghai→Busan | 52.1 h |
| Singapore→Busan | S1, S4, S2 (three bookings) | S1 Singapore→Shenzhen, S2 Shenzhen→Busan | 53.7 h |

In each case the default buys a marginally shorter distance at the price of an
extra transshipment, and each transfer costs roughly half of the next route's
headway. S4's headway is `154` hours, so a transfer added to save 33 nautical
miles costs about three days.

Capacity is not a binding constraint and cannot absorb the difference: the
control run reports service-route utilisation of `0.88%`–`6.12%` and an average
of `0.11` vessels waiting for a berth. Transport time in this scenario is
dominated by sailing time plus waiting for the next departure, which is exactly
what the default ignores.

## Frozen policy

`UserStrategy.assign_associated_bookings` builds the booking chain itself for
newly generated cargo, minimising **estimated transport time** instead of
distance. Every quantity is read from the live runtime objects.

Edge cost, for one booking on one service route:

```text
hours = sum over traversed legs of (sailing_distance * sailing_time_multiplier) / mean_deployed_speed
      + 3.0 * (traversed_legs - 1)
```

`3.0` is the organizer's own fixed `BerthBerthing` duration, charged once per
intermediate port call; it is not a tuned constant. Boarding a route costs the
expected wait for its next departure on the booked segment:

```text
headway  = route cycle hours / number of deployed vessels
wait     = 0.5 * headway
```

A shipment loads only onto a vessel whose next segment equals the booking's
departure segment index, so departures on a given segment are separated by
exactly one headway and `0.5 * headway` is the expected wait. The path cost is
the sum of edge costs plus one boarding wait per service route used.

The chain is chosen by Dijkstra over `(port, service route)` states, so a route
change is priced correctly. Consecutive edges on the same route are forbidden;
this is lossless because the candidate set already contains the direct edge for
every ordered pair of distinct ports on a route, and it guarantees one booking
per route.

Guards, all fail-closed to `None` (organizer fallback):

- only newly generated cargo (`associated_bookings` empty and
  `current_booking_index is None`);
- only nominal service routes (`source_service_route is None`) with at least
  one deployed vessel, so a booking can never be orphaned when the organizer
  restores an alternative route's vessel at recovery;
- ports whose every berth is unavailable are excluded as an edge's arrival or
  intermediate port, read from live `berth.is_available`;
- congested legs are usable at their true `sailing_time_multiplier` cost, but
  only when a congestion-free path also exists. If the only path traverses a
  congested leg, the strategy delegates so the organizer's protective wait
  still applies;
- any malformed, non-finite, ambiguous, or incomplete runtime data delegates.

Bookings are constructed only after the whole path is validated, then appended
in one pass, so no partial chain can be left behind.

## What this replaces

The v1 one-transfer port-closure hold and the inherited multi-transfer
recovery hold are both removed. They exist to avoid a bad detour chosen by the
default; when the strategy chooses the detour itself the predicate is
redundant, and keeping both would confound the experiment. The `False` (hold)
outcome survives only through delegation in the guarded cases above.

## Compliance boundary

No organizer model, event logic, or scoring code is changed. Cargo moves only
through normal bookings, vessels, berths, and cargo handling; nothing is
completed early or teleported. `maritime_data_context` is already an allowlisted
submission import and supplies `Booking`. The strategy is deterministic
(no randomness, no wall clock, no iteration over unordered containers, integer
tie-breaks only), read-only apart from the booking chain the interface requires
it to create, performs no I/O, and keeps no cross-call state.

## Control and acceptance

- accepted control loss: `35.1039547178493` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 35.1039547178493 - 1e-9
```

Equality, worsening, invalid output, crash, or a failed final gate is
rejection. On rejection the candidate code and tests are reverted, the accepted
control is synchronized, and its pinned ATT is restored and re-scored.
