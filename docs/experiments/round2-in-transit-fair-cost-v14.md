# Round 2: cost the in-transit alternative fairly (v14)

**Status: DESIGN — frozen before the authoritative run.**

## Hypothesis

v13 was accepted with two limitations that its own diagnostic counters
measured rather than guessed
([report](round2-in-transit-keep-veto-v13.md)). This experiment fixes the one
that is a modelling error, and leaves the structural one alone.

**The wrong yardstick.** v13 costs the alternative to staying aboard
*optimistically*, with no wait to board it. That was meant as caution, but it
is simply wrong: leaving the service the cargo is riding really does mean
waiting for the next one. Measured against that too-cheap yardstick, rebuilding
looked preferable `4:1` on Round 2, whereas measured against what the organizer
actually does, keeping was preferable `5.3:1`. v13 therefore hands back most of
the harmful rebuilds it was built to prevent.

**A requirement copied from the wrong decision.** v13 refuses to decide unless
a congestion-free path exists from the current port. That guard belongs to the
*booking* decision, where committing fresh cargo to a leg with no way round is
a real choice. Cargo already at sea has no such choice, and the guard fired
`5,142` times on the held-out scenario across only `68` qualifying vessel
calls — which, combined with v13's per-vessel all-or-nothing rule, is the
complete explanation for v13 being inert there.

## Exact participant delta

Two changes inside `_keep_booked_chains`, nothing else:

1. The congestion-free-path requirement is removed. Whatever alternative exists
   is costed and compared on its merits.
2. The alternative is charged the wait to board its first service, unless that
   service is the route the cargo is already riding — which is precisely the
   case the organizer's own merge handles without a transfer.

A destination with no alternative at all now counts as "keep", because the
organizer's rebuild would find none either and would leave the chain alone.

Everything else is untouched: the hook still never mutates a booking, route,
vessel, or berth; it still only ever *declines* a change; and it still
delegates on anything uncertain, including a chain riding a
disruption-alternative route, which this model does not carry and which the
organizer may withdraw at recovery.

## Why this should generalise better than v13

The change is a correction toward the truth, not a tuning step: the wait to
board a different service is real, and pretending otherwise made the comparison
wrong in a fixed direction. Removing the congestion-free requirement deletes a
condition that has no meaning for cargo already at sea, and it is exactly the
condition measured to be blocking the held-out scenario — so unlike v13 this
candidate should actually fire there and can be judged on evidence rather than
on inertness.

The one-sided safety property is unchanged and is what bounds the downside.

## Control and acceptance

- accepted control loss: `11.915883436787134` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `1313f8b970b4dd46db306d0b8501bc1b79ddaecf048b21324f97121b46e655c3`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 11.915883436787134 - 1e-9
```

Acceptance additionally requires no regression on the held-out `shifted`
scenario over 300 measured days, where the accepted control scores `42.6751`.
Unlike v13, an exact tie there would now be a warning rather than a pass, since
the condition that made v13 inert has been removed and the candidate is
expected to fire.
