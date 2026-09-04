# Round 2: a fleet moves to escape a disruption, never to come home (v22)

**Status: REJECTED on Round 2 by its own precommitted rule. It found the
residual defect, which is not the transition at all.**

## What v20 and v21 established

v20 scores `4.912139391692661`, with `91%` of the remaining loss in periods
where nothing is disrupted, and `1.2764` of it in the ten weeks after the
Shanghai-Kaohsiung leg recovers. v21 tested whether that tail was the leftover
cargo on a detour being served by its last vessel; it was not, and starving the
detour made the tail `+0.68` worse. What is left is the **transition itself**:
when a slowdown lifts, the whole fleet changes rotation again, and the cargo in
flight pays for it.

## The measurement that decides it

Each detour, against the rotation it replaces:

| detour | nominal cycle | detour cycle | penalty |
| --- | --- | --- | --- |
| `S5-UALT-1` | `52.31 d` | `52.43 d` | `+0.2%` |
| `S4-UALT-1` | `25.69 d` | `26.66 d` | `+3.8%` |

Coming home buys back `0.12` and `0.97` days of cycle time. Spread over the
cargo that rides those services, that is worth a few hundredths of a day of
mean transport time; the changeover that buys it costs `1.2764` of loss. A
few-percent cycle saving repays only over dozens of turns, while a changeover
is paid all at once by the cargo currently at sea.

## Exact participant delta

Absent a reason to change, a service's target rotation becomes the rotation it
is **already running**, rather than always its nominal loop:

> A fleet moves to escape a live disruption. It never moves merely to shorten
> its loop.

An incumbent detour is kept unless one of two things is true, each of which is
a live disruption justifying a move:

1. it calls a port that is shut — v19's rule, unchanged: go home and wait it
   out there;
2. the multipliers in force are hurting it **more** than they hurt the nominal
   loop. The comparison is between *disruption burdens* — stretched distance
   minus plain distance — not between total cycle lengths. That is the whole
   trick: a burden is zero on any undisrupted rotation whatever its length, so
   with nothing disrupted the incumbent always stays, while a slowdown landing
   on the detour sends the fleet home.

Everything else is v20's, untouched: how a detour is built, the
calls-every-port requirement, the closed-port exclusions, the changeover gate
that decides whether to leave in the first place, the empty-vessel-only
movement, and the never-strand rule.

## Why this should generalise rather than overfit

Comparing burdens rather than lengths is what makes the rule scale-free. It
does not care whether a detour is `0.2%` or `3.8%` longer, and it introduces no
threshold to separate "worth returning for" from "not worth returning for" —
the answer is always "not worth returning for", because only a disruption can
justify a changeover, and a disruption is exactly what a burden measures.

It is also the mirror of the rule that got the fleet out. v18 asked whether a
slowdown would outlast the changeover before moving; v22 asks the same question
on the way back, finds no disruption to justify it, and stays.

## Predictions, fixed before the runs

- Round 2: periods `41-56` improve by most of their `1.2764`; the remaining
  periods pay a `3.8%` longer `S4` loop and a `0.2%` longer `S5` loop. Net
  expected better by roughly `0.6` to `1.3`; a regression rejects.
- `brief`, `mild`, `undisrupted`: **exact ties**, since no detour is ever built
  on them and the rule is unreachable.
- `inserted`, `long`, `twin`, `shifted`: may move either way; none may regress
  against its do-nothing arm.

## Acceptance

- Round 2: `candidate_loss < 4.912139391692661 - 1e-9`;
- `brief` `6.767487342693513`, `undisrupted` `-5.030822520503106`, `mild`
  `5.363436801272705`: exact ties;
- `shifted` no worse than `41.62569844636167`, `long` no worse than
  `77.65274459580378`, `twin` no worse than `40.12987734887265`, `inserted` no
  worse than its do-nothing arm `16.754999739073277`;
- `unbooked == 0` on every arm.

## Result and decision

Authoritative run, 72 periods, `Simulation completed.`

- candidate ATT SHA-256:
  `3ff7ca4b43d52c2eecdcab36c80abdf4818a748f1e9558ae8a2dc450c943a8b5`;
- **candidate loss `13.632583218221225`** against the accepted
  `4.912139391692661`: `+8.720443826528562` (`+177.53%`, worse);
