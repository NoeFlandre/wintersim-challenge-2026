# Plan: Round 1 pure-congestion exclusion v9

1. Commit the frozen v9 design, experiment report, and implementation plan.
2. Add synthetic RED tests proving pure-leg v3 holds now delegate, while
   mixed leg/port holds, closed-port holds, malformed states, boundaries,
   timing equality, deterministic ties, and no-mutation behavior remain as
   specified.
3. Run the focused RED selection against untouched v3 and commit the RED
   contract only after the failure is the missing pure-leg delegation.
4. Implement the smallest participant-only constraint-kind gate. Add no hook,
   dependency, state, route mutation, or unrelated refactor.
5. Add/adjust a real ignored Round 1 integration test using fresh contexts and
   derived timestamps. Prove candidate-only pure-leg activation, retained
   mixed behavior, and complete state immutability.
6. Run focused GREEN, Ruff, Ty, mypy, complete non-integration coverage, and
   integration tests; commit implementation and any correction atomically and
   separately from the design.
7. Run the full preflight, including sync/cmp, smoke, two deterministic
   participant-only packages, restricted scans, clean Git/process checks, and
   a non-overwriting launch manifest. Stop if any gate fails.
8. Launch exactly one managed full Round 1 run, monitor it to Day 360 / Period
   72 / explicit completion / exit 0, and preserve fresh ATT/log evidence
   before any command that can touch active Output.
9. Score the preserved ATT against the authoritative baseline, compare every
   period with v3, and apply the frozen strict gate without tuning.
10. Retain v9 only if it strictly beats v3. Otherwise commit the rejection,
    revert only v9 implementation/test commits in reverse order, synchronize
    and restore v3, re-score exactly, rerun every final gate, update the
    readiness/README/HTML records, and leave `main` clean.
