# Round 1 equal-distance one-transfer tie v27

## Status

Frozen for RED→GREEN implementation. The structural audit is a GO; no full
simulation is authorized until the candidate implementation and all preflight
gates are complete.

## Hypothesis

Accepted v3 remains the control: it holds new cargo only when a disrupted
one-booking direct service is estimated to recover sooner than the safe detour
requiring at least two service-route changes. The previous v25 experiment
installed every equal-distance safe path with fewer route changes and combined
two different shapes: `1→0` and `2→1` route-change reductions. It scored
`21.779788584660977`, so its aggregate result cannot identify which shape was
useful or harmful.

V27 isolates the lower-volume `2→1` half. When the organizer's
distance-shortest safe path has exactly two adjacent service-route changes and
an alternative path has exactly the same total distance but one change, the
candidate installs that complete one-transfer chain. It does not install the
`1→0` direct-route shape and does not alter any v3 recovery hold. Removing one
transfer without increasing sailing distance may reduce handling and headway
exposure while avoiding the larger direct-route reassignment that confounded
v25.

The strongest failure mode is capacity or vessel-phase competition: a
distance-tied path can still be operationally worse when many shipments use
the same service. The official 72-period cumulative score, not activation
counts or mean ATT, decides.

## Exact policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a non-`None` result. The policy is evaluated in this order:

1. Run the unchanged v3 predicate. If it qualifies, return its exact `False`
   hold and perform no mutation.
2. Require a new unbooked shipment, a valid timestamp, a well-formed active
   disruption, and a complete fallback-compatible safe graph. Otherwise return
   `None`.
3. Compute the organizer-compatible distance-shortest safe path. Search only
   exact shortest-distance paths using deterministic context order and select a
   path with the minimum number of adjacent service-route identity changes.
4. Continue only when the fallback path has exactly two changes and the
   selected tied path has exactly one change. For every other count or any
   equality/uncertainty, return `None`.
5. Validate the complete path and install its booking chain transactionally.
   Return `True` only after every booking and reverse reference is installed;
   on any anticipated construction or append failure, roll back and return
   `None`.

All three other hooks remain unconditional `None` delegates. The strategy is
standard-library-only, deterministic, read-only on all delegate/hold paths,
free of scenario identities, dates, seeds, fitted thresholds, I/O, network,
subprocesses, environment/cwd/wall-clock access, randomness, mutable module
state, and organizer-owned imports. A lazy runtime `Booking` lookup is used
only after path validation because the participant package cannot import the
organizer module at package-build time.

## Pre-code audit

The fresh private audit used the Round 1 `create_with_disruption` builder, all
50 valid integer-day disruption midpoints, and every demand in context order:
19,000 observations. It reproduced 48 v3 holds and found 50 candidate-only
`2→1` opportunities with an annual-TEU exposure proxy of 22,150. No `1→0`
opportunity is in this candidate. Every observation was evaluated on a
disposable context; complete snapshots remained unchanged, no model advanced,
and the active ATT file stayed byte-identical.

Ignored audit evidence:

`.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/activation_audit.json`

Audit SHA-256: `e31f0582870f0ed6fa02b6ff2d929d1ec8a928736b1ba5ec9a4799b05329abd6`.
The audit proves structural reachability only; it does not model queues,
vessel phase, capacity competition, or score causality.

## Fixed experiment contract

- checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and the sole local `main` branch;
- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon: `140` / `360` days;
- ATT interval / required numbered periods: `5` / `72`;
- accepted v3 strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- accepted v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control cumulative resilience loss: `19.084638612143134`;
- strict acceptance: `candidate_loss < 19.084638612143134 - 1e-9`;
- candidate evidence directory:
  `.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/`;
- ignored aggregate:
  `experiments/results/round1_equal_distance_one_transfer_tie_v27_20260819.json`.

Exactly one full candidate run is allowed after all gates and an immutable
manifest pass. Equality, worsening, invalid/stale output, incomplete markers,
crash, mutation, or any failed gate is rejection. On rejection, preserve the
fresh ATT/log first, commit the result, revert only v27 implementation/tests
in reverse order, synchronize v3, restore the pinned ATT byte-for-byte,
re-score the exact control, and rerun all final gates. No tuning, duplicate,
second candidate, push, merge, PR, upload, submission, or history rewrite is
part of v27.
