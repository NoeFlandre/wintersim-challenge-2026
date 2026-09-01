# Round 2: port-closure pending-route berth activation (v5)

**Status: PRE-RUN REVIEW — exactly one candidate run authorized after this
record.**

## Hypothesis

During an active port closure, the organizer fallback can reserve an empty
vessel for a disruption-safe alternative service route.  The normal berth
ranking does not explicitly activate that vessel when it is waiting at the
alternative route's first port.  Giving that already-reserved vessel the berth
first can start the safe route sooner and reduce delays for cargo affected by
the closure.  The policy is limited to closure-only periods and only changes a
selection when the fallback queue's first vessel is not the eligible pending
route vessel.

This is a new Round 2 experiment.  The accepted control remains the Round 2
full-headway port-closure recovery hold; all booking, route-construction, and
in-transit policies remain unchanged.

## Exact participant policy

Only `UserStrategy.select_vessel_for_berth` may return a vessel.  It will:

1. require a well-formed active disruption containing at least one closed port
   and no active congested leg;
2. validate the waiting queue as an ordered list/tuple of unique vessel
   objects;
3. find the first waiting vessel that is empty, has a non-empty pending
   alternative route with a valid lowest sequence segment, whose first
   segment departs the requested berth port by object identity, and whose
   route's disruption key matches the active disruption key; and
4. return that original vessel only when it is not already the first queue
   member.  Otherwise it returns `None`, delegating to the organizer fallback.

Malformed or ambiguous state, inactive or mixed disruptions, a missing route,
carried cargo, duplicate sequence indexes, an invalid pending route, or no
eligible queue member delegates without mutation.  The other three hooks remain
unconditional `None` delegates.  The implementation is deterministic,
standard-library-only, read-only, and does not use names, dates, seeds, files,
environment variables, randomness, or organizer imports.

## Compliance boundary

The returned object is always an original member of the organizer's waiting
queue.  The strategy does not alter queues, routes, vessels, cargo, ports,
berths, context, or pending assignments.  It does not bypass transportation or
complete a shipment.  A non-`None` result is used only by the organizer's
existing berth-assignment path.

## Pre-run review

The design was committed before the candidate implementation.  RED unit and
real-context integration tests failed only because the no-op selector returned
`None`; the implementation then passed all focused tests.  Candidate commits
are `2429af5` (implementation) and `853b2ac`/`702d7de` (failure-mode tests and
formatting).  No organizer file was modified.

The fresh non-mutating audit used every valid Round 2 disruption timestamp,
created alternative routes only as setup, and evaluated fresh real objects.
It observed 21 closure-only timestamps and 14 candidate-only selections: the
pending alternative vessel at Shanghai was selected while the fallback chose a
different queue member.  The audit reported `no_mutation=true`,
`model_advanced=false`, and `output_written=false`.  This is structural
activation evidence, not a prediction of the full trajectory.  Its ignored
JSON and script are under
`.challenge/round2/results/port_closure_pending_route_berth_v5_20260901/`;
the JSON SHA-256 is
`7de7df1aaa0343ca4647215e40998d93ec1a85281a025165165acc09a0aaf138a52`.

At the review checkpoint the participant and synchronized Round 2 runtime
files are byte-identical with strategy SHA-256
`1c7de2a1e6a59a6a24d446fdb048cd1c609aa19b66802f7dd539539f03e3c82a`.
Locked UV resolution/sync, Ruff format/lint, Ty, mypy, non-integration tests
(`248` passed; `90.70%` branch coverage), integration tests (`9` passed),
Round 2 sync/cmp, smoke, and restricted-material scans passed.  Two packages
for the actual team `OrtolanForever` were byte-identical, with SHA-256
`b335413b1d0a438fc088ef256e4b5acb2650605736e57f9ec3c176f70278bc58`; each
contains only `response_strategies/README.md` and `user_strategy.py`.  The
active stale Output ATT remains the pinned control SHA
`3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5` (1,262
bytes; mtime `1788224146`).  No simulator process is running and the tracked
worktree is clean before this documentation commit.

The exact launch command, after the final manifest is written, is:

```bash
PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache uv run wsc2026 run \
  --round round2 --full \
  > .challenge/round2/results/port_closure_pending_route_berth_v5_20260901/full_run.log 2>&1
```

The non-overwriting pre-run manifest will pin the final HEAD, hashes, package,
control/baseline scores, stale Output metadata, audit evidence, and this
acceptance expression.  No full run has occurred for v5 at this checkpoint.

## Fixed Round 2 run contract

- round/scenario: `round2` / `create_with_disruption`
- seed: `2026`; `PYTHONHASHSEED=0`
- warm-up: `140` days; measured horizon: `360` days
- ATT interval: `5` days; required periods: `72`
- accepted control loss: `35.1039547178493`
- accepted control ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`
- authoritative Round 2 baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`
- strict acceptance expression:
  `candidate_loss < 35.1039547178493 - 1e-9`

The pinned control snapshot is kept privately at
`.challenge/round2/results/control_v3_20260831/ATT_By_Statistics_Interval.csv`.
Candidate evidence belongs only under the ignored directory
`.challenge/round2/results/port_closure_pending_route_berth_v5_20260901/`.
No organizer source, input, output, archive, or private evidence may be
tracked or packaged.

## TDD and review gate

Commit this design before implementation.  Add RED unit tests for the
closure-only gate, queue order, pending-route identity, stale/malformed route,
carried-vessel, active-boundary, mixed-disruption, no-mutation, and four-hook
contracts.  Add a real Round 2 integration assertion using fresh organizer
objects and a candidate-only pending-route selection.  Implement the smallest
policy, then make the tests GREEN and run all quality gates.

Before any full run, perform a fresh non-mutating activation audit over valid
Round 2 disruption timestamps.  It may construct fresh contexts and call the
organizer route builder, but it must not advance a model, write `Output`, or
alter the context after each observation.  Record candidate-only selection
differences, queue/route identities, hashes, and limitations in ignored JSON.
The audit is a GO gate only when it has positive candidate-only activations and
no mutation/output writes; it is not a score prediction.

The pre-run manifest must pin the exact HEAD, strategy/runtime hashes, control
and baseline hashes/losses, package hash and members, audit hash, stale Output
metadata, exact command, and acceptance rule.  Run exactly one monitored full
simulation after all lock/sync, Ruff, Ty, mypy, coverage, integration, sync,
smoke, deterministic package, restricted-material, diff, and process gates pass.

## Rejection and restoration

Preserve the fresh ATT and raw log before scoring or any overwrite.  Require
exit 0, Day 360, Period 72, explicit completion, a fresh CSV, and a full
72-period score.  Equality, worsening, invalid output, crash, or failed final
gate is rejection.  Commit the result report before using `git revert` for
candidate code/tests, synchronize the accepted control, restore the pinned
control ATT by provenance-preserving copy, re-score the exact control loss, and
rerun every final gate.  Do not tune, rerun, change the threshold, launch a
second candidate, push, merge, submit, or rewrite history under this
experiment.  If accepted, retain the candidate, document the evidence, rerun
final gates, and leave the clean participant package active.
