# Round 0 transfer-aware routing v1

**Status:** completed and rejected on 2026-07-20. The candidate implementation
is preserved in commit `02f5fda` and is not the retained solution.

## Hypothesis

The organizer fallback minimizes sailing distance when it creates an initial
booking chain. That can save a small distance by adding a transshipment, even
though every additional booking can wait for another weekly service and must
be discharged and loaded again.

The candidate will change only `assign_associated_bookings` outside active
disruptions. It will minimize nominal sailing time plus **84 hours per booking
edge**. The first edge's constant penalty cannot change path ordering, so the
effective policy charges 84 hours per transfer. The other three hooks retain
the organizer fallback. During an active disruption, initial booking assignment
also retains the disruption-aware organizer fallback.

This is intentionally a small, deterministic policy. It uses only the provided
context, existing routes, existing segments, vessel speeds, and the organizer's
`Booking` type. It creates no routes, legs, vessels, randomness, I/O, or
cross-run state.

## Pre-run evidence

A read-only analysis of the Round 0 network, weighted by annual OD demand,
compared distance-only paths with the proposed transfer penalty:

| Measure | Distance fallback | Candidate estimate |
| --- | ---: | ---: |
| Mean booking count | 1.411 | 1.350 |
| Mean nominal sailing time | 426.001 h | 427.906 h |
| Demand whose route changes | 0% | 5.72% |

The candidate removes enough transfers to plausibly recover more than the
estimated 1.905-hour sailing detour. Most changes are direct services replacing
shorter multi-service paths in East Asia.

## Screening result

The candidate completed a 90-measured-day screen after the official 140-day
warm-up. Against the first 18 periods of the SHA-pinned fallback CSV, its loss
was `0.9255643155824778` versus `5.409560703625514` for the fallback. That was
enough evidence to advance to a full run, but it did not predict the later
steady-state behavior.

An older ignored file, `experiments/results/fallback_2026.json`, reports a
different first-90-day trajectory and is not comparable to the current
validated model. It must not be used for future acceptance decisions.

## Acceptance rule

1. Add contract tests first and observe them fail for the expected missing
   behavior.
2. Pass formatting, lint, type, unit, integration, smoke, and deterministic
   packaging gates.
3. Run the complete Round 0 scenario with seed 2026, 140 warm-up days, 360
   measured days, and five-day intervals.
4. Retain the candidate only if its Cumulative Resilience Loss is lower than
   `18.673577819840556` by more than `1e-9`.

If it fails, preserve aggregate evidence, document the result, and revert to
the clean fallback before testing another hypothesis.

## Full result

Both values below use the same Round 0 scenario, seed `2026`, 140-day warm-up,
360 measured days, and five-day statistics intervals. Lower Cumulative
Resilience Loss is better.

| Measure | Fallback | Candidate | Candidate delta |
| --- | ---: | ---: | ---: |
| Cumulative Resilience Loss | 18.673577819840556 | 30.635549463232536 | +11.96197164339198 |
| Mean ATT (days) | 20.336944444444445 | 21.117916666666666 | +0.7809722222222213 |

Against the retained fallback, the candidate degraded the score by
**64.058274%**. The successful full run
produced all 72 periods and took 35 minutes 34 seconds.

## Decision

Reject. A fixed expected transfer penalty improved the early 90-day window but
performed badly over the full horizon. Avoiding a transfer without considering
the actual service phase and downstream arrival timing can leave shipments on
longer cyclic routes; nominal sailing time plus a static weekly wait is not an
adequate delivery-time estimate.

Future routing work must either estimate timetable phase from `now` or change a
smaller, directly evidenced subset of OD paths. Do not retest another global
static transfer penalty.

## Local private evidence

Raw organizer output remains local and ignored:

- Candidate ATT SHA-256:
  `a0b82c968d18b907d2c1b8780ad4b259d7f1697a4bfcae0403263af250ddfe85`
- Frozen fallback ATT SHA-256:
  `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`
- Aggregate result:
  `experiments/results/transfer_aware_routing_v1_2026.json`
- Candidate ATT snapshot:
  `.challenge/round0/results/transfer_aware_routing_v1_2026/`

No raw organizer output or experiment result is tracked.
