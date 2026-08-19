# Round 1 mixed one-transfer low-margin recovery hold v16

**Status: PRE-RUN REVIEW — implementation and audit only; no full simulation
authorized yet.**

## Hypothesis

The accepted v3 strategy holds a disrupted direct shipment only when the safe
detour requires at least two service-route changes. V12 added six mixed
leg-plus-port one-transfer cases and was slightly worse than v3. V15 added the
three later/high-margin cases and was much worse. V16 isolates the other three
early/low-margin cases to test whether those cases are the useful part of the
v12 signal and whether the v15 regression came from the late cases.

This is an isolated one-run experiment, not a claim that the static timing
model is sufficient. The official cumulative resilience loss remains the only
acceptance metric.

## Exact policy

Only `assign_associated_bookings` changes. Preserve every v3 decision. For a
new shipment that otherwise matches the v12 mixed one-transfer shape, return
`False` only when:

1. the nominal shortest path is one disrupted direct edge;
2. the safe shortest path has exactly one service-route change;
3. the nominal edge matches both an active leg and active port constraint;
4. the v3 recovery-versus-detour timing margin is positive; and
5. that margin is strictly less than half the first safe-route headway.

The strict upper boundary delegates at equality. Invalid or missing data,
pure leg/port cases, other route-change counts, and all unrelated hooks
delegate. The guard is read-only, deterministic, standard-library-only, and
has no mutable module state, I/O, randomness, dates, identifiers, or organizer
imports.

## Fixed control and acceptance

- checkout: `/Users/noeflandre/wintersim-challenge-2026`, one `main` worktree;
- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required periods: exactly `72`;
- v3 strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- v3 control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control loss: `19.084638612143134`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Equality, worsening, stale/invalid output, incomplete markers, mutation, or a
failed final gate is rejection. Exactly one full simulation is allowed; no
tuning, duplicate run, push, merge, PR, upload, submission, or history rewrite
belongs to v16. A rejection must restore v3 participant files, runtime, and
ATT before final gates.

## Activation audit

The prior immutable profile found six mixed one-transfer candidate-only states
across 50 valid timestamps and 19,000 observations. Their first safe-route
headway is `154.76363636363635` hours; the half-headway boundary is
`77.38181818181818` hours. V16 must retain all 48 v3 activations and expose
exactly the first three mixed cases, with timing margins
`23.551818181818135`, `47.551818181818135`, and `71.55181818181813` hours.
The audit must show three candidate-only and zero control-only activations,
no mutation, no model advancement, and no Output write before implementation
and before any run. The immutable audit passed with SHA-256
`13b238b2de09bd21af06a12e0846d2592406edf0ec4560c530961732685594d1`:
`19,000` observations, `48` v3 activations, `51` candidate activations,
`3` candidate-only, `0` control-only, `no_mutation: true`, and
`output_written: false`.

## TDD and gates

RED tests cover below-buffer hold, equality delegation, above-buffer
delegation, invalid headway delegation, and unchanged v3 multi-transfer hold.
GREEN is the smallest local extension of the v3 timing guard. Before any full
run, locked `uv` resolution/sync, Ruff, Ty, mypy, unit coverage at least 90%,
integration tests, participant/runtime `cmp`, one-day smoke, deterministic
participant-only packages, unchanged control score/ATT, restricted-material
scans, a clean Git state, and no live process are mandatory. Freeze a
non-overwriting manifest. Preserve the raw log and fresh ATT before scoring or
restoration.

## Evidence paths

Ignored v16 evidence belongs under
`.challenge/round1/results/mixed_one_transfer_low_margin_v16_20260819/`; the
aggregate belongs under
`experiments/results/round1_mixed_one_transfer_low_margin_v16_20260819.json`.
This document must be updated with the immutable audit, run, score, decision,
restoration, and final-gate hashes only after each corresponding action.
