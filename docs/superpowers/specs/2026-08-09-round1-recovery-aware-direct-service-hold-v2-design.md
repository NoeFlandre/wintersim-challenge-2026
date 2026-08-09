# Round 1 recovery-aware direct-service hold v2 design

## Status and purpose

This document pre-registers one controlled WSC 2026 Round 1 experiment. The
candidate tests whether a newly generated shipment should temporarily remain at
its origin when the organizer fallback would replace one disrupted direct
service with a multi-service detour that is estimated to arrive later than the
direct service after recovery.

The policy is a materially narrower successor to the interrupted
`round1-recovery-aware-origin-hold-v1` experiment. Version 1 never produced a
complete candidate output or score. Version 2 adds a structural dominance gate:
the nominal path must be one direct booking and the currently safe path must
require a real transfer between at least two service routes.

## Evidence and alternatives

The pinned no-op fallback scores `20.436668751255972` over 72 periods. Previous
Round 1 experiments establish three useful constraints:

- broad initial-booking replacements materially worsened the score;
- broad future-only in-transit rebooking suppression materially worsened the
  score;
- several berth and alternative-vessel policies produced byte-identical output,
  showing that a valid policy can be operationally dormant.

A read-only topology probe of fresh organizer contexts found direct nominal
paths that become three-to-five-booking safe detours during the first disruption
phase. The approved estimator would act on a small but nonzero share of annual
TEU in several active sub-phases. These aggregates establish activation only;
they are not simulation results and do not predict acceptance.

Three approaches were considered:

1. **Recovery-aware direct-service hold (selected).** It is read-only, has
   observed structural activation, and preserves the organizer fallback outside
   a high-confidence direct-versus-transfer case.
2. **Nearest-start alternative-vessel reservation.** This is lower-risk state
   mutation, but two related alternative-route lifecycle policies already tied
   the fallback, and freshly built alternatives initially have pending rather
   than deployed vessels.
3. **Recovery-before-arrival in-transit suppression.** This targets a plausible
   temporal blind spot but requires estimating vessel arrival through live
   operations. The broader predecessor was 14.44% worse, so this is a higher-risk
   next step than the selected origin decision.

## Participant boundary

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a non-`None` value. The other three public hooks remain unconditional
`None` delegates.

The implementation must remain completely self-contained under
`submission/response_strategies/`, use only the Python standard library, and
preserve all four exact public signatures. It must not import organizer-owned
strategy or simulation modules.

The policy may read only the objects reachable from `context`, `now`, and
`shipment`. It must not use scenario names, port names, route identifiers,
calendar dates, seeds, tuned thresholds, files, the current directory,
environment variables, network access, subprocesses, wall-clock time,
randomness, or mutable module-level state.

## Exact policy

The hook returns `None` unless every step below succeeds.

1. Require a valid `datetime` decision time, an origin distinct from the
   destination, an empty pre-existing booking chain, a `None` current booking
   index, and at least one
   well-formed active disruption window using the inclusive-start,
   exclusive-end rule `start <= now < end`.
2. Derive the active closed ports, congested legs, their recovery times, and the
   fallback-compatible disruption key from runtime object identity and stable
   names used only to match the organizer key contract.
3. Enumerate deterministic contiguous booking edges in `context.service_routes`
   order. A nominal graph uses only original routes
   (`source_service_route is None`) without active exclusions. A safe graph
   mirrors the organizer fallback:
   - exclude active congested legs;
   - reject an edge whose arrival or intermediate ports are actively closed,
     exactly matching the fallback edge filter (the edge's departure port is
     not independently excluded);
   - admit an alternative route only when its disruption key matches the active
     key and it has at least one deployed vessel.
4. Run deterministic shortest-distance pathfinding with context port order and
   edge order as tie-breakers. Require:
   - exactly one edge in the nominal path;
   - the nominal edge intersects at least one active disruption;
   - at least two edges in the safe path;
   - at least one adjacent safe-path edge changes service-route identity, proving
     that the safe path introduces a transfer.
5. Estimate route service time from runtime data only. For a route with valid
   deployed vessels:
   - `mean_speed = arithmetic mean of positive finite sailing speeds`;
   - `headway_hours = route_cycle_distance / sum(vessel_speeds)`;
   - `edge_sailing_hours = edge_distance / mean_speed`.
   A path receives `0.5 * headway_hours` when first boarding a route and again
   after each actual change to another route. Consecutive edges on the same
   route do not receive another headway term.
6. Let `recovery` be the latest end time of the active disruptions intersecting
   the nominal edge. Calculate:
   - `hold_hours = hours_until_recovery + nominal_edge_hours`;
   - `detour_hours = sum(safe edge sailing hours and first-boarding headways)`.
