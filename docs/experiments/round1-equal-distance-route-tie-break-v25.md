# Round 1 equal-distance fewer-transfer tie-break v25

**Status: REJECTED — complete; v3 control restoration is pending in this
working state.**

This report is the tracked audit contract for one candidate from the accepted
Round 1 v3 control. The design and executable plan are recorded in the linked
specification and plan. The candidate may proceed to the single full run only
after the final pre-run review below remains green.

## Control

- active policy: accepted multi-transfer recovery hold v3;
- control loss: `19.084638612143134` over 72 periods;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- participant/runtime strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`.

The candidate implementation currently has SHA-256
`0d3193d56ac671f0b928fb98628b3eadf05fe3b634d57ae6658a5ba0ced9396e`.

## Frozen candidate

Preserve v3's existing hold exactly. For a new shipment during an active
disruption, inspect only the fallback-compatible safe graph. If the fallback
distance-shortest path has a different safe path with exactly the same total
distance and strictly fewer adjacent service-route changes, install that tied
path transactionally and return `True`. Otherwise return `None` without
mutation. This is a general topology rule, not a port or date exception.

## Pre-code oracle gate

The oracle must use fresh organizer contexts at every valid integer-day
midpoint, all demands in context order, and disposable shipments. It must not
advance a model or write Output. It must reproduce 50 timestamps, 19,000
observations, 48 v3 control holds, and 100 candidate-only tied-path
opportunities, with no candidate overlap with a v3 hold and no observed
mutation. The immutable ignored evidence belongs at:

`.challenge/round1/results/equal_distance_route_tie_break_v25_20260819/activation_audit.json`.

Counts are structural readiness evidence only; the full scorer decides whether
the policy helps.

## Implementation and activation review

- RED: the new focused test initially failed because v3 delegated the exact
  tie instead of installing the fewer-transfer path.
- GREEN: four focused tests pass for exact-tie installation, non-tie
  delegation, v3-hold precedence, and transactional rollback; the existing v3
  and public-contract tests also pass.
- Real runtime activation audit:
  `.challenge/round1/results/equal_distance_route_tie_break_v25_20260819/candidate_activation_audit.json`;
  it called the actual candidate hook over 19,000 observations and recorded
  100 `True` candidate installations, 48 preserved v3 `False` holds, 18,852
  delegations, shape counts `1->0` (50) and `2->1` (50), no model advance, and
  no Output write. This is structural evidence, not a score.
- The candidate uses only participant-owned code, standard-library helpers,
  and a lazy organizer `Booking` lookup after path validation. It has no
  identity/date/volume exceptions, external I/O, randomness, or mutable global
  state.

## Run contract and decision

The fixed run is Round 1 `create_with_disruption`, seed `2026`,
`PYTHONHASHSEED=0`, 140-day warm-up, 360 measured days, 5-day intervals, and
72 numbered ATT periods. Accept only:

```text
candidate_loss < 19.084638612143134 - 1e-9
```

Exactly one candidate run is allowed. Preserve its fresh ATT and raw log before
scoring, synchronization, smoke, packaging, or restoration. On rejection,
commit the result first, revert only v25 tests/code in reverse order,
synchronize and restore v3, re-score exactly to the control, rerun every final
gate, and leave `main` clean. No tuning or second candidate is allowed.

## Full-run result

The single frozen run completed the required horizon:

- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full` with a
  writable temporary `UV_CACHE_DIR` only for the launcher;
- organizer markers: `Period 72 (Days 356-360)`, `Output Simulation Day: 360`,
  `Simulation completed`;
- simulator runtime: `01:05:33`;
- preserved ATT:
  `.challenge/round1/results/equal_distance_route_tie_break_v25_20260819/ATT_By_Statistics_Interval.csv`;
- candidate ATT SHA-256:
  `f7150c4a544856dde96c0130d6071df3b4b4587cec94c3a02292f46598f7e63b`;
- raw log SHA-256:
  `9187e17568727af5088802e27600a2c2b696b514ac1a4254fb3379e458ee4710`;
- scorer JSON:
  `.challenge/round1/results/equal_distance_route_tie_break_v25_20260819/score.json`;
- period count: `72`;
- mean ATT: `20.53013888888889` days;
- candidate cumulative resilience loss:
  `21.779788584660977`;
- delta versus v3 control: `+2.695149972517843` loss, or `+14.122090689226%`;
- period comparison versus the pinned v3 ATT: 18 better, 19 equal, 35 worse;
  first divergence at Period 19.

The candidate is therefore **REJECTED** under the unchanged strict rule
`candidate_loss < 19.084638612143134 - 1e-9`. The candidate path tie-break
made the result materially worse despite its structural 100-activation audit.
The organizer simulation completed successfully; the shell wrapper's optional
post-run `UV_EXIT` bookkeeping used zsh's read-only `status` name and emitted
an error after completion, so no wrapper exit code is claimed. This does not
change the rejection or the preserved evidence.

The ignored aggregate record is
`experiments/results/round1_equal_distance_route_tie_break_v25_20260819.json`.
