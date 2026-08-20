# Round 1 pure-leg low-margin recovery-hold guard v29

## Status

**PRE-RUN REVIEW.** This document freezes one candidate policy. No full
simulation has been run for v29 and no score is claimed. The accepted v3
strategy remains the control and must be restored if this candidate is
rejected.

## Goal and fixed control

Round 1 measures cumulative resilience loss over 72 five-day periods after a
140-day warm-up and 360 measured days. Lower loss is better. The active,
accepted v3 control is:

```text
control loss = 19.084638612143134
control ATT SHA-256 = 5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a
participant SHA-256 = f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded
```

The only acceptance rule is:

```text
candidate_loss < 19.084638612143134 - 1e-9
```

Equality, a worse result, an invalid or stale ATT file, an incomplete run, a
crash, or a failed final gate is rejection.

## Hypothesis

The v3 control holds new cargo at its origin when a disrupted direct service
is estimated to recover sooner than a safe path requiring at least two
service-route changes. That rule is already the best result found, but it
also holds cargo during pure leg congestion, where the disruption does not
close a port and the safe route may be a viable alternative.

For a pure leg constraint, if the estimated advantage of waiting is smaller
than one departure headway on the first safe route, the waiting decision is
fragile: a normal fallback assignment may catch the next safe sailing rather
than wait for recovery. Delegating only these marginal pure-leg cases may
avoid unnecessary origin dwell while retaining every port-involved hold and
every stronger pure-leg recovery advantage.

This is a structural, context-derived policy, not a fitted date, port, route,
seed, or output threshold. The headway is derived from the deployed vessels
and route cycle distance supplied by the runtime.

## Exact candidate policy

Only `UserStrategy.assign_associated_bookings` may change. The other three
hooks remain unconditional `None` delegates. The candidate starts with the
complete v3 decision and changes exactly one outcome:

1. Require all existing v3 conditions: a new shipment with no booking chain,
   a distinct origin and destination, a valid active disruption, one nominal
   direct edge, a complete safe path with at least two service-route changes,
   finite positive timing data, and `hold_hours < detour_hours`.
2. Match the nominal edge against active constraints. Continue only when the
   set of matching kinds is exactly `{\"leg\"}`. A port closure or mixed
   leg-plus-port disruption is never suppressed.
3. Derive the first safe path's route profile and its positive departure
   headway. If the timing margin
   `detour_hours - hold_hours` is strictly less than that headway, return
   `None` and delegate to the organizer fallback.
4. Otherwise return the v3 boolean `False` and retain the recovery hold.

Any malformed, missing, non-finite, or ambiguous value delegates with
`None`. The comparison is full precision and strict. The implementation must
remain standard-library-only, deterministic, read-only, fail-closed, and
free of organizer imports, I/O, environment reads, wall-clock calls,
randomness, mutable module state, hard-coded scenario data, and output
references.

## Read-only activation evidence

Before coding, a fresh audit evaluated every demand in every one of the 50
valid disruption-window midpoints (19,000 observations) against fresh runtime
contexts. It called no simulator event and did not write the organizer
output. The control participant hash matched the pinned v3 hash and the ATT
file remained byte-identical.

The audit found 48 v3 holds. The proposed rule would retain 39 and delegate
9 control-only holds. Those nine are all pure-leg, two-route-change paths:

| safe path shape | observations | annual-TEU proxy |
| --- | ---: | ---: |
| nominal 2 physical legs, 3 safe edges | 3 | 3,240 |
| nominal 3 physical legs, 3 safe edges | 6 | 41,508 |

The annual-TEU figure is only repeated structural exposure, not transported
volume or a score prediction. The audit reported `no_mutation=true`, no model
advance, no output write, 50 timestamps, and 19,000 observations. Evidence is
private and ignored under
`.challenge/round1/results/pure_leg_low_margin_v29_20260820/`.

## TDD and validation plan

The RED tests must fail against the unchanged v3 behavior for the new pure-leg
suppression boundary, then pass after the smallest participant implementation.
They must cover:

