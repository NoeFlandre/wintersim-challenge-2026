# Round 2 Port-Closure One-Transfer Half-Headway v2

**Status:** Approved for implementation and one full candidate run.

## Goal

Test one narrowly scoped extension of the accepted Round 2 policy while
preserving the current best result as the control. The extension targets only
new shipments whose direct nominal service is blocked by an active port
closure and whose safe replacement needs exactly one service-route change.

## Hypothesis

The accepted policy already holds a direct shipment when waiting for recovery
beats a safe one-transfer detour by more than one full safe-route headway. A
smaller but still explicit half-headway buffer should recover additional
closure-only shipments whose computed waiting advantage is positive and large
enough to cover half of the next safe sailing opportunity. Because the port is
closed rather than merely slow, these cases are expected to be safer than
one-transfer leg-congestion or mixed-constraint cases rejected in earlier
experiments.

The strongest failure mode is that queue, capacity, and vessel-reservation
interactions make the static half-headway estimate optimistic; the detour may
still deliver sooner for some early-window shipments.

## Exact participant delta

Only `UserStrategy.assign_associated_bookings` changes. Every existing v3
decision and the accepted Round 2 full-headway extension remains identical.
For a new shipment satisfying all existing guards:

1. The nominal shortest path has exactly one edge and that edge matches only
   active port-closure constraints.
2. The safe shortest path has at least two edges and exactly one service-route
   change.
3. All route, timing, speed, distance, and headway values are finite and
   positive.
4. The computed timing margin is strictly greater than half the maximum full
   departure headway of the safe-path routes.

The policy returns `False` (retain the shipment in the organizer's normal
origin waiting/retry lifecycle) for this additional subset. Existing
full-headway cases continue to return `False`; all other cases return `None`
and delegate unchanged. Equality delegates. No route, booking, vessel,
shipment, or context object is mutated by the participant method.

The policy is identity-free: it uses only supplied topology, active
constraints, route profiles, and the current timestamp. It contains no port or
route names, dates, seeds, output values, I/O, environment access, network,
subprocess, randomness, wall-clock calls, mutable cross-run state, or
organizer-owned imports. It remains standard-library-only and Python 3.11+
compatible.

## Structural evidence and scope

A fresh non-mutating Round 2 audit evaluated 166 structurally valid disruption
timestamps and all 380 demands at each timestamp (63,080 observations). The
accepted full-headway extension added 254 candidate-only decisions. The
half-headway predicate adds 76 further candidate-only observations, all
closure-only one-change cases, with an annual-TEU exposure proxy of 163,600.
This repeated structural exposure is not transported volume and is not a score
prediction. The audit advanced no model, wrote no organizer Output, and found
no participant mutation.

## Compliance

The candidate modifies only participant-owned files under
`submission/response_strategies/` for evaluation. It does not modify or bypass
event logic and never completes or moves cargo outside the normal logistics
process. No extra dependency is needed. The actual package must contain only
the participant README and strategy file.

## Validation plan

Use RED -> GREEN -> REFACTOR TDD. Add focused tests for the additional
half-headway case, strict equality and below-boundary delegation, preservation
of the existing full-headway decision, pure-leg and mixed-constraint
delegation, malformed/non-finite data fail-closed behavior, deterministic
ties, exact signatures, forbidden capabilities, and state immutability. Add a
real ignored-context audit proving candidate-only activation without model
advancement or Output writes.

Before launch, pass locked UV, Ruff, Ty, mypy, unrounded branch coverage of at
least 90%, all integrations, Round 2 sync/cmp, smoke, deterministic package
twice, restricted-material scans, clean Git, and no-live-process checks.

## Frozen run contract

- Repository layout: the existing canonical `main` worktree only.
- Round/scenario: `round2` / `create_with_disruption`.
- Seed: `2026`; `PYTHONHASHSEED=0`.
- Warm-up: 140 days; measured horizon: 360 days; ATT interval: 5 days;
  required periods: 72.
- Accepted control: current Round 2 full-headway candidate, verified from its
  pinned ATT snapshot before launch.
- Control loss: `35.1039547178493`.
- Control ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`.
- Acceptance rule (full precision, immutable):

  ```text
  candidate_loss < 35.1039547178493 - 1e-9
  ```

Run exactly one complete candidate. Preserve its fresh ATT and raw log before
any scoring, synchronization, smoke, packaging, or restoration. Equality,
worsening, invalid/stale output, incomplete completion markers, crash, timeout,
mutation, or a failed final gate rejects the candidate. On rejection, record
the result, revert only this experiment's implementation/tests, synchronize
the accepted control, restore the pinned control ATT, re-score it, and rerun
all final gates. No tuning, duplicate run, second candidate, push, merge, PR,
upload, submission, or history rewrite is authorized by this experiment.
