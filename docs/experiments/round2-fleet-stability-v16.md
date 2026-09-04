# Round 2: keep the fleet on its rotations (v16)

**Status: DESIGN — frozen before the authoritative run.**

## Hypothesis

`create_alternative_service_routes` is the last decision point of any
consequence still delegated. The organizer's fallback answers a disruption by
building an avoiding route from existing legs and **reserving one vessel from
each affected service onto it**.

For a strategy that routes cargo by transport time, that trade is a bad one in
both directions:

- the affected service loses a share of its departures. A route with `n`
  vessels has headway `cycle / n`; at `n - 1` it becomes `cycle / (n - 1)`.
  S4 runs four vessels, so losing one costs `33%` of its frequency; S2 runs
  two, so losing one would double its headway;
- the new route runs a **single** vessel around a longer loop, so its own
  headway is its whole cycle. This strategy already declines to book such
  routes, precisely because one vessel is not a useful service.

So the reservation removes capacity from the rotations the cargo actually uses
and parks it somewhere the cargo will never board.

## The measurement

Service-route utilisation from the accepted v15 run:

| route | avg capacity TEU | avg carried TEU | utilisation |
| --- | --- | --- | --- |
| S4 Transpacific-South | `43,355` | `1,172` | `2.70%` |
| **S4-ALT-1** (built by the fallback) | `12,945` | **`2`** | `0.02%` |
| S5 Asia-US-East | `104,964` | `2,282` | `2.17%` |
| **S5-ALT-1** (built by the fallback) | `12,971` | **`0`** | `0.00%` |

Two vessels, roughly `26,000` TEU of capacity, spend their disruption windows
carrying `2` TEU and `0` TEU. Comparing S4 against the original v1 control run,
where the same fallback ran, its average capacity falls from `47,074` to
`43,355` — one Neo-Panamax's worth — and S5 falls from `115,104` to `104,964`.

## Exact participant delta

`UserStrategy.create_alternative_service_routes` returns a decision instead of
`None`, for every call and every context. That suppresses the fallback, so no
avoiding route is built and no vessel is reserved away from its service.

Nothing is created, moved, or modified. The organizer validates this hook after
**every** call, including one that returns a decision, and a real-context test
asserts that the validator passes, that route and vessel counts are unchanged,
that every route's deployed-vessel count is unchanged, that no vessel carries a
pending assignment, and that no alternative route exists — while the fallback,
given an identical context, does build routes and does reserve a vessel.

Because the decision is taken from the first call onward, no vessel is ever
switched to an alternative route, so there is never a vessel needing to be
restored to its source route at recovery. The hazard the fallback's own
restoration logic exists to handle cannot arise.

## The risk, stated plainly

The fallback's avoiding routes are the only way the *organizer's* booking logic
can serve an origin-destination pair that has no undisrupted nominal path. This
strategy books nominal routes only, so it never needed them — but when it
delegates a booking, the fallback may now find no path at all and hold the
cargo at its origin.

That risk is much smaller than it was before v12: closed ports are no longer
treated as walls, so nominal paths exist through them at the cost of waiting
for the reopening. The held-out `shifted` scenario, which closes the Singapore
hub that five of the nine services depend on, is the sharpest available test of
exactly this failure mode, and it is a required gate below.

## Why this should generalise

The reasoning contains no constant and nothing specific to Round 2's
disruptions. It follows from two structural facts that hold in any scenario:
one vessel on a longer loop cannot offer a competitive headway, and a service
that gives up a vessel loses a proportionate share of its departures. Both get
worse, not better, on services with few vessels.

## Control and acceptance

- accepted control loss: `10.347110679813037` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `a2084e82fc9badbd13542b9ebab183cfcdc8978da8a00d1065b807bd341bf4c6`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 10.347110679813037 - 1e-9
```

Acceptance additionally requires no regression on either held-out scenario,
where the accepted control scores `42.6642` on `shifted` and `5.3684` on
`mild`, and requires that no arm strand cargo — `unbooked` must stay `0`.
