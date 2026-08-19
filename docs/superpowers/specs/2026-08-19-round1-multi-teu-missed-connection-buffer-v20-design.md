# Round 1 multi-TEU missed-connection buffer v20 design

## Status

**DESIGN FROZEN.** This document authorizes one implementation and, only after
all pre-run gates pass, exactly one full Round 1 candidate simulation. It does
not authorize tuning, a duplicate run, a second candidate, publication, or
submission.

## Starting control

- accepted strategy: multi-transfer recovery hold v3;
- control cumulative resilience loss: `19.084638612143134` over 72 periods;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control participant/runtime SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- starting repository HEAD:
  `dcd912a2d4d80eea7ff3dba25cc09bce9317e06d` on the sole local `main` branch.

## Brainstorm and decision

Four identity-free directions were compared against the complete experiment
ledger.

1. Remove or narrow v3 holds. Rejected before implementation: v4, v9-v11,
   v13-v14, v17, and v18 already showed that several independent removals make
   the score worse.
2. Add one-transfer or generic earlier holds. Rejected before implementation:
   v6-v8, v12, v15-v16, and the read-only audit show that this repeatedly moves
   in a harmful direction. A broader structural early-hold oracle would add 18
   observations, including the same marginal cases that made v7 worse.
3. Replace shortest-distance bookings with estimated fastest bookings.
   Rejected before implementation: a fresh audit found 8,366 changed demand-
   time observations, while the similar disruption-weighted and phase-aware
   booking experiments were materially worse. The footprint is too broad.
4. Preserve v3 and add one capacity-risk buffer only for multi-TEU cargo.
   Selected: it is additive, keeps all 48 audited v3 decisions, has a direct
   queueing rationale, and changes only 11 audited demand-time observations.

## Hypothesis

V3 estimates each safe service boarding with half of that route's headway, but
it does not model a missed sailing caused by insufficient remaining vessel
capacity. A shipment larger than one TEU is harder to fit into the greedy
loading remainder at every transfer. On a safe detour requiring at least two
service changes, one missed connection adds a complete route headway.

For multi-TEU cargo only, treating the shortest headway among the safe path's
boarded routes as one bounded missed-connection risk may correctly favor the
recovering direct service in a small set of marginal cases. One-TEU cargo and
all existing v3 decisions remain unchanged.

## Exact policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a new non-`None` result. The other three hooks remain unconditional
`None` delegates.

The policy preserves every v3 precondition and calculation: empty initial
booking state; well-formed active disruption; one nominal direct booking edge
that intersects the disruption; a complete safe path with at least two service
route changes; deterministic topology order; finite positive speeds,
distances, fleet headways, and timing values; and fail-closed behavior.

After computing the unchanged values:

```text
hold_hours   = disruption recovery wait + nominal direct service hours
detour_hours = safe path sailing hours + half-headway per service boarding
```

the decision is:

1. if `hold_hours < detour_hours`, return `False` exactly as v3 does;
2. otherwise require `shipment.teu_size` to be a non-boolean integer greater
   than one;
3. derive one headway per distinct safe-path route using the existing validated
   route profile and take the minimum positive finite headway;
4. return `False` only when
   `hold_hours < detour_hours + minimum_safe_route_headway_hours`;
5. equality, one-TEU cargo, malformed size/profile, or any uncertainty returns
   `None` without mutation.

The minimum headway is conservative: it represents one missed service on the
most frequent route in the detour. It is derived from live route/fleet data,
not a tuned number. The participant remains deterministic, standard-library-
only, read-only, free of mutable cross-run state, and free of scenario names,
ports, routes, dates, seeds, I/O, environment reads, network, subprocesses,
wall-clock time, and randomness.

## Read-only activation gate

Before implementation, a disposable real-context oracle sampled the midpoint
of every integer day in every valid Round 1 disruption window: 50 timestamps
and all 19,000 demand-time observations. It found 48 v3 holds and 11 additional
two-TEU candidate decisions inside one live safe-route headway, with zero v3
decisions removed. The candidate-only repeated annual-TEU exposure proxy was
`10,053`. Organizer Output was unchanged.

The formal ignored audit must independently reproduce these counts for exact
one- and two-TEU synthetic shipments, snapshot full relevant state around each
oracle call, advance no model event, write no Output, and refuse to overwrite
its evidence. Activation is reachability evidence, not performance evidence.

## Fixed run and decision contract

- round/scenario: `round1` / `create_with_disruption`;
- organizer seed / process hash seed: `2026` / `PYTHONHASHSEED=0`;
- warm-up / measured horizon / ATT interval: `140 / 360 / 5` days;
- required numbered periods: `72`;
- writable uv cache: `/tmp/wsc-uv-cache-v17`;
- sole full-run command:
  `PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache-v17 uv run wsc2026 run --round round1 --full`;
- ignored evidence directory:
  `.challenge/round1/results/multi_teu_missed_connection_buffer_v20_20260819/`;
- ignored aggregate:
  `experiments/results/round1_multi_teu_missed_connection_buffer_v20_20260819.json`;
- acceptance, at full precision:

```text
candidate_loss < 19.084638612143134 - 1e-9
```

Equality, worsening, stale/invalid output, missing Day 360 or Period 72,
nonzero exit, mutation, or failed final gate is rejection. Preserve fresh ATT
and the raw log before scoring, sync, smoke, packaging, or restoration.

If rejected, commit the result record first, revert only candidate code/tests
and participant README changes in reverse order with `git revert`, synchronize
v3, restore its pinned ATT bytes, re-score exactly, rerun every final gate, and
leave v3 active. No second run or candidate is allowed.
