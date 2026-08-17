# Implementation plan: Round 1 port-involved margin guard v11

## Scope

Implement exactly the frozen v11 predicate in
`submission/response_strategies/user_strategy.py`, with participant README
wording and behavior tests. Do not touch organizer files, dependencies,
tooling, unrelated hooks, or the submission boundary.

## Steps

1. Add synthetic RED tests against untouched v3 for:
   - a qualifying mixed leg+port case whose timing margin is below the first
     safe-route headway returning `None` without mutation;
   - equality with the headway retaining v3's `False` hold;
   - a margin above the headway retaining v3's `False` hold;
   - pure-leg cases remaining unchanged;
   - malformed/non-finite headway delegating and complete snapshots unchanged.
2. Add a real ignored Round 1 integration test that derives a mixed
   leg+port, below-headway candidate-only case without port/route/demand names
   and proves `None` plus no mutation. Also prove a retained mixed case and
   pure-leg parity where available.
3. Run the focused tests against untouched v3 and record the expected RED
   failures. Commit only the RED contract.
4. Implement the smallest helper that derives matching constraint kinds and
   the first safe-edge route profile. In `_should_hold`, after the existing
   v3 timing comparison, delegate only when a matching `port` constraint exists
   and the timing margin is strictly below the first safe headway. Catch only
   the existing data-shape/arithmetic errors at the public boundary.
5. Update participant README and module docstring to describe v11. Run focused
   GREEN, Ruff format/check, Ty, and mypy. Commit the implementation.
6. Write ignored activation audit JSON and a non-overwriting pre-run manifest.
   Record exact hashes, audit counts, package members, stale ATT metadata,
   gates, command, no-live-process proof, and acceptance expression.
7. Run the complete preflight, package twice, inspect allowlisted members,
   synchronize/cmp, smoke, restricted scans, and cleanliness checks. Commit
   the pre-run report before launch.
8. Run one managed `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
   only. Monitor that same process until explicit Day 360/Period 72 completion
   and exit 0.
9. Before any overwrite-capable command, preserve the fresh ATT and raw log;
   validate hash, size, header, 72 periods, finite values, and mean; score the
   preserved ATT against the authoritative baseline; write the ignored
   aggregate and tracked result.
10. Apply the immutable score gate. On rejection, commit result first, revert
    implementation/tests in reverse order, synchronize v3, restore the pinned
    ATT, re-score exact control, rerun all final gates, and update public docs
    with the v11 result. On acceptance, retain code and update current-best
    docs. In both cases leave one clean `main` worktree and no live process.

## Explicit exclusions

No second candidate, parameter sweep, post-run tuning, replay, restoration
simulation, manual strategy recreation, organizer-material tracking, push,
merge, PR, submission, or history rewrite.