7. Return `False` only when both estimates are positive and finite and
   `hold_hours < detour_hours` at full precision. Equality delegates. Returning
   `False` leaves the shipment untouched and uses the organizer's existing
   recovery-time retry lifecycle. Return `None` in every other case.

This hook never assigns, clears, or edits bookings. It never mutates routes,
legs, ports, vessels, disruption plans, shipments, collections, or reverse
references. A delegated call and a `False` decision must both leave the complete
observable input state unchanged.

## Failure behavior

Missing relationships, duplicate or invalid sequence indexes, empty or
non-cyclic routes, invalid distances or speeds, non-finite arithmetic,
inconsistent alternative-route metadata, ambiguous disruption targets, no
complete path, or any narrow data-shape exception returns `None` without
mutation. Unexpected programmer errors are not swallowed broadly.

Pathfinding and estimation finish before the public method chooses a return
value. Deterministic list/order operations are used throughout; unordered
containers may be used only for membership, never to choose a tie.

## TDD contract

Strict RED-GREEN-refactor evidence is required.

Synthetic tests must first fail against the no-op adapter for:

- the qualifying direct-versus-transfer case returning `False`;
- exact equality delegating;
- a safe direct path delegating;
- a multi-booking nominal path delegating;
- a nominal path unaffected by active disruptions delegating;
- inclusive start and exclusive end boundaries;
- repeated safe edges on one route not being misclassified as a transfer;
- deterministic path ties;
- malformed, non-finite, and incomplete runtime state failing closed;
- complete immutability for both `False` and `None` outcomes;
- exact public signatures, static methods, and forbidden-import/state checks.

A real ignored Round 1 integration test must derive an active window and a
qualifying OD pair from the actual context without hard-coded names, prove that
the candidate returns `False`, prove a non-qualifying case returns `None`, and
snapshot all relevant context/shipment state before and after each call.

The RED commit must fail because the no-op adapter lacks the approved behavior,
not because of a broken fixture. The minimum participant implementation is then
added and focused GREEN, full unit, integration, lint, type, coverage, smoke,
and package gates are run.

## Fixed experiment identity

- repository constraint: the user's standing requirement is one canonical
  folder and one branch, so this experiment stays on `main` in
  `/Users/noeflandre/wintersim-challenge-2026`; no worktree or experiment branch
  is created;
- starting commit: `ef1589094bbe40a7b2501d9fde84351b2c479347`;
- starting no-op strategy SHA-256:
  `b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`;
- round/scenario: `round1` / `create_with_disruption`;
- seed: `2026`; process environment: `PYTHONHASHSEED=0`;
- warm-up: 140 days;
- measured horizon: 360 days;
- reporting interval: 5 days;
- required period count: 72;
- exact run command:
  `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`;
- pinned fallback cumulative loss: `20.436668751255972`;
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`;
- pinned fallback mean ATT: `20.450972222222223` days;
- pinned fallback snapshot:
  `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`;
- ignored candidate evidence directory:
  `.challenge/round1/results/recovery_aware_direct_service_hold_v2_20260809/`;
- ignored aggregate record:
  `experiments/results/round1_recovery_aware_direct_service_hold_v2_20260809.json`.

The only acceptance expression is:

```text
candidate_cumulative_loss < 20.436668751255972 - 1e-9
```

It is evaluated over exactly 72 numbered periods without rounding. Mean ATT is
descriptive only. Equality, worsening, a crash, incomplete output, a stale ATT
file, an invalid period count, or any failed gate is rejection.

## Preflight, run, and restoration

Before the long run, require locked `uv` resolution, Ruff format and lint, Ty,
mypy, non-integration coverage of at least 90.00%, all integration tests,
participant/runtime byte identity, Round 1 smoke, two byte-identical compliant
packages, clean diff/status, clean restricted-material scans, a freshly verified
fallback score/hash, and proof that no simulator is running.

Pin the candidate HEAD, strategy SHA, package SHA/members, fallback snapshot,
and stale Output hash/mtime. Execute exactly one managed full candidate run and
monitor it until exit, Day 360, Period 72, explicit completion, and a fresh CSV.
No code, threshold, or policy changes are permitted after launch.

Preserve the raw log and fresh ATT bytes before scoring or synchronization.
Record the ATT hash, size, mtime, mean, all per-period values, complete scorer
JSON, better/equal/worse period counts, delta, relative change, runtime, and
decision in the ignored evidence and tracked experiment report.

If accepted, retain the candidate and rerun all final gates. If rejected,
commit the result report first, revert only candidate implementation and test
commits in reverse order with `git revert`, synchronize the restored no-op
adapter, restore the pinned fallback ATT bytes, re-score them exactly, and rerun
all final gates. The design and result history remain. No second candidate,
tuning run, submission, push, merge, pull request, or history rewrite is part of
this experiment.
