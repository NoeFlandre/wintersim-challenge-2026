# v29 — a ride is charged for the calls at both of its ends

## Where this came from

Seven candidates in a row had been rejected, and none of the remaining ideas
had a mechanism behind them. Rather than guess an eighth, this iteration built
the measurement that had been named but never made: a read-only instrumentation
of the organizer's three shipment activities that timestamps every entry and
exit, so a realized transport time can be split into the phases that make it up.

### Measurement 1 — where the time is

Round 2, 360 measured days, our arm (v23) against a do-nothing arm, TEU-weighted
days per completed TEU:

| phase | do-nothing | v23 | delta |
|---|---|---|---|
| aboard a vessel | 12.803 | 12.578 | −0.226 |
| waiting at the origin port | 4.424 | 3.855 | −0.569 |
| waiting at a transshipment port | 2.468 | 1.712 | −0.756 |
| **total** | **20.281** | **18.753** | **−1.528** |

Time aboard is 69% of the realized transport time and is the term we had moved
least. Everything the strategy had been tuning — boarding waits, transfers —
is the other 31%.

### Measurement 2 — calibrating the cost model against reality

A second instrumented run recorded, for every boarding, the realized wait and
the headway the strategy charges for it; and for every ride, the realized time
aboard against the nominal sailing time of its bookings.

Boardings are priced about right, and there is no origin-versus-transshipment
asymmetry to exploit:

| boarding | realized | charged headway | ratio |
|---|---|---|---|
| at the origin port | 98.3 h | 113.3 h | 0.868 |
| at a transshipment port | 94.5 h | 118.2 h | 0.799 |

Rides are not. Grouping every ride by how many legs it spans and subtracting
the nominal sailing time leaves an excess that is almost exactly linear in the
number of **port calls**, counting both of the ride's own ends:

| legs | realized | nominal sailing | excess | excess / (legs + 1) |
|---|---|---|---|---|
| 1 | 116.2 | 104.5 | 11.6 | 5.8 |
| 2 | 171.2 | 153.4 | 17.8 | 5.9 |
| 3 | 253.3 | 230.5 | 22.8 | 5.7 |
| 4 | 376.0 | 348.3 | 27.7 | 5.5 |
| 5 | 435.1 | 398.7 | 36.4 | 6.1 |
| 6 | 436.6 | 395.4 | 41.2 | 5.9 |
| 7 | 599.2 | 549.4 | 49.8 | 6.2 |

So a port call costs a riding shipment about **6.0 h** — the organizer's fixed
3 h of berthing, plus roughly 2.3 h of cargo handling at the network's loads,
plus a little queueing — and a ride waits through **legs + 1** of them, because
it begins when loading starts at the boarding call and ends when discharge
finishes at the landing call.

The cost model charged `3 h x (legs - 1)`: the calls in between only, the two
end calls free.

## The defect

Riding through a hub keeps one call there. Transferring at that hub turns it
into two: a discharge call off the first vessel and a loading call onto the
second. Under the old arithmetic the model saw the opposite — riding through
paid 3 h for the intermediate call and transferring paid nothing — so a
transfer looked **3 h cheaper** than riding through when it is in truth about
**6 h dearer**. A nine-hour error, in the wrong direction, on every transfer
decision the strategy makes.

## The change

One term. `hours = sailing + _BERTHING_HOURS * (step + 1)` in `_route_edges`,
and the matching walk in `_edge_arrival` now charges a call before the first
leg and after the last one instead of only between legs.

No new constant: the per-call charge stays the organizer's own 3 h berthing
time. The measurement says 6 h is closer, but 3 h is the half of it that is a
published constant rather than a property of this scenario's cargo volumes, and
it already corrects the sign of the transfer term. Deliberately conservative.

## Precommitted acceptance rule

Frozen before the run. ACCEPT only if **all** hold:

1. Round 2 Cumulative Resilience Loss `< 4.844560541925512 - 1e-9`. Equality is
   a rejection.
2. `unbooked == 0` on every arm.
3. No held-out arm is worse than its do-nothing (v16) arm.
4. `brief` and `undisrupted` stay within tolerance of their v16 arms.

Otherwise REJECT and restore v23.

## Result — REJECTED

| arm | v23 | v29 | change |
|---|---|---|---|
| **Round 2 (scored)** | `4.844560541925512` | `4.844560541925512` | **exact tie**, 0/72 periods changed |
| `shifted` | `41.625698` | `41.625619` | `-0.0002%` |
| `twin` | `40.129877` | `40.129877` | exact tie |
| `inserted` | `15.534240` | `16.810051` | **`+8.21%`**, and `+0.33%` worse than doing nothing (`16.7550`) |

`unbooked == 0` on every arm. The Round 2 ATT file is byte-identical to the
control (`c5243b5e5716a907...`).

Rule 1 fails on the equality alone. Rule 3 fails as well: `inserted` is now
worse than its do-nothing arm. Rejected, and v23 restored.

## Why it was inert where it mattered and harmful where it was not

Round 2 did not move a single period. The reason is a magnitude the
measurement could have told me before the run, and I did not check: boarding a
service costs a **full headway, about 113 h**, while the call term in dispute
is **3 h** — under 3% of it. Hop count is decided almost entirely by the
headway, so shifting the per-transfer term by 6 h flips a chain only where two
candidates sit within 6 h of each other, and in Round 2 that never happened.

Where it did flip choices — `inserted`, whose closed port forces the search to
weigh genuinely close alternatives — the flips were harmful, badly enough to
drop below doing nothing. A term too small to help on the graded scenario is
still large enough to hurt on a scenario whose margins are tight. That is the
worst shape a change can have, and it is an argument for a strict
no-regression gate, not against it.

## What the measurement is worth anyway

The two instrumented runs are the durable result of this iteration, and they
bound the search rather than extend it. Per completed TEU under v23:

* **11.75 d is nominal sailing distance.** Rides average 193.0 h of nominal
  sailing and shipments average 1.46 rides.
* **12.58 d is time aboard.** So time aboard is **94% irreducible sailing**;
  the whole port-call and queueing residual inside it is about 0.8 d.
* **3.86 d is waiting at the origin, 1.71 d waiting at transfers.** Both are
  priced at roughly the right magnitude already: realized over charged is
  `0.868` at the origin and `0.799` at a transfer, with no asymmetry between
  them worth exploiting.

Total `18.75 d` = `11.75` sailing + `5.57` waiting + `~1.4` port calls. The
sailing term is set by the network's distances and the waiting term by the
published headways. Neither is something a booking strategy can bargain with;
it can only avoid spending more of them than it must, which the accepted policy
already does to within a fraction of a day of the do-nothing arm on a calm
network.
