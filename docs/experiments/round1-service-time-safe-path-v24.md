# Round 1 service-time safe-path refinement v24

**Status: DESIGN FROZEN — pre-code activation audit passed; no candidate
implementation or full simulation has started.**

This is one separately named experiment from the accepted Round 1 v3 control.
It tests whether v3 sometimes holds cargo only because it measures the safe
detour's *distance-shortest* path, even though another safe path would complete
faster when sailing time and service-route headways are considered.

## Control and decision rule

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and one local branch: `main`;
- round/scenario: `round1` / `create_with_disruption`;
- organizer seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon: `140` / `360` days;
- ATT interval / required numbered periods: `5` days / `72`;
- accepted v3 participant strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- accepted v3 ATT snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- accepted v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- accepted v3 cumulative resilience loss: `19.084638612143134`;
- authoritative Round 1 baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- immutable acceptance expression:
  `candidate_loss < 19.084638612143134 - 1e-9`.

Equality, worsening, invalid or stale output, an incomplete run, mutation, a
failed gate, or a crash is rejection. The candidate ATT and raw log must be
preserved before scoring or restoration. No tuning or second candidate belongs
to v24.

## Evidence and hypothesis

The accepted v3 policy retains a new shipment at origin when its disrupted
one-booking direct service is estimated to recover sooner than the shortest
safe path requiring at least two service-route changes. The current helper
selects both nominal and safe paths by total sailing distance, then estimates
service time for the selected path.

The private, read-only v24 oracle evaluates the safe graph with a deterministic
service-time cost instead: sailing time (`distance / mean fleet speed`) plus
half the route headway whenever the path enters a different service route.
The nominal path and recovery estimate remain unchanged. A v24 decision keeps
the v3 hold only when this fastest safe path requires at least two route changes
and `recovery_wait + nominal_service_hours < fastest_safe_service_hours`.
Otherwise it delegates with `None`. This is a single semantic refinement; it
does not add one-transfer holds or alter any other hook.

The rationale is bounded and identity-free: a distance-shortest detour can
contain transfers that a faster direct safe service avoids. The full scorer,
not the activation count or mean ATT, decides whether correcting this
classification improves the scenario.

### Candidate scorecard

| Dimension | Score | Reason |
| --- | ---: | --- |
| Adjacent evidence | 1/2 | The audit directly exposes a v3 subset, while broad pure-congestion suppression was harmful; this is a new, narrower distinction. |
| Candidate-only activation | 2/2 | Ten control-only observations are reproducibly exposed, with a 45,828 annual-TEU structural exposure proxy. |
| Call-site semantic fit | 2/2 | The change remains at the initial-booking hold decision, where v3 already compares recovery and safe-detour time. |
| Upside/downside | 2/2 | It vetoes only apparent false-positive holds whose fastest safe path has zero route changes; all existing v3 holds otherwise remain. |
| Hidden-scenario generalization | 2/2 | The rule uses runtime topology, distance, speed, fleet, and headway data, not scenario identities or dates. |
| Implementation safety | 1/2 | A stateful Dijkstra over supplied objects is more code than the current distance helper, but can be deterministic, read-only, and fail closed. |
| Novelty | 2/2 | No prior full experiment selected safe paths by service-time cost. |
| Behavioral testability | 2/2 | Synthetic direct-fast/long-distance and multi-transfer cases plus a real-context candidate-only activation are testable before a run. |

The scorecard selects this candidate over further TEU, margin, route-reentry,
berth-priority, or in-transit variants already rejected or shown dormant.

## Pre-code activation audit

The immutable private audit is
`.challenge/round1/results/service_time_safe_path_v24_20260819/activation_audit.json`
and its read-only driver is in the same ignored directory. It created a fresh
organizer context at the midpoint of every valid integer disruption day and
evaluated every demand in context order: `50` timestamps and `19,000`
observations. Organizer route preparation was disposable setup only.

The audit result is `go: true`:

- v3 control activations: `48`;
- v24 oracle activations: `38`;
- candidate-only activations: `0`;
- control-only activations: `10`;
- control-only annual-TEU exposure proxy: `45,828`;
- every control-only shape: nominal path `1` edge, fastest safe path `2`
  edges, and `0` service-route changes;
- all calls were non-mutating; no model event advanced;
- the Round 1 Output ATT remained byte-identical at SHA-256
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- no Output file was written.

