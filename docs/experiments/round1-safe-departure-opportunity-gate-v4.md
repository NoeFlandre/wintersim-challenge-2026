# Round 1 safe-departure opportunity gate v4

## Status

**PRE-RUN.** The approved candidate is implemented through strict RED -> GREEN
TDD. No full simulation has started. Exactly one full candidate run may begin
only after every mandatory preflight gate below passes and the immutable launch
identity is committed and recorded in the ignored manifest.

## Question being tested

The accepted multi-transfer recovery-hold v3 policy lowered Round 1 cumulative
resilience loss to `19.084638612143134`. It prevents a new shipment from taking
a fragmented safe detour when an interrupted direct service is estimated to
recover and deliver sooner. The accepted result also showed that some periods
became worse and that origin waiting increased during parts of the run.

Version 4 tests whether a hold should be limited to cases where the affected
direct service recovers within one complete headway of the first safe service
the shipment would otherwise board. The intended tradeoff is to retain the
high-exposure, short-wait protection from multi-transfer detours while avoiding
long origin holds that skip multiple safe departure opportunities.

## Read-only activation evidence

Before design approval, a non-simulation structural audit evaluated fresh
organizer contexts at daily midpoints of all active Round 1 disruption windows.
It did not advance the event model, write outputs, or establish causality.

Among 19,000 demand-time observations, accepted v3 would hold in 48 cases
covering five anonymous demands. The v4 gate retained 21 of those cases and
`54,585 / 77,478` (`70.45%`) of annual-TEU-weighted activation exposure. The
retained subset included every observed high-volume short-wait case. This is
only evidence that both sides of the gate are live; performance is unknown
until the one authorized run finishes.

## Exact candidate policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a non-`None` result. The other three hooks remain unconditional `None`
delegates.

The candidate retains every v3 condition:

- a new shipment with no booking chain and a distinct origin/destination;
- a well-formed relevant disruption active under `start <= now < end`;
- a deterministic one-edge nominal shortest path intersecting an active
  constraint;
- a complete deterministic safe path that mirrors organizer exclusions and
  active-alternative-route eligibility;
- at least two adjacent service-route changes in that safe path;
- positive finite topology, fleet, speed, distance, recovery, and timing data;
- the existing full-precision estimate:

  ```text
  hold_hours = remaining recovery wait + nominal boarding and sailing
  detour_hours = safe boarding, transfers, and sailing
  ```

Version 4 derives the first safe edge's live route profile using the existing
`_route_profile` helper. It returns the exact boolean `False` only when:

```text
hold_hours < detour_hours
and remaining_recovery_wait_hours <= safe_first_route_headway_hours
```

The headway boundary is inclusive. Equality between hold and detour still
delegates. A longer recovery wait, inactive disruption, structurally different
path, missing value, invalid number, malformed topology, or unexpected data
returns `None` so the organizer fallback remains authoritative.

The strategy is read-only, deterministic, standard-library-only, and
fail-closed. Both outcomes preserve all participant-visible objects and
collections. It has no scenario name, seed, calendar date, port name, route ID,
demand identity, tuned parameter, I/O, environment access, randomness,
wall-clock access, organizer import, or mutable module state.

## Alternatives rejected before implementation

1. A nominal-direct-route headway gate was less directly connected to the safe
   opportunity being declined.
2. A one-nominal-headway benefit-margin gate discarded most high-volume audit
   exposure.
3. Requiring at least three route changes made the policy nearly dormant.
4. Exact live vessel-phase prediction was rejected as substantially more
   complex after an earlier phase-aware candidate scored
   `24.21744876585007`.

## Approved design and plan

- design commit: `c957ff9`;
- implementation-plan commit: `154c412`;
- design:
  `docs/superpowers/specs/2026-08-10-round1-safe-departure-opportunity-gate-v4-design.md`;
- plan:
  `docs/superpowers/plans/2026-08-10-round1-safe-departure-opportunity-gate-v4.md`.

The user's explicit one-folder/one-branch constraint applies: all work occurs
in `/Users/noeflandre/wintersim-challenge-2026` on the sole local branch
`main`. No worktree or experiment branch is permitted.

## RED -> GREEN evidence

The RED contract is commit `cc33661`.

Against untouched accepted v3, the focused suite collected 43 tests. Exactly
two assertions failed and 41 passed:

- `test_recovery_wait_beyond_safe_first_headway_delegates_without_mutation`:
  accepted v3 returned `False` while v4 requires `None`;
- `test_real_round1_context_contains_qualifying_and_delegated_calls`: a derived
  real Round 1 long-wait case returned `False` while v4 requires `None`.

