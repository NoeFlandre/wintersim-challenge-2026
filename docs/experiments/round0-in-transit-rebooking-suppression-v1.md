# Round 0 in-transit rebooking suppression v1

**Status:** SUCCESS_REJECTED

## Hypothesis

Round 0 disruptions last approximately 14–20 days. The organizer fallback may
react to them by shortening current bookings, discharging cargo at intermediate
ports, and rebuilding remaining paths. For cargo already aboard a vessel, the
extra discharge, transshipment, weekly-service wait, and longer replacement
route may cost more than simply remaining on its original booking through a
short disruption.

The candidate will suppress in-transit booking replanning during active
disruptions. It returns a handled result (`False`) from
`adjust_bookings_before_cargo_handling` only while at least one disruption is
active, making no mutation whatsoever during that active call. Outside active
disruptions it returns `None` so the organizer fallback may apply normal
in-transit replanning.

This is the only authorized strategy change. The other three strategy hooks
(`select_vessel_for_berth`, `create_alternative_service_routes`,
`assign_associated_bookings`) remain no-op delegates. New shipments continue
to use the organizer's disruption-aware booking assignment. Alternative-route
behavior remains organizer fallback. Berth selection remains organizer fallback.

## Exact one-hook scope

Only `adjust_bookings_before_cargo_handling(context, now, vessel)` is changed.
All other hooks continue to return `None` unconditionally.

## Active/inactive return behavior

- During an active disruption: return exactly `False` (handled, no mutation).
- Outside any active disruption: return `None` ("not handled; use the
  organizer fallback").

The organizer call site in `simulation_model/vessel_queuing_for_berth.py`
distinguishes fallback strictly with `is None`:

```python
user_decision = UserStrategy.adjust_bookings_before_cargo_handling(...)
if user_decision is None:
    DefaultStrategy.adjust_bookings_before_cargo_handling(...)
```

Returning `False` outside an active disruption would prevent the organizer
fallback from running its normal in-transit replanning and is explicitly
disallowed.

## No-mutation rule

During an active disruption call, the implementation must not mutate:
- context collections (legs, routes, segments, bookings, vessels, ports,
  shipment lists, demand lists, disruption_plans, or any other attribute);
- vessel assignment (assigned_service_route, pending_assigned_service_route,
  current_segment, current_berth, deployed_vessels membership);
- vessel carried shipments or their stored references;
- booking sequence references, departure/arrival segment indices, or service
  route `associated_bookings` lists;
- shipment `associated_bookings`, `current_booking_index`, or storage port;
- segment `current_vessels` lists;
- any object reachable from `context`, `vessel`, or `now`.

It simply returns `False`.

## Full-run configuration

- Seed: 2026
- Warm-up: 140 days
- Measured duration: 360 days
- Interval: 5 days
- Period count: 72
- Scenario: Round 0 `create_with_disruption` (measurement-relative disruption
  offsets)

## Current-checkout acceptance threshold

The authoritative comparable reference for this checkout is the locally
reproduced fallback:

- Score: `18.673577819840556`
- ATT SHA-256: `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`

**Acceptance rule:** Retain the candidate only if the complete 72-period score
is lower than `18.673577819840556` by more than `1e-9`. A smoke run, partial
run, or mean ATT alone can never satisfy acceptance.

## Historical threshold (secondary reporting only)

- Historical score: `18.276620672293834`
- Historical ATT SHA: `ed4f274f827959ce4261303996bbde035aa784f7b7d070b9bbdf6bea1c7cbb03`

Report separately whether the candidate also beats this historical value. It
does not affect the accept/reject decision in this checkout.

## Rejection/restoration procedure

If the candidate score is equal to or above `18.673577819840556`:

1. Update this document to `SUCCESS_REJECTED` with evidence-limited wording.
2. Record all metrics, hashes, runtime, and the rejection reason.
3. Commit the result documentation separately:
   `docs: record rejected in-transit rebooking result`
4. Revert the implementation commit with `git revert`; do not manually
   recreate the no-op adapter.
5. Synchronize the reverted no-op adapter into the organizer tree.
6. Restore `.challenge/round0/source/Output/ATT_By_Statistics_Interval.csv`
   from a verified current-checkout fallback snapshot.
7. Verify the restored SHA is exactly
   `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`.
8. Verify its score is exactly `18.673577819840556`.
9. Rerun final gates and deterministic packaging.
10. Leave the experiment branch clean with the no-op fallback active.

## No-second-candidate rule

Do not attempt another hypothesis regardless of outcome. This is the only
authorized candidate for this experiment.

## Full result

| Measure | Value |
| --- | --- |
| Candidate Cumulative Resilience Loss | `21.681637022046967` |
| Candidate ATT SHA-256 | `da64a36f38aae32ca93993b09e7e88f53d59069474465c10d0585c0836040fe7` |
| Baseline score threshold (current-checkout fallback) | `18.673577819840556` |
| Delta vs baseline threshold | `+3.008059202206411` (much worse, not lower by more than `1e-9`) |
| Mean ATT across numbered period rows (days) | `20.525694444444444` |
| Period count | `72` |
| Runtime | `26:21` |
| Beats historical `18.276620672293834`? | No |
| Beats current-checkout `18.673577819840556`? | No (worse) |

The candidate produced a different ATT output than the current-checkout
fallback (different SHA, different per-period values). Therefore suppressing
the organizer's in-transit rebooking hook caused a measurable scoring
degradation in this Round 0 run (cumulative loss rose by ~3.01). The
experiment did not instrument per-port/per-cargo flow sufficiently to
establish whether the degradation came from new shipments that could not be
rerouted away from the disruption, or from carried shipments that became
trapped on disrupted legs when in-transit replanning was suppressed.

The candidate score `21.681637022046967` is well above the current-checkout
acceptance threshold of `18.673577819840556`, so the candidate is rejected
on the acceptance rule alone.

## Decision

Reject. The candidate score `21.681637022046967` is above the current-checkout
acceptance threshold of `18.673577819840556` by more than `1e-9`. The
underlying cause of the degradation was not established by this experiment.

## Rejection/restoration procedure (executed)

1. This document was updated to `SUCCESS_REJECTED` (this file).
2. All metrics, hashes, and runtime recorded above.
3. Result documentation committed separately via
   `docs: record rejected in-transit rebooking result`.
4. Implementation commit (`1c6a230`) reverted via `git revert`; the no-op
   adapter is restored automatically.
5. The reverted no-op adapter synchronized into the organizer tree.
6. `.challenge/round0/source/Output/ATT_By_Statistics_Interval.csv` restored
   from a verified current-checkout fallback snapshot (the bytes were
   preserved in
   `.challenge/round0/results/fallback_reproduction_current_checkout_run1/`
   and `_run2/`).
7. Verified restored SHA:
   `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`.
8. Verified restored score: `18.673577819840556`.
9. Final gates rerun; deterministic packaging re-verified.
10. Branch left clean with the no-op fallback active.

## Final implementation commit (rejected)

- Implementation commit SHA: `1c6a230`
- Revert commit SHA: see `git log` after this `docs: record rejected in-transit rebooking result` commit.
