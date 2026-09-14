# v32 — close a rotation up around a shut port, using only its own legs

## What eleven rejections taught, applied

Every rejected candidate since v23 failed in one of two ways, and both are
avoidable by construction:

* **Acting on something not yet known.** v11 (noisy phases), v28 (a convex
  function of them), v30 and v31 (a closure that has not started). Four
  rejections, all for pricing a forecast.
* **A term too small to decide anything.** v29's `3 h` against a `113 h`
  headway; inert where it should have helped and harmful where margins were
  tight.

v32 is built to fail neither test. It fires only on a port that **is shut
right now** — the same fact v12 already reads off the live berths — and the
quantity it changes is enormous rather than marginal.

## The finding

The score is entirely in the last 110 days, which are the echo of two port
closures, and the accepted policy explicitly declines to do anything about
them: *"A shut port is never routed around."* That rule was written for
*detours* — sailing the service through ports it does not serve — and the
measurement says the bypasses really are terrible:

| service | nominal cycle | cycle avoiding Piraeus via any legs |
|---|---|---|
| S1 | `44.72 d` | `70.82 d` (via New Jersey — far worse) |

But S1 is not the only service at Piraeus. **S7 turns there**:
`Singapore → Colombo → Jebel Ali → Piraeus → Jebel Ali → Colombo`. Delete the
shut port and the rotation closes up on its **own legs** —
`Singapore → Colombo → Jebel Ali → Colombo` — with no port added:

| | cycle | headway on 5 vessels |
|---|---|---|
| S7 nominal | `28.18 d` | `5.64 d` |
| S7 with Piraeus closed up | **`13.60 d`** | **`2.72 d`** |

Less than half. And Jebel Ali is served by S7 alone, which is why
`Rotterdam→Jebel Ali`, `Shenzhen→Jebel Ali`, `Hamburg→Jebel Ali`,
`Shanghai→Jebel Ali`, `Jebel Ali→Shanghai` and `Jebel Ali→Los Angeles` are all
in the top ten of standing backlog — about `7%` of the whole metric. Today all
five S7 vessels keep sailing into a closed port and freeze there; the port
statistics show `36 vessel-days` of queueing at Piraeus, `20%` of the
S1+S7 fleet over the fourteen days of the closure.

## The change

A new pass in `_service_targets`, gated on a port being shut now:

1. `_excised_legs` deletes every shut port from a rotation and reconnects it
   **using only that rotation's own legs**. If they do not close up, nothing is
   built. A port that was an out-and-back turn simply disappears.
2. The result must be a strictly shorter cycle, and it calls no shut port, so
   the existing `_rotation_beats` test applies unchanged.
3. **A shut port is never dropped by the last service calling it**, so cargo
   bound there keeps a rotation to be booked on and waits the closure out.
4. When the port reopens it is no longer shut, the pass does not fire, and the
   service's target reverts to its full rotation. The existing drain machinery
   walks the vessels home.

There is no changeover gate, and deliberately so. v18 needed one because a
detour is a *repositioning*: the vessel has to get to a rotation that may be
somewhere else. An excision is a **subsequence** — the vessel joins and leaves
at a port both rotations call, so the changeover is a skipped call and costs
nothing. Enforcing "only the rotation's own legs" is what makes that true, and
it is enforced in code, not assumed.

No new constant anywhere.

## Sizing it first (lessons 54 and 65)

The accepted run is `1.35%` of ATT above baseline — `4.5 hours`. This change
halves a service's cycle for a fortnight. It is the first candidate since v23
whose magnitude is unambiguously larger than the target rather than comparable
to it.

## Generalization

Six of the eight held-out scenarios close a port, across seven different ports.
By hand-check the rule fires on `shifted` (S7 drops a shut Singapore),
`brief` and `r2_seed7` (S7 drops Piraeus) and is inert on `long`, `mild`,
`inserted`, `twin` and `undisrupted`, because in those the rotations' own legs
do not close up. That is the behaviour wanted: it acts only where the network
really offers a shorter cycle.

`brief` is the sharpest test — an `8-day` closure against a `13.60 d` stub
cycle, so if a changeover cost exists after all, it shows up there.

## Precommitted acceptance rule

Frozen before the run. ACCEPT only if **all** hold:

1. Round 2 Cumulative Resilience Loss `< 4.844560541925512 - 1e-9`. Equality is
   a rejection.
2. `unbooked == 0` on every arm.
3. No held-out arm is worse than its do-nothing (v16) arm.
4. No held-out arm regresses against v23: `shifted` `41.625698`,
   `brief` `6.767487`, `inserted` `15.534240`, `twin` `40.129877`.

Otherwise REJECT and restore v23.

## Result — REJECTED

| arm | v23 | v32 | change |
|---|---|---|---|
| **Round 2 (scored)** | `4.844560541925512` | `5.846536658227643` | **`+20.68%`** (5 better / 52 equal / 15 worse) |
| `brief` | `6.767487` | `8.036186` | `+18.75%`, and the same against doing nothing |
| `shifted` | `41.625698` | `44.981163` | `+8.06%`, and `+5.4%` worse than doing nothing |
| `inserted` | `15.534240` | `15.534240` | **exact tie** |

`unbooked == 0` everywhere. Rules 1, 3 and 4 all fail. Rejected, and v23
restored. This is the worst candidate since v28.

## What was right, and what was wrong

The mechanics were right in every detail that could be checked in advance. The
rule fired exactly where the hand-analysis said it would and nowhere else —
`S7-UALT-1` built at Piraeus on Round 2 and `brief`, Singapore on `shifted`,
and `inserted` bit-identical because no rotation there closes up. The
organizer's own `validate_alternative_route_strategy_result` accepted the new
rotation every time. The cycle really does halve, `28.18 d → 13.60 d`, and the
service really does stop freezing vessels at a shut port.

And it made things `20%` worse.

The reason is not the changeover, which is what I had braced for. `brief` was
picked as the sharpest test because its `8-day` closure is shorter than the
`13.60 d` stub cycle, so the fleet cannot complete a turn before coming back —
and it was indeed the worst arm. But Round 2's closure is `14 days`, which
*does* outlast the stub, and Round 2 lost `+20.68%` anyway. **A v18-style
changeover gate would not have saved this**; the threshold is not what is
wrong.

What is wrong is the thing being dropped. S7 is the only service joining the
Gulf and the Eastern Mediterranean to Asia. Closing its rotation up around
Piraeus buys a shorter cycle for Singapore–Colombo–Jebel Ali and pays for it by
severing Piraeus from S7 entirely for a fortnight, forcing that traffic onto
S1's much longer path. The frequency gained on the stub is worth less than the
connection lost — and the loss lands on exactly the cargo the closure already
hurts most.

That is v12's rule, arrived at from the other direction: **a closure is a wait,
and waiting it out is cheaper than routing around it** — whether the routing is
done by the booking model (v30, v31) or by the fleet (v32).

## Sizing does not predict sign

v29 was rejected for being a `3 h` term against a `113 h` headway: too small to
decide anything. v32 was built to be the opposite — it halves a service's cycle
for two weeks, unambiguously the largest lever found all round — and it is the
worst result of the eleven. Magnitude was never the binding constraint. Every
candidate since v23 has had the right size and the wrong sign.