- periods better/equal/worse: `15 / 24 / 33`;
- `inserted` held-out arm `16.48955958688245`, still inside its do-nothing arm
  `16.7550` but worse than v20's `16.1746`.

`candidate_loss < 4.912139391692661 - 1e-9` fails, so the candidate is
**rejected**.

## Why it failed

| window | v20 | v22 | delta |
| --- | --- | --- | --- |
| Shanghai-Kaohsiung congestion | `0.0129` | `-0.4034` | `-0.4163` |
| Piraeus closed | `0.4558` | `0.3876` | `-0.0682` |
| Colombo-New Jersey congestion | `-0.7061` | `-0.7061` | `0.0000` |
| Qingdao-Busan congestion | `0.2719` | `0.5936` | `+0.3218` |
| Tianjin closed | `0.4102` | `2.7666` | `+2.3565` |
| no disruption active | `4.4675` | `10.9941` | `+6.5266` |

The premise was right and the conclusion was wrong. Not coming home **did**
help the window it was aimed at — the Shanghai-Kaohsiung window went from
`0.0129` to `-0.4034`, better than the undisrupted baseline. The `+6.53` that
buries it is somewhere else entirely, and the run's own route statistics say
what it is:

| route | avg capacity TEU | avg carried TEU |
| --- | --- | --- |
| `S4` | `24,999` | `611` |
| `S4-UALT-1` | `43,610` | `993` |
| `S5` | `30,597` | `554` |
| `S5-UALT-1` | `94,941` | `1,952` |

Both services ran **permanently split** between two rotations for the whole
run. The never-strand rule holds a rotation's last vessel until no unfinished
shipment still holds a booking on it, and a single vessel on a 26-day loop
serves its remaining cargo so slowly that the condition never clears. Two thin
half-services are far worse than one whole service on either rotation, and
`33` undisrupted periods paid `+6.53` for it.

## The residual defect this exposes

The accepted policy has the same disease, in the mirror image. v20's own route
statistics:

| route | avg capacity TEU | avg carried TEU |
| --- | --- | --- |
| `S4` | `42,972` | `1,097` |
| `S4-UALT-1` | `13,389` | `109` |
| `S5` | `94,717` | `2,030` |
| `S5-UALT-1` | `22,768` | `332` |

After the fleets come home, each detour keeps roughly one vessel — `24%` and
`19%` of its service's capacity — parked on a rotation nobody books any more,
carrying `109` and `332` TEU. That is about **two of the fleet's 41 vessels
idle for most of the run**, and it is the `1.2764` that periods `41-56` carry.
It is permanent, not a transient.

So the residual is not the transition. It is the **parked last vessel**.

## Why it is hard, stated precisely

The vessel is held because cargo is still booked on the rotation, and that
cargo cannot be moved:

- cargo **aboard** a vessel can be replanned, through
  `adjust_bookings_before_cargo_handling`;
- cargo **waiting at a port** for a booking on that rotation cannot. No hook
  is called for it: `assign_associated_bookings` fires once, when the shipment
  is generated, and nothing revisits an already-booked shipment at rest.

So letting the last vessel go would strand that cargo outright, which is the
one outcome worse than a parked vessel. The waiting stock for a rotation is
about one headway's worth of arrivals, which would clear on its own — but
cargo whose *later* legs are booked on the rotation keeps arriving for weeks,
and that is the tail that keeps the vessel there.

Any real fix therefore has to stop multi-leg chains from being written onto a
rotation that will be withdrawn before the cargo reaches it. v21 tried the
blunt version of that — refuse rides that outlive the rotation — and lost
`1.68` inside the window because it also refused the rides the detour exists
for. The narrower version, refusing only a *non-first* booking on a temporary
rotation, is untried and is the next thing to measure.

## Lessons

36. **A split fleet is much worse than either rotation.** `33` undisrupted
    periods cost `+6.53` for running two half-services. Vessel-reassignment
    policies should be judged on whether the fleet ends up whole, not on which
    rotation it ends up on.
37. **The premise can be right and the conclusion still wrong.** Not coming
    home genuinely improved the target window. It lost on a side effect in
    periods that had no disruption at all — which only window attribution
    showed.
38. **Read the route statistics, not just the ATT.** `Avg Capacity TEU` split
    across a route and its detour is what identified both v22's failure and the
    residual defect in the accepted policy. The scalar loss showed neither.
