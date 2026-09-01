# Round 2: upper-quartile pure-leg multi-transfer recovery hold (v8)

**Status: DESIGN — implementation and full run not yet authorized.**

## Hypothesis

The accepted Round 2 control keeps the established multi-transfer recovery
hold from Round 1. A read-only audit of the exact Round 2 context found 31 such
holds: 24 are caused by pure sailing-leg congestion and 7 by a pure port
closure. The leg-congestion group contains two very different exposures: five
high-volume observations for a 6,393-TEU demand and 19 lower-volume
observations for 826–1,296-TEU demands. The port-closure group has large
recovery margins and is left untouched.

The candidate tests whether the lower-volume pure-leg holds create more shared
network backlog than they save in direct cargo time. It keeps the current
policy for all one-transfer cases, all port-closure multi-transfer cases, all
high-volume pure-leg cases, and every malformed or ambiguous input. Only a
well-formed pure-leg multi-transfer hold whose demand is below the context's
deterministic upper quartile delegates to the organizer fallback.

This is deliberately narrower than the rejected Round 2 one-transfer
TEU-dominance and half-headway extensions. It changes no route construction,
berth ordering, in-transit rebooking, or organizer event logic. The full
72-period cumulative resilience-loss score remains the only performance gate.

## Exact participant delta

Only `UserStrategy.assign_associated_bookings` changes. Preserve every current
precondition, graph, shortest-path, timing, and exception rule. In the existing
multi-transfer branch (`safe_path` has at least two service-route changes):

1. If `hold_hours >= detour_hours`, delegate as before.
2. If the nominal edge's matching active constraints are exactly pure `leg`
   constraints, require the shipment demand to be present in a well-formed
   `context.demands` list/tuple and have positive finite `annual_teus` at or
   above the deterministic third quartile. Otherwise delegate.
3. For pure `port` constraints, mixed constraints, and any other well-formed
   multi-transfer case, retain the existing `hold_hours < detour_hours`
   decision unchanged.

The quartile is computed from all context demands in their supplied sequence,
with equality included. Missing/non-sequence demand populations, duplicate or
foreign demand identity, non-finite/non-positive volumes, malformed topology,
and non-finite timing fail closed to `None`. The strategy remains deterministic,
read-only, standard-library-only, and returns only `False` or `None`.

## Challenge compliance

Only participant files under `submission/response_strategies/` are evaluated.
The participant does not import organizer modules, use files, network,
subprocesses, environment variables, wall-clock time, randomness, mutable
cross-run state, hard-coded ports/routes/dates/seeds, or third-party packages.
Returning `None` delegates to the organizer; returning `False` keeps the
shipment in the normal origin retry flow. No shipment, booking, route, vessel,
port, berth, context, or event state is edited.

## TDD and activation gate

Commit this design before implementation. RED tests must fail against the
accepted v1 adapter only for the new lower-quartile pure-leg delegation. GREEN
tests must cover upper-quartile equality inclusion, lower-quartile delegation,
port-closure preservation, mixed-constraint preservation, malformed/missing
demand populations, demand identity, existing one-transfer behavior, exact
timing equality, public signatures, and complete no-mutation behavior. Add a
real Round 2 integration assertion derived from the organizer context.

Before a full run, perform a fresh non-mutating audit at every valid Round 2
disruption midpoint and every demand. Compare an independent accepted-v1
oracle with the candidate. Require the candidate-only difference to be zero,
the control-only differences to be exactly the declared pure-leg,
below-third-quartile slice, and no unexpected decisions, mutation, model
advancement, or `Output` write. Activation is a GO gate only and does not
predict the score.

## Fixed control and run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and one local branch: `main`;
- round/scenario: `round2` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required numbered periods: `72`;
- accepted-control strategy SHA-256:
  `b4857197a73d7eae4a1d6d1bde3d31e50aa09aff8fcb9a08849d0ea53207ce41`;
- accepted-control ATT snapshot:
  `.challenge/round2/results/port_closure_one_transfer_full_headway_v1_20260831/ATT_By_Statistics_Interval.csv`;
- accepted-control ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
- accepted-control cumulative loss: `35.1039547178493`;
- authoritative Round 2 baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:
  `candidate_loss < 35.1039547178493 - 1e-9`;
- private ignored candidate evidence directory:
  `.challenge/round2/results/multi_transfer_leg_teu_guard_v8_20260901/`.

After all preflight gates, freeze an immutable non-overwriting manifest with
exact HEAD, participant/runtime hashes, accepted-control and baseline hashes,
audit counts, deterministic package metadata, stale Output metadata, and the
exact run command. Run exactly one full candidate. Preserve its fresh ATT and
raw log before scoring or any sync, smoke, packaging, or restoration. Equality,
worsening, invalid output, crash, timeout, incomplete completion, mutation, or
failed final gate is rejection. On rejection, document first, revert only v8
code/tests with `git revert`, synchronize the accepted control, restore and
re-score the pinned ATT, rerun all final gates, and then continue with a new
separately documented experiment if the user has asked to keep iterating.
No tuning, duplicate run, second candidate within v8, push, merge, submission,
or history rewrite is part of this experiment.
