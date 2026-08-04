# Round 1 progress-first berth priority experiment

## Decision

Run exactly one Round 1 candidate that changes only
`UserStrategy.select_vessel_for_berth`.

During an active disruption, classify each waiting vessel by the next physical
leg it will use after the berth service:

- **progress-capable**: the next leg is not an active congested leg and its
  arrival berth is not actively closed;
- **blocked**: the next leg is an active congested leg or its arrival berth is
  actively closed.

If a queue contains at least one vessel in each class, choose a
progress-capable vessel using the organizer fallback's normalized ranking
(waiting time, carried TEU, vessel capacity, and handling workload), preserving
the original queue order for exact ties. In every other situation return
`None` so the organizer fallback handles the decision unchanged.

The policy is intentionally narrow: it changes ordering only when the queue
contains a meaningful progress distinction during an active disruption. It
does not name ports, routes, dates, seeds, or disruption-specific constants.

## Rationale and evidence

The fallback ranking already considers waiting time, carried TEU, vessel
capacity, and handling workload, but it does not consider whether the selected
vessel can depart on an immediately usable next leg. A blocked vessel can
consume a scarce berth while remaining unable to progress, allowing a
progress-capable vessel to wait behind it and propagating congestion. The
candidate tests whether preserving the fallback ranking among usable vessels
reduces that propagation without replacing the fallback in ordinary states.

Previous experiments rejected age-weighted berth priority, a TEU-delay Smith
ratio, blanket in-transit rebooking suppression, transfer penalties, temporal
safe routing, alternative-route suppression, and a transshipment barrier. This
experiment therefore targets a different observable decision property and
does not reuse those policies.

## Implementation boundaries

- Participant-owned code only: `submission/response_strategies/`.
- A small helper module is allowed only if explicitly added to the overlay and
  packager allowlists and included in the package-member tests.
- Standard library only; no organizer strategy imports, filesystem, network,
  subprocess, environment, wall-clock, randomness, or mutable module state.
- The helper reads runtime objects only and never mutates any input.
- Active plans use the organizer's end-exclusive interval semantics:
  `start <= now < end`.
- A malformed or ambiguous state delegates with `None`; no broad exception
  catch is permitted.
- The other three hooks remain unconditional `None` delegates.

## TDD contract

RED tests must fail against the baseline because it delegates in the mixed
queue case. They cover:

1. inactive/no-disruption delegation;
2. active disruption with all-progress-capable or all-blocked vessels;
3. mixed queue chooses an original progress-capable vessel by fallback rank;
4. active-boundary inclusivity and end-exclusive recovery;
5. closed-arrival berth and congested-next-leg classification;
6. exact tie/queue-order preservation;
7. malformed plans, vessels, and routes fail closed;
8. no mutation and object-identity preservation;
9. the public static-method signature and other-hook delegation.

GREEN must be achieved with the minimum helper and no unrelated refactor.
An ignored integration test must exercise a real Round 1 context and verify
that the selected result is an original waiting-vessel object and state is
unchanged.

## Fixed run contract

- round: `round1`
- scenario: `create_with_disruption`
- seed: `2026`
- warm-up: `140` days
- measured horizon: `360` days
- statistics interval: `5` days
- required periods: `72`
- paired process environment: `PYTHONHASHSEED=0`
- candidate command:
  `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback score: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- acceptance expression (full precision, no rounding):
  `candidate_score < 20.436668751255972 - 1e-9`

Candidate evidence will be preserved before restoration under:

`.challenge/round1/results/progress_first_berth_v1_20260804/`

The ignored aggregate record is:

`experiments/results/round1_progress_first_berth_v1_20260804.json`

## Rejection and cleanup

Equality, worsening, a crash, incomplete output, a failed package/runtime
gate, or a non-72-period CSV is rejection. Before any restore, copy the fresh
ATT, raw log, score JSON, hashes, period statistics, and package metadata to
the ignored evidence paths and update the tracked experiment report.

For rejection, revert candidate implementation, helper, allowlist, and test
commits in reverse order with `git revert`; retain this contract and result
history. Synchronize the no-op adapter, restore the fallback ATT from the
pinned ignored snapshot, and re-score it to the exact pinned score. Run every
final quality, integration, smoke, packaging, cleanliness, process, and
restricted-material gate again.

Exactly one candidate full run is authorized. No tuning, second candidate,
parameter sweep, post-run code change, submission, push, merge, pull request,
or history rewrite is part of this experiment.
