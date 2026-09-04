# Round 2: keep an in-transit chain that already wins (v13)

**Status: DESIGN — frozen before the authoritative run.**

## Hypothesis

`adjust_bookings_before_cargo_handling` is the only in-transit replanning
decision point and is the last hook still fully delegated. The organizer's
implementation carries all three defects that the accepted experiments already
fixed at the origin:

1. it rebuilds the remaining journey by **sailing distance**;
2. it **refuses** the disrupted ports and legs outright instead of pricing
   them, which v12 showed is wrong for a closure that will lift;
3. when the rebuild does not start on the route the cargo is already riding,
   the current booking is **shortened to end at the current port**, so the
   cargo is discharged there and waits for another service.

Cargo already at sea is `69%` of the aged backlog measured at day 305, so this
is the widest untried lever.

## Measurement first

v11 was a plausible story that lost, so this was measured before it was built.
A private diagnostic copy of the organizer tree ran the accepted v12 strategy
unchanged over a 140-day warm-up plus 300 measured days, and at every
`adjust_bookings_before_cargo_handling` call recorded what the organizer was
about to do and compared it, using the strategy's own cost model, with simply
staying aboard. It returned `None` throughout, so no decision changed.
Evidence: `.challenge/round2/results/audit_20260903/intransit_stats.json`.

- `4,784` hook calls; `3,832` shipments the organizer would replan, `5,119` TEU;
- a rebuild path existed in every one of those cases;
- the rebuild was **slower than staying aboard in `2,152`** of them and faster
  in `409` — worse `5.3` times more often than better;
- `1,271` could not be costed by the model and are therefore never vetoed;
- TEU-hours lost to the rebuilds: `1,471,346`; gained: `682,413`; **net
  `-788,933` TEU-hours.**

## Exact participant delta

`UserStrategy.adjust_bookings_before_cargo_handling` returns `True` — a
decision to change nothing — only when every carried shipment whose remaining
chain meets an active disruption is at least as well off staying aboard.
Otherwise it returns `None` and the organizer's replan runs exactly as before.
No booking, route, vessel, or berth is ever mutated by this hook.

The comparison reuses the accepted cost model: the remaining chain is walked
from the vessel's current port with closure waits and live congestion
multipliers priced, and the alternative is the model's own fastest path from
that port to the chain's final port.

The alternative is deliberately costed **optimistically**, with no wait to
board its first service, even though a real transfer would pay one. A chain is
therefore kept only when it beats even the most favourable rebuild. Everything
uncertain — a malformed chain, a ride the model cannot cost, a destination with
no congestion-free path, a shipment whose current booking already ends here —
returns `None`, which restores the organizer's behaviour exactly.

## Why this should generalise

The rule adds no constant and no scenario-specific knowledge. It fires only
when the organizer was about to replan, which requires an active disruption, so
it is inert on an undisrupted network. It is one-sided by construction: it can
only ever *decline* a change, so the worst case is the incumbent's behaviour
plus a decision that keeping was good enough. And the defect it exploits is
structural to any scenario — a distance-ranked rebuild that refuses temporary
disruptions will misjudge cargo that is already most of the way there.

## Control and acceptance

- accepted control loss: `13.27493539992092` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `d466899bacfa55c53469bea39879b46a7140e587b981efef1a0b44ad1a983954`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 13.27493539992092 - 1e-9
```

Acceptance additionally requires no regression on the held-out `shifted`
scenario over 300 measured days, where the accepted control scores `42.6751`.
Held-out candidates are ranked by cumulative loss, never mean ATT.
