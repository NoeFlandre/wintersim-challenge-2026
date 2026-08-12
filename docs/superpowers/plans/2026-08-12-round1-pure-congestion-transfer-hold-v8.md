# Plan: Round 1 pure-congestion transfer hold v8

1. Commit the frozen design, experiment report, and one-run evidence paths.
2. Add synthetic RED tests against v3: pure one-physical-leg congestion-only
   one-transfer returns `False`; closed-berth, multi-physical-leg, mixed, and
   malformed cases still delegate; existing v3 multi-transfer behavior and
   immutability remain unchanged.
3. Run the focused tests and record the expected missing-behavior failures.
4. Implement the minimum candidate branch in the participant strategy. Add no
   new hook, package dependency, configuration, state, or unrelated refactor.
5. Add a real Round 1 integration test using a fresh context and derived
   disruption-window timestamps. Prove candidate-only activation and complete
   no-mutation state equality.
6. Run focused GREEN, Ruff, Ty, mypy, full non-integration coverage, and all
   integration tests. Commit the implementation and test corrections
   separately from the design.
7. Run the complete preflight, including sync/cmp, smoke, two deterministic
   participant-only packages, restricted-material scans, clean Git/process
   checks, and a non-overwriting pre-run manifest.
8. Launch exactly one managed full Round 1 run. Monitor the same process to
   Period 72, Day 360, explicit completion, exit 0, and a fresh CSV.
9. Preserve raw ignored evidence first, score the preserved ATT against the
   authoritative baseline, compare all 72 periods with v3, and apply the
   immutable strict gate.
10. Retain the candidate only if it strictly beats v3. Otherwise commit the
    result, revert candidate-only commits, synchronize/restore v3, re-score it,
    rerun all final gates, update readiness and HTML docs, and leave `main`
    clean with no live simulator.
