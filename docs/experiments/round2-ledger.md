# Round 2 experiment ledger

One row per controlled Round 2 experiment. Lower cumulative resilience loss is
better. Every score is the full 72-period result of exactly one authoritative
run (140-day warm-up, 360 measured days, five-day periods, seed `2026`,
`PYTHONHASHSEED=0`, scenario `create_with_disruption`) scored against the
authoritative baseline ATT
`1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`.

| # | Behavioural delta | Activation | Loss | vs incumbent | Periods B/E/W | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| ctl | Round 1 v3 multi-transfer recovery hold, synchronized fresh into Round 2 | 31 holds | `35.50366097019303` | — | — | control |
| v1 | + hold port-closure-only one-change detours when the recovery margin exceeds one full safe-route headway | +254 holds (285) | `35.1039547178493` | `-0.3997` (`-1.126%`) | 11/57/4 | **accepted** |
| v2 | v1 threshold relaxed to half a headway | +76 holds (337) | `35.6743500877092` | `+0.5704` (`+1.625%`) | 8/57/7 | rejected |
| v3 | v1 threshold relaxed to three quarters of a headway | +26 holds (287) | `35.535225309642755` | `+0.4313` (`+1.229%`) | 8/57/7 | rejected |
| v4 | v1 restricted to late-recovery windows (drops early holds) | fewer holds | `35.8691309610454` | `+0.7652` (`+2.180%`) | 4/59/9 | rejected |
| v5 | berth hook: prefer a vessel pending an alternative route during closures | 14 selections | `35.1039547178493` | `0.0000` (tie) | 0/72/0 | rejected (equality) |
| v6 | v1 holds dropped below the third-quartile annual-TEU threshold | 285 to 168 holds | `35.84344929789106` | `+0.7395` (`+2.107%`) | 10/59/3 | rejected |
| v7 | v1 plus upper-quartile-TEU half-headway holds | +39 holds (324) | `35.41374495066942` | `+0.3098` (`+0.882%`) | — | rejected |
| v8 | delegate lower-quartile pure-leg multi-transfer holds | — | design only | — | — | never run |
| v9 | **architecture change:** build the booking chain from estimated transport time instead of delegating to the organizer's distance-based shortest path | 66,070 chains where the incumbent delegated; 285 former holds now booked | `20.248013560766417` | `-14.8559` (`-42.320%`) | 50/0/22 | **accepted** |
| v10 | charge a full headway per boarding instead of half, the correction derived from the measured per-boarding residual | every chain re-costed; transfers priced twice as dearly relative to sailing | `14.897068731156086` | `-5.3509` (`-26.427%`) | 54/2/16 | **accepted** |
| v11 | read the first boarding wait from live vessel positions instead of the headway statistic | every first boarding re-costed | `18.3386705330832` | `+3.4416` (`+23.103%`) | 30/0/42 | rejected (also failed held-out) |
| v12 | treat a port closure as temporary: charge the wait until it reopens instead of deleting the port, and book cargo bound for one rather than holding it | 17 of 72 periods change; congestion windows untouched | `13.27493539992092` | `-1.6221` (`-10.889%`) | 15/55/2 | **accepted** (held-out `-10.32%`) |
| v13 | keep an in-transit chain when it already beats the best alternative, instead of letting the organizer rebuild it by distance | fires on Round 2; inert on the held-out scenario | `11.915883436787134` | `-1.3591` (`-10.238%`) | 19/32/21 | **accepted** (held-out exact tie) |

## Lessons carried forward

1. **The hold predicate is exhausted.** Relaxing the v1 margin (v2, v3, v7) and
   tightening it (v4, v6) both lose. v1 sits at a local optimum worth about
   `1.1%` of the objective, and the whole family only ever moves 15 of 72
   periods.
2. **Berth selection is inert here.** v5 changed 14 selections and produced a
   byte-identical ATT. The control run confirms why: an average of `0.11`
   vessels wait for a berth, so berth priority cannot matter.
3. **Structural activation counts do not predict score.** v2 added 76 holds and
   v7 added 39; both lost. v6 removed 117 and lost. Only the 72-period score
   decides.
4. **Backlog is what the metric punishes.** ATT counts every unfinished
   shipment's age at each period end, so a hold that does not pay off is
   charged in every period it spans. That is the mechanism behind v2/v3/v7:
   marginal-margin holds accumulate age faster than they save transit time.