These are structural reachability facts, not performance evidence. The audit
does not model queues, capacity competition, event history, or downstream
consequences, and repeated demand-time observations are not unique cargo
volume.

## Exact participant policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
change. The other three hooks remain unconditional `None` delegates.

The candidate preserves every v3 precondition: a new unbooked shipment,
distinct origin and destination, a well-formed active disruption, a nominal
shortest path of exactly one edge intersecting the active constraint, a
complete safe graph, finite positive route/fleet/speed/distance/recovery data,
and the strict timing comparison. The only changed step is safe-path choice:

1. build the same nominal and disruption-safe edge graphs as v3;
2. choose a deterministic minimum service-time safe path using context port
   order, route order, and edge order for equal-cost ties;
3. require at least two service-route identity changes on that path;
4. return `False` only when recovery wait plus nominal service hours is
   strictly less than the chosen safe-path service hours;
5. return `None` for a faster safe direct/single-route path, malformed data,
   missing data, non-finite values, or any uncertainty.

The implementation must be standard-library-only, read-only, deterministic,
identity-free, and fail closed. It must not use I/O, environment or process
access, wall-clock time, randomness, mutable module state, organizer imports,
hard-coded ports/routes/dates/seeds, or output/scorer manipulation.

## RED → GREEN requirements

Before production code, add focused behavioral tests that fail against the
untouched v3 implementation only because:

- a safe direct route that is longer by distance but faster by service time
  must delegate instead of returning the v3 hold;
- a genuine multi-transfer fastest safe path retains the v3 hold;
- equal service-time ties are deterministic and follow the documented context
  order;
- malformed route, fleet, speed, distance, port, or graph data delegates
  without mutation;
- all public signatures, non-target hooks, and forbidden-capability checks
  remain unchanged.

Add or update one real Round 1 integration contract that finds the audited
control-only topology, verifies v24 delegates there, verifies an existing
multi-transfer v3 hold remains `False`, and snapshots complete state before
and after each call. Commit the RED tests before implementation, then make
the smallest participant-only implementation and prove focused GREEN.

## Preflight and one-run contract

Before any operational run, require all of the following from the frozen
candidate:

- `uv lock --check` and `uv sync --locked --all-groups`;
- Ruff format/check, `ty`, and mypy;
- non-integration tests with true branch coverage at least `90.00%`;
- all integration tests;
- Round 1 synchronization and byte-identical participant/runtime strategy and
  README;
- one-day Round 1 smoke with `SMOKE_OK`;
- two deterministic participant-only packages with allowlisted members only;
- fresh v3 control score/ATT identity;
- clean Git state, one worktree, one `main` branch, and restricted-material
  scans;
- proof that no simulator, probe, or organizer process is live;
- a non-overwriting manifest pinning the exact candidate HEAD, participant and
  runtime hashes, package hash/members, control and baseline hashes, stale
  Output metadata, run configuration, acceptance expression, and gate results.

Run exactly once, with no changes after launch:

```text
PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache-v24 \
uv run wsc2026 run --round round1 --full
```

Monitor the same process to exit `0`, Day 360, Period 72, `Simulation
completed.`, and a fresh ATT write. Copy the fresh ATT and raw log to the
predeclared ignored directory before scoring, synchronization, smoke,
packaging, or restoration. Score exactly 72 numbered periods against the
authoritative baseline and apply the expression above without rounding.

Candidate evidence paths:

- `.challenge/round1/results/service_time_safe_path_v24_20260819/ATT_By_Statistics_Interval.csv`;
- `.challenge/round1/results/service_time_safe_path_v24_20260819/full_run.log`;
- `experiments/results/round1_service_time_safe_path_v24_20260819.json`.

## Rejection and restoration

On equality, worsening, invalid output, crash, incomplete run, or failed gate,
commit this result record first, then revert only the v24 implementation and
candidate-test commits in reverse order with `git revert`. Synchronize the
restored v3 participant files, restore the pinned v3 ATT snapshot byte-for-
byte, re-score it to exactly `19.084638612143134`, and rerun every final gate.
Never recreate the v3 strategy manually, tune after the result, or run a
second candidate inside v24.

If accepted, retain the candidate, rerun every final gate, and document the
new score and hashes. In either case leave the sole `main` worktree clean.
No push, merge, pull request, upload, submission, archive publication, or
history rewrite is part of this experiment.
