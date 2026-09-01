# Round 2: port-closure one-transfer TEU-dominance guard (v6)

**Status: DESIGN — no candidate run authorized yet.**

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
