# Round 1 recovery-aware direct-service hold v2

**Status: PRE-RUN REVIEW — one fixed candidate run is authorized.**

## Question being tested

When a disruption breaks a shipment's normal direct service, the organizer may
immediately book a much longer path that transfers between several liner
services. This experiment asks whether the shipment should instead remain at
its origin when the direct service is estimated to recover and deliver sooner
than that transfer path.

This is not a general rerouting replacement. It acts only on a new shipment
whose normal shortest route is one direct booking, whose currently safe
shortest route needs a real change between services, and whose hold estimate is
strictly shorter. All other decisions remain with the organizer.

## Exact participant behavior

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` can
return a non-`None` result. The other three hooks remain unconditional `None`
delegates.

During a well-formed active disruption, the policy builds two deterministic,
read-only route graphs from runtime objects:

- the **nominal graph** contains original service routes without disruption
  exclusions;
- the **safe graph** mirrors the fallback's closed-port, congested-leg, and
  active-alternative-route filters.

It finds shortest-distance paths using context port and route order for exact
ties. It proceeds only when the nominal path is one disruption-affected edge
and the safe path has at least two edges with an actual service-route change.
For each used route it derives mean vessel speed and headway from the deployed
fleet. Sailing time plus half a headway is charged on first boarding and after
each route change.

The policy compares, without rounding:

```text
hold = hours until the affected direct edge recovers
       + direct-path sailing and boarding time
detour = safe-path sailing, boarding, and transfer time
```

It returns the exact boolean `False` only when `hold < detour`. The organizer's
existing retry lifecycle then keeps the shipment at origin until another
booking attempt. Equality, missing data, malformed topology, invalid numbers,
an inactive window, or any structurally different path returns `None`.

The strategy never creates, clears, or edits bookings. It never mutates a
shipment, route, segment, leg, port, vessel, disruption plan, context
collection, or reverse reference.

## Challenge compliance

The complete runtime remains under `submission/response_strategies/` and uses
only the Python standard library. The implementation has exact public hook
signatures and contains no organizer import, filesystem/network/subprocess
access, environment or current-directory dependency, wall-clock access,
randomness, mutable module state, scenario name, port name, route identifier,
calendar date, seed table, or tuned threshold.

Stable port/leg names are used only to mirror the organizer disruption-key
contract. Congested physical legs are excluded by runtime object identity.
Lists and context order select every pathfinding tie; sets are membership-only.
The user's standing repository constraint is one canonical folder and only
`main`, so this experiment intentionally does not create the otherwise usual
worktree/experiment branch.

## TDD evidence

The approved design is commit `6f863fb`; its executable plan is `135258d`.
The RED contract is commit `f362706`. Against the untouched no-op adapter, the
focused run had exactly three expected behavioral failures and 21 passes:

- qualifying direct-versus-transfer decision;
- inclusive disruption-start decision;
- deterministic equal-distance tie choosing the slower transfer path from
  context port order.

Each failure was `None is False`, proving missing behavior rather than a broken
fixture. The implementation commit is `01e41c9`; real-context and coverage
tests are commit `d5f7d29`.

Focused GREEN has 38 synthetic policy tests. They cover the qualifying leg and
closed-port cases, exact equality, safe direct and same-service paths,
multi-booking nominal paths, active boundaries, context-order ties, eligible
and ineligible alternative routes, malformed/non-finite runtime shapes, exact
public signatures, forbidden capabilities, and complete no-mutation outcomes.

The real ignored Round 1 integration contract derives windows and OD pairs
from `create_with_disruption()` without hard-coded names. It found its first
qualifying sample at measured-relative day `204.5`, demand-order index `119`:

- active constraints: 4;
- nominal path: 1 edge;
- safe path: 5 edges with 3 route changes;
- estimated hold: `463.63749999999999` hours;
- estimated detour: `466.36431818181813` hours.

The public hook returned `False` and the complete observed context/shipment
snapshot was identical before and after. A dynamically derived time outside
all disruption windows returned `None` with the same immutability proof. These
figures establish activation and contract validity only; they are not a
simulation result or a performance prediction.

## Fixed run and decision contract

- round/scenario: `round1` / `create_with_disruption`;
- organizer seed: `2026`; process environment: `PYTHONHASHSEED=0`;
- warm-up: 140 days;
- measured horizon: 360 days;
- reporting interval: 5 days;
- required numbered ATT periods: 72;
- exact command:
  `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`;
- pinned fallback loss: `20.436668751255972`;
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`;
- pinned fallback mean ATT: `20.450972222222223` days;
- pinned fallback snapshot:
  `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`;
