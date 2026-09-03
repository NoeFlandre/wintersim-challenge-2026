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

## After v10

The incumbent is `14.897068731156086`, `57.56%` below the `35.1039547178493`
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

Open questions now:

- the wait is still a statistic. Reading the next departure from live vessel
  positions and segment occupancy would remove the calibration question
  entirely, and it is the natural successor to v10;
- `adjust_bookings_before_cargo_handling` remains fully delegated, so cargo
  already in transit is still replanned by the organizer's distance-based
  search. Nothing has yet been tried there;
- `9.7485` of the remaining `14.897` loss sits in the 33 periods with no active
  disruption, so general routing quality, not disruption response, is still
  where most of the objective lives.
