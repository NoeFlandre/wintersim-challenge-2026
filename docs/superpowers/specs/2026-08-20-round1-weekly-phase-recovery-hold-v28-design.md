# Round 1 weekly-phase recovery hold v28

## Context

The accepted Round 1 v3 strategy holds new cargo only when a disrupted direct
service is estimated to recover sooner than a safe detour requiring at least
two service-route changes. Its timing estimate uses half of a derived route
headway at each service-route transition. That estimate is conservative but
does not use the organizer's declared weekly release phase
(`start_day_of_week`).

The current organizer runtime releases the first vessel for a service route at
the next configured weekday/time and releases subsequent vessels on a fixed
seven-day cadence. A read-only structural audit over 50 valid disruption
midpoints and 19,000 fresh demand observations found nine cases where v3
delegates but an exact weekly-phase estimate favors the direct recovery hold,
plus one v3 hold that the phase estimate would reject. The candidate below is
additive: it keeps the known-good v3 hold and adds only the nine phase-positive
delegations. The audit is reachability evidence, not a score prediction.

## Candidate policy

Change only `UserStrategy.assign_associated_bookings` and only for a new
shipment during a valid active disruption. Preserve the complete v3 predicate
and its `False` result unchanged. If v3 would delegate, evaluate the same
nominal one-edge path, safe path with at least two service-route changes,
constraint recovery, and data-validation prerequisites. Estimate path service
time by:

1. sailing each edge using the existing route mean deployed-vessel speed;
2. when entering a different service route, adding the non-negative wait from
   the current simulated timestamp to that route's configured weekly release
   phase (`start_day_of_week`, Monday-based fractional days); and
3. continuing with the resulting timestamp for each subsequent route change.

Return `False` only when `recovery_wait + phase_nominal_time <
phase_safe_time` at full precision. Otherwise return `None`, except that an
existing v3 hold still returns `False` exactly as before. Invalid, missing,
non-finite, boolean-as-number, or non-positive data delegates. The estimate is
read-only, deterministic, standard-library-only, and has no external I/O,
identity/date tables, randomness, mutable module state, or organizer import.

## Alternatives considered

1. Replace v3's half-headway estimate with phase timing everywhere. This would
   suppress one existing v3 hold and is needlessly risky; the additive policy
   preserves all proven behavior.
2. Rebuild the organizer's initial booking path using phase-aware Dijkstra.
   A prior broad phase-aware booking experiment scored `24.21744876585007`, so
   path installation is rejected.
3. Add another berth or in-transit policy. Prior variants were equal, dormant,
   or materially worse and do not address the observed v3 timing gap.

The additive phase-only hold is the smallest novel policy with candidate-only
activation and a bounded downside: it does not remove any accepted v3 hold.

## Invariants

- all four public method signatures remain unchanged;
- the three non-booking hooks remain unconditional `None` delegates;
- every `None` path leaves context, shipment, routes, and Output unchanged;
- all path/timing ties remain deterministic and follow context order;
- weekly phase is validated as a finite number in `[0, 7)`;
- `start <= now < end` disruption boundaries remain unchanged;
- no participant import reaches organizer `default_strategy.py` or other
  unshipped files;
- no filesystem, environment, subprocess, network, wall-clock, or random
  access is introduced;
- no mutable cross-run/module state is introduced.

## Frozen run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and one branch: `main`;
- round/scenario: `round1` / `create_with_disruption`;
- organizer seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required numbered periods: `72`;
- accepted v3 strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- accepted v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- accepted v3 loss: `19.084638612143134`;
- authoritative Round 1 baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- acceptance expression: `candidate_loss < 19.084638612143134 - 1e-9`;
- ignored evidence directory:
  `.challenge/round1/results/weekly_phase_recovery_hold_v28_20260820/`;
- ignored aggregate:
  `experiments/results/round1_weekly_phase_recovery_hold_v28_20260820.json`.

Exactly one candidate full run is allowed. The fresh ATT and raw log must be
preserved before scoring, synchronization, smoke, packaging, or restoration.
Equality, worsening, invalid output, incomplete output, a failed gate, or a
crash is rejection. On rejection, commit the result, revert only v28 code and
tests in reverse order, synchronize v3, restore its pinned ATT bytes, re-score
the exact control, and rerun all final gates. No tuning, duplicate run, push,
merge, PR, upload, submission, or history rewrite is part of this experiment.
