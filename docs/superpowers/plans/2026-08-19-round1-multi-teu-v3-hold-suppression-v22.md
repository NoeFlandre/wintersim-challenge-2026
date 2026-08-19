# Implementation plan: Round 1 multi-TEU v3 hold suppression v22

1. Reconfirm the clean `main` control, current v3/runtime/ATT hashes, and no
   live simulator. Run a fresh identity-free one-/two-TEU activation audit and
   require the frozen 50/19,000/48/48/0/48 counts with no mutation or Output
   write.
2. Add synthetic RED tests and a real Round 1 integration test. Cover the
   multi-TEU suppression, exact-one-TEU preservation, missing/malformed cargo
   data, active boundaries, read-only delegation, and unchanged public hooks.
3. Commit RED tests, verify only the new suppression assertions fail, then
   implement the smallest participant-only guard and README update. Run GREEN,
   Ruff, Ty, and mypy; commit implementation separately.
4. Run all preflight gates: locked `uv`, formatting/lint, Ty, mypy, branch
   coverage >=90%, integration tests, sync/cmp, smoke, deterministic package
   twice, restricted scans, clean Git state, and no-live-process checks. Freshly
   rescore and pin the v3 control and write a non-overwriting manifest.
5. Launch exactly one fixed Round 1 full run. Monitor to exit 0, Day 360,
   Period 72, explicit completion, and fresh ATT write. Preserve ATT/log before
   score, compute the exact 72-period score and comparison, and apply the
   strict threshold unchanged.
6. If rejected, commit the report before reverting v22 code/tests, synchronize
   v3, restore/re-score the pinned ATT, rerun all final gates, and leave a clean
   `main`. If accepted, retain v22, document the new best, and rerun final
   gates without changing the candidate.
