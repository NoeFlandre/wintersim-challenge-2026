# Round 2: a port closure is temporary, not a wall (v12)

**Status: DESIGN — frozen before the authoritative run.**

## Hypothesis

The accepted v10 policy treats any port whose berths are all unavailable as
permanently unusable: no ride may arrive there or call there on the way, and
cargo bound for it is delegated, which makes the organizer hold it at its
origin. But a closure has an end date, and that date is in
`context.disruption_plans`. Cargo that will not reach the port until after it
reopens loses nothing by being routed through it, and cargo bound for it is
better off sailing now and waiting at the far end than waiting at the origin
and sailing afterwards.

The held-out evidence says this is where the objective is most exposed. On a
structurally different scenario built for
[the v11 experiment](round2-live-departure-phase-v11.md) — congestion on
`Singapore->Colombo`, `Busan->Los Angeles` and `Rotterdam->Tanger Med`, plus
closures at **Singapore** and **Rotterdam** — the accepted v10 policy loses
`24.4653` over 30 measured periods, against roughly `6` over Round 2's first
30. ATT climbs from `13.7` to `24.9` days and stays there for nine periods.
Singapore is the hub of five of the nine services, so shutting it makes almost
every Asia-Europe and Asia-Indian-Ocean chain unroutable under a policy that
treats the closure as a wall, and the cargo simply ages at its origin.

Round 2's own closures are short (14 days at Piraeus, 7 at Tianjin), which is
exactly the regime where the timing matters most: much of the cargo planned
during those windows would arrive after they lift.

## Exact participant delta

1. `_closure_recovery` reads the hours from now until each port whose
   close-berth plan is active reopens.
2. An edge that calls at a shut port is no longer discarded. It carries
   `closed_calls`, the `(hours into the ride when the call happens, hours until
   that port reopens)` pairs, and `_edge_arrival` charges the wait: a call that
   would land before the reopening is held until it, and everything after it
   shifts by the same amount.
3. The path search costs an edge with `_edge_arrival` from the current label
   instead of adding a fixed duration, which makes the cost time-dependent in
   this one respect. The dependence is FIFO — setting off later never arrives
   earlier — so the search remains correct.
4. A closed destination is therefore routable, and cargo bound for one is
   booked rather than delegated.

**With no closure active the arrival reduces to `depart + edge.hours`, exactly
the v10 cost.** The behavioural delta is confined to the windows where a
closure is live, which keeps attribution clean and bounds the risk.

## Guarding the epoch assumption

Plan offsets are relative to the start of the simulation, which this code takes
to be `datetime.min`. Rather than trust that, a reopening time is used only
when the plan arithmetic and the live berth state agree: the port must be shut
according to `berth.is_available` *and* have a close-berth plan that the offset
arithmetic says is active. If a future round starts its clock elsewhere the two
disagree, no reopening time is produced, and the port falls back to being
treated as impassable — the v10 behaviour. A malformed plan, a non-datetime
`now`, and a congested-leg plan all produce no reopening time by the same route.

## Why this should generalise

The change adds no tuned constant. It replaces a categorical assumption that
is simply false — "a shut port is shut forever" — with the duration the model
itself publishes. It is inert on an undisrupted network, inert when closure
timing cannot be established, and its benefit grows with how short the closure
is relative to the transit time, which is a property of any scenario rather
than of this one.

## Control and acceptance

- accepted control loss: `14.897068731156086` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `4f22259de77c2e77477ba21f0f7c36c988ee9c5e80cca425984fe65aa0ad6eb4`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 14.897068731156086 - 1e-9
```

Acceptance additionally requires no regression on the held-out `shifted`
scenario, scored against the organizer baseline over the same periods. Learning
from v11, the held-out runs are extended to 300 measured days so they cover
their disruption windows *and* the recovery tail; v11's misleading held-out
verdict came from a 150-day horizon that stopped before the effects landed.
Held-out candidates are ranked by cumulative loss, never by mean ATT, which
disagreed in sign for v11.