- pure-leg margin below first safe headway delegates with `None`;
- exact headway equality retains the v3 `False` decision;
- a mixed leg-plus-port constraint is never suppressed;
- malformed route or timing data delegates without mutation;
- existing v3 positive, inactive, one-change, and boundary behavior remains;
- no file, environment, organizer-module, mutable-global, or nondeterministic
  capability is introduced;
- the real ignored Round 1 context produces the declared structural behavior
  without advancing the model or changing output.

After GREEN, run the complete local gates before launch: locked `uv` sync,
Ruff format/lint, `ty`, mypy, non-integration branch coverage at least 90%,
all integration tests, Round 1 sync and byte comparison, smoke, two
deterministic compliant packages, restricted-material scans, clean Git state,
and no live simulator. Freeze all hashes and the exact command in an ignored,
non-overwriting manifest.

## Implementation and candidate audit

The RED contract was committed as `f751c5e`. Against the unchanged v3
implementation it produced exactly one expected failure: the pure-leg,
below-headway fixture still returned v3's `False` instead of the required
delegating `None`; the equality and mixed-constraint safeguards passed.

The minimum GREEN implementation and participant README were committed as
`cdd2fb1`. The focused v3 plus v29 tests pass (`42 passed`), and Ruff passes
on the participant and focused test files. The candidate participant hash is
`0f8ae2d2ab1c479dd07e372589257c4cf6d805fb9565a5d3e72b3c067cbac0a3`.

After synchronization, a separate real-context audit exercised the actual
public hook at all 50 valid timestamps and all 19,000 demands. It found 48
control v3 holds, 39 candidate holds, and 9 control-only delegations. It
reported no mutation, no model advance, no output write, and the unchanged
control ATT hash. This is a readiness gate, not a performance result; the
full simulation remains unauthorized until the complete preflight manifest is
frozen.

## Pre-run verification record

Preflight passed before launch on the canonical `main` branch. The launch
manifest is the ignored, non-overwriting file
`.challenge/round1/results/pure_leg_low_margin_v29_20260820/launch_manifest.json`.
It pins the candidate and runtime hashes, the v3 control and baseline ATT
hashes, the stale Output metadata, package members and hash, the exact command,
and the strict acceptance expression.

- `uv lock --check` and locked all-group sync passed (29 packages resolved).
- Ruff format and lint passed; `ty` and mypy passed.
- Non-integration tests passed: 230 selected, 8 deselected; branch coverage
  `90.69%` (above the 90% gate).
- Integration tests passed: 8.
- Round 1 sync and byte comparison passed; one-day smoke returned `SMOKE_OK`.
- Two `V29Validation` packages were byte-identical with SHA-256
  `ca9cd351d314c531c98bda488db9bc271f72e47f6bc5004b3a735cd665e2ff4f` and
  contained only the README and participant strategy.
- The active v3 control was rescored over exactly 72 periods to
  `19.084638612143134`; its ATT and the pinned v3 snapshot share SHA-256
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.
- Restricted-material scans, `git diff --check`, one-branch/one-worktree, and
  no-live-simulator checks passed. The tracked working tree was clean.

No full candidate simulation, candidate score, tuning, duplicate run, push,
merge, upload, or submission has occurred at this point.

## One-run procedure

Exactly one full candidate run is authorized after the preflight manifest is
reviewed. Use `PYTHONHASHSEED=0` and the manifest-pinned
`uv run wsc2026 run --round round1 --full` command. Monitor the same process
to exit zero, Day 360, Period 72, `Simulation completed`, and a fresh ATT
write. Preserve the raw log and ATT bytes before scoring, sync, smoke,
packaging, or restoration. Score the preserved ATT with the official scorer
against the authoritative Round 1 baseline over all 72 periods.

If the strict threshold is not beaten, commit the result, revert the candidate
implementation and RED tests in reverse order, synchronize and restore the
accepted v3 participant and pinned ATT, rescore the control exactly, rerun all
final gates, and leave the repository clean. Do not tune, rerun, build a
second candidate, submit, upload, push, merge, or rewrite history as part of
this experiment.
