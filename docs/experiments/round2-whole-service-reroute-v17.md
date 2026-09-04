# Round 2: reroute a whole service around a slowdown (v17)

**Status: REJECTED on the held-out generalisation rule, before the
authoritative run. Its diagnosis was right and its rule was incomplete; v18
adds the missing term.**

## Where the loss is

v16 scores `9.762649496857325`. Its per-period loss, bucketed by which
disruption is active:

| window | periods | loss | share |
| --- | --- | --- | --- |
| Shanghai-Kaohsiung congestion | 13 | `7.7506` | `79.4%` |
| no disruption active | 33 | `3.9546` | `40.5%` |
| Tianjin closed | 3 | `0.4714` | `4.8%` |
| Piraeus closed | 4 | `-0.3479` | `-3.6%` |
| Colombo-New Jersey congestion | 13 | `-0.8973` | `-9.2%` |
| Qingdao-Busan congestion | 6 | `-1.1689` | `-12.0%` |

Four of the five disruption windows are now *better* than the undisrupted
baseline. Nearly four fifths of what is left sits in one 60-day window, where
the loss ramps monotonically (`0.139` at period 29 to `1.2523` at period 38)
and then collapses within a single period once the slowdown lifts.

## What is actually ageing there

A diagnostic run of v16 classified every unfinished shipment at measured days
139 and 185. Evidence: `.challenge/round2/shakao_diag/out.json`.

| measured day | waiting TEU | in-transit TEU | in-transit TEU-hours |
| --- | --- | --- | --- |
| 139 | `8,884` | `16,394` | `5.56M` |
| 185 | `7,515` | `21,826` | `11.83M` |

Cargo waiting at ports *falls*; cargo at sea grows by a third and its
TEU-hours more than double. Nothing is stranded (`0` unbooked throughout). The
backlog is cargo that has been loaded and is sailing the long way round.

That is a direct consequence of the network's shape. `S4` is
`Shanghai -> Kaohsiung -> Los Angeles`, and the slowdown sits on its first
leg, so every Shanghai-to-America booking either eats a `5x` leg or leaves the
service. The strategy's own cost model, priced over all 380 demands with the
slowdown active and again with nothing active, shows what it does instead:

| OD | annual TEU | calm chain | congested chain | extra |
| --- | --- | --- | --- | --- |
| Shanghai -> Los Angeles | `6,393` | `S4` direct | `S2` + `S9` | `+3.10 d` |
| Singapore -> Los Angeles | `2,948` | `S1` + `S4` | `S1` + `S2` + `S9` | `+2.90 d` |
| Los Angeles -> Kaohsiung | `1,296` | `S4` direct | `S9` + `S2` | `+4.63 d` |

Single-booking rides become two- and three-booking chains through Busan.

## The move the fleet is not allowed to make

The organizer's own fallback already knows the answer. Asked for an
alternative during this window it builds

```
S4-ALT-1: Shanghai -> Shenzhen -> Kaohsiung -> Los Angeles -> Shanghai
```

which avoids the slowed leg for `+467` nm — a `26.66`-day cycle against `S4`'s
`25.69`-day nominal cycle and `30.11` days at the speeds now in force. Every
port `S4` calls is still called, in the same order.

The fallback then reserves **one** of `S4`'s four vessels onto it
(`_reserve_one_vessel_for_alternative_route` returns after the first). That is
the worst of both worlds: the surviving `S4` rotation still crawls through the
slowdown *and* has lost a quarter of its frequency, while the new rotation runs
a single vessel and so offers a headway of its whole cycle. v16 measured that
trade and refused it, which was right — and left the good rotation unused.

Nothing in `validate_alternative_route_strategy_result` limits a new route to
one vessel. It requires only that new routes are built from existing legs, form
a connected cycle with consecutive segment indexes, and deploy vessels that
came from a pre-existing route. Moving a whole service is a legal, intended use
of the hook.

## Exact participant delta

`create_alternative_service_routes` stops being a no-op and implements one
rule:

> Move an entire service onto a detour around a slowdown when the detour still
> calls every port the rotation calls and its cycle is strictly shorter than
> the rotation's cycle at the speeds now in force. Never abandon a port because
> it is temporarily shut.

Concretely, per call:

1. Read the live slowdown set: every leg whose `sailing_time_multiplier`
   exceeds `1`. A route with a closed port anywhere on its rotation is left
   alone entirely — v12 established that a closure is a wait, not a reason to
   drop a port, and v16 measured that leaving the fleet alone beats diverting
   it in both closure windows.
2. For each nominal route with at least one slowed leg, build the detoured
   rotation: replace each slowed segment `A -> B` by the fastest path
   `A -> ... -> B` over legs that are neither slowed nor touching a shut port,
   and keep every other segment as it is. Inserting ports can only add calls,
   so the "calls every port" condition holds by construction.
