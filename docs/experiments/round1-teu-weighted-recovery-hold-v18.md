# Round 1 TEU-weighted recovery hold v18

**Status: REJECTED — one authorized full simulation completed; the pinned v3
control was restored.**

## Hypothesis

Accepted v3 holds every newly generated shipment when a disrupted direct
service is estimated to recover sooner than a safe detour requiring at least
two service-route changes. The official Average Transport Time (ATT) is
weighted by each shipment's TEU size. A one-TEU shipment contributes less
weight to that objective than a multi-TEU shipment, while still consuming a
booking opportunity and network capacity. V18 therefore tests one narrow
refinement: keep the proven v3 hold for shipments larger than one TEU and
delegate exactly one-TEU shipments to the organizer fallback.

The strongest failure mode is that one-TEU shipments are numerous and their
detours create queue pressure; delegating them could increase total delay even
after TEU weighting. The complete 72-period scorer, not the audit or mean ATT,
decides.

## Exact policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
change. Preserve every v3 topology, disruption, path, timing, boundary,
exception, and immutability rule. After the existing shipment-shape checks,
read `shipment.teu_size` as a finite positive number and return `None` when it
is exactly one TEU or when it is missing, non-positive, non-finite, or a
boolean. For a shipment with `teu_size > 1`, evaluate the unchanged v3
predicate and return its existing `False` hold or `None` delegation. The other
three hooks remain unconditional `None` delegates.

The `> 1` boundary is the smallest identity-free cargo-size distinction: it is
not fitted to a result, date, demand, route, port, or seed. The strategy must
remain read-only, deterministic, standard-library-only, fail-closed, free of
I/O/environment/network/subprocess/randomness/wall-clock access, and free of
mutable module or cross-run state. No organizer source may be imported by the
participant package.

## Activation audit contract

Before implementation, a private read-only audit must use the active Round 1
`create_with_disruption` builder, the 50 valid integer-day midpoint timestamps,
and every demand in context order (19,000 observations). For each observation,
evaluate the unchanged v3 predicate on a fresh one-TEU shipment and evaluate
the frozen v18 oracle on one- and two-TEU shipments. Capture complete
before/after context, shipment, and Output signatures around every call; do not
advance a model or write organizer Output.

The audit is expected to reproduce 48 v3 holds. It must show that the v18
oracle retains those holds for two-TEU cargo and delegates the one-TEU version,
with finite anonymous annual-TEU exposure, no mutation, unchanged Output, and
no model advancement. These are reachability and exposure facts only, not a
score prediction. The immutable audit JSON belongs at
`.challenge/round1/results/teu_weighted_recovery_hold_v18_20260819/activation_audit.json`.

The audit passed before implementation with SHA-256
`959bb26a4f929291344b49075dc4e200347a13165afe3bdafa62291a38582906`:
`50` timestamps, `19,000` observations, `48` v3 holds, `0` one-TEU v18 holds,
`48` two-TEU v18 holds, `48` control-only one-TEU activations, a repeated
annual-TEU exposure proxy of `77,478`, `no_mutation: true`, unchanged Output,
and `model_advanced: false`. This is structural reachability evidence only.

## Fixed control and acceptance

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and one local `main` branch;
- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / interval: `140` / `360` / `5` days;
- required numbered ATT periods: `72`;
- accepted v3 strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- accepted v3 ATT snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- accepted v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- freshly verified v3 control loss: `19.084638612143134`;
- acceptance expression (full precision, strict):
  `candidate_loss < 19.084638612143134 - 1e-9`.

Equality, worsening, invalid/stale output, a crash, incomplete completion
markers, mutation, or any failed final gate is rejection. Candidate ATT/log
and aggregate evidence are ignored/private under
`.challenge/round1/results/teu_weighted_recovery_hold_v18_20260819/` and
`experiments/results/round1_teu_weighted_recovery_hold_v18_20260819.json`.

## TDD and one-run procedure

Add RED behavior tests before production code: a multi-TEU qualifying shipment
must retain the v3 `False` hold; an exact one-TEU qualifying shipment must
delegate with `None`; malformed/non-finite sizes must delegate; and complete
state snapshots, boundaries, equality, deterministic topology, public
signatures, forbidden capabilities, and all inherited v3 behavior must remain
covered. Include a real Round 1 integration assertion using a multi-TEU
shipment and an exact-one-TEU delegated case. RED must fail only because
untouched v3 still holds the exact-one-TEU case. GREEN is the smallest
fail-closed cargo-size guard.

