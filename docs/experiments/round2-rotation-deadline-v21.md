# Round 2: never book cargo onto a rotation that will not outlive the ride (v21)

**Status: REJECTED on Round 2 by its own precommitted rule. It disproved the
hypothesis it was built on, and that is what pointed at v22.**

## Where the remaining loss is

v20 scores `4.912139391692661`. Its remaining loss by window:

| window | periods | loss | share |
| --- | --- | --- | --- |
| no disruption active | 33 | `4.4675` | `90.9%` |
| Piraeus closed | 4 | `0.4558` | `9.3%` |
| Tianjin closed | 3 | `0.4102` | `8.3%` |
| Qingdao-Busan congestion | 6 | `0.2719` | `5.5%` |
| Shanghai-Kaohsiung congestion | 13 | `0.0129` | `0.3%` |
| Colombo-New Jersey congestion | 13 | `-0.7061` | `-14.4%` |

Every disruption window is now at or below the undisrupted baseline, and `91%`
of what is left sits in periods with nothing disrupted at all. Periods `41-56`
— the ten weeks after the Shanghai-Kaohsiung leg recovers — carry `1.2764` on
their own.

## The mechanism

A detour is the only bookable rotation for its service while the slowdown
lasts, so by the time the slowdown lifts it is carrying about a full pipeline
of cargo. Then the target flips back to the nominal rotation and the fleet
starts coming home. Three of the four vessels leave promptly; the fourth is
held by the never-strand rule until no unfinished shipment still holds a
booking on the detour. That leftover cargo is then served by **one** vessel on
a rotation whose headway is its entire cycle — about `26.7` days for `S4`. The
fleet is split, both halves are thin, and it takes weeks to resolve.

Managing that by moving vessels differently runs into a circularity: the fleet
cannot leave while the cargo is there, and the cargo cannot clear quickly with
one vessel. So the fix is not to manage the pile. It is not to create it.

## Exact participant delta

One condition is added to the path search:

> A ride on a temporary rotation may only be booked if it ends before that
> rotation is due to be withdrawn.

A temporary rotation is withdrawn when the slowdown that justifies it lifts, so
its deadline is the smallest `hours until this multiplier lifts` across its
source rotation's slowed legs — the same epoch-guarded quantity the changeover
gate and v15's costing already use. A slowdown whose end cannot be established
has no deadline, exactly as it is assumed permanent everywhere else. Nominal
rotations have no deadline and are untouched.

The search already computes each ride's arrival time, so the test is a
comparison between two numbers it has in hand. There is no constant.

The effect is to taper the detour's intake: early in a window every ride fits
inside the remaining life and nothing changes, and as the window closes the
long rides stop being offered while the short ones still are. By the time the
slowdown lifts the detour is empty, the whole fleet comes home at once, and
there is no thin-fleet tail.

## Why this should generalise rather than overfit

It is the same sentence as v20's, applied to the cargo instead of the ports: a
rotation is only worth *using* for as long as it will be there. v20 asked
whether a detour could be sailed for as long as it was needed; this asks
whether a ride can be finished before the detour goes away. Both are
feasibility tests read from runtime state, and both refuse rather than
optimise when the answer is no.

It is deliberately conservative in the safe direction. The detour is not
actually withdrawn at the instant the slowdown lifts — it is withdrawn when it
drains — so a ride ending slightly after that instant would in truth have been
fine. Refusing it anyway is what guarantees the drain tail is empty.

## Predictions, fixed before the runs

- Round 2: the two 60-day windows give up a little near their ends, periods
  `41-56` improve by most of their `1.2764`. Net expected better; a regression
  rejects.
- `brief`, `undisrupted`, `mild`: **exact ties**, since no detour is ever built
  on any of them.
- `inserted`, `long`, `twin`, `shifted`: may move either way; none may regress
  against its do-nothing arm.

## Acceptance

- Round 2: `candidate_loss < 4.912139391692661 - 1e-9`;
- `brief` `6.767487342693513`, `undisrupted` `-5.030822520503106` and `mild`
  `5.363436801272705` must be exact ties;
- `shifted` no worse than `41.62569844636167`, `long` no worse than
  `77.65274459580378`, `twin` no worse than `40.12987734887265`, `inserted` no
  worse than its do-nothing arm `16.754999739073277`;
- `unbooked == 0` on every arm.

## Result and decision

Authoritative run, 72 periods, `Simulation completed.`

- candidate ATT SHA-256:
  `b58111922215e55b49ef2bb854e1f0a41caea18a4c25daccd54aad365a256273`;
- **candidate loss `6.5457552167823945`** against the accepted
  `4.912139391692661`: `+1.6336158250897332` (`+33.26%`, worse);
- periods better/equal/worse: `18 / 16 / 38`.

`candidate_loss < 4.912139391692661 - 1e-9` fails, so the candidate is
**rejected** and the held-out arms were not needed.

## Why it failed, and what it disproved

| window | v20 | v21 | delta |
| --- | --- | --- | --- |
| Shanghai-Kaohsiung congestion | `0.0129` | `1.6911` | `+1.6781` |
| Piraeus closed | `0.4558` | `0.7196` | `+0.2638` |
| no disruption active | `4.4675` | `4.5126` | `+0.0452` |
| Colombo-New Jersey congestion | `-0.7061` | `-0.7027` | `+0.0034` |
| Tianjin closed | `0.4102` | `0.2408` | `-0.1693` |
| Qingdao-Busan congestion | `0.2719` | `0.0843` | `-0.1876` |

Two things went wrong, and the second is the interesting one.

The cost is concentrated in the window itself: refusing long rides on the
detour for the last stretch of a slowdown pushes exactly the cargo the detour
exists for back onto the two- and three-booking chains through Busan, and the
detour's value there is very large — the whole `7.7377` that v18 won.

**And it did not fix the tail it was built for.** Periods `41-56` went from
`1.2764` to `1.9605`, `+0.68` *worse*. So the hypothesis was wrong: the
ten-week tail is not the leftover pile being served by one vessel. Starving the
detour just moved the same cargo onto slower chains, and it aged in the same
periods either way. The tail is the cost of the transition in whatever form the
cargo takes it.

That is what makes the transition, not the pile, the thing to remove — and the
cheapest way to remove a transition is not to make it. Hence v22.

## Lessons

34. **A negative result that relocates the cost is more informative than one
    that merely fails.** v21 was supposed to shrink periods `41-56` and made
    them worse, which ruled out the pile as the cause and left the transition
    itself as the only candidate.
35. **The detour's value inside its window is large and fragile.** Any rule
    that reduces how much cargo can use it pays back the `7.74` that building
    it won. Tapering intake is not a cheap lever.