5. **The loss was never where the experiments were looking.** Per-period
   attribution of the control run puts `47.7%` of the loss in the
   Shanghai-Kaohsiung congestion window and `38.3%` in periods with no active
   disruption. The two port closures, which are the only place the v1-v7 family
   could act, hold `5.8%` between them. Attribute the objective before
   choosing where to intervene.
6. **Capacity is not a constraint.** Service-route utilisation runs `0.88%` to
   `6.12%`. Transport time is dominated by sailing time plus waiting for the
   next departure, so re-routing cargo between services has no meaningful
   congestion cost — and choosing services by distance, which ignores departure
   frequency, leaves real time on the table. This is the observation v9 acts on.

## After v13

The incumbent is `11.915883436787134`, `66.05%` below the `35.1039547178493`
that started the round.

7. **Measure the model against the simulation, then correct the mechanism.**
   v10 was a one-line change worth `-5.35`. It came from pairing each
   shipment's estimate with its realized transit time, finding a residual that
   scaled with boardings rather than with shipments, and matching its size to
   half the mean headway. Its per-window result then confirmed all three of its
   predictions, including recovering `-1.7830` of exactly the periods v9 had
   lost and repairing the Piraeus window without a closure-specific rule. This
   is the cheapest lever found so far per unit of effort.
8. **Resist coefficient search.** The residual admits both a proportional and a
   constant-per-boarding fit, neither decisive, with most variance OD-specific.
   `1.0` was taken because it is the mechanism value, not because it scored
   best; no sweep was run.

9. **Check the mechanism before building the fix.** The natural explanation
   for v10's late-run excursion was that vessels stuck at a closed port make
   the headway statistic lie. The run's own statistics refuted it: vessels
   waiting for a berth never exceed `0.22` on average while waiting cargo
   climbs steadily. A plausible-sounding correction would have addressed a
   cause that is not present.

Open questions are attributed with evidence in
[`round2-remaining-loss-attribution.md`](round2-remaining-loss-attribution.md):
`9.7485` of the remaining `14.897` sits in periods with no active disruption,
`0` unfinished shipments are unbooked, `69%` of aged backlog is already in
transit, and no OD pair exceeds `2.2%` of it. The two widest remaining levers
are reading the next departure from live vessel state instead of estimating it,
and taking over in-transit replanning.

## Generalisation protocol, added at v11

From v11 onward a candidate must also beat the incumbent on a **held-out
scenario** it was never developed against, built from the organizer's own
baseline builder and disruption helpers: the `shifted` scenario closes
**Singapore** and **Rotterdam** and congests `Singapore->Colombo`,
`Busan->Los Angeles` and `Rotterdam->Tanger Med`, with different durations and
multipliers from Round 2. Both arms share the scenario and seed, so the
organizer baseline supplies the weights and cumulative loss ranks them
directly.

The protocol has already changed two decisions:

10. **It rejected v11 on independent evidence** before the authoritative run
    finished, and the authoritative run agreed.
11. **Rank by the metric, never by mean ATT.** v11 improved mean ATT on both
    held-out scenarios while making one *worse* on cumulative loss. The
    objective weights a period by `baseline / ATT^2`, so it cares more about a
    shipment-hour lost in a good period than in a bad one, and a candidate that
    wins big on a few bad periods while losing a little on many good ones looks
    good on an average and bad on the score.
12. **Held-out runs must outlast their disruption windows.** v11's `r2_seed7`
    comparison ran 150 measured days, stopped before the Shanghai-Kaohsiung
    window where most of the incumbent's advantage accrues, and wrongly
    favoured the candidate. v12's held-out runs use 300 measured days.
13. **Watch when an effect can show up at all.** Booking cargo instead of
    holding it cannot move ATT while the cargo is unfinished, because ATT
    charges its age either way; it moves ATT when the cargo completes. v12's
    Piraeus window shows no change while the four periods after it do.

14. **A one-sided change can be banked on a tie.** v13's held-out ATT was
    byte-identical to its control. That is not absence of evidence but
    evidence of harmlessness, because the hook cannot mutate anything and can
    only decline a change; where it does not fire, behaviour is exactly the
    incumbent's. A change that could mutate state would not earn the same
    benefit of the doubt.
15. **Count why a rule declines, not just how often it fires.** v13's tie was
    fully explained by counting delegate reasons: affected shipments cluster
    at roughly 174 per vessel call, so its per-vessel all-or-nothing rule let a
    single un-costable shipment veto the whole call. The same counters showed
    its yardstick was wrong: costing the alternative optimistically flips
    keep-versus-rebuild from `5.3:1` for keeping to `4:1` against it.
