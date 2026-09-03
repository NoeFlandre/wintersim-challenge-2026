# Round 2: how faithful is the transport-time cost model?

The v9 strategy chooses booking chains by an estimated transport time built
from three terms: sailing time at live leg multipliers, `0.5 * headway` for
each service route boarded, and the simulation's fixed three-hour berthing time
per intermediate port call. This note measures that estimate against what the
simulation actually delivers, so the next iteration is driven by evidence
rather than by tuning.

## Method

A private, throwaway copy of the organizer tree under the ignored
`.challenge/round2/candidate_check/diag_source/` carried a diagnostic-only
instrumented strategy that recorded the estimate it computed for each shipment.
It then ran the organizer's own loop for a 140-day warm-up plus 60 measured
days and paired each estimate with the realized
`completion_time - generated_time`.

The instrumented copy exists only for analysis. It is never synchronized back
into `submission/`, never packaged, and never used for a scored run. Evidence:
`.challenge/round2/results/audit_20260903/diag.json`.

## Result

171,129 completed shipments.

- mean estimate: `373.47` hours;
- mean realized: `448.36` hours;
- mean residual: `+74.90` hours.

Broken down by the number of bookings in the chain:

| bookings | shipments | mean residual (h) | median residual (h) |
| --- | --- | --- | --- |
| 1 | 98,565 | `+51.23` | `+36.78` |
| 2 | 60,060 | `+100.31` | `+75.33` |
| 3 | 12,504 | `+139.43` | `+111.99` |

The residual grows by `+49.08` hours from one booking to two and `+39.12`
hours from two to three. It is therefore not a fixed per-shipment offset: it
scales with the number of **boardings**, at roughly `+45` hours each.

## Diagnosis

A constant per-shipment offset would not change which chain is cheapest, but a
per-boarding offset does: it means the model systematically under-prices every
transfer relative to sailing time.

The size of the offset identifies its origin. The nine service routes have
these headways:

| route | cycle (h) | vessels | headway (h) |
| --- | --- | --- | --- |
| S1 | `1073.3` | 8 | `134.2` |
| S2 | `150.3` | 2 | `75.2` |
| S3 | `84.8` | 2 | `42.4` |
| S4 | `616.5` | 4 | `154.1` |
| S5 | `1255.4` | 9 | `139.5` |
| S6 | `626.1` | 5 | `125.2` |
| S7 | `676.4` | 5 | `135.3` |
| S8 | `47.9` | 1 | `47.9` |
| S9 | `591.6` | 5 | `118.3` |

The unweighted mean headway is `108.0` hours, so half a headway is `54.0`
hours — which is what the per-boarding residual measures. The realized wait for
a departure is close to a **full** headway rather than half of one.

Two mechanisms explain that, and both are properties of the model rather than
of the estimate's arithmetic:

1. Cargo is loaded only if it is already waiting when a vessel begins its port
   call, and a shipment that becomes available during the connecting vessel's
   handling misses it and waits another full headway.
2. Sailing duration carries a ±5% random variation, so vessels on a route drift
   out of even spacing and bunch. For a random arrival the mean wait is
   `E[gap^2] / (2 * E[gap])`, which exceeds `headway / 2` whenever gaps vary,
   and approaches a full headway as that variance grows.

## Consequence for the next experiment

Charging `1.0 * headway` per boarding instead of `0.5 * headway` is the
evidence-derived correction. It is not a free parameter fitted to a score: it
doubles the price of every transfer relative to sailing time, which shifts the
policy toward fewer transfers and toward higher-frequency services, and it is
what the residual measurement says the simulation actually charges.

This is deliberately **not** folded into v9. The v9 candidate is frozen and its
authoritative run is already under way, so the correction is a separate,
separately scored experiment.
