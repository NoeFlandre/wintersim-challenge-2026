# Round 1 safe-departure opportunity gate v4

## Status

**REJECTED — COMPLETE; V3 RESTORED.** Exactly one authorized candidate run
completed successfully, but its cumulative resilience loss was
`25.943159029801052`, which is worse than the immutable v3 control
`19.084638612143134`. The fresh evidence was preserved and audited, and the
accepted v3 strategy and output are again active.

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

Completed on 2026-08-10 before any full simulation:

- `uv lock --check`: 29 packages resolved;
- `uv sync --locked --all-groups`: 29 resolved and 25 checked;
- Ruff format: 21 files already formatted;
- Ruff lint: all checks passed;
- Ty: all checks passed;
- mypy: no issues in 8 source files;
- non-integration suite: 230 passed and 8 deselected;
- true branch coverage: `90.89%`, above the fixed `90%` floor;
- real-context integration suite: 8 passed and 230 deselected;
- Round 1 synchronization copied exactly the participant README and strategy;
- participant/runtime README and strategy were byte-identical after sync;
- one-day Round 1 smoke: `SMOKE_OK` and `smoke: OK`;
- participant/runtime strategy remained byte-identical after smoke at SHA-256
  `cb9106fe5484f56cd41f2f5b25b7957d9c5172f56ed405c09b888b22dfa5f2ec`;
- smoke left the stale accepted Output unchanged at 1,262 bytes, mtime epoch
  `1786355147`, and SHA-256
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- two Round 1 validation packages were byte-identical SHA-256
  `7f6f10e5b679a3cac538662608871dfba51a37b6a4de24cde46705d57736d3b4`,
  6,110 bytes, and contained only:
  `Round1_NoeFlandre/response_strategies/README.md` and
  `Round1_NoeFlandre/response_strategies/user_strategy.py`;
- both candidate validation archives were moved outside the repository to
  `/tmp/wsc-v4-package.9o2s8e/` and were not uploaded or submitted;
- the accepted v3 snapshot freshly rescored to exactly
  `19.084638612143134` over 72 periods;
- accepted v3 snapshot and stale active Output remained byte-identical at
  SHA-256 `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- `git diff --check` passed and the tracked tree was clean before this report
  update;
- exactly one worktree and one local branch (`main`) exist;
- no live WSC or Round 1 organizer simulation process was found;
- tracked-file and reachable-history scans found no restricted organizer ZIP,
  restricted blob, `Input/`, `Output/`, organizer `main.py`, or
  `default_strategy.py`.

The commit containing this completed gate record is the immutable launch HEAD.
The ignored manifest must record its full SHA, candidate/runtime hashes,
package identity, control evidence, stale Output metadata, run configuration,
acceptance expression, and no-live-process proof before execution. Any mismatch
at the immediate pre-launch recheck cancels authorization without starting the
simulator.

## Full-run result

Exactly one candidate simulation ran from immutable launch HEAD
`2c102c6a64e42adf845e6202a96cec2999f0e461` with participant/runtime strategy
SHA-256
`cb9106fe5484f56cd41f2f5b25b7957d9c5172f56ed405c09b888b22dfa5f2ec`.
The immediate pre-launch recheck matched the manifest: tracked status was
clean, participant/runtime bytes matched, the stale Output and v3 control
snapshot both had SHA-256
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`,
and no other WSC simulator was live.

- start UTC: `2026-08-10T10:37:59Z`;
- finish UTC: `2026-08-10T11:05:54Z`;
- simulator runtime: `00:27:18`;
- process exit: `0`;
- terminal evidence: warm-up completed, Day 360, Period 72 (Days 356–360),
  Output Simulation Day 360, and `Simulation completed.`;
- fresh candidate ATT SHA-256:
  `27ef8f6ccbda22bed498d8f4cb161ead2a5e0d01659a932c7ea8fb7a0ade5e42`;
- fresh candidate ATT size and source mtime: 1,262 bytes and epoch
  `1786359931`, newer than the pinned stale epoch `1786355147`;
