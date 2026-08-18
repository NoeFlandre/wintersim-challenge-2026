# Implementation plan: mixed-constraint one-transfer recovery hold v12

This plan follows the approved v12 design and ends at a mandatory pre-run
review. It does not authorize a full simulation.

## Phase 1: read-only audit and design freeze — complete

1. Verify the one-worktree `main` layout, clean tracked status, no live WSC
   process, restricted-material scans, v3 participant/runtime identity, control
   ATT, baseline ATT, and exact control score.
2. Privately inspect the four current Round 1 call sites, `DefaultStrategy`, and
   validation. Record paths, symbols, hashes, and semantic conclusions only;
   never track organizer source.
3. Commit this plan, the design specification, and the pre-run experiment report
   before any strategy code change.
4. Run the identity-free fresh-context activation audit. Require 50 timestamps,
   19,000 observations, 48 v3 activations, a non-empty exact mixed one-transfer
   candidate-only subset, strict finite margins, and complete no-mutation/output
   proofs. Write the audit JSON atomically and refuse overwrites.
5. Commit an anonymous tracked audit summary only if every audit gate passes.

**Audit result:** all gates passed on 2026-08-18: 50 timestamps, 19,000
observations, 48 v3 activations, 54 v12 activations, 6 exact mixed
leg-and-port one-transfer candidate-only cases, zero control-only cases, strict
finite margins, no mutation, no model advancement, and no Output write. The
ignored JSON SHA-256 is
`fe43717342f48d514ec9cae172b4282213751d7c0b828eba20c83005f1f3fa98`.

## Phase 2: RED to GREEN — complete

1. Add focused synthetic and real-context tests. Against untouched v3, RED must
   fail only because the exact mixed one-transfer candidate-only behavior returns
   `None` instead of `False`; all retained and negative cases must pass.
2. Commit the RED tests separately.
3. Add one shared matching-constraint helper and the one route-change eligibility
   branch in `_should_hold`; refactor recovery lookup through the helper without
   changing v3 timing, graph, tie, or exception behavior.
4. Update the participant README with the precise v12 rule. Commit the minimum
   GREEN implementation separately.
5. Run focused GREEN tests, then all formatter, linter, Ty, mypy, coverage, and
   integration gates. All gates passed; the completed preflight record is
   committed and the ignored non-overwriting manifest is the final step before
   senior review.

## Phase 3: stop for review — in progress; no run authorized

Verify synchronized participant/runtime bytes, one-day smoke, stale Output
metadata, re-scored control and baseline hashes, two deterministic packages
containing only the two participant files, restricted scans, clean Git state,
and no live process. Freeze the manifest at the reviewed HEAD and stop. The
implementation and listed checks are complete; only the final manifest write
and this review handoff remain. Do not launch the full run until a senior
review explicitly authorizes it.

## If a later run is authorized

Launch exactly one fixed v12 run, preserve the fresh ATT and raw log before any
restoration or overwriting operation, score all 72 periods with the official
scorer, apply the exact strict expression, and document the result. On equality,
worsening, invalidity, or any failed gate, commit the result first, revert only
candidate implementation/tests in reverse order, synchronize v3, restore the
pinned v3 ATT bytes, re-score exactly, rerun all final gates, and stop. Never
tune or rerun v12 in place.
