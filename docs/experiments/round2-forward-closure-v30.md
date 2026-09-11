# v30 — price a closure the ride will meet, not only one already in force

## Where this came from

v29's measurement showed that time aboard is `94%` irreducible sailing, which
left the disruption response as the only place with headroom. So this iteration
asked a question nobody had asked in 29 experiments: **where in the 360 days
does the surviving loss actually sit?**

Scoring the accepted run period by period against the organizer baseline:

| periods | days | loss |
| --- | --- | --- |
| 1–50 | 1–250 | **`-0.48`** |
| 51–72 | 251–360 | **`+5.33`** |

The first 250 days — which carry all three congestion windows — are *net
better than the undisrupted baseline*. The entire score is the last 110 days.
And within them the profile rises steadily to a peak at days 291–315 (`+1.8 d`
over baseline), collapses at day 321, then climbs again to the end.

A do-nothing arm on the same scenario has the same shape, twice as large
(`+10.43` over the same tail, `34.57` overall). So the tail is the scenario's,
not something the policy creates — but half of it is still unclaimed.

The two disruptions in that stretch are **port closures**: Piraeus shut on
measured days 260–274, Tianjin on 320–327. The peaks trail each closure by
roughly one Asia–Europe transit, which is what a delayed cohort of cargo looks
like when ATT is credited at completion.

## The defect

`_closure_recovery` selects plans with `start <= now < end`. A closure that has
not started yet is invisible to the booking cost model. So cargo booked in the
fortnight before a closure is costed as though the port were open, boards a
chain that calls there, and then sits until it reopens — the whole wait, paid
in full, having been priced at zero.

This is the same defect v12 fixed for the *other* direction. v12 stopped the
model from treating a shut port as permanently gone; it did not teach it that
an open port can shut.

## The change

A new `_closure_windows` reads the same published `disruption_plans` that v12,
v15 and v20 already read, and returns every closure window **not yet over** as
`(hours until it shuts, hours until it reopens)` pairs per port. `_route_edges`
carries those windows on each timeline step in place of the single "hours until
this port reopens" scalar, and `_edge_arrival` pushes the clock to the end of
whichever window the call lands inside — a window already in force being just
the special case whose `shuts` is `0`.

The epoch guard is strengthened to match: the plans are trusted only when they
reproduce the live berth state exactly — every port shut now has a window
covering `now`, and every window covering `now` belongs to a port that is shut.
A different simulation epoch fails that test and degrades to v12's behaviour
rather than charging waits at the wrong times.

### Sizing the term first (lesson 54)

The wait being priced is up to `14 days = 336 h` for Piraeus and `7 days` for
Tianjin, against a boarding headway of about `113 h`. Two to three headways:
easily enough to move a chain, unlike v29's `3 h`.

## Precommitted acceptance rule

Frozen before the run. ACCEPT only if **all** hold:

1. Round 2 Cumulative Resilience Loss `< 4.844560541925512 - 1e-9`. Equality is
   a rejection.
2. `unbooked == 0` on every arm.
3. No held-out arm is worse than its do-nothing (v16) arm.
4. `inserted`, whose scenario carries a closure inserted mid-slowdown, must not
   regress against v23's `15.534240`.

Otherwise REJECT and restore v23.

## Result — REJECTED

| arm | v23 | v30 | change |
|---|---|---|---|
| **Round 2 (scored)** | `4.844560541925512` | `5.226163836397828` | **`+7.88%`** (3 better / 52 equal / 17 worse) |
| `inserted` | `15.534240` | `17.910337` | `+15.30%`, and `+6.9%` worse than doing nothing |
| `shifted` | `41.625698` | `44.514572` | `+6.94%`, and `+4.3%` worse than doing nothing |
| `twin` | `40.129877` | `40.129877` | exact tie (no closure in that scenario) |

`unbooked == 0` everywhere. Rule 1 fails; rules 3 and 4 fail as well.
Rejected, and v23 restored.

## Where it went wrong, period by period

The change is precisely targeted — and that is what makes the diagnosis clean:

| periods | days | v23 | v30 |
|---|---|---|---|
| 1–50 | 1–250 | `-0.4779` | `-0.4779` (bit-identical) |
| 51–72 | 251–360 | `+5.3224` | `+5.7040` |

Nothing moves until period 53, days 261–265, which is exactly when Piraeus
shuts. From there every period to the end changes, and 15 of 17 get worse.
Only two improve, and the larger of the two is period 65, days 321–325 —
Tianjin's window, the one case where the closure being priced starts within a
few days of the booking.

## Why pricing a forecast loses where pricing a state wins

v12 charges the wait for a closure **in force**, and was worth `-10.89%`. v30
charges the wait for a closure **still ahead**, and costs `+7.88%`. Same
arithmetic, same plans, opposite sign — because the two quantities are not
equally knowable.

For a closure in force, the input is a fact: the port is shut and the plan says
when it reopens. The quantity shrinks as the closure runs, and an arrival
estimate that is wrong by days barely changes the answer, because the wait is
charged to *whatever* arrives before the reopening.

For a closure still ahead, the input is a prediction: will this ride arrive
inside a window that opens in a fortnight? The arrival estimate carries a
boarding wait of about `113 h` and a vessel position that random-walks about
four days over a rotation, so the error on that prediction is comparable to the
`14-day` window itself. Every wrong "yes" pays a detour for a closure the cargo
would have missed anyway, and the detour is charged in full while the avoided
wait was never going to be paid.

This is the third time the same shape has lost. v11 took a minimum over noisy
per-vessel estimates and lost `+23%`; v28 took a convex function of noisy
phases and lost `+131%`; v30 takes a threshold decision on a noisy arrival time
and loses `+7.9%`. Minimum, convex functional, indicator — all three are
non-linear in an input whose error is as large as the effect being estimated.

## What this closes

The closure lever is now measured from both sides and is exhausted: pricing the
closures in force is worth keeping, pricing the ones ahead is not. Together
with v29's finding that time aboard is `94%` irreducible sailing and that both
boarding waits are already priced within `13-20%` of what is realized, and with
the period profile showing the first 250 days already net better than the
undisrupted baseline, the accepted policy sits close to the floor of what these
four hooks can reach on this network.
