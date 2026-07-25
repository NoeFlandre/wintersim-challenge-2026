# Round 0 Safe-Shuttle Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and evaluate one deterministic recovery-shuttle response that preserves organizer fallback behavior while keeping one eligible empty vessel moving on a safe subcycle during an active disruption.

**Architecture:** `UserStrategy.create_alternative_service_routes` preserves the standard alternative-route lifecycle inside participant-owned code, then extends it only when an affected original route has no complete safe alternative for the active disruption key. Pure helper functions derive the active safe graph and deterministic shuttle plan; mutation helpers install fully planned routes and manage eligible empty vessels. All other hooks remain unconditional delegates.

> **Reviewed implementation deviation (2026-07-25):** The initial plan called
> organizer-owned `response_strategies.default_strategy`, but the mandatory
> packaging gate correctly rejected that unshipped module. RED tests were
> updated in commit `34ece05` to require a self-contained lifecycle. The final
> candidate imports only documented `maritime_data_context` entities and
> independently covers ordinary alternative creation, reservation, switching,
> restoration, and the recovery-shuttle extension. The historical task steps
> below preserve the original plan for auditability; this note governs the
> reviewed implementation.

**Tech Stack:** Python 3.11-compatible standard library, organizer-provided maritime entities and fallback strategy, pytest, Ruff, mypy, uv, and the local Round 0 integration environment.

---

### Task 1: Pin recovery-shuttle behavior with failing synthetic tests

**Files:**
- Create: `tests/unit/test_safe_shuttle_recovery.py`
- Create: `tests/integration/test_safe_shuttle_recovery_round0.py`
- Modify: `tests/unit/test_user_strategy_contract.py`

- [ ] **Step 1: Replace the baseline-only selector assertion**

Update `test_select_vessel_for_berth_returns_none_and_does_not_mutate` only if
needed to keep it as a no-op assertion. Keep all exact-signature tests.
`select_vessel_for_berth`, `assign_associated_bookings`, and
`adjust_bookings_before_cargo_handling` must still return `None`.

- [ ] **Step 2: Write synthetic organizer-shaped fixtures**

Create minimal `Port`, `Leg`, `Segment`, `Route`, `Vessel`, `Berth`,
`DisruptionPlan`, and `Context` classes. Use identity-based objects and ordered
lists. The route fixture must contain:

```python
safe_a -> safe_b -> blocked -> remote -> safe_a
safe_a -> safe_b -> safe_c -> safe_a
```

The source route uses the first sequence. The context graph also contains the
safe three-port cycle. The active plan closes `blocked`, making `remote`
unreachable from the safe strongly connected component.

- [ ] **Step 3: Write active-state and graph tests**

Add tests that import these future helpers:

```python
from response_strategies.user_strategy import (
    _active_disruption_state,
    _build_recovery_plan,
    _find_shortest_leg_path,
)
```

Cover:

```python
def test_active_interval_is_start_inclusive_end_exclusive(): ...
def test_safe_graph_excludes_closed_port_incident_legs(): ...
def test_safe_graph_excludes_congested_leg_by_identity(): ...
def test_shortest_path_ties_preserve_context_leg_and_port_order(): ...
def test_plan_uses_largest_mutually_reachable_source_anchor_component(): ...
def test_plan_starts_immediately_upstream_of_first_disrupted_segment(): ...
def test_plan_returns_none_for_fewer_than_two_mutually_reachable_anchors(): ...
```

The main plan assertion is:

```python
plan = _build_recovery_plan(context, source_route, closed_ports, congested_legs)
assert plan is not None
assert plan.start_port is safe_a
assert [(leg.departure_port, leg.arrival_port) for leg in plan.legs] == [
    (safe_a, safe_b),
    (safe_b, safe_c),
    (safe_c, safe_a),
]
```

- [ ] **Step 4: Write mutation and lifecycle tests**

Patch `DefaultStrategy.create_alternative_service_routes` with a recording
staticmethod in synthetic unit tests. Cover:

