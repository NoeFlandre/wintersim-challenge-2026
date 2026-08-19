# Round 1 three-change mixed low-margin delegation v23 plan

1. Freeze the tracked v23 design/report and pin the accepted v3 control:
   strategy SHA `f04bda9d...`, ATT SHA `58389938...`, score
   `19.084638612143134`, baseline SHA `2b26eab7...`, and the fixed Round 1
   `create_with_disruption` / seed 2026 / `PYTHONHASHSEED=0` / 140+360-day /
   5-day configuration.
2. Run a fresh ignored read-only audit over every integer-day midpoint inside
   each valid disruption window and every demand in context order. Compare the
   unchanged v3 predicate with the independent v23 subtraction, snapshot all
   observed state, and require at least one real control-only activation,
   zero mutation/model advance/Output writes, and exact v3 activation count.
   A dormant or malformed-only predicate is a no-go and consumes no run.
3. Add focused RED tests for the mixed three-change low-margin delegation,
   strict equality retention, above-headway retention, two-change retention,
   pure-leg retention, v3 positive hold parity, malformed/fail-closed inputs,
   full state immutability, signatures, and forbidden capabilities. Add a real
   ignored-context integration assertion for the derived control-only case.
4. Implement the smallest GREEN change: reuse the existing v3 oracle and,
   after it qualifies, return `None` only for the exact v23 predicate; return
   the original `False` for every retained v3 hold. Keep all other hooks as
   delegates. Run focused tests, Ruff, Ty, and mypy.
5. Run all preflight gates and freeze a non-overwriting ignored manifest with
   HEAD, strategy/runtime hashes, package hash/members, control/baseline
   hashes/score, stale Output metadata, audit hash, exact command, and no-live
   process proof. Stop for review if any identity differs.
6. Execute exactly one managed full run. Preserve fresh ATT and raw log before
   scoring, sync, smoke, packaging, or restoration; score exactly 72 periods;
   accept only `candidate_loss < 19.084638612143134 - 1e-9`.
7. On rejection, commit the result first, revert only v23 implementation/tests
   in reverse order, synchronize v3, restore the pinned ATT bytes, re-score
   exactly, rerun every final gate, document the clean state, and leave no
   candidate active. Never tune or run a second candidate.

