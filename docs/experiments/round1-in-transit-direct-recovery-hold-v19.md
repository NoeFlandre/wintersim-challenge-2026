# Round 1 in-transit direct recovery hold v19

**Status: DESIGN FROZEN — implementation and activation audit pending; no
full simulation has run for v19.**

## Selection and hypothesis

The accepted v3 policy protects newly generated cargo at origin when waiting
for a disrupted direct service is estimated to finish sooner than the safe
detour requiring at least two service-route changes. It does not participate
in `adjust_bookings_before_cargo_handling`, where the organizer fallback may
replan cargo that is already on a vessel. The only previous in-transit test
suppressed broad future-only replans and worsened materially, so it does not
justify changing that behavior generally.

V19 tests the narrower semantic gap: when a carried shipment is still on its
single direct booking and the unfinished direct service itself is affected,
letting the direct service recover may be better than discharging and creating
a fragmented detour. The candidate returns `False` only when every carried
shipment whose unfinished path is affected satisfies this direct-current
recovery comparison, and at least one such shipment exists. Future-only
impacts, mixed vessels, multi-booking cargo, alternative routes, one-transfer
detours, inactive disruptions, and uncertainty delegate to the organizer
fallback.

The strongest failure mode is that a vessel can carry cargo with different
needs or that the fallback's replan is valuable even for a directly affected
current booking. The all-qualifying-vessel guard bounds that risk; the official
72-period cumulative resilience loss, not activation counts or mean ATT,
decides.

## Exact participant policy

Only `UserStrategy.adjust_bookings_before_cargo_handling(context, now, vessel)`
may change. The three other hooks retain the active v3 behavior exactly.

The hook is read-only and returns `False` only if:

1. the context and timestamp contain a well-formed active disruption;
2. the vessel has at least one carried shipment and valid current segment;
3. every carried shipment that has an active unfinished impact is a single,
   original-route booking whose current unfinished direct edge is affected;
4. for every such shipment, the nominal path from the vessel's current port to
   its destination has one edge, the safe path has at least two route changes,
   and `recovery_wait + nominal_service_hours < safe_detour_service_hours` at
   full precision; and
5. at least one shipment meets those conditions, with no affected shipment
   outside the qualifying set.

An unaffected shipment does not itself force delegation, but an affected
future-only, multi-booking, alternative-route, malformed, or otherwise
ambiguous shipment does. Returning `None` must leave all objects unchanged and
lets the organizer fallback perform its established replan. Returning
`False` also performs no mutation and prevents the fallback replan for the
whole vessel. No route, booking, vessel, or output is created or edited.

The policy uses only the supplied runtime objects, deterministic context order,
standard-library imports, and the existing identity-free v3 topology/timing
helpers. It contains no port/route/vessel/demand IDs, dates, seeds, fitted
thresholds, I/O, environment or process access, wall-clock time, randomness,
organizer imports, or mutable cross-run state. It fails closed on malformed
data and uses explicit route/booking identity only to validate the relationships
already supplied by the runtime.

## Candidate scorecard

| Dimension | Score | Reason |
| --- | ---: | --- |
| Adjacent evidence | 1/2 | The broad future-only suppression was harmful, but no direct-current isolation has been measured. |
| Candidate-only activation | 2/2 | A disposable real-context probe can construct carried direct bookings over the existing v3 qualifying observations. |
| Call-site fit | 2/2 | This hook is the organizer's exact pre-cargo-handling replan gate. |
| Upside/downside | 2/2 | It targets avoidable transshipment while delegating mixed and uncertain vessels. |
| Hidden-scenario generalization | 2/2 | The rule is topology/timing based, not scenario identity based. |
| Safety | 2/2 | Pure read-only primitive return with complete state snapshots. |
| Novelty | 2/2 | No prior full experiment tested this direct-current, all-qualifying vessel policy. |
| Testability | 2/2 | Synthetic booking/vessel cases plus a real ignored-context activation audit. |

Alternatives rejected before implementation: a broad in-transit suppression
repeats the rejected deferred-rebooking experiment; another initial-booking
one-transfer extension repeats v12/v15/v16/v6/v8 failures; berth and
alternative-route policies have already been equal or materially worse.

## Activation audit contract

Before production code, a private ignored audit must use the active Round 1
`create_with_disruption` builder, every valid integer-day midpoint in the union
of disruption windows, and every demand in context order. Each observation
uses a disposable context, the fallback's route preparation only as setup, and
a fresh real `Shipment`, `Booking`, and existing `Vessel` arranged at the
current port immediately before the affected direct edge. It must compare the
control delegate with the frozen v19 oracle, snapshot the complete context,
vessel, shipment, booking, and Output signatures around every oracle call, and
never advance a model or write organizer Output.

The audit must record all observations, direct-current candidate-only
activations, control-v3-shaped exposure, delegation categories, malformed and
mixed guards, no mutation, unchanged Output, and explicit limitations that
activation is not score evidence. A GO requires at least one real candidate-
only activation, same-observation comparison, no mutation, no model advance,
and no Output write. Evidence is immutable and ignored at:

`.challenge/round1/results/in_transit_direct_recovery_hold_v19_20260819/activation_audit.json`.

## Fixed control and run contract

- checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one canonical worktree and the sole local `main` branch;
- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / interval: `140` / `360` / `5` days;
- required numbered ATT periods: `72`;
- launch HEAD before implementation: `be39d9f6425ffd796089200458f01a6b78d2ebbf`;
- accepted v3 strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- accepted v3 ATT snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- accepted v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- freshly verified v3 control loss: `19.084638612143134`;
- strict acceptance: `candidate_loss < 19.084638612143134 - 1e-9`;
- candidate evidence directory:
  `.challenge/round1/results/in_transit_direct_recovery_hold_v19_20260819/`;
- ignored aggregate:
  `experiments/results/round1_in_transit_direct_recovery_hold_v19_20260819.json`;
- exact run command:
  `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`.

Equality, worsening, invalid or stale output, incomplete completion markers,
mutation, a failed gate, or a crash is rejection. The full run is exactly one
candidate run. No tuning, duplicate, second candidate, push, merge, PR,
upload, submission, or history rewrite is part of v19.

## TDD and restoration procedure

Write RED behavior tests before production code. Against untouched v3, RED
must fail only for the direct-current all-qualifying case; the future-only,
mixed, multi-booking, one-transfer, inactive, malformed, exact-boundary,
state-identity, public-signature, forbidden-capability, and retained-v3 cases
must remain green. GREEN is the smallest read-only predicate and should add no
unrelated refactor. Run focused tests, Ruff, Ty, and mypy before committing
implementation.

Before launch, require locked uv resolution/sync, Ruff format/lint, Ty, mypy,
non-integration branch coverage at least 90.00%, serial integration tests,
Round 1 sync/cmp, smoke, two deterministic participant-only packages, fresh
v3 score/ATT identity, restricted-material scans, clean Git state, and no live
simulator. Freeze a non-overwriting manifest with all hashes and gate results.

After completion, preserve the fresh ATT and raw log before scoring or any
restore/sync/smoke/package operation. Score exactly 72 numbered periods and
apply the expression unchanged. On rejection, commit the result first, revert
only v19 implementation/tests in reverse order with `git revert`, synchronize
v3, restore the pinned ATT snapshot byte-for-byte, re-score exactly, rerun all
final gates, and leave v3 active. On acceptance, retain the candidate and rerun
all final gates. This report and ignored evidence remain the audit trail.
