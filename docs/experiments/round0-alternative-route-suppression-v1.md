# Round 0 alternative-route suppression v1

**Status:** SUCCESS_REJECTED

## Hypothesis

The organizer's default alternative-route policy creates cyclic detours and
reserves/transfers vessels from affected original routes. Round 0 disruptions
last roughly 14–20 days, while services operate on weekly cycles. For these
relatively short disruptions, moving vessels away from established routes may
impose broader capacity and schedule costs that outweigh the temporary detour
benefit.

The candidate will suppress alternative-route creation during active
disruptions. It returns a handled result (`False`) from
`create_alternative_service_routes` only while at least one disruption is
active, making no mutation whatsoever during that active call. Outside active
disruptions it returns `None` so the organizer fallback may perform normal
cleanup and restoration.

This is the only authorized strategy change. The other three strategy hooks
(`select_vessel_for_berth`, `assign_associated_bookings`,
`adjust_bookings_before_cargo_handling`) remain no-op delegates.

## Exact one-method scope

Only `create_alternative_service_routes(context, now, vessel=None)` is changed.
All other hooks continue to return `None` unconditionally.

## Why inactive calls must return `None`

The organizer call sites in `vessel_being_served.py`,
`vessel_queuing_for_berth.py`, and `shipment_waiting_for_loading_at_origin_port.py`
distinguish fallback strictly with `is None`:

```python
route_decision = UserStrategy.create_alternative_service_routes(...)
if route_decision is None:
    DefaultStrategy.create_alternative_service_routes(...)
```

Returning `False` outside an active disruption would prevent the organizer
fallback from running its cleanup/restoration logic (restoring vessels to
original routes, removing inactive alternative routes). That would break the
fallback contract and is explicitly disallowed.

## No-mutation requirement

During an active disruption call, the implementation must not:
- Add, remove, or replace any vessel, leg, route, segment, booking, or port
- Mutate any attribute of `context`, `vessel`, or related objects
- Create new objects or modify collections

It simply returns `False` as the active handled result.

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

1. Update this document to `SUCCESS_REJECTED`.
2. Record all metrics, hashes, runtime, and the reason for rejection.
3. Commit the result documentation separately:
   `docs: record rejected alternative-route suppression result`
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
| Candidate Cumulative Resilience Loss | `18.673577819840556` |
| Candidate ATT SHA-256 | `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658` |
| Baseline score threshold (current-checkout fallback) | `18.673577819840556` |
| Delta vs baseline threshold | `0.0` (equal, not lower by more than `1e-9`) |
| Mean ATT across numbered period rows (days) | `20.336944444444445` |
| Period count | `72` |
| Runtime | `28:47` |
| Beats historical `18.276620672293834`? | No |
| Beats current-checkout `18.673577819840556`? | No (equal, not below) |

The candidate produced a byte-identical ATT CSV to the current-checkout
locally reproduced fallback. Because acceptance requires the candidate score
to be strictly lower than the threshold by more than `1e-9`, the candidate
is rejected.

This outcome is consistent with the hypothesis's mechanism: Round 0
disruptions are short (14–20 days) compared with the 360 measured days, and
the other three strategy hooks (which still delegate to the organizer
fallback) include disruption-aware booking assignment and in-transit booking
adjustment. Those hooks already build paths that avoid the disrupted
ports/legs during the disruption window. Suppressing the alternative-route
creation does not provide any additional routing benefit because the
alternative routes were not being used during the disruption in a way that
meaningfully changed ATT for these short disruptions within the 360-day
measured horizon.

## Decision

Reject. The candidate score `18.673577819840556` is equal to the
current-checkout locally reproduced fallback score, not strictly lower by
more than `1e-9`.

## Rejection/restoration procedure (executed)

1. This document was updated to `SUCCESS_REJECTED` (this file).
2. All metrics, hashes, and runtime recorded above.
3. Result documentation committed separately via
   `docs: record rejected alternative-route suppression result`.
4. Implementation commit (`a90a4e3`) reverted via `git revert`; the no-op
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

- Implementation commit SHA: `a90a4e3`
- Revert commit SHA: see `git log` after this `docs: record rejected alternative-route suppression result` commit.
