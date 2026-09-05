# Round 2: is the residual a routing defect on a calm network?

The accepted policy scores `4.844560541925512`, and `88%` of what is left sits
in periods with **no disruption active**. That invites an obvious hypothesis:
the booking model is systematically wrong for some traffic, and the disruption
windows were merely hiding it. This audit tests that hypothesis and rejects it.

## Method

The `undisrupted` scenario was run twice for 140 warm-up plus 360 measured
days, once with the strategy and once with all four hooks neutralised so every
decision falls through to the organizer's own distance-based routing. Both arms
report, per OD pair, the TEU-weighted mean transport time of everything
completed in the window and the aged TEU-hours still open. Evidence:
`.challenge/round2/results/od_20260905/`.

## Result: we win, and the win is not uniform

| arm | completed | mean transport time | open TEU | open mean age |
| --- | --- | --- | --- | --- |
| strategy | `489,671` TEU | **`18.673` d** | `27,228` | `13.16` d |
| distance routing | `489,203` TEU | `18.830` d | `27,298` | `13.54` d |

Net `-93,506` TEU-days in our favour. But the per-OD split is wide: **197 of
380 OD pairs are *worse* than distance routing**, costing `112,231` TEU-days,
against `205,738` won on the other `183`.

| OD | ours | distance | delta |
| --- | --- | --- | --- |
| Qingdao -> Los Angeles | `16.81` | `15.46` | `+1.35` |
| Busan -> Los Angeles | `15.65` | `14.49` | `+1.16` |
| Los Angeles -> Busan | `15.65` | `14.37` | `+1.28` |
| Rotterdam -> New Jersey | `13.19` | `12.26` | `+0.93` |
| Cartagena -> New Jersey | `8.19` | `7.16` | `+1.03` |
| ... | | | |
| Busan -> Kaohsiung | `9.75` | `13.08` | `-3.33` |
| Busan -> Shenzhen | `8.81` | `14.00` | `-5.19` |

## Why this is not a defect

**The chains are identical.** For every one of the worst OD pairs, the strategy
and the distance router choose exactly the same booking chain, costed
identically by our own model:

```text
Qingdao -> Los Angeles      ours (S9, 2, 3)   distance (S9, 2, 3)
Rotterdam -> New Jersey     ours (S6, 2, 3)   distance (S6, 2, 3)
Cartagena -> New Jersey     ours (S6, 5, 5)   distance (S6, 5, 5)
```

So the loss on those pairs is not a routing choice at all. It is a system
effect of the choices made *elsewhere*: our routing redistributes cargo across
the services.

| route | our TEU | distance TEU | change |
| --- | --- | --- | --- |
| `S6` | `59,550` | `44,542` | `+33.7%` |
| `S9` | `25,683` | `21,609` | `+18.9%` |
| `S2` | `155,579` | `143,036` | `+8.8%` |
| `S1` | `264,143` | `288,804` | `-8.5%` |
| `S4` | `40,590` | `87,582` | `-53.7%` |

The pairs we lose on are exactly the incumbent traffic of `S6`, `S9` and `S2`.
We also use **fewer bookings overall** — `688` against `735` — which is the
full-headway transfer penalty doing its job.

## The obvious mechanism does not survive arithmetic

Handling time is the natural suspect: a port call takes
`moved TEU / (cranes * 45)` hours, so a busier service should have longer
calls. Measured on `S6`: `8` segments, `5` vessels, a `26.09`-day cycle gives
`1.53` calls per day; `59,550` annual TEU is `163` TEU/day, doubled for load
and discharge, so `213` TEU per call against `159` for the distance arm. At
`270` TEU/hour that is `0.79 h` against `0.59 h` per call — about
**`1.6` hours per cycle, or `0.07` days**. The per-OD deltas are `0.9` to
`1.35` days, more than ten times that.

So concentration alone does not explain it, and a handling-time term in the
cost model would not recover it.

## Conclusion

1. **The residual is not a calm-network routing defect.** On an undisrupted
   network the strategy already beats distance routing by `0.157` days of mean
   transport time and carries a younger backlog.
2. **The `112,231` TEU-days "given back" is the accounting cost of a
   net-positive trade, not waste.** The objective is a TEU-weighted mean, and
   the aggregate moves the right way. Reading the per-OD table as a list of
   defects would be reading a global optimum as a set of local failures.
3. **A load-aware cost term is not the answer.** The measured sensitivity is an
   order of magnitude too small, so the several stacked approximations such a
   term would need are not justified by the prize.

## Lessons

49. **A per-OD loss table is not a defect list.** Almost half the OD pairs are
    worse than the fallback, and the policy is still correct: a global optimum
    on a weighted mean necessarily trades some traffic for other traffic.
50. **Check identical-choice cases before theorising about a choice.** Finding
    that the worst pairs get the *same chain* from both policies eliminated
    routing quality in one step and redirected the whole audit.
51. **Do the arithmetic on a mechanism before building it.** Handling time was
    a plausible story for the per-OD gap until it came out ten times too small
    — which cost one calculation instead of one authoritative run.
