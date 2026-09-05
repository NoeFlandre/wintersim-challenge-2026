# Round 2: rebuild an in-transit chain by time instead of handing it back (v24)

**Status: REJECTED. Inert on Round 2 and harmful where it did fire — but the
investigation of *why* it was inert found a live defect, which v25 fixes.**

## The gap

v9 established the largest single result of this round: choosing a booking
chain by estimated **transport time** rather than by sailing **distance** is
worth `-42.3%`. Every accepted candidate since has been a refinement of that
cost model.

The in-transit decision does not use it. `adjust_bookings_before_cargo_handling`
compares the booked chain against the best alternative and returns `True` when
keeping wins — but when keeping *loses*, it returns `None`, which hands the
shipment to `DefaultStrategy`, whose rebuild is a shortest-**distance** search.
So precisely when a chain most needs replacing, it is replaced by the policy v9
measured as much worse.

It is worse than that: the hook decides per **vessel**, not per shipment. One
carried shipment that would be better off rebuilt sends *every* shipment on
that vessel to the distance rebuild, including the ones whose chains the model
had just judged best left alone.

## Exact participant delta

When the booked chain loses to the best alternative from the current port, the
strategy now rebuilds that shipment's remaining chain itself, using the path
its own cost model already computed for the comparison, and returns `True`.

The mutation is the organizer's own, step for step: the completed part of the
current booking is retained up to this port; if the first new ride is on the
service the cargo is already aboard, the two are merged into one booking so no
transfer is charged; otherwise the current booking is shortened to end here and
the cargo is discharged to wait; later bookings are replaced, and the route
booking lists are kept consistent. Only the **path** differs — chosen by time,
not by distance.

Two properties are preserved deliberately:

- **Per shipment, not per vessel.** A chain the model judged worth keeping is
  now kept even when another shipment on the same vessel is rebuilt.
- **Mutate last.** Nothing is written until the whole pass has succeeded, so a
  shipment can never be left with a half-written chain — the same discipline
  the booking assignment has used since v9.

Every unreadable-state path still returns `None` before any mutation, so the
degraded behaviour is exactly today's.

## Why this should generalise rather than overfit

It applies the round's best-established result to the one population that was
still excluded from it, and it removes a coupling (per-vessel all-or-nothing)
that has no justification in the model. There is no new constant and no new
concept: the path is the one the veto already computes, and the mutation is the
organizer's.

The change can only fire where the organizer would itself have replanned — the
hook is only consulted for cargo whose remaining chain meets an active
disruption — so on an undisrupted network it is unreachable.

## Predictions, fixed before the runs

- `undisrupted`: **exact tie**; the hook never fires.
- Round 2 and every disrupted scenario: expected better, since the population
  affected is cargo the organizer would otherwise route by distance. A
  regression rejects.
- `unbooked` must stay `0`: a rebuild writes a complete chain or none at all.

## Acceptance

- Round 2: `candidate_loss < 4.844560541925512 - 1e-9`;
- `undisrupted` exact tie at `-5.030822520503106`;
- `shifted` no worse than `41.62569844636167`, `mild` no worse than
  `5.363436801272705`, `long` no worse than `77.65274459580378`, `twin` no
  worse than `40.12987734887265`, `brief` no worse than `6.767487342693513`,
  `inserted` no worse than `15.534240459359498`;
- `unbooked == 0` on every arm.

## Result and decision

Authoritative run, 72 periods, `Simulation completed.`

- candidate ATT SHA-256:
  `c5243b5e5716a90724245ee62c8fedee3fb80cc87e472ca6f68b36a30adacc56` —
  **byte-identical to v23's**, so the loss is `4.844560541925512`, a `0.0`
  delta with all 72 periods equal;
- held-out `inserted`: `18.31966762269539` against v23's
  `15.534240459359498`, `+2.7854` (`+17.93%`, worse).

The rule requires `candidate_loss < 4.844560541925512 - 1e-9`. A tie is a
rejection, and `inserted` regresses badly on top, so the candidate is
**rejected** and the remaining arms were not needed.

## Two findings

**It never fires on Round 2.** The rebuild branch is only reached after the
kept chain has been costed, and on Round 2 the veto returns `None` earlier than
that. So the change is unreachable there, which the byte-identical ATT proves
exactly.

**Where it does fire, it is worse than delegating.** On `inserted` it is
`+17.93%`. Rebuilding whenever the alternative is cheaper by any margin ignores
what the rebuild itself costs: when the new first ride is on a different
service the cargo is discharged here to wait, and the comparison does not
charge that. The organizer's distance rebuild is not good, but it is applied to
the same population by a search that at least does not thrash.

## The defect this exposed

Chasing "why is it unreachable" found something live in the accepted policy.
Since v18 the network is built only from rotations open for **new bookings** —
each service's current target. Once a detour becomes the target, the nominal
rotation leaves the network **while still carrying its whole fleet**:

```text
S4: 4 vessels, S4-UALT-1: 0
bookable routes: S1 S2 S3 S5 S6 S7 S8 S9      <- no S4
keep cost for a ride on S4: None
```

So every shipment aboard the rotation a service is leaving becomes uncostable,
the veto returns `None`, and the organizer rebuilds all of it by distance —
precisely the population v9 measured distance routing as worst for, at
precisely the moment the fleet is mid-changeover.

That is v25.

## Lessons

41. **An inert result is still a result, and "why is it inert?" is the
    question worth asking.** A byte-identical ATT proved the branch was
    unreachable, and finding out why located a live defect that had been in the
    accepted policy since v18.
42. **Replacing a plan has a cost the comparison must carry.** Rebuilding onto
    a different service discharges the cargo to wait; comparing only the two
    journey estimates makes every marginal difference look worth acting on.
