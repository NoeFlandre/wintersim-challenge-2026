# v31 — charge a closure that is already open when the ride sets off

## Where this came from

Three measurements this round, in order.

**1. The score is the last 110 days.** Scoring the accepted run period by
period against the organizer baseline: periods 1–50 are net `-0.48` — better
than the *undisrupted* baseline — and periods 51–72 are `+5.33`. A do-nothing
arm has the same profile twice as large (`+10.43`, `34.57` overall). The tail
trails each of the two port closures by roughly one transit.

**2. The metric is backlog, not completions.** Splitting the ATT numerator per
period: **65–85% of it is standing backlog**, about `26,000–29,000 TEU` aged
`12–15 days`, and only the remaining 15–35% is cargo completed in the period.
Nothing is ever held unbooked (`0` TEU in every period). Of the backlog,
`66–90%` is at sea — cargo riding its booked chain. In the tail both the
standing backlog (`26.3k → 29.7k`) and its mean age (`13.1 → 14.8 d`) rise
about `11%` together, which is Little's law saying time-in-system rose.

**3. The fleet is not the problem.** Tracing vessel assignments every five
days: `S5` moves onto `S5-UALT-1` for the Colombo–New Jersey slowdown and is
fully home by day 170; `S4` moves onto `S4-UALT-1` for Shanghai–Kaohsiung and
is fully home by day 246. From day 246 to day 360 **every service runs at
nominal strength** — and the tail is elevated anyway.

That leaves the closures themselves, and it sizes the target precisely: the
period-mean ATT is `1.35%` above baseline, which on `14.07 days` is **4.5
hours**. Every remaining lever has to be worth hours, not days.

## The change, and why this shape

v30 charged **every** closure window not yet over to whichever call landed
inside it, and lost `+7.88%`: pricing a fortnight-out window is a threshold on
an arrival time whose error is as wide as the window. But v30's per-period
table had one clear gain — period 65, days 321–325, `-0.123`, the Tianjin
window, the one case where the closure being priced starts within days of the
booking rather than weeks.

v31 keeps exactly that case and drops the rest. `_edge_arrival` charges a
window only when `shuts <= depart_hours`: the closure must already be open at
the moment the ride sets off. A window in force now has `shuts == 0` and is
always charged, so **v12's accepted behaviour is preserved exactly**; a window
that opens after the ride departs is ignored, so **v23's behaviour is preserved
for everything else**. The only new cases are closures that open during the
wait to board, or during the earlier legs of the same chain.

No new constant: the horizon is the model's own departure clock.

`v23 ⊂ v31 ⊂ v30`, by construction.

## Precommitted acceptance rule

Frozen before the run. ACCEPT only if **all** hold:

1. Round 2 Cumulative Resilience Loss `< 4.844560541925512 - 1e-9`. Equality is
   a rejection.
2. `unbooked == 0` on every arm.
3. No held-out arm is worse than its do-nothing (v16) arm.
4. Neither `inserted` (`15.534240`) nor `shifted` (`41.625698`) regresses
   against v23.

Otherwise REJECT and restore v23.

## Result — REJECTED

| arm | v23 | v30 (full lookahead) | v31 (open at departure) |
|---|---|---|---|
| **Round 2 (scored)** | `4.844560541925512` | `5.226164` (`+7.88%`) | `5.151597` (**`+6.34%`**) |
| `inserted` | `15.534240` | `17.910337` (`+15.30%`) | `15.616991` (`+0.53%`) |
| `shifted` | `41.625698` | `44.514572` (`+6.94%`) | `45.027191` (**`+8.17%`**) |
| `twin` | `40.129877` | tie | tie (no closure there) |

`unbooked == 0` everywhere. Round 2: 4 better / 53 equal / 15 worse.
Rule 1 fails; rule 3 fails on `shifted`, which is `+5.5%` worse than its
do-nothing arm; rule 4 fails on both. Rejected, and v23 restored.

## What the narrowing actually did

It behaved as designed and it did not help.

On Round 2 and on `inserted` it recovered much of v30's damage — `inserted`
went from `+15.30%` back to `+0.53%`, which confirms the diagnosis that the
harm in v30 came from long-horizon windows. But it recovered only a fifth of
the Round 2 loss, and on `shifted` the narrowed rule is **worse than the broad
one** (`+8.17%` against `+6.94%`).

That last result is the informative one. If long horizons were simply noisy and
short ones sound, narrowing would improve every arm monotonically. It does not.
Charging some closures and not others splits cargo between two policies that
each make sense on their own, and on `shifted` the mixture is worse than either
pure rule.

## What this closes, for good

The closure lever is now measured at three settings:

| what is priced | Round 2 |
|---|---|
| closures in force only (v12, accepted) | `4.844561` |
| plus those opening before the ride departs (v31) | `5.151597` (`+6.34%`) |
| plus every window not yet over (v30) | `5.226164` (`+7.88%`) |

The accepted setting is not a point on a slope, it is the optimum, and the
penalty rises monotonically with how much forecast is admitted. **Price exactly
what the live berths confirm, and nothing else.** There is no horizon at which
a closure forecast pays, not even one measured in hours.

Taken with this round's measurements — the score is `1.35%` of ATT, about
`4.5 hours`; `65-85%` of the metric is standing backlog and `66-90%` of that is
cargo at sea on its booked chain; nothing is ever held unbooked; both detour
fleets return and the network runs at nominal strength for the last 114 days —
the accepted policy is at a local optimum that these four hooks cannot leave
with the information available to them.
