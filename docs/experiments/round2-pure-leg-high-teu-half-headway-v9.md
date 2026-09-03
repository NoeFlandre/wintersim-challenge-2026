# Round 2: pure-leg high-TEU half-headway recovery gate (v9)

**Status: DESIGN FROZEN — pre-implementation.**

This document freezes one new, independently named Round 2 experiment. It is
not a score claim and it authorizes no second candidate, tuning, publication,
or submission.

## Incumbent and evidence

The verified incumbent is Round 2 v8, the upper-quartile pure-leg
multi-transfer recovery hold:

- incumbent cumulative resilience loss: `34.62237395179777`;
- incumbent ATT snapshot:
  `.challenge/round2/results/multi_transfer_leg_teu_guard_v8_20260901/ATT_By_Statistics_Interval.csv`;
- incumbent ATT SHA-256:
  `616a8b07870d9de0b2597cb317ee14d4743455f5d4b34f315adf15895fc95700`;
- current participant strategy SHA-256:
  `7e9794843eae071186cfdff4d835fb5d3e645bbd3d09008c86ac7977af1a17ee`;
- authoritative Round 2 baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`.

The v8 non-mutating audit covered 166 valid disruption midpoints, 380 demands
per fresh context, and 63,080 observations. It found 19 lower-volume pure-leg
holds that v8 deliberately delegates and five remaining upper-quartile
pure-leg multi-transfer holds. Those five have positive recovery margins of
approximately 20, 44, 68, 92, and 116 hours, while the maximum safe-path
headway is approximately 154 hours. The exact figures are audit evidence, not
scenario identifiers or fitted output values.

## Hypothesis

Because v8 improved the score by removing only low-volume pure-leg holds, the
remaining high-volume pure-leg holds may still be harmful when their apparent
recovery advantage is too small to cover a normal safe-service departure
opportunity. Changing only those marginal decisions to delegation should reduce
origin/network backlog while retaining the stronger-margin high-volume holds.

The strongest failure mode is that a high-volume shipment's direct TEU-weighted
benefit is valuable even below half a headway; delegating the three weakest
remaining holds could therefore increase the official loss. The full
72-period score, not activation count or mean ATT, decides.

## Exact candidate policy

Only `UserStrategy.assign_associated_bookings` changes. Preserve every v8
precondition, graph construction, shortest-path tie order, timing calculation,
exception boundary, and all other hooks.

In the existing multi-transfer branch, after the nominal direct edge is shown
to match **only active leg-congestion constraints** and the demand is proven to
be in the deterministic upper quartile:

1. keep the existing `hold_hours < detour_hours` requirement;
2. compute the positive recovery margin (`detour_hours - hold_hours`);
3. require the margin to be **strictly greater than half** the largest
   safe-path service headway;
4. return `False` only when that strict half-headway condition holds; otherwise
   return `None` and let the organizer fallback decide.

The candidate therefore changes no port-only, mixed-constraint, one-transfer,
lower-quartile, malformed, inactive, or non-positive-margin decision. Missing,
ambiguous, non-finite, or invalid headway data delegates fail-closed. The
threshold is a semantic fraction of live route headway, not a port, route,
demand, date, seed, output-period, or score lookup.

## Alternatives considered and selection

Several identity-free candidates were considered before code:

| Candidate | Expected upside | Downside | Safety/live evidence | Decision |
| --- | --- | --- | --- | --- |
| Remove every remaining pure-leg upper-quartile hold | More backlog relief | Loses all five high-TEU direct benefits | Live but broad; prior pure-leg exclusion was harmful in Round 1 | Reject as too risky |
| Delegate only high-TEU pure-leg margins at or below 0.5 headway | Tests the weakest remaining slice and retains stronger margins | The three removed observations may still be TEU-beneficial | Directly live in v8 audit; read-only and one-hook | **Selected** |
| Change berth ordering for affected cargo | Could reduce queue spillover | Prior berth policies were no-effect or degraded and need more mutable state | Weak activation evidence | Reject |
| Suppress in-transit rebooking | Could avoid transfer churn | The analogous suppression was materially worse | Different hook but adverse adjacent evidence | Reject |

The selected policy is the smallest new semantic timing gate supported by the
v8 audit and has bounded, structurally identifiable activation. Activation is a
go/no-go condition only; it is not a prediction of improvement.

## TDD and activation contract

Implement with RED -> GREEN -> REFACTOR:

- commit this design before participant code changes;
- add focused synthetic tests that fail only because the half-headway guard is
  absent, including strict-boundary, retained strong-margin, delegated weak-
  margin, lower-quartile, port/mixed preservation, malformed data, and
  no-mutation cases;
- implement the smallest standard-library-only read-only helper/predicate;
- add a real ignored-context integration test and a fresh-context activation
  audit comparing v8's independent oracle with the candidate;
- require the audit to find the declared high-TEU pure-leg delegation slice,
  zero unexpected opposite decisions, no participant mutation, no model event
  advancement, and no Output write.

The expected audit difference is three control-only delegations in the observed
context (the three margins not exceeding half a headway) and two retained
holds. This expectation is a review target, not a hard-coded strategy rule; if
the live audit disagrees, stop before any full run and document why.

## Fixed run contract and acceptance

- round/scenario: `round2` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required periods: `72`;
- acceptance expression: `candidate_loss < 34.62237395179777 - 1e-9`;
- candidate evidence directory:
  `.challenge/round2/results/pure_leg_high_teu_half_headway_v9_20260903/`;
- run command after an immutable pre-run freeze:

  ```text
  PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache uv run wsc2026 run --round round2 --full > .challenge/round2/results/pure_leg_high_teu_half_headway_v9_20260903/full_run.log 2>&1
  ```

Run exactly one frozen candidate only after all lock, sync, format, Ruff, Ty,
mypy, test/coverage, integration, sync/cmp, smoke, deterministic-package,
restricted-material, control-score, stale-Output, and no-live-process gates
pass. Preserve the fresh ATT and raw log before scoring, synchronization,
smoke, packaging, or restoration. Analyze every period against v8 and record
activation counts and the mechanistic lesson.

Equality, worsening, invalid output, incomplete completion, a failed gate, or
any compliance issue is rejection. On rejection, preserve ignored evidence,
commit the result report, revert only this candidate's implementation/tests in
reverse order, synchronize and re-score the pinned v8 ATT, rerun final gates,
and leave v8 active. No tuning, duplicate run, second candidate within v9,
push, merge, PR, upload, submission, or history rewrite is authorized.