```python
def test_hook_invokes_default_once_and_returns_true(): ...
def test_hook_creates_one_valid_idempotent_recovery_route(): ...
def test_route_uses_existing_legs_and_consecutive_segment_indexes(): ...
def test_hook_does_not_reserve_an_arbitrary_vessel(): ...
def test_hook_switches_one_empty_source_vessel_at_shuttle_start(): ...
def test_hook_refuses_loaded_misplaced_foreign_and_duplicate_vessels(): ...
def test_three_other_hooks_remain_none(): ...
def test_module_has_no_mutable_global_state_or_forbidden_imports(): ...
```

For the successful switch:

```python
result = UserStrategy.create_alternative_service_routes(context, active_now, vessel)
assert result is True
shuttle = next(route for route in context.service_routes if route is not source_route)
assert vessel.assigned_service_route is shuttle
assert vessel.current_segment is None
assert vessel in shuttle.deployed_vessels
assert vessel not in source_route.deployed_vessels
assert all(segment.associated_leg in original_legs for segment in shuttle.segments)
```

- [ ] **Step 5: Run tests and verify RED**

Run:

```bash
uv run pytest tests/unit/test_safe_shuttle_recovery.py \
  tests/unit/test_user_strategy_contract.py -q
uv run pytest tests/integration/test_safe_shuttle_recovery_round0.py -q
```

Expected: collection fails because the recovery helpers do not exist. Confirm
that the failure is specifically missing candidate behavior, not fixture or
syntax errors.

- [ ] **Step 6: Commit RED tests**

```bash
git add tests/unit/test_safe_shuttle_recovery.py \
  tests/unit/test_user_strategy_contract.py \
  tests/integration/test_safe_shuttle_recovery_round0.py
git commit -m "test: define safe-shuttle recovery policy"
```

### Task 2: Implement the minimal safe-shuttle policy

**Files:**
- Modify: `submission/response_strategies/user_strategy.py`
- Modify: `submission/response_strategies/README.md`

- [ ] **Step 1: Add immutable planning types and active-state extraction**

Use only these top-level imports:

```python
import datetime as dt
import math
from dataclasses import dataclass
from typing import Any
```

Resolve `Segment`, `ServiceRoute`, and `DefaultStrategy` with local imports
inside the public route hook and pass the entity classes into the installation
helper. Do not cache them. This keeps the participant module importable in
public unit/CI environments where the private organizer tree is absent.

Define frozen local planning records:

```python
@dataclass(frozen=True)
class _DisruptionState:
    closed_ports: tuple[Any, ...]
    congested_legs: tuple[Any, ...]
    key: tuple[tuple[str, ...], tuple[tuple[str, str], ...]]


@dataclass(frozen=True)
class _RecoveryPlan:
    start_port: Any
    legs: tuple[Any, ...]
```

`_active_disruption_state(context, now)` must validate plan timing narrowly,
use `start <= now < end`, preserve identity-order collections, and build the
same sorted name-based disruption key as the organizer fallback.

- [ ] **Step 2: Implement deterministic safe graph helpers**

Add:

```python
def _is_safe_leg(leg, closed_ports, congested_legs) -> bool: ...
def _reachable_ports(start, safe_legs) -> tuple[Any, ...]: ...
def _find_shortest_leg_path(context, origin, destination, safe_legs): ...
def _unique_source_anchors(source_route, closed_ports) -> list[Any]: ...
def _largest_mutually_reachable_component(anchors, safe_legs) -> list[Any]: ...
```

Shortest paths initialize distances in `context.ports` order, choose the first
minimum-distance unvisited port, traverse safe legs in `context.legs` order,
and update predecessors only on a strict improvement.

- [ ] **Step 3: Implement complete pre-mutation shuttle planning**

`_build_recovery_plan` must:

```python
safe_legs = [
    leg for leg in context.legs
    if _is_safe_leg(leg, closed_ports, congested_legs)
]
anchors = _unique_source_anchors(source_route, closed_ports)
component = _largest_mutually_reachable_component(anchors, safe_legs)
```

