# Round 1 port-closure exclusion v10

**Status: PRE-RUN VERIFIED — implementation complete; no full run has run.**

This is one separately named Round 1 experiment from the accepted v3 control.
The participant boundary remains only `submission/response_strategies/`; the
organizer source, inputs, outputs, and private evidence remain ignored.

## Hypothesis

The accepted v3 recovery hold is valuable for pure leg congestion: the direct
v9 subtraction of those 22 holds degraded the score to
`22.38757990186231`. It is unresolved whether holds involving a closed port
are equally beneficial. V10 keeps every v3 hold whose matching nominal-edge
constraints are all congested legs, but delegates any hold with a matching
closed-port constraint. This may avoid origin waiting during port-closure
episodes while retaining the proven pure-leg recovery behavior.

Strongest failure mode: port-involved holds may be essential for cargo facing
blocked berths, so removing them could reproduce v9's degradation.

## Activation audit

The read-only audit sampled every integer-day midpoint inside each valid
disruption window, using a fresh `create_with_disruption()` context and every
demand in context order. It examined 50 timestamps and 19,000 observations
without advancing a model, writing Output, or mutating a retained context.

- v3 control holds: `48`;
- v10 retains pure-leg holds: `22`;
- v10 control-only delegation cases with a matching port constraint: `26`;
- port-involved annual-TEU exposure proxy: `21,126`;
- port-involved shapes: 16 observations with a two-change/four-edge safe path
  and 10 with a three-change/five-edge safe path;
- no mutation observed.

Activation and exposure are structural evidence, not score predictions. The
ignored audit JSON will be stored at
`.challenge/round1/results/port_closure_exclusion_v10_20260817/activation_audit.json`.

## Frozen policy and invariants

Only `assign_associated_bookings` may differ from v3. After all existing v3
guards and timing comparison pass, the candidate returns `False` only when the
matching constraint-kind set for the nominal edge is exactly `("leg",)`. Any
matching `port`, mixed constraint set, malformed state, missing data, inactive
window, equality, or non-positive/non-finite value delegates with `None` and
does not mutate state. The other three hooks remain unconditional `None`.

The implementation must be standard-library-only, deterministic, identity-free
except for existing structural object matching, free of I/O/environment/
network/process/wall-clock/random access, and free of mutable cross-run state.

## Implementation and pre-run verification

The RED tests were committed in `f2172fb`, and the corrected delegation
contract was committed in `6848cc2`. The minimal participant implementation and
submission README update are in `0694754`. The candidate strategy SHA-256 is
`359d48c120dfed776be71de97e2b40df7ffa7d57bdd6ee69aa5ea027e0577e44`.

Focused RED/GREEN verification is complete: the final focused unit and real
context integration selection passes 42 tests. Full pre-run gates also pass:
`uv lock --check`, locked `uv sync --all-groups`, Ruff format/check, Ty, mypy,
228 non-integration tests with 90.64% branch coverage, and 9 integration tests.
Runtime sync produced byte-identical participant files. Round 1 smoke returned
`SMOKE_OK`. Two packages were byte-identical at SHA-256
`f470b1f584819638308356b70b9decd4d1680922ff28f3bf74b179202062d4d3` and
contained only the two participant files.

The non-mutating activation audit is preserved at
`.challenge/round1/results/port_closure_exclusion_v10_20260817/activation_audit.json`
(SHA-256
`b2f24b190539031d67681ee79b187a905b177c517e902c3e29367ccb94dd51d1`). The
non-overwriting pre-run manifest is at
`.challenge/round1/results/port_closure_exclusion_v10_20260817/pre_run_manifest.json`.
No candidate ATT or full-run log existed when the manifest was frozen.

## Fixed control and run contract

- control participant/runtime strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control score: `19.084638612143134` over 72 periods;
- authoritative baseline SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- round/scenario: `round1` / `create_with_disruption`;
- seed/environment: `2026` / `PYTHONHASHSEED=0`;
- warm-up/measured horizon: `140 / 360` days;
- ATT interval/periods: `5` days / `72`;
- candidate evidence directory:
  `.challenge/round1/results/port_closure_exclusion_v10_20260817/`;
- ignored aggregate: `experiments/results/round1_port_closure_exclusion_v10_20260817.json`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

## TDD and restoration contract

RED tests must fail only because untouched v3 returns `False` for mixed
leg+port holds. GREEN must pass synthetic and real-context delegation,
pure-leg retention, inherited v3 boundaries/fail-closed cases, signatures,
forbidden-capability checks, and complete state snapshots. Exactly one full run
is allowed after all gates and a non-overwriting manifest are committed.

On equality, worsening, invalid output, crash, timeout, stale output, or failed
gate: preserve fresh ATT/log first; commit the result; revert only v10
implementation/tests in reverse order; synchronize v3; restore and re-score the
pinned v3 ATT; rerun every final gate; and leave Git clean. No tuning, second
candidate, push, merge, PR, upload, submission, or history rewrite is part of
this experiment.
