# Round 1 dominance-filtered carried-TEU berth priority v1

**Status: DESIGN REVIEW — no candidate simulation is authorized yet.**

## Hypothesis

The organizer berth policy is a normalized heuristic (waiting time, carried
TEU, vessel capacity, and a handling-workload penalty).  During an active
disruption, a berth decision delays every shipment already carried by each
waiting vessel.  A weighted-shortest-processing-time (WSPT) order based on
carried TEU and the vessel's actual berth service time is a more direct proxy
for the TEU-weighted transport-time objective than the fallback's fixed
weights.  This experiment tests that one scheduling change while leaving all
route and booking behavior to the organizer.

## Exact participant policy

Only `UserStrategy.select_vessel_for_berth` may return a vessel.  It acts only
when at least one well-formed disruption plan is active.  For every waiting
vessel it reads, without mutation:

- carried TEU across all carried shipments;
- TEU discharged at the current segment and loaded at the next segment;
- the vessel's crane count (`max(1, int(loa / 55))`), vessel capacity, and queue
  order; and
- the fallback-compatible service time, `3 hours + handled_teu / (cranes * 45)`.

The candidate selects the maximum `carried_teu / service_time` ratio, using
waiting-queue order for exact ties.  It returns `None` (organizer fallback)
for inactive/malformed state, empty queues, or when the candidate selects the
same vessel as the fallback-compatible normalized policy.  The three other
hooks remain unconditional `None` delegates.  No route, booking, cargo,
vessel, or context mutation is allowed.

This is intentionally different from the rejected TEU-delay Smith experiment:
that experiment used `carried_teu + projected_loading_teu` as the ratio weight
and was byte-identical to the fallback.  This candidate isolates the measured
in-transit carried-TEU weight and refuses to alter stable periods.

## Constraints and invariants

The participant module is standard-library-only and must not import organizer
strategy code.  It must not use files, environment variables, processes,
network, wall-clock time, randomness, mutable module state, route/port/date
tables, or seed-specific behavior.  Returned objects must be members of the
waiting queue.  Any malformed object or non-finite numeric value fails closed
with `None` and no mutation.  The policy must be deterministic and preserve
the exact public method signatures.

## Fixed run contract

- round/scenario: `round1` / `create_with_disruption`
- seed: `2026`; `PYTHONHASHSEED=0`
- warm-up: `140` days; measured horizon: `360` days
- ATT interval: `5` days; required periods: `72`
- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback cumulative loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- fallback snapshot:
  `.challenge/round1/results/fallback_control_seed0_20260803/ATT_By_Statistics_Interval.csv`
- acceptance (full precision, strict):
  `candidate_loss < 20.436668751255972 - 1e-9`

Candidate evidence must be copied before any restore or overwrite into the
ignored directory
`.challenge/round1/results/dominance_carried_teu_berth_v1_20260807/` and the
ignored aggregate
`experiments/results/round1_dominance_carried_teu_berth_v1_20260807.json`.

## TDD and pre-run gate

Commit this design before implementation.  Add RED tests that fail against
the no-op adapter for active WSPT selection and boundary/tie behavior, then
implement the minimum policy and make them GREEN.  Tests must cover inactive
delegation, exact active boundaries, deterministic ties, malformed/fail-closed
inputs, queue membership, no mutation, all four hooks, real Round 1 objects,
packaging imports, and the distinction from the prior projected-load Smith
policy.

Before any full run, all lock/sync, Ruff format/check, Ty, mypy, non-integration
coverage (`>=90.00%` unrounded), integration, Round 1 sync/cmp, smoke,
deterministic package-twice, restricted-material, diff, and process checks must
pass.  The fallback score/hash must be freshly verified and the exact candidate
HEAD and strategy hash recorded here.  This review checkpoint authorizes no
simulation yet.

## One-candidate rejection procedure

Exactly one monitored full run is allowed after pre-run review.  Preserve the
fresh CSV and raw log before scoring or restoration; require Day 360, Period 72,
and a fresh output.  Apply the strict expression unchanged.  Equality,
worsening, invalid output, crash, incomplete run, or failed gates is rejection:
commit the result, revert candidate code/tests in reverse order with
`git revert`, synchronize the no-op adapter, restore and re-score the pinned
fallback bytes, rerun every final gate, and leave no candidate active.  No
tuning, duplicate run, second idea, submission, publication, or history rewrite
is permitted.