Then choose the upstream safe departure port of the first unsafe source
segment, rotate the component to that anchor, join every consecutive pair
with `_find_shortest_leg_path`, and validate the final connected cycle before
returning `_RecoveryPlan`. Return `None` without mutation on any incomplete
plan.

- [ ] **Step 4: Install route and switch one eligible vessel**

Add:

```python
def _install_recovery_route(context, source_route, disruption_key, plan): ...
def _clear_unusable_pending_assignments(context, shuttle, current_vessel): ...
def _try_switch_empty_vessel(vessel, source_route, shuttle) -> bool: ...
```

The route identifier is the first unused
`f"{source_route.id}-RECOVERY-{index}"`. Set:

```python
route.source_service_route = source_route
route.disruption_key = disruption_key
route.is_participant_recovery_shuttle = True
```

Construct every `Segment` before appending the route and segment references.
The switch requires an empty vessel at the first segment's departure port and
performs the same collection updates as the organizer's safe route switch.

- [ ] **Step 5: Wire the public hook**

The public method must follow this order:

```python
DefaultStrategy.create_alternative_service_routes(context, now, vessel)
state = _active_disruption_state(context, now)
if state is None:
    return True
for source_route in tuple(context.initial_service_routes):
    if not _source_route_is_affected(source_route, state):
        continue
    matching = _matching_alternatives(context, source_route, state.key)
    shuttle = next(
        (route for route in matching
         if getattr(route, "is_participant_recovery_shuttle", False)),
        None,
    )
    if shuttle is None and matching:
        continue
    if shuttle is None:
        plan = _build_recovery_plan(
            context, source_route, state.closed_ports, state.congested_legs
        )
        if plan is None:
            continue
        shuttle = _install_recovery_route(context, source_route, state.key, plan)
    _clear_unusable_pending_assignments(context, shuttle, vessel)
    _try_switch_empty_vessel(vessel, source_route, shuttle)
return True
```

The three other methods continue returning `None`.

- [ ] **Step 6: Run focused tests and verify GREEN**

```bash
uv run pytest tests/unit/test_safe_shuttle_recovery.py \
  tests/unit/test_user_strategy_contract.py -q
```

Expected: all focused tests pass.

- [ ] **Step 7: Format, lint, typecheck, and commit**

```bash
uv run ruff format submission tests/unit/test_safe_shuttle_recovery.py
uv run ruff check submission tests/unit/test_safe_shuttle_recovery.py
uv run mypy submission
git add submission/response_strategies/user_strategy.py \
  submission/response_strategies/README.md \
  tests/unit/test_safe_shuttle_recovery.py \
  tests/unit/test_user_strategy_contract.py
git commit -m "feat: preserve service capacity with safe recovery shuttle"
```

### Task 3: Validate against the real Round 0 contract

**Files:**
- Modify if contract correction is required:
  `submission/response_strategies/user_strategy.py`
- Existing test: `tests/integration/test_safe_shuttle_recovery_round0.py`

- [ ] **Step 1: Review the already-red real-context integration test**

Load `submission/response_strategies/user_strategy.py` by file path after
adding the ignored Round 0 source and `o2despy` directories to `sys.path`.
Create `scenario_builders.create_with_disruption()`, choose a timestamp one
second inside the active window, and invoke the hook.

Assert:

```python
assert result is True
validate_alternative_route_strategy_result(context, snapshot)
custom = [
    route for route in context.service_routes
    if getattr(route, "is_participant_recovery_shuttle", False)
]
assert custom
assert all(
    segment.associated_leg in original_legs
    for route in custom
    for segment in route.segments
)
assert all(
    segment.sequence_index == index
    for route in custom
    for index, segment in enumerate(route.segments, start=1)
)
```

Call it again and assert the custom route identity list is unchanged.

- [ ] **Step 2: Run the integration test against the implementation**

```bash
uv run pytest tests/integration/test_safe_shuttle_recovery_round0.py -q
```

