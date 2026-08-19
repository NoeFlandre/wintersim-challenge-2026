# Implementation plan: Round 1 multi-TEU mixed one-transfer v21

## Scope

Implement exactly the frozen v21 policy in the participant strategy. Do not
alter the scorer, organizer source, inputs, outputs, dependencies, CLI, or any
other hook.

## Steps

1. Preserve the clean v3 control identity and add the ignored atomic activation
   audit under `.challenge/round1/results/multi_teu_mixed_one_transfer_v21_20260819/`.
   Re-run it against fresh real contexts and require the frozen 50/19,000,
   48/0/54/6 counts, no mutation, no model advancement, and unchanged Output.
2. Add RED synthetic and real-context tests before production code. Cover the
   multi-TEU mixed one-transfer hold, exact-one-TEU delegation, malformed and
   non-finite cargo sizes, unchanged v3 multi-transfer behavior, strict timing
   and disruption boundaries, deterministic ties, missing data, no mutation,
   signatures, package restrictions, and real candidate-only activation.
3. Run the focused tests and capture only intended RED failures against the
   untouched v3 implementation. Commit the RED tests separately.
4. Implement the minimum cargo-size guard and mixed one-transfer predicate,
   reusing v3 helpers and the existing constraint matching semantics. Run the
   same focused selection GREEN, then Ruff, `ty`, and mypy. Commit only the
   participant implementation and participant README wording.
5. Run the complete preflight: locked uv, formatting/lint, `ty`, mypy,
   non-integration branch coverage at least 90%, integration tests, Round 1
   sync/cmp, smoke, deterministic participant-only package twice, restricted
   scans, one-worktree/main cleanliness, and no-live-process checks.
6. Commit the frozen result report and write a non-overwriting pre-run
   manifest containing all launch identities and the exact one-run command.
   Revalidate every manifest field immediately before launch.
7. Launch only:

   `PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache-v17 uv run wsc2026 run --round round1 --full`

   Monitor the same process below 60-second intervals to exit 0, Day 360,
   Period 72, `Simulation completed.`, and a fresh ATT write.
8. Copy the fresh ATT and raw log to ignored evidence before any scoring,
   sync, smoke, packaging, or restore. Score exactly 72 periods against the
   authoritative baseline, write the ignored aggregate, and apply the frozen
   strict threshold without rounding or tuning.
9. If rejected, commit the result before reverting v21 implementation/tests
   in reverse order. Synchronize v3, restore and re-score the pinned ATT,
   rerun every final gate, update the tracked report, and leave clean `main`.
   If accepted, retain v21, update the report with the new best, and rerun all
   final gates without changing the candidate.
