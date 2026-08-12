# Round 1 pure-congestion transfer hold v8

**Status: frozen for one controlled experiment.**

## Objective and hypothesis

The accepted v3 policy holds new cargo only when a disrupted direct service is
estimated to recover sooner than a safe path requiring at least two service
route changes. Earlier v2 held every safe path with a transfer and improved the
fallback but was worse than v3; v6 tested a different one-transfer slice where
the nominal direct booking spanned multiple physical legs and also worsened.

This experiment isolates a remaining structural case rather than reopening
those rejected policies:

> When one physical direct leg is only slowed by congestion, and the shortest
> safe alternative needs exactly one service-route change, retaining the v3
> recovery-versus-detour timing decision may avoid an unnecessary transfer
> without accepting a closed-berth or multi-leg nominal route.

The strongest failure mode is that even a pure congestion delay is preferable
to waiting at origin because the organizer retry lifecycle, vessel cadence, or
port queues differ from the static timing estimate. The official cumulative
loss, not the activation audit, decides the experiment.

## Exact candidate policy

Only `UserStrategy.assign_associated_bookings(context, now, shipment)` may
return a non-`None` value. The other three hooks remain unconditional
delegates.

The candidate preserves every v3 check and result for existing v3 holds. It
adds one branch for the previously delegated one-transfer subset. It returns
`False` only when all of these are true:

1. the shipment is new, unbooked, and has distinct origin and destination;
2. the disruption state is valid and active under `start <= now < end`;
3. the nominal shortest path is exactly one edge, that edge is affected, and
   that edge spans exactly one physical leg;
4. the safe shortest path has at least two edges and exactly one adjacent
   service-route change;
5. every active constraint intersecting the nominal edge is a congested-leg
   constraint; no closed-berth constraint qualifies;
6. all v3 finite-positive topology, fleet, speed, distance, recovery, and
   timing checks pass; and
7. `hold_hours < detour_hours` at full precision.

All other states return `None` and delegate. The candidate is read-only,
deterministic, standard-library-only, fail-closed, and contains no scenario
identities, dates, seed tables, fitted thresholds, I/O, environment access,
randomness, wall-clock access, mutable cross-run state, or organizer imports.

## Fresh structural activation evidence

A read-only audit used a fresh `create_with_disruption()` context for each
midpoint of every integer day in every valid disruption window (50 timestamps,
19,000 demand-time observations, all demands in context order). It evaluated
the v3 predicate and the frozen candidate predicate without advancing a model,
writing Output, or mutating observed state.

The candidate-only subset contained 7 observations with an annual-TEU exposure
proxy of `10,152`. Every observation had one physical nominal leg, one safe
service-route change, and congestion-only constraints. Closed-berth and
multi-physical-leg nominal shapes were excluded. This is activation evidence,
not a score prediction; the audit is retained only as ignored local evidence.

## Alternatives rejected before implementation

- Re-enabling every one-transfer hold repeats the rejected v2 policy.
- Re-enabling multi-physical-leg nominal edges repeats the rejected v6 shape.
- Including closed-berth or mixed constraints combines different operational
  mechanisms and was not selected.
- Headway or numeric-margin gates repeat the rejected v4 direction and fit an
  additional timing boundary to one scenario.
- Berth, alternative-route, and in-transit policies have already been dormant
  or materially harmful in this Round 1 checkout.

## Immutable run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and one local branch: `main`;
- starting HEAD: `7c8e08481411de3b734f35990e26e30df3e9bc18`;
- active control: accepted multi-transfer recovery hold v3;
- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control cumulative loss: `19.084638612143134` over 72 periods;
- pinned control snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- round/scenario: `round1` / `create_with_disruption`;
- organizer seed: `2026`; `PYTHONHASHSEED=0`;
- warm-up / measured horizon: `140 / 360` days;
- ATT interval / required periods: `5` days / `72`;
- candidate evidence directory:
  `.challenge/round1/results/pure_congestion_transfer_hold_v8_20260812/`;
- ignored aggregate result:
  `experiments/results/round1_pure_congestion_transfer_hold_v8_20260812.json`;
- exact command:
  `PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache-0812 uv run wsc2026 run --round round1 --full`;
- acceptance expression:
  `candidate_loss < 19.084638612143134 - 1e-9`.

Exactly one full candidate run is permitted. Equality, worsening, a crash,
incomplete output, wrong period count, stale output, or any failed gate is
rejection. No code, threshold, test, documentation, tuning, duplicate run,
submission, push, merge, PR, upload, or history rewrite is part of this
experiment.

## Rejection and restoration

Preserve candidate ATT and the raw log before scoring, synchronization, smoke,
or restoration. Commit the result report first. If rejected, revert only the
candidate implementation/tests in reverse order with `git revert`, synchronize
the tracked v3 strategy, restore the pinned v3 ATT bytes byte-for-byte, re-score
to exactly `19.084638612143134`, and rerun every final gate. Keep this design,
plan, audit, and result history.
