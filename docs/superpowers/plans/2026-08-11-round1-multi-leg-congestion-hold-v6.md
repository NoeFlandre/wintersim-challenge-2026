# Implementation plan: multi-leg congestion hold v6

1. Re-verify the accepted v3 control, one-worktree/one-branch layout, clean
   status, restricted-material scans, no-live-process proof, and the anonymous
   activation audit. Store only aggregate audit evidence in the ignored v6
   result directory.
2. Commit the frozen design, plan, and experiment contract before strategy
   edits. The contract must pin v3's score/ATT/strategy identities, fixed run
   configuration, candidate evidence paths, threshold, one-run limit, and
   restoration procedure.
3. Add focused synthetic RED tests to the v3 policy contract. They must fail
   against untouched v3 for the pure-leg multi-physical-leg one-transfer case,
   while proving delegation for single-leg, closed-berth, mixed-constraint,
   two-edge, inactive, equality, malformed, and unrelated existing cases. Add
   one real-context candidate-only activation test with complete no-mutation
   snapshots. Run and commit RED separately.
4. Implement the minimum participant-owned predicate change: retain v3's
   multi-transfer branch and add only the frozen one-transfer pure-leg,
   multi-leg nominal branch. Keep signatures, pathfinding tie rules, timing,
   validation, error boundary, and non-target hooks unchanged. Run focused
   GREEN, then Ruff, Ty, mypy, full unit, and integration checks; commit the
   implementation atomically.
5. Run the mandatory preflight: locked uv resolution/sync, Ruff format/check,
   Ty, mypy, true branch coverage at least 90%, all integration tests, Round 1
   sync and byte identity, smoke, two deterministic participant-only packages,
   clean restricted scans, and no live simulator. Write a non-overwriting
   ignored manifest pinning every launch identity and gate result, then commit
   the completed tracked pre-run record.
6. Immediately recheck the manifest, candidate HEAD, participant/runtime SHA,
   v3 control ATT, stale Output metadata, and process list. Run exactly one
   managed `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`, polling
   the same process below 60 seconds until Day 360, Period 72, and
   `Simulation completed.`.
7. Preserve the fresh ATT and raw log before any score, sync, smoke, or restore.
   Score all 72 periods against the authoritative Round 1 baseline, record
   full precision, hashes, mean, and better/equal/worse counts, then apply the
   frozen gate without tuning.
8. If accepted, retain v6 and rerun all final gates. If rejected, commit the
   result, revert candidate implementation/tests in reverse order, synchronize
   and byte-verify v3, restore and re-score the pinned ATT, rerun all final
   gates, and leave a clean canonical `main` checkout with private evidence
   only in ignored paths.
