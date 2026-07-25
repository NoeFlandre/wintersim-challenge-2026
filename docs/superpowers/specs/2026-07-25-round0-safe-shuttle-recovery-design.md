# Round 0 Safe-Shuttle Recovery Design

## Objective

Run one controlled Round 0 experiment that attempts to reduce the
current-checkout fallback Cumulative Resilience Loss of
`18.673577819840556`. The candidate must remain valid for undisclosed
scenarios and seeds, preserve organizer simulation integrity, and modify only
the participant-owned `response_strategies` submission surface.

## Evidence and motivation

Round 0 closes Kaohsiung for 14 measured days and simultaneously multiplies
three sailing legs for 18-20 days. The current fallback's loss is concentrated
well after those plans end:

- Days 1-60: `0.071518`
- Days 61-80: `0.042706`
- Days 81-100: `0.405949`
- Days 101-140: `3.315449`
- Days 141-180: `5.578522`
- Days 181-220: `4.184662`

The long tail is consistent with vessels beginning long, multiplied sailings
and remaining unavailable after the disruption ends. The organizer's default
alternative-route builder requires a disruption-avoiding cycle through all
non-closed anchor ports of an affected source route. If one anchor is not
reachable in the safe graph, it creates no route for that source route.

A read-only baseline trace also showed that berth-priority experimentation has
very little leverage: the congestion gate called the participant berth hook
only twice through measured day 100. A completion-rate rule would change one
choice, but that choice would send a vessel toward a five-times-slower leg.
The strategy therefore targets vessel-route continuity instead of berth
sequencing or another global cargo-routing rewrite.

## Candidate policy

Only `UserStrategy.create_alternative_service_routes` changes behavior. The
other three hooks return `None` unconditionally.

The hook first invokes the organizer's `DefaultStrategy` for the same call.
This preserves its restoration, cleanup, ordinary alternative-route creation,
and pending-vessel behavior. The participant hook then adds a recovery shuttle
only for an affected original service route that still has no usable
alternative route for the active disruption key.

The hook returns `True` after invoking the organizer default itself, preventing
the call site from invoking it a second time.

### Active disruption model

An active plan satisfies:

```text
start = datetime.min + timedelta(days=start_offset_days)
end = start + timedelta(days=duration_days)
start <= now < end
```

The safe directed leg graph excludes:

- every leg targeted by an active plan with `multiplier > 1`;
- every leg whose departure or arrival port has an actively closed berth.

Duplicate berth plans for the same port collapse naturally to one excluded
port identity. Leg and port identity, not names, determine membership.

### Recovery-shuttle construction

For each affected original route without a usable organizer alternative:

1. Read its segments in `sequence_index` order.
2. Collect unique safe departure-port anchors in source-route order.
3. Partition those anchors by mutual reachability in the safe directed graph.
4. Select the component containing the most source-route anchors. Ties use the
   earliest anchor in source-route order.
5. Require at least two anchors.
6. Choose the first safe port immediately upstream of a disrupted source-route
   segment as the shuttle start when it belongs to the chosen component;
   otherwise use the component's earliest source-route anchor.
7. Rotate the component's source order to that start.
8. Connect each consecutive anchor, including the final return to the first,
   with a deterministic shortest-distance path over safe existing legs.
9. Reject the candidate before mutation if any connection is missing, if the
   concatenated route is empty, or if it does not form a connected cycle.
10. Create one `ServiceRoute` and consecutive `Segment` objects, using only
    organizer-provided entity classes and existing legs. Mark
    `source_service_route` and `disruption_key` so organizer cleanup can restore
    vessels after recovery.

No source route, existing leg, existing segment, shipment, or booking is
modified.

### Vessel transfer

At most one vessel is deployed to a recovery shuttle.

The strategy only switches the `vessel` supplied to the hook when all of these
conditions hold:

- it is assigned to the shuttle's source route;
- it has no carried shipments;
- it is currently at the shuttle start port after cargo handling;
- neither an assigned nor pending vessel already serves that shuttle.

The switch removes the vessel from its old route and current segment
collections, adds it to the shuttle's `deployed_vessels`, sets the assigned
route to the shuttle, clears pending assignment, and sets `current_segment` to
`None`. This matches the organizer's route-switch representation and is
validated by its `strategy_validation` checks.

The strategy does not reserve an arbitrary vessel in advance. This avoids
pinning a vessel that cannot reach the safe switch point during the disruption.

## Determinism and runtime constraints

- Standard library plus organizer-provided
  `response_strategies.default_strategy` and `maritime_data_context` classes.
- No filesystem, environment, network, subprocess, current-working-directory,
  wall-clock, or random access.
- No mutable module-level or cross-run state.
- No hardcoded port names, route IDs, disruption dates, durations, multipliers,
  or tuned thresholds.
- Context list order and strict-less-than shortest-path updates define all
  ties.
- The strategy is observational until a complete route has been constructed.

## Failure behavior

Expected malformed or incomplete organizer-shaped inputs cause the extension
to skip that source route after the organizer default has already handled the
call. No broad `except Exception` or `except BaseException` is permitted.

The custom route is fully planned before context mutation. Entity constructors
run before any append. Appending the already-constructed route and segments is
then deterministic and covered by synthetic and real-context tests.

## Test design

Strict red-green-refactor TDD will cover:

- exact four-hook signatures and three unconditional delegates;
- active interval boundaries;
- safe-graph exclusion of closed ports and congested legs;
- deterministic shortest paths and tie handling;
- largest mutually reachable source-anchor component selection;
- start-port choice immediately upstream of disruption;
- no route when fewer than two safe mutually reachable anchors exist;
- only existing legs and consecutive segment indexes;
- idempotence for repeated calls with the same disruption key;
- no arbitrary vessel reservation;
- switching exactly one eligible empty vessel at the start port;
- refusing loaded, misplaced, foreign-route, or duplicate vessels;
- no mutable global state and no forbidden imports or I/O;
- organizer validation against the real ignored Round 0 context.

## Controlled experiment

Configuration is fixed before observing the candidate result:

- Scenario: `create_with_disruption`
- Seed: `2026`
- Warm-up: `140` days
- Measured duration: `360` days
- Statistics interval: `5` days
- Required period count: `72`
- Acceptance: candidate score `< 18.673577819840556 - 1e-9`
- Historical secondary reference: `18.276620672293834`

Exactly one candidate policy is authorized. There is no parameter tuning or
second strategy.

If accepted, retain the implementation and evidence. If rejected or equal,
commit the result record, revert the implementation commit with `git revert`,
synchronize the restored no-op strategy, restore the SHA-pinned fallback ATT
snapshot, and rerun final gates.

Raw organizer data and outputs remain under ignored `.challenge/` and
`experiments/results/` paths. No push, merge, PR, submission, or history
rewrite is part of this experiment.
