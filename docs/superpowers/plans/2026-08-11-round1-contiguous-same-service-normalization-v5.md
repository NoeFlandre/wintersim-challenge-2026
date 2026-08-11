# Implementation plan: contiguous same-service normalization v5

1. Verify the current v3 control, strategy/runtime byte identity, clean Git
   layout, restricted-material scans, and no live simulator. Preserve the
   fresh read-only activation audit as ignored JSON with its schema and hash.
2. Add focused synthetic RED tests to the existing v3 contract file and one
   real-context integration assertion. Run only those tests and record the
   expected failures against v3; commit the RED tests separately.
3. Implement the smallest participant-only change:
   - accept a non-empty nominal path when all edges share one route object;
   - aggregate recovery over all nominal edges;
   - keep the existing safe-path transfer count, timing comparison, validation,
     delegation, and public signatures unchanged.
4. Run focused GREEN tests, then the full unit/integration, Ruff format/check,
   Ty, and mypy gates. Fix only implementation/test defects while preserving
   the frozen policy; commit implementation corrections atomically.
5. Write a non-overwriting ignored pre-run manifest containing candidate HEAD,
   strategy/runtime hashes, package bytes/members, control score/hash, audit
   counts, stale Output metadata, fixed run configuration, acceptance
   expression, and all gate results. Run sync, smoke, and two deterministic
   validation packages; move archives to `/tmp`.
6. Immediately before launch, recheck the manifest identities and process list.
   Run exactly one managed `PYTHONHASHSEED=0 uv run wsc2026 run --round round1
   --full`, monitor the same process below 60 seconds until Day 360/Period 72
   and `Simulation completed.`.
7. Before scoring or restoration, copy the fresh ATT and raw log to the
   predeclared ignored evidence directory. Score all 72 periods against the
   authoritative Round 1 baseline, record full precision, hashes, mean, and
   better/equal/worse period counts, then apply the frozen gate unchanged.
8. If accepted, retain the candidate and rerun every final gate. If rejected,
   commit the result report first, revert candidate commits in reverse order,
   synchronize and byte-verify v3, restore and re-score the pinned v3 ATT, and
   rerun every final gate. Leave one clean `main` worktree with private
   evidence only in ignored paths.
