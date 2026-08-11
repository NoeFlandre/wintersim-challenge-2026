# Plan: Round 1 transfer-berthing overhead v7

1. Record the frozen design and the private activation-audit schema/hash.
2. Add synthetic RED tests for the six-hours-per-route-change boundary,
   retained v3 holds, delegation, malformed values, signatures, and no
   mutation; commit the RED contract.
3. Implement the minimum arithmetic change in the participant strategy and
   update participant README wording; reach focused GREEN, real Round 1
   candidate-only activation, Ruff, Ty, and mypy.
4. Run the complete preflight: locked uv, true branch coverage, integration,
   Round 1 sync/cmp and smoke, deterministic package twice, control score/hash,
   restricted-material scans, clean Git, one worktree/branch, and no live
   simulator. Commit the pre-run record and write a non-overwriting ignored
   manifest.
5. Run exactly one `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
   process, monitor it to Day 360/Period 72 and explicit completion, preserve
   the raw log and ATT before scoring, then score against the authoritative
   Round 1 baseline.
6. If the strict score improves, retain the candidate and rerun all final
   gates. Otherwise commit the result, revert candidate implementation/tests,
   synchronize v3, restore and re-score the pinned v3 ATT, and rerun every
   final gate. In both cases leave a clean tracked state and a complete report.
