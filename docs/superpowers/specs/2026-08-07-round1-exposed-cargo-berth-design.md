# Round 1 exposed-cargo berth priority v1

## Decision

Test one participant-only change to `UserStrategy.select_vessel_for_berth`.
During an active disruption, prioritize a waiting vessel by the amount of
currently carried cargo whose remaining booking chain is exposed to an active
closed berth or congested leg, multiplied by the vessel's elapsed berth-wait
hours. Return the original queue object with the greatest positive score and
preserve queue order for exact ties. Delegate with `None` everywhere else.

The candidate is deliberately narrower than the rejected global age-weighted
berth rule: it considers only cargo that the runtime can show is on an active
disruption-exposed booking chain, and it is inactive outside disruption
windows. It does not change routes, bookings, cargo, vessel assignments, or
the organizer's behavior for vessels without an exposed backlog.

## Evidence and rationale

Round 1's fallback berth rule is a normalized mixture of waiting time, carried
TEU, capacity, and handling workload. The challenge metric is TEU-weighted
Average Transport Time, so delay of exposed TEU is the most directly relevant
local queue cost. Earlier experiments showed:

- generic progress-first and Smith-ratio berth policies produced byte-identical
  ATT, meaning their signals did not change the selected vessel in this run;
- the global age-weighted carried-TEU policy materially worsened Round 0,
  showing that indiscriminately reordering every congested queue is unsafe;
- routing and broad in-transit-rebooking changes were materially worse, while
  several narrow route policies were equality-only.

This policy therefore restricts overrides to an observable, disruption-related
TEU backlog and retains deterministic, fail-closed delegation for all other
states. The hypothesis is that serving the oldest largest exposed backlog
first reduces disruption-induced TEU-hours without the collateral queue
reordering of the failed global policy.

## Exact policy contract

1. If `waiting_vessels` is empty, `current_time` is not a datetime, or the
   context has no well-formed active disruption plan, return `None`.
2. Active plans are those with finite positive `start_offset_days` and
   `duration_days` for which `datetime.min + start <= current_time < end`.
   A plan contributes either its target leg or its target berth's port. Any
   malformed plan or target causes fail-closed delegation rather than a guess.
3. For each waiting vessel, inspect its `carried_shipments`. For every
   shipment, validate a finite non-negative TEU size and inspect all valid
   associated bookings and route segments. A shipment is exposed when any
   segment's leg is an active target leg, or either endpoint is an active
   closed-berth port. If any required object is malformed, return `None` for
   the complete hook call; never partially rank a malformed queue.
4. Read `waiting_since_by_vessel` as vessel-to-datetime. Missing entries use
   `current_time`; negative elapsed time is clamped to zero. The vessel score
   is `exposed_teu * waiting_hours`.
5. If every score is zero or all scores are exactly equal, return `None` so
   the organizer fallback retains control. Otherwise return the original
   vessel with the maximum score; `max` must use the supplied queue order for
   equal scores.
6. The method is read-only and deterministic. It uses only standard-library
   imports, no organizer imports, no I/O, no environment/process/network/
   wall-clock/random access, no hard-coded scenario names, ports, dates,
   thresholds, or mutable module state. The other three hooks remain exact
   no-op delegates.

## Run contract and gate

- branch: `codex/round1-exposed-cargo-berth-v1`
- base: `b4ce07b4dbfec0edc6dc2954c4bdd3a4b375e8da`
- round/scenario: `round1` / `create_with_disruption`
- seed: `2026`; `PYTHONHASHSEED=0`
- warm-up: 140 days; measured horizon: 360 days
- ATT interval: 5 days; required periods: 72
- command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- strict acceptance: `candidate_loss < 20.436668751255972 - 1e-9`

Candidate evidence must be copied before any restore to the ignored directory
`.challenge/round1/results/exposed_cargo_berth_v1_20260807/`; the aggregate
record belongs at
`experiments/results/round1_exposed_cargo_berth_v1_20260807.json`.

## TDD and pre-run checkpoint

RED tests must fail against the untouched no-op adapter for active exposed
selection and boundary behavior. GREEN tests must cover active/inactive
windows, closed-port and congested-leg exposure, elapsed-wait scoring, exact
tie delegation, queue identity, malformed fail-closed cases, missing wait
entries, and no mutation. An ignored real Round 1 integration test must build
the organizer context and verify the policy returns only supplied vessel
objects and preserves context state.

Before the full run, pass locked `uv` resolution/sync, Ruff format/check, Ty,
mypy, non-integration coverage >=90%, all integration tests, Round 1 sync and
byte comparison, smoke, deterministic participant-only packaging twice,
restricted-material scans, diff hygiene, and no-running-process checks. The
fallback ATT must match the pinned bytes and re-score exactly. Commit the
pre-run report and stop for review at that point; no run is allowed before all
gates pass.

## One-run and restoration rules

Exactly one full candidate run is allowed. Do not tune, rerun, alter the
threshold, submit, publish, rewrite history, or attempt a second candidate.
Monitor one managed process until Day 360, Period 72, explicit completion, and
fresh CSV output. Preserve the raw log and CSV before scoring or restoration.

Accept only the strict full score. On equality, worsening, crash, incomplete
output, invalid period count, or any failed gate, commit the result report,
revert candidate code/tests in reverse order with `git revert`, synchronize the
no-op adapter, restore the pinned fallback ATT bytes, re-score exactly, rerun
all final gates, remove the temporary worktree/branch, and reconcile/push only
the tracked documentation to `main` if the owner has requested publication.
Organizer source, input/output trees, and archives remain private/ignored.
