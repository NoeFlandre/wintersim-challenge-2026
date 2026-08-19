# Round 1 equal-distance fewer-transfer tie-break v25

## Status

Frozen for pre-run review. The implementation and real-context activation
audit are green; this design still does not authorize a full simulation by
itself.

## Hypothesis

The accepted v3 policy improves disrupted direct cargo by holding it at origin
when a multi-transfer detour is slower. For all other cargo, the organizer
fallback minimizes total sailing distance and resolves equal-distance paths by
edge/context order. A read-only audit of the real Round 1 context found 100
same-distance alternatives where that deterministic tie resolution selected a
path with one additional service-route change:

- Qingdao → Busan: one change versus an equal-distance zero-change path;
- Qingdao → Tianjin: two changes versus an equal-distance one-change path.

Fewer service-route changes avoid a transfer and its handling/headway exposure
without increasing sailing distance. The candidate therefore tests only this
exact, topology-derived tie-break while preserving every v3 recovery hold.

## Exact policy

Only `UserStrategy.assign_associated_bookings` may return a non-`None` result.
The v3 `False` hold is evaluated first and is unchanged. If it does not hold,
the candidate considers only a new, unbooked shipment during a well-formed
active disruption. It reconstructs the fallback-compatible safe booking graph,
finds the fallback distance-shortest path, and computes the minimum
route-change count over the exact shortest-distance subgraph. It returns `True`
and installs a complete booking chain
only when a different tied path has strictly fewer adjacent service-route
changes. Every other state returns `None` and delegates unchanged to the
organizer.

The implementation uses runtime topology and context order only. It must
not name ports, routes, dates, seeds, scenarios, or fixed volumes; it must not
read or write files, use the environment, network, subprocesses, wall-clock
time, randomness, or mutable module state. It must import `Booking` lazily only
after a complete path is validated, install references transactionally, and
roll back on failure. Both delegate and v3-hold paths remain mutation-free.

## Evidence and limits

The pre-code oracle examined 50 derived disruption-window midpoints and all
380 demands (19,000 observations) without advancing a model or writing
Output. It reproduced 48 v3 holds and found 100 candidate-only equal-distance
fewer-transfer ties, with no overlap with a v3 hold. This establishes structural
activation only; the official 72-period full score remains the sole performance
decision. A path tie does not prove that vessel phase or berth queues will be
better, so the candidate is intentionally limited to exact distance ties.

The post-implementation real-context audit invoked the actual participant hook
over the same 19,000 observations and observed exactly 100 candidate
installations, 48 v3 holds, 18,852 delegations, no model advancement, and no
Output write.

## Fixed experiment contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and the sole local branch: `main`;
- round/scenario: `round1` / `create_with_disruption`;
- seed: `2026`; `PYTHONHASHSEED=0`;
- warm-up: `140` days; measured horizon: `360` days;
- ATT interval: `5` days; required numbered periods: `72`;
- accepted v3 control loss: `19.084638612143134`;
- accepted v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- candidate evidence directory:
  `.challenge/round1/results/equal_distance_route_tie_break_v25_20260819/`;
- ignored aggregate:
  `experiments/results/round1_equal_distance_route_tie_break_v25_20260819.json`;
- strict acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Exactly one full candidate run is permitted after all gates pass. Equality,
worsening, invalid output, incomplete completion markers, mutation, a crash, or
a failed gate is rejection. On rejection, preserve ATT/log before any restore,
commit the result, revert only candidate tests/code in reverse order,
synchronize v3, restore its pinned ATT byte-for-byte, re-score the exact
control, rerun all final gates, and leave the clean v3 state active. No tuning,
second candidate, push, merge, PR, upload, or submission is part of v25.
