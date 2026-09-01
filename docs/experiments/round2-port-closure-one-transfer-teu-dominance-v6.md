# Round 2: port-closure one-transfer TEU-dominance guard (v6)

**Status: REJECTED — control restored; exactly one candidate run completed.**

## Hypothesis

The accepted Round 2 control holds a new direct shipment when a port-only
closure makes a robust one-transfer detour slower than waiting for the direct
service to recover.  That policy is beneficial in aggregate, but it also
changes the origin backlog for every qualifying demand.  Round 2's ATT is
weighted by the shipment's TEU size, so a hold decision on a high-volume demand
has more objective impact than one on a low-volume demand and can justify the
same recovery protection more strongly.

This experiment keeps the accepted full-headway policy and all multi-transfer
behavior unchanged.  It adds one general, data-derived guard only to the
one-transfer, port-closure-only extension: the demand's `annual_teus` must be
at or above the live demand population's third quartile.  The threshold is
computed from the supplied context in deterministic context order; no port,
route, date, seed, output, or fitted scenario value is used.  The intended
trade-off is to retain protection for the upper-volume flows while allowing
lower-volume flows to use the organizer's normal safe-detour fallback, reducing
their possible backlog spillover.

The strongest failure mode is that lower-volume demands still influence shared
vessel queues, so removing their holds may lose more network benefit than it
saves.  The full 72-period cumulative resilience-loss score is decisive.

## Exact participant delta

Only `UserStrategy.assign_associated_bookings` differs from the accepted v1
control.  Preserve every existing guard and calculation.  In the final
one-change/port-only/full-headway branch, return `False` only when:

1. the existing accepted full-headway margin is strictly positive and larger
   than the maximum safe-route headway; and
2. the shipment demand is present in a well-formed `context.demands` sequence
   and its positive `annual_teus` is at least the deterministic third-quartile
   value of all positive, finite demand volumes.

If the demand population or any volume is malformed, non-finite, non-positive,
or the shipment demand is not an object in that population, delegate with
`None`.  Existing multi-transfer holds remain exactly as in the control.  The
strategy is read-only, deterministic, standard-library-only, fail-closed, and
does not construct or edit bookings, routes, vessels, cargo, or context.

## Challenge compliance

The only evaluated files are under `submission/response_strategies/`.  The
participant does not modify or bypass organizer event logic, complete cargo
early, move cargo between ports, access files/environment/network/processes,
use randomness or wall-clock time, import organizer modules, or retain
mutable cross-run state.  Returning `False` uses the organizer's normal origin
waiting/retry lifecycle; returning `None` delegates to the organizer fallback.

## TDD and activation review

Commit this design before code.  Add RED tests for upper-quartile qualification,
below-threshold delegation, strict threshold equality, malformed/non-finite
demand populations, demand identity, preservation of multi-transfer control,
all existing boundary guards, public signatures, and complete state
immutability.  Add a real Round 2 integration test with a candidate-only
high-volume qualifying demand and a low-volume delegate.

Before any full run, perform a fresh non-mutating audit at every valid Round 2
disruption timestamp and every demand.  Compare an independent accepted-v1
oracle with the candidate, record candidate-only delegations and annual-TEU
exposure by quartile, and prove no participant mutation, model advancement, or
`Output` write.  Positive candidate/control differences and unchanged output
are required for GO; activation is not a score prediction.

## Pre-run review record (2026-09-01)

The candidate was implemented only after the design and RED tests were
committed. The existing one-transfer control fixture was updated to include
the real `annual_teus` field and demand population required by the new guard;
this does not alter organizer code or the control policy.

- implementation HEAD: `a7029ce`;
- participant strategy SHA-256: `df6399104bc44645b739afc187eb475ef2e21ea13186b0f43b435665ef8f3377`;
- synchronized runtime copy matches the participant byte-for-byte;
- activation audit: 166 valid timestamps × 380 demands = 63,080 observations;
- accepted-v1 control holds: 285; candidate holds: 168;
- candidate-only delegations: 117, all below the third-quartile threshold;
- candidate-only lower-quartile annual-TEU proxy: 162,903;
- unexpected candidate holds: 0; malformed populations: 0;
- participant mutation: none; model advanced: false; Output write: false;
- activation audit script SHA-256:
  `a10889cecb1c32455cb89f44c715baab62e5112455d02a63bbfd67fa3577537d`;
- activation audit JSON SHA-256:
  `e1859414d7d39546df36e268eb1149eb3b0ea26dc98c696169598229b696dd92`;
