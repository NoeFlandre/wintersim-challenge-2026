# Recovery-Aware Direct-Service Hold v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate exactly one deterministic Round 1 policy that leaves a newly
generated shipment at origin when its disrupted one-booking direct service is
estimated to recover and deliver sooner than the organizer's currently safe
multi-route transfer path.

**Architecture:** Keep the complete participant implementation in
`submission/response_strategies/user_strategy.py`. Build two read-only route
graphs from the runtime context: an unrestricted original-service graph for the
nominal path and a fallback-compatible disruption-safe graph for the current
path. Use deterministic shortest-distance pathfinding and runtime-derived
headway/sailing estimates. Only `assign_associated_bookings` may return a
non-`None` value, and only the exact boolean `False`; the participant never
mutates simulation state. Work directly on the user's sole `main` checkout and
do not create a branch or worktree.

**Tech Stack:** Python 3.11+, standard-library-only participant code, `uv`,
pytest/pytest-cov, Ruff, `ty`, mypy, and the repository `wsc2026` CLI with the
local ignored Round 1 organizer source.

---

## Fixed experiment identity

- Repository: `/Users/noeflandre/wintersim-challenge-2026`
- Branch: `main` only
- Design commit: `6f863fb`
- Starting no-op strategy SHA-256:
  `b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`
- Round/scenario: `round1` / `create_with_disruption`
- Seed/process determinism: organizer seed `2026`; `PYTHONHASHSEED=0`
- Warm-up/measured/interval: 140 days / 360 days / 5 days
- Required numbered ATT periods: 72
- Pinned control loss: `20.436668751255972`
- Pinned control ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- Pinned control snapshot:
  `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`
- Candidate evidence directory:
  `.challenge/round1/results/recovery_aware_direct_service_hold_v2_20260809/`
- Aggregate record:
  `experiments/results/round1_recovery_aware_direct_service_hold_v2_20260809.json`
