# Round 2: price a rotation by the vessels staying on it (v26)

**Status: REJECTED — an exact tie. It makes the model self-consistent and
changes no decision.**

## What v25 established

v25 corrected a real category error — the in-transit veto costs the ride cargo
is *on*, so it must see every rotation still sailing, not only the ones open
for new bookings — and scored `+14.39%`. The run said why: with the ride now
costable, the veto **keeps** cargo on a rotation the fleet is abandoning,
because a ride is priced at `cycle / deployed vessels` and a draining rotation
is counted with the fleet it has rather than the one vessel it is about to
have. Delegating had been accidentally right.

So v25 was half a fix. Both halves are needed, and they are the same idea
applied to two places.

## Exact participant delta

1. **Honest headway.** Every rotation is priced by the vessels **staying** on
   it: a vessel whose `pending_assigned_service_route` points at a different
   rotation is leaving as soon as it is empty at a port that one calls, and no
   longer counts towards this one's frequency. A rotation nobody is staying on
   quotes no headway at all and is left out of the network rather than failing
   it.
2. **Two networks, one headway rule.** `_network` gains `bookable_only`. The
   booking hook and the veto's *alternative* use the bookable set exactly as
   before; the veto's *kept* chain is costed over every rotation still crewed,
   including one being left.

The second is v25's change; the first is what makes it honest. Neither adds a
constant, and `bookable_only` defaults to true so no other caller moves.

## Why this should generalise rather than overfit

`deployed_vessels` is a snapshot, and every headway in the model reads it. That
is correct for a stable service and wrong for one mid-changeover — which is
precisely when the veto is consulted most, and precisely where v25 measured the
error at `14%`. Counting only the vessels that are staying is what the quantity
was always meant to be: how often will this service actually depart?

It also removes a fail-closed path that was doing real work for the wrong
reason, and replaces it with one that does the same work for the right one: a
rotation being wound down now prices itself badly, so the veto lets it go on
the merits instead of because the arithmetic failed.

## Predictions, fixed before the runs

- `brief`, `mild`, `undisrupted`: **exact ties**. No detour is built, so no
  vessel is ever reserved away and no rotation is unbookable-but-sailing.
- Round 2, `shifted`, `long`, `twin`, `inserted`: expected better than v23 —
  cargo aboard a draining rotation is judged on a true estimate instead of
  being handed to a distance rebuild. A regression rejects.
- `unbooked` must stay `0`.

## Acceptance

- Round 2: `candidate_loss < 4.844560541925512 - 1e-9`;
- `brief` `6.767487342693513`, `undisrupted` `-5.030822520503106`, `mild`
  `5.363436801272705`: exact ties;
- `shifted` no worse than `41.62569844636167`, `long` no worse than
  `77.65274459580378`, `twin` no worse than `40.12987734887265`, `inserted` no
  worse than `15.534240459359498`;
- `unbooked == 0` on every arm.

## Result and decision

Authoritative run, 72 periods, `Simulation completed.` **Candidate loss
`4.844560541925512`** — a `0.0` delta with all 72 periods equal. The rule
requires a strict improvement, so the candidate is **rejected**.

## Why it ties

This is the satisfying half of v25's story. With the honest headway in place, a
rotation the fleet is leaving prices itself so badly that the veto lets its
cargo go **on the merits** — reaching exactly the outcome v23 reached by
failing closed when the ride could not be costed at all.

The two paths converge on identical behaviour, which is worth knowing: the
fail-closed delegation v25 removed was not an accident of arithmetic after all,
it was the right answer arrived at cheaply. The model is now self-consistent
either way, and self-consistency here buys nothing.

## Lessons

46. **Converging on the incumbent is evidence, not failure.** Two independent
    routes to the same 72 identical periods say the incumbent's behaviour is
    the model's considered answer, not a lucky artefact.