- pre-run package SHA-256 (both runs identical):
  `7b9d1dba7b5644e2ab0479ea709f98ef85df5bab313aa889d38cacd310cf419a`;
- package members are exactly `response_strategies/README.md` and
  `response_strategies/user_strategy.py` under the Round 2 archive root;
- pre-run Output ATT is the accepted-control snapshot SHA
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
- no live simulation was observed before launch.

All lock, sync, Ruff, Ty, mypy, unit-coverage, integration, smoke, package,
parity, restricted-material, and diff checks passed. The single authorized
command is recorded in the frozen run contract below; no tuning or duplicate
run is permitted.

## Full-run result (2026-09-01)

The one authorized candidate run completed normally. The log contains Period
72 (Days 356–360), Output Simulation Day 360, `Simulation completed.`, and the
CSV-written marker. The fresh ATT was copied to the ignored evidence directory
before scoring or restoration.

- candidate ATT SHA-256: `1680c9ae89882a1897d63dbf771e29dfcdaff27fa2442a88392bfc5cbe260d56`;
- candidate mean ATT: `15.596944444444444` days across 72 numbered periods;
- candidate cumulative resilience loss: `35.84344929789106`;
- accepted-control loss: `35.1039547178493`;
- delta: `+0.7394945800417645` (`+2.1065848163989154%`);
- ATT periods versus control: 10 better, 59 equal, 3 worse;
- strict acceptance expression: `candidate_loss < 35.1039547178493 - 1e-9`;
- decision: **REJECTED** because the candidate is worse than the control;
- raw log SHA-256:
  `2dcb3f3cacf449d556712259de24aad1c99cf0f13eaae15d3a33b3f67d838793`;
- score JSON SHA-256:
  `63f8ea6ca128d9f942b4ca2bee8f2f7bff73b9b3481b9616175e2a00cf861439`.

The complete machine-readable result is retained at the ignored
`result.json`; no tuning or duplicate candidate run was performed.

## Final restoration (2026-09-01)

The candidate and its v6 RED tests were reverted only after the result was
recorded:

- `796d113` reverts the v6 implementation, integration test, README, and
  control-fixture support change;
- `72fa96e` reverts the v6 RED contract tests;
- `uv run wsc2026 sync --round round2` restored the accepted v1 participant
  strategy;
- the accepted v1 ATT snapshot was restored to the runtime Output path and is
  byte-identical to the pinned control.

Post-restoration verification passed: control strategy SHA
`b4857197a73d7eae4a1d6d1bde3d31e50aa09aff8fcb9a08849d0ea53207ce41`, active
ATT SHA `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`,
and re-scored loss `35.1039547178493` over 72 periods. Lock/check and sync,
Ruff format/lint, Ty, mypy, 234 non-integration tests with 90.36% branch
coverage, 8 integration tests, Round 2 smoke, deterministic two-run package
(SHA `f9d3bdccb5b273552f6543a0632bffe1596db27c3c700f136f6b95499b07551d`),
diff hygiene, and restricted-material scans all passed. The working tree is
clean and no simulator is running.

## Frozen run contract

- round/scenario: `round2` / `create_with_disruption`;
- seed: `2026`; `PYTHONHASHSEED=0`;
- warm-up: `140` days; measured horizon: `360` days;
- ATT interval: `5` days; required numbered periods: `72`;
- accepted control loss: `35.1039547178493`;
- accepted control ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
- authoritative Round 2 baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- immutable acceptance rule:
  `candidate_loss < 35.1039547178493 - 1e-9`.

Candidate evidence belongs only under the ignored
`.challenge/round2/results/port_closure_one_transfer_teu_dominance_v6_20260901/`
directory.  The private accepted-control snapshot is
`.challenge/round2/results/port_closure_one_transfer_full_headway_v1_20260831/ATT_By_Statistics_Interval.csv`.

After locked UV, Ruff, Ty, mypy, coverage, integration, sync/cmp, smoke,
deterministic packaging, restricted-material, clean-tree, and no-live-process
gates pass, freeze a non-overwriting manifest and run exactly one full
candidate.  Preserve the fresh ATT and raw log before scoring or any
sync/smoke/package/restoration operation.  Equality, worsening, invalid or
incomplete output, mutation, timeout, or a failed final gate rejects the
candidate.  Record the result first; on rejection revert only v6 code/tests,
synchronize the accepted v1 control, restore and re-score its pinned ATT, rerun
all gates, and leave the control active.  No tuning, duplicate run, second
candidate, push, merge, submission, or history rewrite is part of v6.
