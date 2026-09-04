# Round 2: keep the fleet on its rotations (v16)

**Status: ACCEPTED — complete. It improves Round 2 by `5.65%`, regresses
neither held-out scenario, and strands no cargo anywhere.**

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

## Full-run result

One authoritative run completed all 72 periods in `00:18:28`, with the ATT
proved fresh against the pinned stale mtime `1788516612935704258`.

- candidate ATT SHA-256: `beace437a6c0d55bce87d35b38bfcfe25c897aa7749e17fc3425a2fa7e1de885`;
- **candidate cumulative resilience loss: `9.762649496857325`**;
- accepted v15 control loss: `10.347110679813037`;
- difference: `-0.584461182955712` (`-5.6485448067737565%`);
- periods better/equal/worse: `34 / 22 / 16`.

```text
9.762649496857325 < 10.347110679813037 - 1e-9
```

is true, so the Round 2 rule is met. This is the first result under `10`.

Mean ATT actually rises slightly, from `14.3053` to `14.3251` days, while the
loss falls. That is the metric behaving as defined rather than an inconsistency:
a period contributes `(1 - baseline / ATT) * days`, whose derivative in ATT is
`baseline / ATT^2`, so an hour saved in a good period is worth more than an
hour lost in a bad one. The same effect is why mean ATT was abandoned as a
ranking statistic after v11.

### The mechanism, confirmed in the output

Service-route utilisation from this run contains **no alternative routes at
all**, and the affected services have their full fleets back:

| route | v15 avg capacity TEU | v16 avg capacity TEU |
| --- | --- | --- |
| S4 Transpacific-South | `43,355` | **`50,919`** |
| S5 Asia-US-East | `104,964` | **`115,161`** |
| S4-ALT-1 | `12,945` (carrying `2` TEU) | absent |
| S5-ALT-1 | `12,971` (carrying `0` TEU) | absent |

### By window

| window | periods | v15 | v16 | delta |
| --- | --- | --- | --- | --- |
| Qingdao->Busan congestion | 6 | `0.8436` | `-1.1689` | `-2.0124` |
| no active disruption | 33 | `5.8592` | `3.9546` | `-1.9046` |
| Piraeus closure | 4 | `0.3711` | `-0.3479` | `-0.7191` |
| Tianjin closure | 3 | `0.8200` | `0.4714` | `-0.3486` |
| Colombo->New Jersey congestion | 13 | `-0.8973` | `-0.8973` | `+0.0000` |
| Shanghai->Kaohsiung congestion | 13 | `3.3504` | `7.7506` | `+4.4002` |

## Held-out results

| held-out scenario | v15 | v16 | delta | unbooked |
| --- | --- | --- | --- | --- |
| `shifted` | `42.6642` | `42.6642` | `0.0000` | `0` |
| `mild` | `5.3684` | `5.3634` | `-0.0050` (`-0.09%`) | `0` |

The `shifted` tie is the important one, because that scenario was the stated
risk: it shuts the Singapore hub on which five of the nine services depend, and
suppressing avoiding routes removes the only way the organizer's own booking
logic can serve a pair with no undisrupted nominal path. **No cargo was
stranded** — `unbooked` is `0`, and the same `385,405` shipments complete as
under the control. The risk did not materialise, which is consistent with v12
having already stopped treating closed ports as walls: nominal paths exist
through them at the cost of waiting for the reopening, so the avoiding routes
were not carrying anything the strategy needed.

## Why it is accepted

- the Round 2 gain is `5.65%`, the largest since v12;
- neither held-out scenario regresses and one improves;
- no arm strands cargo, which was a required gate rather than an afterthought;
- the reasoning rests on two structural facts with no constants — one vessel on
  a longer loop cannot offer a competitive headway, and a service that gives up
  a vessel loses a proportionate share of its departures — and both get worse,
  not better, on services with fewer vessels;
- the decision creates, moves, and modifies nothing, and the organizer's own
  validator passes after it.

## Post-acceptance verification

- `uv lock --check`, locked sync, Ruff format and lint, mypy, ty: clean;
- 284 non-integration tests, `91.22%` branch coverage (gate `90%`);
- 7 real-context integration tests, including one asserting the organizer's
  validator accepts the decision, that route, vessel and per-route deployment
  counts are unchanged, that no vessel carries a pending assignment and no
  alternative route exists, and that the fallback on an identical context does
  build routes and does reserve a vessel;
- participant and runtime `user_strategy.py` byte-identical at
  `603435e065e2cff7853412a917da83f314a73b384b42899ac3e50a8ff28157f8`;
- Round 2 smoke: `smoke: OK`;
- deterministic participant-only package, twice, SHA-256
  `57b0d12cb3a271f3989c1ef457b7e2f6f4cac6566b0add8ca970b7aada175ef1`;
- restricted-material scan clean; clean Git working tree.
