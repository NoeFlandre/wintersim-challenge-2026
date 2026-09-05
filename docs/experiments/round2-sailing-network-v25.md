# Round 2: cost cargo on the rotation it is actually sailing (v25)

**Status: REJECTED on Round 2. The defect it describes is real; the fix is
wrong, and the run explains why.**

## The defect

Since v18 the strategy builds one network, from the rotations open for **new
bookings** — each service's current target. The in-transit veto uses that same
network to answer a different question: *how long will the cargo already aboard
take if nothing changes?*

Those questions do not have the same answer set. When a service moves to a
detour, its nominal rotation stops taking bookings immediately but keeps
sailing, with its whole fleet, until the vessels move across one at a time.
Measured on the real Round 2 context, mid-window:

```text
S4: 4 vessels, S4-UALT-1: 0
bookable routes: S1 S2 S3 S5 S6 S7 S8 S9      <- no S4
keep cost for a ride on S4: None
```

With the ride uncostable the veto returns `None`, and **every shipment aboard
the rotation being left is rebuilt by the organizer's shortest-distance
search** — the policy v9 measured at `-42.3%` against time-based routing — for
the whole duration of a changeover.

## Exact participant delta

`_network` gains one flag, and the veto uses two networks:

- **what may be booked**: rotations that are each service's current target,
  exactly as now. The alternative the veto compares against, and any chain the
  booking hook writes, still come only from here.
- **what is sailing**: every rotation with deployed vessels, including one a
  service is in the middle of leaving. The *kept* chain is costed here.

That is the whole change. No decision rule moves, no constant appears, and the
booking hook is untouched — `bookable_only` defaults to true, so every other
caller behaves exactly as before.

## Why this should generalise rather than overfit

It corrects a category error rather than tuning an outcome: an estimate of what
will happen to cargo already at sea must be taken over the world as it is, not
over the subset the strategy is willing to sell. Any scenario that ever moves a
fleet has the same gap, and the size of it scales with how long changeovers
last.

## Predictions, fixed before the runs

- `brief`, `mild`, `undisrupted`: **exact ties** — no detour is built, so no
  rotation is ever unbookable-but-sailing.
- Round 2, `shifted`, `long`, `twin`, `inserted`: expected better, since cargo
  aboard a draining rotation stops being handed to the distance rebuild. A
  regression rejects.
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

Authoritative run, 72 periods, `Simulation completed.`

- candidate ATT SHA-256:
  `9415549bf607e6a30923087643fa446eb74c135e064bbcc61d86c30f35421e62`;
- **candidate loss `5.541576684632464`** against `4.844560541925512`:
  `+0.6970161427069517` (`+14.39%`, worse);
- periods better/equal/worse: `14 / 30 / 28`;
- held-out `inserted`: `15.534240459359498`, an exact tie.

`candidate_loss < 4.844560541925512 - 1e-9` fails, so the candidate is
**rejected** and the remaining arms were not needed.

## Why it failed

The premise was right: cargo aboard a rotation the fleet is leaving really is
sailing, and refusing to cost it really does hand it to a distance rebuild. But
making it costable makes the veto **keep** those chains, and keeping them is
worse.

The reason is in the headway. A ride is costed at `cycle / deployed vessels`,
and the deployed vessel count of a rotation being drained is the count it has
*now*, not the one it is heading for. Mid-changeover that number is still four;
within days it is one, and the last vessel stays until the rotation drains. So
the model rates a service that is about to collapse as if it were healthy, and
holds cargo on it.

Delegating was accidentally right. The organizer's distance rebuild is a poor
search, but it gets the cargo **off** a rotation the fleet is abandoning, and
that matters more here than the quality of where it goes.

## What would actually be needed

Costing a draining rotation honestly means pricing it with the fleet it will
have, not the fleet it has: its headway should reflect the vessels that are
staying, and the ones already reserved away should not count. That is a real
and self-contained idea, and it is the form this experiment should have taken.
It is not attempted here, because the accepted policy already gets this
population off the rotation and the measured cost of getting it wrong in the
other direction is `+14%`.

## Lessons

43. **A defect being real does not make the obvious fix right.** The network
    split is a genuine category error, and correcting it cost `14%`, because a
    second error - pricing a rotation by the fleet it currently has - was
    cancelling it.
44. **Check what a vessel count will be, not what it is.** Every headway in the
    model reads `deployed_vessels` at the instant of the estimate. That is
    correct for a stable service and wrong for one mid-changeover, which is
    exactly when the veto is consulted most.
45. **Accidentally-right behaviour is still load-bearing.** Removing a
    fail-closed path because it fires "for the wrong reason" removed a
    protection that was doing real work.