Both failures were the expected missing behavior (`assert False is None`).
There were no collection, import, fixture, mutation, or dormancy failures.

The minimal GREEN implementation is commit `1169632`. It adds one route-profile
lookup and one `wait_hours > safe_first_profile.headway_hours` delegation gate
inside `_should_hold`, plus participant prose. It does not change graph
construction, path selection, recovery selection, route-change counting,
service-time arithmetic, exception handling, public signatures, or any
non-target hook.

The same focused suite then passed `43 / 43` in `10.27s`. It includes:

- recovery wait below the headway: hold;
- recovery wait exactly equal to the headway: hold;
- recovery wait above the headway: delegate;
- both boundary outcomes preserve complete synthetic snapshots;
- real Round 1 retained and delegated cases derived without identities;
- malformed first-safe-route profile delegation;
- all inherited topology, deterministic-order, public-surface,
  forbidden-capability, fail-closed, and no-mutation contracts.

Changed-surface static gates also passed:

- Ruff format: 14 files already formatted;
- Ruff lint: all checks passed;
- Ty: all checks passed;
- mypy: no issues in the participant source.

## Fixed control and run identity

- active control: accepted multi-transfer recovery hold v3;
- control cumulative resilience loss: `19.084638612143134`;
- control period count: `72`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- candidate strategy SHA-256 after GREEN:
  `cb9106fe5484f56cd41f2f5b25b7957d9c5172f56ed405c09b888b22dfa5f2ec`;
- original no-op fallback loss: `20.436668751255972`;
- round/scenario: `round1` / organizer `create_with_disruption`;
- seed: `2026`;
- `PYTHONHASHSEED=0`;
- warm-up: `140` days;
- measured horizon: `360` days;
- reporting interval: `5` days;
- required numbered periods: `72`;
- exact run command:
  `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`;
- candidate evidence directory:
  `.challenge/round1/results/safe_departure_opportunity_gate_v4_20260810/`;
- ignored aggregate:
  `experiments/results/round1_safe_departure_opportunity_gate_v4_20260810.json`.

The sole acceptance expression is fixed before execution:

```text
candidate_cumulative_loss < 19.084638612143134 - 1e-9
```

Lower is better. Equality, invalid output, a crash, an incomplete run, or any
failed required gate is rejection. Mean ATT and individual periods are
descriptive only; the official cumulative resilience loss determines the
decision.

## Mandatory pre-run gate

Before the one full run, all of the following must pass at a clean immutable
launch commit and be recorded here and in an ignored atomic manifest:

1. `uv lock --check` and locked all-group synchronization;
2. repository-wide Ruff format/lint, Ty, and mypy;
3. non-integration tests with true branch coverage at least `90%`;
4. the complete real-context integration suite;
5. Round 1 participant/runtime synchronization and byte identity;
6. one-day smoke with `SMOKE_OK`, followed by identity and stale-ATT checks;
7. two byte-identical validation packages containing only the participant
   README and strategy, moved outside the repository;
8. fresh v3 control hash and score verification;
9. clean Git state, one worktree, one local branch, no live simulator, and
   clean restricted-material scans;
10. a committed pre-run record and an ignored manifest pinning all launch
    identities, output metadata, commands, gates, and the acceptance rule.

No full run is authorized while any item is missing or failed.

## One-run evidence and decision procedure

Immediately before launch, recheck the manifest, HEAD, strategy/runtime hashes
and byte identity, control snapshot, stale Output metadata, clean status, and
no-live-process evidence. Stream the sole run to the fixed ignored log and
monitor only that process. Never launch a duplicate.

Require exit zero, simulation Day 360, Period 72 (Days 356-360), the explicit
`Simulation completed.` marker, and a fresh ATT write. Copy the fresh source
ATT byte-for-byte to the candidate evidence directory before scoring, sync,
smoke, or restoration. Validate identical hashes, finite values, and 72
numbered periods.

Score only the preserved candidate against the authoritative Round 1 baseline
CSV. Record full-precision scorer output, all period losses, ATT/log hashes,
mean, timing, control comparisons, and the immutable decision in the ignored
aggregate and this report.

If accepted, v4 remains active and public current-best documentation is
updated. If rejected, first commit the result record, then revert the
implementation and RED-test commits in reverse order, synchronize v3, restore
the accepted v3 ATT snapshot byte-for-byte, require the pinned strategy/ATT
hashes and score, and rerun every final gate. No second v4 candidate, tuning,
push, upload, or submission is allowed.

## Preflight verification record

Pending. No full simulation has started.