Expected: pass and create at least one valid participant shuttle. If it fails,
the output must identify a concrete organizer-contract mismatch.

- [ ] **Step 3: Correct a concrete contract mismatch only when Step 2 exposes one**

For a failing assertion, preserve the approved policy and modify only the
responsible helper. Rerun the exact failing test, the focused unit file, and
the integration file. Do not add a new policy or parameter.

- [ ] **Step 4: Commit the integration gate**

```bash
git add tests/integration/test_safe_shuttle_recovery_round0.py \
  submission/response_strategies/user_strategy.py
git commit -m "test: validate recovery shuttle on Round 0"
```

### Task 4: Run pre-experiment gates

**Files:**
- Modify: `docs/experiments/round0-safe-shuttle-recovery-v1.md`

- [ ] **Step 1: Record the fixed hypothesis and threshold**

Create the experiment record from the approved design, including the exact
algorithm, no-second-candidate rule, configuration, baseline score/SHA,
acceptance rule, and automatic restoration procedure.

- [ ] **Step 2: Run all gates**

```bash
uv lock --check
uv sync --locked --group dev --group simulation
uv run ruff format --check .
uv run ruff check .
uv run mypy src/wsc2026_tools submission
uv run pytest -m "not integration" \
  --cov=src/wsc2026_tools --cov=submission \
  --cov-report=term-missing --cov-fail-under=90
uv run pytest -m integration -q
uv run wsc2026 sync --round round0
cmp submission/response_strategies/user_strategy.py \
  .challenge/round0/source/response_strategies/user_strategy.py
uv run wsc2026 smoke --round round0
```

Expected: every command exits zero.

- [ ] **Step 3: Verify deterministic packaging**

Build Round 1 validation archives twice, hash the archives and sorted member
lists, confirm equality and that only participant-owned
`response_strategies/README.md` and `user_strategy.py` are present. Delete the
generated validation archive after recording the hashes.

- [ ] **Step 4: Commit the ready-to-run record**

```bash
git add docs/experiments/round0-safe-shuttle-recovery-v1.md
git commit -m "docs: prepare safe-shuttle recovery experiment"
```

### Task 5: Execute, score, decide, and restore if required

**Files:**
- Modify: `docs/experiments/round0-safe-shuttle-recovery-v1.md`
- Create ignored: `.challenge/round0/results/safe_shuttle_recovery_v1_2026/ATT_By_Statistics_Interval.csv`
- Create ignored: `experiments/results/safe_shuttle_recovery_v1_2026.json`

- [ ] **Step 1: Preserve the active fallback snapshot**

Verify before the run:

```text
Fallback score = 18.673577819840556
Fallback ATT SHA = 10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658
```

- [ ] **Step 2: Run exactly one complete candidate**

```bash
uv run wsc2026 run --round round0 --full
```

Monitor it to normal completion. Do not start an overlapping run.

- [ ] **Step 3: Preserve and score candidate evidence**

Copy the completed ATT CSV into the ignored candidate result directory,
compute SHA-256, require exactly 72 numbered periods, and run:

```bash
uv run wsc2026 score \
  --scenario-att .challenge/round0/source/Output/ATT_By_Statistics_Interval.csv \
  --baseline-att .challenge/round0/source/Output/Baseline_ATT_By_Statistics_Interval.csv \
  --json
```

- [ ] **Step 4: Apply the fixed decision rule**

Accept only when:

```python
candidate_score < 18.673577819840556 - 1e-9
```

If accepted, retain the implementation. If equal or worse:

1. Commit the result documentation.
2. Revert the implementation and integration commits using `git revert`.
3. Synchronize the restored no-op strategy.
4. Restore the active ATT from the pinned fallback snapshot.
5. Verify exact fallback SHA and score.

- [ ] **Step 5: Run final gates and commit the final record**

Rerun Task 4's full gates, deterministic packaging, restricted-material
history/tracked-file searches, `git diff --check`, and `git status`.
Commit the final result record. Leave a clean branch with either the accepted
candidate or the verified no-op fallback.