- Exact candidate command:
  `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- Acceptance expression:
  `candidate_cumulative_loss < 20.436668751255972 - 1e-9`

## Task 1: Freeze and verify the plan

**Files:**

- Create: `docs/superpowers/plans/2026-08-09-round1-recovery-aware-direct-service-hold-v2.md`
- Verify: `docs/superpowers/specs/2026-08-09-round1-recovery-aware-direct-service-hold-v2-design.md`

- [x] Confirm `git status --short --branch` shows only `main`, the design commit,
  and this new plan.
- [x] Confirm `git worktree list` contains only the canonical checkout and
  `git branch --format='%(refname:short)'` contains only `main`.
- [x] Review the spec and plan for temporary markers:

  ```bash
  rg -n '(TO)(DO)|(T)(BD)|(FIX)(ME)|(PLACE)(HOLDER)' \
    docs/superpowers/specs/2026-08-09-round1-recovery-aware-direct-service-hold-v2-design.md \
    docs/superpowers/plans/2026-08-09-round1-recovery-aware-direct-service-hold-v2.md
  git diff --check
  ```

- [x] Commit only the implementation plan:

  ```bash
  git add docs/superpowers/plans/2026-08-09-round1-recovery-aware-direct-service-hold-v2.md
  git commit -m "docs: plan recovery-aware direct-service hold experiment"
  ```

## Task 2: RED unit contract

**Files:**

- Create: `tests/unit/test_round1_recovery_aware_direct_service_hold_v2.py`
- Inspect: `tests/unit/test_user_strategy_contract.py`
- Test: `submission/response_strategies/user_strategy.py`

- [ ] Build local immutable-style fakes with `types.SimpleNamespace` for ports,
  legs, route segments, service routes, vessels, disruption plans, context,
  demand, and shipment. Route helpers must produce cyclic routes with unique
  integer `sequence_index` values and deployed vessels with positive finite
  `sailing_speed` values.
- [ ] Use this canonical qualifying topology:

  ```text
  nominal original route: O -> D, distance 100, speed 10
  active congested leg: O -> D
  safe original route A: O -> X, distance 1000, speed 10
  safe original route B: X -> D, distance 1000, speed 10
  decision time: 12 hours before recovery
  nominal service estimate: 10 sailing hours
  hold estimate: 22 hours
  safe transfer estimate: greater than 200 hours
  expected public decision: False
  ```

- [ ] Add public-hook tests for all approved behavior:

  1. qualifying direct-versus-transfer returns the exact boolean `False`;
  2. inclusive disruption start can return `False`;
  3. exclusive disruption end delegates with `None`;
  4. exact finite equality delegates with `None`;
  5. a safe direct one-edge path delegates;
  6. a nominal path with two bookings delegates;
  7. a nominal direct edge not intersecting the active disruption delegates;
  8. a two-edge safe path on the same route delegates because it is not a
     transfer;
  9. an existing booking chain delegates;
  10. a non-`None` current booking index delegates;
  11. identical origin/destination delegates;
  12. no active disruption delegates;
  13. invalid/missing plan, segment, distance, port, route, vessel, speed, or
      alternative-route metadata delegates;
  14. NaN and infinity in every arithmetic input delegate;
  15. deterministic equal-distance ties follow context port and route order;
  16. both `False` and `None` calls preserve a deep identity/value snapshot of
      shipment, demand, plans, routes, segments, legs, ports, and vessels.

- [ ] Add static contract tests that inspect the participant module and assert:

  - all four public methods are `staticmethod` objects with the exact organizer
    signatures;
  - only `assign_associated_bookings` can have a non-`None` return path;
  - no organizer import, filesystem/network/subprocess/environment/random/time
    access, module-level mutable collection, or broad `except Exception` /
    `except BaseException` exists;
  - imported modules are standard-library modules only.

- [ ] Run the focused file against the untouched no-op adapter:

  ```bash
  uv run pytest tests/unit/test_round1_recovery_aware_direct_service_hold_v2.py -q
  ```

  Record the exact failing test names. RED is valid only when the qualifying and
  inclusive-start expectations fail because the adapter returns `None`; fixture
  import/construction errors invalidate RED.

- [ ] Commit the genuine RED tests:

  ```bash
  git add tests/unit/test_round1_recovery_aware_direct_service_hold_v2.py
  git commit -m "test: specify recovery-aware direct-service hold policy"
  ```

## Task 3: GREEN participant implementation

**Files:**

- Modify: `submission/response_strategies/user_strategy.py`
- Modify: `submission/response_strategies/README.md`
- Test: `tests/unit/test_round1_recovery_aware_direct_service_hold_v2.py`

- [ ] Add only these standard-library facilities: `datetime`, `math`,
  `numbers`, `typing.Any`, and immutable tuple-like private records.
- [ ] Define immutable private records with the following information:

  ```python
  class _Constraint(NamedTuple):
      kind: str
      departure_name: str | None
      arrival_name: str
      recovery: datetime.datetime


  class _ActiveState(NamedTuple):
      constraints: tuple[_Constraint, ...]
      closed_port_names: frozenset[str]
      congested_leg_keys: frozenset[tuple[str, str]]
      disruption_key: str


  class _Edge(NamedTuple):
      departure: Any
      arrival: Any
      intermediate_ports: tuple[Any, ...]
      route: Any
      distance: float
      legs: tuple[Any, ...]
  ```

- [ ] Implement narrow scalar/object readers that accept positive finite real
  values, reject booleans, and return `None` for malformed data. Port matching
  uses stable non-empty `port.name`; runtime identity is retained in each edge.
- [ ] Implement `_active_state(context, now)` exactly as follows:

  - require `now` to be `datetime.datetime`;
  - convert numeric `start_day` and `duration` to windows anchored at
    `datetime.datetime.min`;
  - use `start <= now < end`;
  - accept a closed-port constraint only when `close_berth` is true and the
    plan unambiguously targets one berth/port;
  - accept a congested-leg constraint only when `congestion_multiplier > 1.0`
    and the plan unambiguously targets one leg;
  - reject malformed or ambiguous active plan shapes by returning `None`;
  - produce the fallback-compatible disruption key from active closed-port
    names and congested-leg name pairs in deterministic sorted order;
  - do not use a set to choose a port, route, edge, recovery, or tie.

- [ ] Implement ordered cyclic route reading:

  - require at least two route segments;
  - require every `sequence_index` to be a unique non-negative integer;
  - sort a copied list by `sequence_index` without mutating the route;
  - require every segment to have a valid port and associated leg;
  - require each leg to have positive finite distance and coherent departure /
    arrival port names.

- [ ] Enumerate every contiguous cyclic edge from each departure segment to
  each later arrival segment. Each edge stores all traversed legs, the final
  arrival port, intermediate arrival ports, route identity, and summed distance.
- [ ] Build the nominal edge list in `context.service_routes` order using only
  original routes where `source_service_route is None` and applying no active
  exclusions.
- [ ] Build the safe edge list in the same order using fallback-compatible
  rules:

  - original routes are eligible;
  - an alternative route is eligible only when its non-empty
    `disruption_key == active_state.disruption_key` and it has at least one
    deployed vessel;
  - exclude an edge containing an active congested leg;
  - exclude an edge whose final arrival or any intermediate arrival is an
    active closed port;
  - do not independently reject an edge because its departure is closed.

- [ ] Implement deterministic shortest-distance pathfinding:

  - use `context.ports` order for unvisited-node and equal-distance choices;
  - iterate eligible edges in route/edge enumeration order;
  - relax only for a strict lower finite distance, never `<=`;
  - use identity-based integer keys locally so unhashable organizer objects are
    supported;
  - return `None` for duplicate port identities, incomplete paths, invalid
    arithmetic, or predecessor cycles.

- [ ] Implement the structural gate before service-time estimation:

  - nominal shortest path has exactly one edge;
  - that edge contains an active congested leg or arrives/intermediately calls
    at an active closed port;
  - safe shortest path has at least two edges;
  - at least one adjacent safe edge changes route object identity.

- [ ] Implement route profiles and path service estimates:

  ```text
  mean_speed = sum(valid deployed-vessel speeds) / vessel_count
  route_cycle_distance = sum(all ordered cyclic route-leg distances)
  headway_hours = route_cycle_distance / sum(valid deployed-vessel speeds)
  edge_sailing_hours = edge.distance / mean_speed
  path wait = 0.5 * headway_hours on first boarding and each route change
  ```

  Every deployed vessel on a used route must have a positive finite speed. An
  empty deployed-vessel collection, invalid speed, invalid cycle, or non-finite
  intermediate result makes the decision delegate.
- [ ] Compute recovery as the latest end of every active constraint intersecting
  the single nominal edge. Compute full-precision estimates:

  ```text
  hold_hours = max(0, (recovery - now).total_seconds() / 3600)
               + nominal_path_service_hours
  detour_hours = safe_path_service_hours
  ```

  Return `False` only when both are positive finite and
  `hold_hours < detour_hours`; equality and every other state return `None`.
- [ ] Catch only the explicit narrow data-shape/arithmetic family at the public
  boundary: `AttributeError`, `IndexError`, `KeyError`, `TypeError`,
  `ValueError`, `ZeroDivisionError`, `FloatingPointError`, and `OverflowError`.
  Never catch `Exception` or `BaseException`.
- [ ] Keep `select_vessel_for_berth`, `create_alternative_service_routes`, and
  `adjust_bookings_before_cargo_handling` as unconditional `return None`.
- [ ] Update `submission/response_strategies/README.md` to describe the active
  experimental policy, read-only guarantee, and delegate conditions without
  claiming a performance result.
- [ ] Run focused GREEN and static gates:

  ```bash
  uv run pytest tests/unit/test_round1_recovery_aware_direct_service_hold_v2.py -q
  uv run ruff format submission/response_strategies/user_strategy.py \
    tests/unit/test_round1_recovery_aware_direct_service_hold_v2.py
  uv run ruff check submission/response_strategies/user_strategy.py \
    tests/unit/test_round1_recovery_aware_direct_service_hold_v2.py
  uv run ty check submission tests/unit/test_round1_recovery_aware_direct_service_hold_v2.py
  uv run mypy submission
  ```

- [ ] Commit the minimal GREEN implementation:

  ```bash
  git add submission/response_strategies/user_strategy.py \
    submission/response_strategies/README.md
  git commit -m "feat: hold direct-service cargo for disruption recovery"
  ```

## Task 4: Real Round 1 integration contract

**Files:**

- Create: `tests/integration/test_round1_recovery_aware_direct_service_hold_v2.py`
- Test: `submission/response_strategies/user_strategy.py`

- [ ] Mark the module `pytest.mark.integration` and skip with an actionable
  message when `.challenge/round1/source` is absent.
- [ ] Load the participant file by absolute path under a unique module name.
  Import organizer `main` before `default_strategy` to satisfy the organizer's
  runtime import order; do not change organizer modules or files.
- [ ] Construct a fresh `scenario_builders.create_with_disruption()` context.
  Derive candidate timestamps from actual plan windows using the 25%, 50%, and
  75% points. Do not hard-code a plan date, port name, route name, or OD pair.
- [ ] At each derived time, call the organizer fallback alternative-route hook
  once so the context matches the real initial-booking call state. Enumerate
  real demands in organizer order, construct a fresh real `Shipment`, and call
  the participant hook until the first qualifying `False` is found.
- [ ] Fail the test if no qualifying runtime case exists. For the found case,
  record only structural diagnostics in the assertion message: active plan
  count, nominal edge count, safe edge count, and route-change count.
- [ ] Before and after each participant call, snapshot and compare:

  - shipment scalar fields, booking list identities, and current booking index;
  - demand origin/destination identities;
  - context route, vessel, port, and disruption-plan collection identities;
  - route source/disruption metadata, segment/leg identities, deployed-vessel
    and associated-booking identities;
  - vessel assigned/pending/current route/segment/berth and carried-shipment
    identities;
  - disruption-plan target, timing, closure, and congestion fields.

- [ ] In a separate fresh context, derive a time strictly outside all real
  windows and prove a real shipment delegates with `None`, again with complete
  snapshot equality.
- [ ] Run focused integration and the complete suite:

  ```bash
  uv run pytest tests/integration/test_round1_recovery_aware_direct_service_hold_v2.py -q -vv
  uv run pytest -q
  uv run pytest -m "not integration" \
    --cov=src/wsc2026_tools --cov=submission --cov-report=term-missing \
    --cov-fail-under=90
  uv run pytest -m integration -q
  ```

- [ ] Commit the integration contract:

  ```bash
  git add tests/integration/test_round1_recovery_aware_direct_service_hold_v2.py
  git commit -m "test: verify recovery hold in Round 1 context"
  ```

## Task 5: Pre-run review, report, and gates

**Files:**

- Create: `docs/experiments/round1-recovery-aware-direct-service-hold-v2.md`
- Verify: all candidate source/tests/docs

- [ ] Write a `PRE-RUN REVIEW` report containing the approved hypothesis,
  exact policy, known limitations, RED/GREEN commit SHAs, observed real
  activation, no-mutation evidence, fixed run identity, pinned control, strict
  decision expression, evidence paths, and rollback sequence.
- [ ] Independently review the complete diff for challenge compliance. Reject
  preflight if participant code uses scenario/port/route constants, tuned
  thresholds, organizer imports, I/O, network, subprocess, environment,
  randomness, wall clock, mutable globals, unordered tie selection, or mutation.
- [ ] Run the exact preflight gates:

  ```bash
  uv lock --check
  uv sync --locked --all-groups
  uv run ruff format --check .
  uv run ruff check .
  uv run ty check
  uv run mypy
  uv run pytest -m "not integration" \
    --cov=src/wsc2026_tools --cov=submission --cov-report=term-missing \
    --cov-fail-under=90
  uv run pytest -m integration -q
  uv run wsc2026 sync --round round1
  cmp submission/response_strategies/user_strategy.py \
    .challenge/round1/source/response_strategies/user_strategy.py
  cmp submission/response_strategies/README.md \
    .challenge/round1/source/response_strategies/README.md
  uv run wsc2026 smoke --round round1
  git diff --check
  ```

- [ ] Package twice into a temporary directory, hash complete archive bytes,
  compare byte identity, and inspect members. Require exactly the approved
  `response_strategies` payload and no organizer/runtime material.
- [ ] Run README-prescribed restricted-material scans and require no tracked or
  reachable organizer ZIP, `Input/`, `Output/`, `main.py`, or
  `default_strategy.py`.
- [ ] Prove no `wsc2026 run`, organizer `main.py`, or known candidate process is
  active for this checkout.
- [ ] Re-hash the pinned fallback snapshot and active Output ATT. Score the
  pinned snapshot with `wsc2026 score --json`; require exactly 72 periods and
  loss `20.436668751255972` before launch.
- [ ] Record candidate HEAD, strategy SHA, package SHA/member list, active ATT
  hash/size/mtime, test counts, and all gate results in the report.
- [ ] Commit the report:

  ```bash
  git add docs/experiments/round1-recovery-aware-direct-service-hold-v2.md
  git commit -m "docs: record recovery hold pre-run review"
  ```

- [ ] Review the committed candidate one final time. Do not alter code, tests,
  thresholds, or policy after the run begins.

## Task 6: Execute exactly one full candidate run

**Files:**

- Preserve: `.challenge/round1/results/recovery_aware_direct_service_hold_v2_20260809/full-run.log`
- Produce: `.challenge/round1/source/Output/ATT_By_Statistics_Interval.csv`

- [ ] Create a unique `/tmp` pre-run backup containing the active ignored
  `response_strategies` runtime and current fallback ATT. Record hashes and
  mtimes without changing source.
- [ ] Create the evidence directory and start exactly this command once:

  ```bash
  PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full
  ```

  Stream stdout/stderr to the evidence log and preserve the process exit code.
- [ ] Poll the same process at intervals no longer than 60 seconds. Do not launch
  a duplicate, edit files, run smoke/sync, or score an incomplete Output file.
- [ ] Require all completion evidence:

  - process exit code zero;
  - `Period Result Output: Period 72 (Days 356-360)`;
  - `Output Simulation Day: 360`;
  - `Simulation completed.`;
  - a fresh ATT file whose mtime/hash differs from the recorded stale file.

- [ ] If any completion condition fails, classify the candidate as rejected and
  proceed directly to evidence preservation/restoration. Never invent or infer
  missing periods.

## Task 7: Preserve, score, and decide

**Files:**

- Preserve: `.challenge/round1/results/recovery_aware_direct_service_hold_v2_20260809/ATT_By_Statistics_Interval.csv`
- Create: `experiments/results/round1_recovery_aware_direct_service_hold_v2_20260809.json`
- Modify: `docs/experiments/round1-recovery-aware-direct-service-hold-v2.md`

- [ ] Before any sync, smoke, packaging, or restoration, copy the fresh ATT file
  byte-for-byte into the ignored evidence directory and hash both paths. Require
  byte equality at preservation time.
- [ ] Parse and validate exactly 72 numbered periods, finite ATT values, expected
  header, mean ATT, size, and mtime. Preserve the complete period values in the
  ignored aggregate JSON.
- [ ] Score only the preserved candidate against the Round 1 baseline with the
  repository scorer and retain the complete scorer JSON.
- [ ] Calculate without rounding:

  - candidate cumulative loss;
  - absolute and relative delta from `20.436668751255972`;
  - better/equal/worse period counts against the pinned fallback ATT;
  - candidate ATT and log SHA-256 values;
  - wall/simulation runtime and exact start/end timestamps.

- [ ] Apply only:

  ```text
  ACCEPTED iff candidate_loss < 20.436668751255972 - 1e-9
  ```

  Equality, worsening, missing/incomplete/non-finite output, crash, stale bytes,
  or a failed gate is `REJECTED`.
- [ ] Update the tracked report with exact evidence and an evidence-limited
  interpretation. Commit the result before any candidate revert:

  ```bash
  git add docs/experiments/round1-recovery-aware-direct-service-hold-v2.md
  git commit -m "docs: record recovery hold experiment result"
  ```

## Task 8: Retain or restore, then finish cleanly

**Files:**

- On rejection, restore: `submission/response_strategies/user_strategy.py`
- On rejection, restore: `submission/response_strategies/README.md`
- Update after result: `README.md`
- Update after result: `docs/round1-readiness.md`
- Update after result: `docs/challenge-overview.html`

- [ ] If accepted, retain candidate source/tests and synchronize the retained
  participant runtime once.
- [ ] If rejected, revert candidate commits in reverse dependency order using
  `git revert`, never manual recreation or history rewrite:

  1. integration-test commit;
  2. implementation commit;
  3. RED unit-test commit.

  Keep the design, plan, pre-run report, and result report commits.
- [ ] On rejection, run `uv run wsc2026 sync --round round1`, prove the active
  runtime strategy and README are byte-identical to restored submission files,
  require the no-op strategy SHA
  `b377e70d9744e897009d24236289ed5f36cf85d0499a484b7f896b30f1a3a135`,
  copy the pinned fallback ATT bytes back to active Output, require SHA
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`,
  and re-score exactly `20.436668751255972` over 72 periods.
- [ ] Update the public-facing Round 1 summary documents in plain language. Do
  not expose organizer files, private paths that reveal organizer data, raw
  runtime contents, or ignored evidence bytes.
- [ ] Run final gates in the final active state:

  ```bash
  uv lock --check
  uv sync --locked --all-groups
  uv run ruff format --check .
  uv run ruff check .
  uv run ty check
  uv run mypy
  uv run pytest -q
  uv run pytest -m "not integration" \
    --cov=src/wsc2026_tools --cov=submission --cov-report=term-missing \
    --cov-fail-under=90
  uv run pytest -m integration -q
  uv run wsc2026 smoke --round round1
  git diff --check
  ```

- [ ] Repeat deterministic packaging and restricted-material scans in the final
  state. Verify only one checkout/branch, no active process, clean status, and
  exact current HEAD.
- [ ] Commit only final public documentation with a Conventional Commit message.
  Do not push, merge, open a PR, submit an archive, rewrite history, tune the
  policy, or start a second candidate.