Before a full run, require locked `uv` resolution/sync, Ruff format/lint, Ty,
mypy, non-integration branch coverage at least 90.00%, serial integration
tests, Round 1 sync/cmp, smoke, two deterministic participant-only packages,
fresh v3 score/ATT identity, restricted-material scans, clean Git state, and
no live simulator. Freeze a non-overwriting manifest with the exact launch
HEAD and all hashes. Run the fixed full command exactly once, monitor it to
Day 360/Period 72/`Simulation completed`, preserve fresh ATT and raw log before
scoring, and apply the expression unchanged.

If rejected or invalid, commit the result first, revert only the v18
implementation and candidate tests in reverse order with `git revert`, sync
the v3 participant files, restore the pinned v3 ATT byte-for-byte, re-score
exactly, rerun every final gate, and leave v3 active. No tuning, duplicate
run, second candidate inside v18, push, merge, PR, upload, submission, or
history rewrite is authorized.

## Full-run result (2026-08-19)

The pre-run manifest was rechecked after its README hash correction and before
launch. The single permitted command was attempted literally first; it exited
before simulation because the default uv cache was not writable (log SHA
`428110c146046e897b3cda61be7243c9c56c1389651ce31de39877a203f84c2a`). The
same pinned command was then run once with the predeclared writable temporary
uv cache. No simulator had started during the failed literal attempt, so this
was the only operational candidate run.

The authorized run exited `0` and reached every required completion marker:
Period 72 (Days 356–360), Output Simulation Day 360, `Simulation completed`,
and a fresh ATT write. The raw log is preserved at
`.challenge/round1/results/teu_weighted_recovery_hold_v18_20260819/full_run.log`
(SHA-256
`cc0abb4a4904312c6eb7113c3d9dbbcd1693e9081519b6a713b87ad85a486c03`). The
fresh ATT was copied before scoring to
`.challenge/round1/results/teu_weighted_recovery_hold_v18_20260819/ATT_By_Statistics_Interval.csv`
(SHA-256
`07abd2668852b8c7b3c59904178f125774561f33d6c5905548a509ef4b4413c8`). It
contains exactly 72 numbered periods and has mean ATT `20.468055555555555`
days.

Scoring the preserved ATT against the authoritative Round 1 baseline produced
cumulative resilience loss `20.744602632173724` over 72 periods. The pinned
v3 control is `19.084638612143134`, so the candidate delta is
`+1.6599640200305898` (`+8.695%`); 10 periods improved and 62 worsened, with
none equal. The strict acceptance rule therefore rejects v18. It did not beat
the control or the historical target.

The complete machine-readable result is retained (ignored/private) at
`experiments/results/round1_teu_weighted_recovery_hold_v18_20260819.json`.
The candidate implementation and test commits were then reverted in reverse
order (`1deccfc`, `0d3702b`, `f69c79e`), the v3 participant files were synced,
and the pinned v3 ATT snapshot was restored and re-scored exactly at
`19.084638612143134`. The final active participant strategy is therefore the
accepted v3 control, not the rejected v18 variant.

## Post-rejection verification

Restoration commits are `27f9c5c` (implementation), `fc97ed0` (formatting),
and `434969a` (RED tests), following result commit `3576bd5`. After the
restoration, all checks passed: locked uv check/sync, Ruff format and lint,
Ty, mypy, the full suite (`235 passed`), non-integration coverage (`227
passed`, `90.84%` branch coverage), and serial integration tests (`8 passed`).
Round 1 sync and participant/runtime comparisons are byte-identical; smoke is
`SMOKE_OK`; two participant-only packages are byte-identical with SHA-256
`a88fa1f534049cec96ffdf7d0204b2dc1fa3d685ceb438d9cecf45b4fcc5eef3`.

The active Output ATT and pinned v3 snapshot both hash to
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a` and
re-score to `19.084638612143134` over 72 periods. Restricted-material scans,
`git diff --check`, and the no-live-process check are clean. The worktree is
clean on `main`; no push, merge, PR, upload, submission, tuning, duplicate
run, or history rewrite was performed.