- candidate evidence directory:
  `.challenge/round1/results/recovery_aware_direct_service_hold_v2_20260809/`;
- ignored aggregate:
  `experiments/results/round1_recovery_aware_direct_service_hold_v2_20260809.json`.

The only acceptance expression is:

```text
candidate_cumulative_loss < 20.436668751255972 - 1e-9
```

It is applied to all 72 periods at full precision. Mean ATT is descriptive.
Equality, worsening, a crash, stale/incomplete output, an invalid period count,
or a failed gate is rejection.

## Pre-run verification record

The reviewed code/test HEAD is `d5f7d290c41e01b403eab982f20a9622cbed4060`.
The participant strategy SHA-256 is
`144493d651d0eb967dc8725a34997d118b22ce3db116ca5126699bb8ea2b743c`,
and the synchronized Round 1 runtime copy is byte-identical.

Fresh preflight gates passed on 2026-08-09:

- `uv lock --check` and `uv sync --locked --all-groups`: 29 packages resolved;
- Ruff format: 21 files already formatted; Ruff lint: all checks passed;
- `ty check src/wsc2026_tools submission`: all checks passed;
- mypy over `src/wsc2026_tools` and `submission`: 8 files, no issues;
- non-integration tests: 226 passed, 8 deselected, true coverage `90.71%`;
- real integration suite: 8 passed, 226 deselected;
- Round 1 sync and byte comparison: passed;
- one-day Round 1 smoke: `SMOKE_OK`;
- two validation packages: byte-identical SHA-256
  `0d53063a66238881fca922cae7a3ea5b6feba4936f061302554103494f337ddb`,
  5,867 bytes, containing only
  `response_strategies/README.md` and
  `response_strategies/user_strategy.py` beneath the required top directory;
- pinned and active fallback ATT: byte-identical SHA-256
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`;
- fresh fallback score: `20.436668751255972` over 72 periods;
- stale pre-run active ATT: 1,262 bytes, mtime epoch `1786143554`;
- `git diff --check`, tracked/reachable restricted-material scans, one-worktree /
  one-branch checks, and no-running-simulator check: passed.

The generated validation archive was moved out of the repository. No
submission, upload, push, merge, pull request, or history rewrite occurred.

## One-run evidence and restoration procedure

Immediately before launch, an ignored manifest will pin the exact launch HEAD,
strategy/runtime hashes, package hash/members, fallback score/hash, and stale
Output identity. Exactly one managed full run is allowed. No code, threshold,
policy, or test change is permitted after launch.

The raw log and fresh candidate ATT bytes must be copied to the precommitted
ignored evidence directory before scoring or synchronization. Completion
requires exit code zero, Day 360, Period 72, `Simulation completed.`, a fresh
ATT mtime/write, 72 numbered rows, and finite values.

If accepted, the candidate remains active and every final gate is rerun. If
rejected, the result is committed first; candidate integration, implementation,
and RED-test commits are reverted in reverse order with `git revert`; the
restored no-op adapter is synchronized; the pinned ATT is restored and rescored;
and every final gate is rerun. The design, plan, and result audit history remain.
No second candidate, tuning run, submission, push, merge, PR, or history rewrite
is part of this experiment.

