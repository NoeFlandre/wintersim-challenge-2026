# Round 1 contiguous same-service normalization v5

## Status

**PRE-RUN DESIGN FROZEN — no candidate simulation has started.** This report
is the tracked contract for one candidate run under the autonomous experiment
goal. It records the exact control, hypothesis, activation audit, tests,
preflight, decision rule, and restoration procedure.

## Hypothesis

The accepted v3 policy already avoids long safe detours when a disrupted
nominal service is estimated to recover sooner. Its implementation treats a
nominal shortest path with more than one booking edge as ineligible, even when
all adjacent edges use the same service-route object. In the real topology,
six identity-free observations had exactly that shape and would still prefer a
recovery hold under the existing timing comparison. Normalizing this contiguous
same-service path should protect those cargo flows without broadening the policy
to genuine multi-service transfers.

The strongest failure case is that a same-route multi-edge booking can encode a
real operational transfer or otherwise be semantically different from a single
booking; in that case the extension can add harmful holds. The full scorer, not
the audit, will decide.

## Exact candidate

Only `assign_associated_bookings` may return `False`; the other three hooks
remain unconditional `None` delegates. The candidate preserves all v3 gates:
new unbooked shipment, distinct origin/destination, active well-formed
disruption, deterministic shortest paths, safe path with at least two route
changes, complete finite positive route/fleet/timing data, and strict
`hold_hours < detour_hours`.

The only eligibility change is that a nominal path is accepted when it is
non-empty and either has one edge or has multiple edges whose route objects are
all identical. Recovery is the latest matching active constraint across every
nominal edge. Any mixed-route multi-edge nominal path delegates. The strategy
is read-only, deterministic, standard-library-only, fail-closed, and free of
scenario identities, I/O, randomness, wall-clock access, mutable globals, and
organizer imports.

## Fresh activation audit

The audit used a fresh `create_with_disruption()` context per derived timestamp,
called the organizer fallback route-preparation helper only as setup, then
evaluated all demand objects in context order without advancing the model or
writing Output. It sampled the midpoint of each integer day inside every valid
disruption window (50 timestamps, 19,000 demand-time observations).

- v3 control activations: 48;
- proposed candidate activations: 54;
- candidate-only activations: 6;
- candidate-only annual-TEU exposure proxy: 7,776;
- every candidate-only shape: nominal path 2 edges, safe path 3 edges, 2 safe
  route changes;
- observed mutation: none.

These are structural activation and exposure observations, not score
predictions. The ignored JSON audit is retained at
`.challenge/round1/results/contiguous_same_service_normalization_v5_20260811/activation_audit.json`.

## Fixed control and run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- layout: one worktree, one local branch (`main`), no push or publication;
- control: accepted v3 multi-transfer recovery hold;
- control loss: `19.084638612143134` over 72 periods;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- scenario: `create_with_disruption`;
- organizer seed: `2026`;
- `PYTHONHASHSEED`: `0`;
- warm-up: 140 days;
- measured horizon: 360 days;
- ATT interval: 5 days;
- required numbered periods: 72;
- candidate ATT evidence: `.challenge/round1/results/contiguous_same_service_normalization_v5_20260811/ATT_By_Statistics_Interval.csv`;
- candidate aggregate: `experiments/results/round1_contiguous_same_service_normalization_v5_20260811.json`;
- candidate log: `.challenge/round1/results/contiguous_same_service_normalization_v5_20260811/full_run.log`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

The active Output ATT is stale control evidence until a fresh completed run
writes it. Candidate bytes must be copied before scoring, sync, smoke, or
restoration.

## TDD and preflight

RED tests must demonstrate same-service multi-edge activation, later-edge
recovery, mixed-route delegation, malformed/inactive delegation, unchanged v3
behavior, no mutation, and real-context candidate-only activation. GREEN is
the minimum participant implementation. The required gates are locked uv
resolution/sync, Ruff format/lint, Ty, mypy, true non-integration coverage of
at least 90%, integration tests, Round 1 sync and byte comparison, smoke, two
byte-identical participant-only packages, restricted-material scans, one clean
worktree/branch, and no live simulator.

## One-run decision and restoration

Exactly one full candidate run is allowed. After launch no code, tests,
thresholds, documentation, or policy may change. A crash, timeout, missing
fresh ATT, wrong period count, equality, worsening score, or failed gate is
rejection. If rejected, preserve ignored evidence and commit this result,
revert candidate implementation/test commits with `git revert`, synchronize
the accepted v3 strategy, restore the pinned v3 ATT snapshot byte-for-byte,
re-score it at `19.084638612143134`, and rerun all final gates. No second
candidate, tuning, submission archive, push, merge, PR, or history rewrite is
authorized by this report.
