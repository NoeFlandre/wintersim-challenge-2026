# Round 0 first performance result

**Status:** completed and rejected on 2026-07-20. The repository has been
restored to the organizer-fallback `UserStrategy`.

## Experiment

The first candidate changed only `select_vessel_for_berth`. When congestion
required a user decision, it prioritized the vessel with the largest sum of
shipment TEU multiplied by shipment age. The other three strategy hooks kept
delegating to the organizer fallback.

The hypothesis was that prioritizing older, heavier in-transit cargo would
reduce TEU-weighted Average Transport Time without changing routes, bookings,
vessels, legs, or organizer state.

The candidate implementation is preserved in commit `1a9fca2` and was restored
to fallback behavior by commit `7e30d63` after the result failed the predeclared
acceptance rule.

## Comparable run

Both values below use the same Round 0 scenario, seed `2026`, 140-day warm-up,
360 measured days, and five-day statistics intervals. Lower Cumulative
Resilience Loss is better.

| Measure | Fallback | Candidate | Candidate delta |
| --- | ---: | ---: | ---: |
| Cumulative Resilience Loss | 18.276620672293834 | 22.319920008142585 | +4.043299335848751 |
| Mean ATT (days) | 20.276666666666667 | 20.55986111111111 | +0.2831944444444445 |

The candidate degraded Cumulative Resilience Loss by **22.122795%**. It had
lower ATT in 32 periods and higher ATT in 40 periods. The completed simulation
took 34 minutes 11 seconds.

## Decision

The acceptance rule required a loss lower than the fallback by more than
`1e-9`. The candidate was therefore rejected and is not the current solution.
The clean solution retained for future work is the validated organizer-fallback
adapter.

During review, a secondary implementation defect was also found: the intended
berth-waiting tie-break treated the organizer mapping as name-to-number, while
the runtime supplies vessel-to-datetime. The primary age-weighted policy still
ran to completion, but the defective tie-break must not be copied into a future
candidate.

This is one practice scenario and one seed. It is a useful first result, not
evidence of hidden-scenario robustness and not a leaderboard submission.

## Local private evidence

Raw organizer output remains local and ignored:

- Fallback ATT SHA-256:
  `ed4f274f827959ce4261303996bbde035aa784f7b7d070b9bbdf6bea1c7cbb03`
- Candidate ATT SHA-256:
  `c7d888125170a42c946ed205206f8d5a331b243caab15fc497a07e2dac27e8b9`
- Baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`
- Aggregate result:
  `experiments/results/age_weighted_carried_teu_berth_priority_v1_2026.json`
- Candidate ATT snapshot:
  `.challenge/round0/results/age_weighted_carried_teu_berth_priority_v1_2026/`

No raw organizer output or experiment result is tracked.

## Resume point

Future work should start from the fallback strategy and treat
`18.276620672293834` as the fixed-seed Round 0 reference. Introduce one new
hypothesis at a time, test the exact runtime contract, and compare a complete
run before retaining it.

Public release and merge remain separately blocked pending an owner-authorized
history purge and coordinated force-push of the restricted Round 0 ZIP.
