# Round 2: where the remaining loss lives after v10

The active strategy scores `14.897068731156086`. This note attributes what is
left, so the next experiment is chosen from measurement rather than intuition.
It also records one hypothesis that measurement refuted.

## Loss profile over the run

Per-period loss of the accepted v10 run against the authoritative baseline:

| periods | mean loss per period |
| --- | --- |
| 1-24 | `-0.0325` |
| 25-48 | `+0.1855` |
| 49-72 | `+0.4677` |

The first third is now *better* than the baseline on average. The loss is
concentrated late, and the largest single excursion is periods 56-63
(measured days 276-315), where ATT climbs to `18.74` days against a flat
baseline of about `14.2`. No disruption is active in that stretch: the Piraeus
closure ends on measured day 274 and the Tianjin closure does not start until
day 320.

By window, `9.7485` of the remaining `14.897` sits in the 33 periods with no
active disruption. General routing quality, not disruption response, is where
most of the objective still lives.

## A hypothesis the measurement refuted

The obvious explanation for a post-closure excursion was vessel paralysis: a
vessel that arrives at a closed port waits for a berth, so during the 14-day
Piraeus closure S1's eight vessels should queue there in turn, crippling the
only Asia-Europe service for weeks. The strategy's headway is
`cycle_hours / len(deployed_vessels)`, which cannot see a stuck vessel, so it
would keep rating S1 as frequent.

The run's own port statistics do not support this. Across periods 48-72 the
average number of vessels waiting for a berth stays between `0.06` and `0.22`,
while waiting cargo grows steadily from `7,663` to `8,697` TEU. The excursion is
ageing cargo, not blocked vessels. An effective-vessel-count correction would
have been a plausible-sounding change addressing a cause that is not there.

## What the backlog actually is

A diagnostic run of the active strategy stopped at measured day 305 and
classified every unfinished shipment. Evidence:
`.challenge/round2/results/audit_20260903/backlog_day305.json`.

- `22,192` unfinished shipments, `31,386` TEU, TEU-weighted mean age
  `16.62` days;
- `15,269` in transit, `6,923` booked and waiting at their origin, and
  **`0` unbooked**.

Zero unbooked shipments is the headline: the chain builder never leaves cargo
without a plan, so none of the remaining loss comes from cargo that could not
be routed. Roughly `69%` of it is cargo that is already moving and simply has a
long way to go.

The aged TEU-hours spread across long-haul pairs rather than concentrating on
any disruption:

| OD | mean age (days) | in transit | at origin | share of aged TEU-hours |
| --- | --- | --- | --- | --- |
| Rotterdam->Jebel Ali | `22.14` | 196 | 54 | `2.16%` |
| Los Angeles->New Jersey | `29.87` | 126 | 111 | `2.05%` |
| New Jersey->Los Angeles | `28.07` | 234 | 13 | `1.99%` |
| Shanghai->Rotterdam | `22.62` | 242 | 2 | `1.95%` |
| Shanghai->Hamburg | `23.13` | 245 | 3 | `1.86%` |
| Rotterdam->Shenzhen | `23.70` | 197 | 36 | `1.83%` |

By destination the largest shares are Jebel Ali `12.94%`, Rotterdam `11.90%`,
Los Angeles `10.87%` and Hamburg `9.16%`. No single OD pair exceeds `2.2%`, so
there is no remaining hot spot to fix - only the general quality of long-haul,
multi-transfer plans.

`Los Angeles->New Jersey` illustrates the structure: the network has no direct
trans-US service, so cargo must travel Los Angeles to Asia and onward via
Colombo, or across Europe, and `111` of its `237` unfinished shipments are still
waiting at origin after a mean `29.87` days.

## Candidate next experiments, in the order the evidence supports

1. **Read the next departure from live state instead of estimating it.** The
   wait is still the statistic `cycle_hours / vessel_count`. Vessel positions,
   `segment.current_vessels`, and vessel activity state are all readable, so the
   actual time until a vessel next departs the booked segment could be computed
   instead. This removes the calibration question that v10 answered only
   approximately, and it applies to every booking in every period - the widest
   reach of any remaining idea, and the one that addresses long-haul
   multi-transfer plans where the estimate is least accurate.
2. **In-transit replanning.** `adjust_bookings_before_cargo_handling` is still
   fully delegated, so cargo already moving is replanned by the organizer's
   distance-based search whenever a disruption starts after it was booked. With
   `69%` of aged backlog in transit this is the second-widest lever, and it
   reuses the cost model already proven at the booking decision.
3. **Nothing further on hold predicates.** Eight experiments established that
   the hold family is exhausted, and the `0` unbooked shipments above confirm
   holding is no longer where the loss is.
