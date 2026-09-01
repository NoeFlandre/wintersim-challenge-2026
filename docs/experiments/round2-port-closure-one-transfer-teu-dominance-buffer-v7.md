# Round 2: upper-quartile TEU half-headway closure hold (v7)

**Status: DESIGN — no candidate implementation or full run is authorized yet.**

## Hypothesis

The accepted Round 2 control holds a new direct shipment when a port-only
closure makes a one-transfer detour slower than waiting for direct recovery by
more than one full safe-route headway.  A read-only audit of the current Round
2 context found a second reachable group: the recovery margin is positive and
larger than half a safe-route headway, but not larger than the full headway.
There are 106 such one-transfer observations; 52 are upper-quartile annual-TEU
demands, and 39 of those also exceed the half-headway boundary.

Round 2's objective is TEU-weighted transport time.  This experiment tests
whether the conservative borderline group is worth holding only for the
highest-volume demand flows, where avoiding a detour has the greatest direct
objective exposure.  The accepted full-headway policy remains unchanged for
all demands, as does every multi-transfer decision.  The new rule is an
identity-free combination of live timing and demand data, not a scenario or
seed lookup.

The strongest failure mode is that even a positive timing advantage below one
full headway is not robust in the event-driven queue: retaining these extra
shipments may increase shared vessel congestion and downstream waiting more
than it reduces their direct service time.  The official 72-period cumulative
resilience-loss score, not the structural activation count, decides.

## Exact participant delta

Only `UserStrategy.assign_associated_bookings` changes.  Preserve the accepted
v1 predicate and all preconditions.  In its one-change, port-closure-only
branch:

1. keep returning `False` for the existing strict full-headway condition
   (`margin > max_safe_headway`) for every well-formed demand;
2. for a positive margin at or below one full headway, return `False` only when
   `margin > 0.5 * max_safe_headway` and the shipment demand is present in a
   well-formed `context.demands` sequence whose positive finite `annual_teus`
   is at or above the deterministic third quartile;
3. otherwise return `None` and delegate to the organizer fallback.

The half-headway comparison is strict at the lower boundary and the existing
full-headway decision is retained at its equality boundary.  A malformed or
missing demand population, non-finite/non-positive volume, or demand object not
present by identity delegates.  Multi-transfer holds, pure congestion, mixed
constraints, inactive windows, and every other hook remain exactly as in the
accepted control.  The strategy is read-only, deterministic, standard-
library-only, fail-closed, and never constructs or edits bookings, routes,
vessels, cargo, context, files, outputs, or model state.

## Challenge compliance

Only participant files under `submission/response_strategies/` are evaluated.
The candidate does not modify or bypass organizer event logic and uses the
normal origin waiting/retry lifecycle: `False` means no booking is assigned,
while `None` delegates to the organizer.  It uses no organizer imports,
filesystem/network/subprocess/environment access, wall-clock time, randomness,
mutable cross-run state, hard-coded ports/routes/dates/seeds, or extra package.

## TDD and activation gate

Commit this design before code.  RED tests must fail against the accepted v1
adapter only for the new upper-quartile half-headway behavior and must cover
strict lower/full boundaries, upper and below-quartile demands, malformed
populations, demand identity, preservation of existing full-headway and
multi-transfer holds, public signatures, and complete no-mutation behavior.
Add a real Round 2 integration test that derives a high-volume candidate-only
case and a lower-volume delegate from the organizer context.

Before any full run, perform a fresh non-mutating audit at every valid Round 2
disruption midpoint and every demand. Compare an independent accepted-v1
oracle with the candidate, require candidate-only holds in the declared
upper-quartile half-headway slice, verify zero control-only decisions and no
unexpected holds, and prove no participant mutation, model advancement, or
`Output` write. Activation is a GO gate only; it is not score evidence.

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
  `.challenge/round2/results/port_closure_one_transfer_teu_dominance_buffer_v7_20260901/`.

After the full preflight, freeze an immutable non-overwriting manifest with the
exact HEAD, strategy/runtime hashes, accepted-control/baseline hashes, audit
counts, package members/hash, stale Output metadata, and run command. Exactly
one full candidate run is allowed. Preserve the fresh ATT and raw log before
scoring or any sync, smoke, package, or restoration command. Equality,
worsening, incomplete output, crash, timeout, mutation, or failed final gate
rejects the candidate. On rejection, document first, revert only v7 code/tests
with `git revert`, synchronize the accepted v1 control, restore its pinned ATT,
re-score exactly, rerun all final gates, and leave `main` clean. No tuning,
duplicate run, second candidate, push, merge, submission, or history rewrite
belongs to v7.
