# Round 1 empty alternative-route reservation v1

## Goal and falsifiable hypothesis

Round 1's organizer fallback constructs disruption-avoiding alternative
service routes and reserves the first eligible vessel from each affected
original route. That reservation is based on vessel index, not on whether the
vessel is carrying cargo. A carrying vessel cannot switch to its pending
alternative until it becomes empty; an otherwise unreserved empty vessel from
the same original route can activate the same already-built safe route sooner.

The falsifiable hypothesis is that moving a pending alternative reservation
from a carrying vessel to an empty source-route vessel reduces disruption
backlog and TEU-weighted Average Transport Time without changing route
construction, booking assignment, berth choice, or carried cargo.

## Exact participant policy

Only `UserStrategy.create_alternative_service_routes` may return a non-`None`
value. On a call with no active, well-formed disruption key or with no matching
existing alternative routes, it returns `None`, so the organizer fallback owns
route creation and lifecycle restoration exactly as before.

When active plans produce a valid dynamic key, the strategy scans existing
`context.service_routes` in context order. For each matching alternative route,
it finds its pending vessel. If that vessel is still assigned to the
alternative's original source route and carries at least one shipment, the
strategy searches that source route's deployed vessels in context order for a
different vessel that is still assigned to the source route, has no pending
alternative reservation, and carries no shipments. It clears the old pending
pointer, assigns the pending alternative pointer to the empty vessel, and
returns `True`. It makes at most one deterministic replacement per matching
alternative. If no safe replacement exists, it returns `None` and the fallback
continues unchanged.

The strategy never creates or deletes routes/legs/vessels, changes deployed
lists, changes assigned routes, edits bookings or cargo, or imports organizer
strategy code. It uses only standard-library modules, no I/O/network/
subprocess/environment/wall-clock/randomness/global mutable state, and fails
closed on malformed timing, plan, route, or vessel state. The other three hooks
remain unconditional `None`.

## TDD and validation contract

RED tests must fail against the no-op adapter for an active matching
alternative whose pending vessel carries cargo and an empty eligible source
vessel. Tests must also cover inactive/mismatched keys, empty pending vessels,
already-pending candidates, missing/malformed state, multiple alternatives,
deterministic context order, no mutation on delegation, and preservation of
route/leg/vessel collections. A real Round 1 integration test must construct
the organizer context, create the real fallback alternative, then verify the
reservation swap without changing route or vessel membership.

The implementation must pass locked `uv` checks, Ruff, Ty, mypy, coverage
(`>=90.00%` unrounded), integration, sync/cmp, smoke, deterministic packaging
twice, restricted-material, diff, and process gates before the full run.

## Fixed candidate contract

- branch: `codex/round1-empty-alternative-reservation-v1`
- starting commit: `8b13491bbd099e762a5d05b666e1d83aa828298e`
- round: `round1`
- scenario: `create_with_disruption`
- seed: `2026`
- `PYTHONHASHSEED=0`
- warm-up: `140` days
- measured horizon: `360` days
- ATT interval: `5` days; required periods: `72`
- pinned fallback loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- fallback snapshot:
  `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`
- acceptance: `candidate_loss < 20.436668751255972 - 1e-9`
- candidate evidence directory (ignored):
  `.challenge/round1/results/empty_alternative_reservation_v1_20260807/`
- ignored aggregate: `experiments/results/round1_empty_alternative_reservation_v1_20260807.json`

Exactly one full candidate run is authorized after the pre-run review record
is committed. On equality, worsening, invalid output, crash, incomplete output,
or a failed gate: preserve evidence, commit the result, revert candidate code
and tests in reverse order with `git revert`, synchronize the no-op adapter,
restore and re-score the pinned fallback, and rerun all final gates. No tuning,
second candidate, submission, publication, push/merge/PR, or history rewrite is
allowed in this experiment.
