# Round 0 safe-shuttle recovery v1

**Status:** READY_FOR_ONE_FULL_RUN

## Fixed hypothesis

The organizer fallback creates no alternative for an affected source route
when its complete non-closed anchor sequence cannot be connected through the
active safe-leg graph. That can remove all useful service from a still
strongly connected subset of the route and prolong the post-disruption cargo
backlog.

This candidate first runs the organizer fallback, then creates one
deterministic temporary cycle for an affected original route only when the
fallback created no matching alternative. The cycle covers the largest
mutually reachable subset of safe source-route anchors and uses only existing
non-disrupted legs. It takes an empty source-route vessel only if that vessel
is supplied to the hook at the cycle's start port.

The real Round 0 contract check produces the missing `S4` recovery cycle
`Shanghai -> Busan -> Qingdao -> Shanghai`; it leaves the organizer-created
`S2` alternative unchanged. These names are observations from the private
Round 0 fixture, not constants in the participant implementation.

## Scope and challenge constraints

- Only `UserStrategy.create_alternative_service_routes` extends behavior.
- The organizer default is invoked exactly once by the hook.
- The other three hooks return `None` unconditionally.
- No new vessels or legs are created.
- No organizer source, input, output, or default strategy is tracked.
- No filesystem, environment, subprocess, network, wall-clock, randomness,
  mutable module state, hardcoded scenario names, or tuned parameters are used.
- Route planning is complete and deterministic before context mutation.
- Exactly one candidate and one complete run are authorized.

## Candidate identity

- Branch: `codex/round0-safe-shuttle-recovery-v1`
- Reviewed candidate HEAD: `e96322a821be0989953db2cd0a22e47c1744b3d0`
- Implementation commit: `1d3a770`
- RED test commit: `4c423bd`
- Real-contract test commit: `e96322a`
- Candidate `user_strategy.py` SHA-256:
  `88f10f990a2b5e5deba53482be122b6501b3bdeb285420968ea456ff7f868286`

## Fixed full-run configuration

- Scenario: `create_with_disruption`
- Seed: `2026`
- Warm-up: `140` days
- Measured duration: `360` days
- Statistics interval: `5` days
- Required numbered periods: `72`
- Command: `uv run wsc2026 run --round round0 --full`

## Pinned comparison and acceptance

Current-checkout fallback:

- Cumulative Resilience Loss: `18.673577819840556`
- ATT SHA-256:
  `10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658`
- Snapshot:
  `.challenge/round0/results/fallback_reproduction_current_checkout_run1/ATT_By_Statistics_Interval.csv`

Historical secondary evidence:

- Cumulative Resilience Loss: `18.276620672293834`
- ATT SHA-256:
  `ed4f274f827959ce4261303996bbde035aa784f7b7d070b9bbdf6bea1c7cbb03`

Retain the candidate only when its complete 72-period score is:

```text
candidate_score < 18.673577819840556 - 1e-9
```

Equality is rejection. The historical value is reported separately and does
not control this checkout's accept/reject decision.

## Rejection and restoration

If the run is equal, worse, incomplete, or invalid:

1. Preserve the candidate ATT and aggregate metrics under ignored evidence
   paths.
2. Record the measured result and evidence-limited conclusion here.
3. Commit that result record.
4. Revert candidate code and candidate-specific tests with `git revert`;
   do not manually reconstruct the no-op adapter.
5. Synchronize the restored fallback adapter.
6. Restore the pinned fallback ATT snapshot and verify its exact SHA and score.
7. Rerun final lint, type, test, integration, smoke, packaging, safety, and
   cleanliness gates.

No second candidate, tuning pass, push, merge, PR, submission, or history
rewrite is authorized.

## Result

Pending the single complete run.