3. Qualify the detour iff its cycle hours are strictly below the rotation's
   cycle hours at the multipliers now in force. Both sums use the route's own
   mean vessel speed, so the comparison is a pure statement about the service.
4. Create at most one such route per source route, from the existing `Leg`
   objects, and reserve **every** vessel of the source route onto it. Vessels
   switch one at a time, under the organizer's own safety condition: only a
   vessel carrying nothing, standing at the new rotation's start port, ever
   moves. No cargo is teleported and no shipment is completed artificially.
5. Restore the fleet to its source rotation once the detour no longer
   qualifies **and** no unfinished shipment still holds a booking on it. The
   second half of that condition is what makes the change safe: a rotation is
   never withdrawn from under cargo that is still counting on it.
6. The bookable network now includes a qualifying detour rotation. It has to:
   with the whole fleet on it, refusing to book it would leave the strategy
   routing cargo around a service it had just improved. A detour that has
   stopped qualifying is excluded from new bookings, which is what drains it.

The hook returns `True` on every path, including every unreadable-state path,
so the degenerate behaviour is exactly v16's.

## Why this should generalise rather than overfit

The rule names no port, leg, route, scenario or threshold. Its two conditions
are a structural one (the detour serves the same ports) and a quantitative one
read from runtime state (the detour's cycle is shorter). On a network with no
detour worth taking it does nothing and reproduces v16 exactly; on a scenario
whose slowdown sits somewhere else entirely it applies the same test to
whatever route is affected. The constants involved are the organizer's own:
the three-hour berthing time already used since v9, and the multipliers and
distances the model publishes.

It also removes a special case rather than adding one. Since v9 the strategy
has refused to book any route with a `source_service_route`, a blanket rule
whose stated reason was that such routes carry a single vessel and are
withdrawn under their cargo. Both halves of that reason are now addressed
directly — the fleet is whole, and withdrawal waits for the cargo — so the
blanket rule is replaced by the honest headway the cost model already computes.

## Control and acceptance

- accepted control loss: `9.762649496857325` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `beace437a6c0d55bce87d35b38bfcfe25c897aa7749e17fc3425a2fa7e1de885`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 9.762649496857325 - 1e-9
```

Equality, worsening, invalid output, a crash, or a failed gate is rejection.
Acceptance additionally requires the held-out scenarios not to regress
(`shifted` control `42.6642`, `mild` control `5.3634`) and `unbooked == 0` on
every arm.

## Held-out result and decision

Both held-out scenarios were run for a 140-day warm-up plus 300 measured days,
seed as recorded in the harness, and scored with the organizer baseline
supplying the period weights. Evidence:
`.challenge/round2/results/audit_20260903/v17_{shifted,mild}.json`.

| held-out scenario | v16 loss | v17 loss | delta | unbooked |
| --- | --- | --- | --- | --- |
| `shifted` | `42.6642` | `41.6257` | `-1.0385` (`-2.43%`) | `0` |
| `mild` | `5.3634` | `7.3809` | `+2.0175` (`+37.62%`) | `0` |

The `mild` regression triggers the precommitted rule on its own, so v17 is
**rejected** and the authoritative run was not spent on it.

## Why it failed, and what the split shows

The two verdicts disagree in a way that names the missing term exactly.

`shifted` slows legs for `45`, `40` and `30` days; `mild` for `30` and `25`
days. The rotations they hit have cycles of `24.65` to `52.31` days. So on
`shifted` at least one affected service can complete a rotation change and
still have most of the slowdown left to benefit from, while on `mild` the
slowdown that reaches `S4` lasts `25` days against `S4`'s `25.69`-day cycle.

A rotation change is not free. Vessels move one at a time and only when empty,
so the changeover takes about one turn of the rotation — and it is paid twice,
once out and once back. The per-period `mild` deltas show precisely that: the
regression is not in the disruption window at all. It appears at measured day
`201` — twenty-six days *after* the last slowed leg recovers — and runs at
`+0.1` to `+0.2` per period until day `290`, which is the fleet still coming
home while the rotation it is leaving serves its remaining cargo with what is
left of the fleet.

`0` unbooked on both arms confirms the cost is not stranded cargo: the
never-leave-a-rotation-without-vessels rule held. The cost is the changeover
itself.

## Lessons

1. **A rotation change has a transition cost of about one cycle, paid twice.**
   Any rule that moves a fleet must compare the slowdown's *remaining life*
   against that cost. v17 compared only the two cycle lengths, which is the
   steady-state comparison and answers the wrong question.
2. **Two held-out scenarios that disagree are worth more than two that
   agree.** A single regression says "reject"; a split says *why*. The
   difference between `shifted` and `mild` is disruption duration against
   rotation cycle, and that ratio is exactly the term the rule was missing.
3. **Look at where a held-out regression lands in time, not just its size.**
   The `mild` loss sat entirely outside the disruption window, which ruled out
   every explanation involving the detour's quality and pointed at the
   changeover.