- numbered periods: 72, plus two expected organizer summary rows;
- exact numbered-period mean ATT: `20.79875` days;
- full-run log SHA-256:
  `1c544974ed7a40bf98517e021787b22c1595ca99e2984e81234fe7140fa89a9c`.

Before scoring, synchronization, smoke, or restoration, the fresh source ATT
was copied byte-for-byte to the ignored candidate evidence path. Source and
snapshot hashes matched, all numbered values were finite, the CSV header was
canonical, and no simulation process remained.

## Score and decision

The repository scorer was run only on the preserved candidate ATT against the
authoritative Round 1 baseline ATT. It produced:

- candidate cumulative resilience loss: `25.943159029801052`;
- accepted v3 cumulative resilience loss: `19.084638612143134`;
- candidate minus v3: `+6.8585204176579175`;
- relative change: `+35.937386906000896%` (worse);
- candidate periods versus v3: 8 better, 20 equal, 44 worse;
- period count: 72.

The immutable decision expression is false:

```text
25.943159029801052 < 19.084638612143134 - 1e-9
```

**Decision: REJECTED.** The result directly rejects this exact implementation
under the fixed public Round 1 scenario and seed. It does not prove that every
long wait is beneficial: the experiment did not instrument per-shipment causal
flows, and 8 periods improved. It does show that removing the selected long
holds caused large aggregate degradation, so v3's long-hold subset should not
be removed by this headway rule.

## Preserved private evidence

- pre-run manifest:
  `.challenge/round1/results/safe_departure_opportunity_gate_v4_20260810/pre_run_manifest.json`;
- candidate ATT snapshot:
  `.challenge/round1/results/safe_departure_opportunity_gate_v4_20260810/ATT_By_Statistics_Interval.csv`;
- raw full-run log:
  `.challenge/round1/results/safe_departure_opportunity_gate_v4_20260810/full_run.log`;
- aggregate result:
  `experiments/results/round1_safe_departure_opportunity_gate_v4_20260810.json`.

All evidence paths are ignored and untracked. No second candidate, tuning,
push, upload, email, archive submission, or history rewrite occurred.

## Restoration and final verification

The rejection record was committed before restoration. Commit `54dfee5`
reverted implementation commit `1169632`, then commit `e5373f4` reverted RED
contract commit `cc33661`, exactly in the predeclared reverse order. The Round
1 participant files were synchronized afterward, and the accepted v3 ATT
snapshot was copied byte-for-byte back to the active organizer Output.

The restored state was independently re-audited:

- participant and runtime strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- active and pinned v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- freshly re-scored active loss: `19.084638612143134` over 72 periods;
- candidate ATT and log SHA-256 values, score, delta, relative change, period
  comparison, candidate strategy blob, manifest, and ignored aggregate all
  agree;
- no restoration simulation, second candidate, tuning, or replay ran.

All final gates passed after restoration:

- locked `uv` checks completed with 29 resolved packages and 25 checked;
- Ruff format/lint, Ty, and mypy passed;
- non-integration suite: 227 passed and 8 deselected, with `90.84%` true branch
  coverage;
- integration suite: 8 passed and 227 deselected;
- participant/runtime synchronization and byte comparison passed;
- one-day smoke emitted `SMOKE_OK` and did not change the restored strategy or
  ATT hashes;
- the active Output freshly re-scored to the exact accepted v3 result after
  smoke;
- two final packages were byte-identical SHA-256
  `5f63fce47a5dc3e5b84cc66660b7772826bdc9b169466796f9d0e327b6068d19`,
  5,907 bytes, and contained only
  `Round1_NoeFlandre/response_strategies/README.md` and
  `Round1_NoeFlandre/response_strategies/user_strategy.py`;
- the validation copies remain outside the repository under
  `/tmp/wsc-v4-final-package.DQ1rEA/` and were not uploaded or submitted;
- Git diff, one-worktree/one-branch, no-live-simulator, and restricted-material
  checks passed.

The repository therefore retains v3 as the current best. Version 4 is a
complete, reproducible rejected experiment, not an active strategy.
