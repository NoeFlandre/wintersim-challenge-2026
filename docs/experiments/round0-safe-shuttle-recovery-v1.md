# Round 0 safe-shuttle recovery v1

**Status:** SUCCESS_REJECTED

## Fixed hypothesis

The organizer fallback creates no alternative for an affected source route
when its complete non-closed anchor sequence cannot be connected through the
active safe-leg graph. That can remove all useful service from a still
strongly connected subset of the route and prolong the post-disruption cargo
backlog.

This candidate reproduces the standard alternative-route creation,
reservation, switching, and restoration lifecycle inside participant-owned
code. It creates one deterministic temporary cycle for an affected original
route only when a complete safe alternative cannot be built. The cycle covers
the largest mutually reachable subset of safe source-route anchors and uses
only existing non-disrupted legs. It takes an empty source-route vessel only
if that vessel is supplied to the hook at the cycle's start port.

The real Round 0 contract check produces the missing `S4` recovery cycle
`Shanghai -> Busan -> Qingdao -> Shanghai`; it leaves the organizer-created
`S2` alternative unchanged. These names are observations from the private
Round 0 fixture, not constants in the participant implementation.

## Scope and challenge constraints

- Only `UserStrategy.create_alternative_service_routes` extends behavior.
- No organizer-owned `response_strategies` implementation is imported.
- Standard alternatives retain their reservation, switching, and restoration
  behavior before the recovery-shuttle extension is considered.
- The other three hooks return `None` unconditionally.
- No new vessels or legs are created.
- No organizer source, input, output, or default strategy is tracked.
- No filesystem, environment, subprocess, network, wall-clock, randomness,
  mutable module state, hardcoded scenario names, or tuned parameters are used.
- Route planning is complete and deterministic before context mutation.
- Exactly one candidate and one complete run are authorized.

## Candidate identity

- Branch: `codex/round0-safe-shuttle-recovery-v1`
- Full-run candidate HEAD: `50f1cbff2274fe493613ad7a65c1b75049c17b3e`
- Initial implementation commit: `1d3a770`
- Package-compliance RED test commit: `34ece05`
- Self-contained lifecycle correction: `1f7e70c`
- RED test commit: `4c423bd`
- Real-contract test commit: `e96322a`
- Candidate `user_strategy.py` SHA-256:
  `f59d79b9029206b022223752ccaab155fd7d9c68944c11ba23396012409262da`

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

| Measure | Value |
| --- | --- |
| Candidate Cumulative Resilience Loss | `23.018662496580724` |
| Current-checkout fallback | `18.673577819840556` |
| Delta vs fallback | `+4.345084676740168` |
| Relative change vs fallback | `+23.26862435608641%` |
| Candidate ATT SHA-256 | `af28d1e6afd32a1e0bce32818385be380c5836f7f51ccb7470d32b2389fb47ce` |
| Mean ATT over numbered periods | `20.613472222222224` days |
| Period count | `72` |
| Periods better / equal / worse than fallback | `16 / 17 / 39` |
| Simulation runtime | `00:18:02` |
| Beats historical `18.276620672293834`? | No |
| Beats current-checkout fallback by more than `1e-9`? | No |

The result is rejected. The complete candidate score is higher than the
current-checkout fallback by `4.345084676740168`, so it fails the fixed
strict-improvement rule without ambiguity.

The runtime evidence confirms that the policy was behaviorally active:
the standard `S2` alternative remained present, an `S4` recovery shuttle was
created over the safe three-port subcycle, and one 13,000-TEU vessel transferred
to it during the disruption. The shuttle's observed utilization was very low
(about `0.30%` in the cumulative route table), and 39 of 72 ATT periods were
worse than the pinned fallback. These observations are consistent with the
extra shuttle displacing more valuable capacity than it recovered, but the run
did not instrument shipment-level counterfactuals, so that causal explanation
remains plausible rather than proven.

The first candidate implementation failed the mandatory package gate because
it imported the unshipped organizer-owned
`response_strategies.default_strategy` module. That candidate was not run.
The package-valid candidate evaluated here instead implemented the standard
alternative-route lifecycle within participant-owned code and passed
deterministic packaging twice before simulation.

## Evidence

- Candidate ATT snapshot (ignored):
  `.challenge/round0/results/safe_shuttle_recovery_v1_2026/ATT_By_Statistics_Interval.csv`
- Aggregate result (ignored):
  `experiments/results/safe_shuttle_recovery_v1_2026.json`
- Candidate package SHA-256:
  `137bc9b5e55f8b4b044606dfef4fb6e1d7c280367cd56e976371a978f73d2fa3`
- The package contained only
  `response_strategies/README.md` and
  `response_strategies/user_strategy.py`.

Exactly one complete candidate was run. No tuning or second strategy was
attempted.
