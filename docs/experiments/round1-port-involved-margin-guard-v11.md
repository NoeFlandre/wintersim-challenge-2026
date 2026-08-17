# Round 1 port-involved margin guard v11

**Status: PRE-RUN REVIEW — implementation complete; no full run authorized yet.**

This is one separately named Round 1 candidate from the accepted v3 control.
The participant boundary remains only `submission/response_strategies/`; all
organizer source, inputs, outputs, and private evidence remain ignored.

## Hypothesis and exact policy

V10 showed that removing every port-involved v3 hold is harmful. V11 tests a
smaller uncertainty: a port-involved hold whose timing advantage is less than
the first safe service route's full headway may be too fragile to justify
waiting at origin. Only those cases delegate; all pure-leg holds and
port-involved cases with a margin at least one full safe headway retain the v3
`False` hold.

The policy changes only
`UserStrategy.assign_associated_bookings(context, now, shipment)`:

```text
if v3 would hold and a matching constraint is a port closure and
   detour_hours - hold_hours < first_safe_route_headway_hours:
    return None
else:
    return the existing v3 decision
```

The equality boundary retains the hold. All existing v3 guards, strict timing
comparison, exception handling, three delegated hooks, read-only behavior, and
submission restrictions remain unchanged. The strongest failure mode is that
even a small positive margin is useful for fragmented detours, so delegating
these cases could worsen loss.

## Fresh structural audit

The audit used fresh `create_with_disruption()` contexts at every integer-day
midpoint inside every valid disruption window and every demand in context
order. It sampled 50 timestamps and 19,000 observations without advancing a
model, writing Output, or retaining mutated state.

- v3 control holds: `48`;
- v11 retained holds: `35`;
- v11 candidate-only delegations: `13`;
- candidate-only annual-TEU exposure proxy: `9,876`;
- all candidate-only cases matched both `leg` and `port` constraints and had a
  timing margin below the first safe-route headway;
- no mutation observed.

Activation and exposure are structural evidence, not score predictions. The
ignored audit JSON will be stored at
`.challenge/round1/results/port_involved_margin_guard_v11_20260817/activation_audit.json`.

## RED → GREEN implementation record

The RED contract was committed as `8dd0781697935a08778f681f9dcdf37026894e2b`.
Against untouched v3, exactly the new low-margin synthetic assertion and the
real-context low-margin assertion failed; the rest of the focused suite passed.
The GREEN implementation was committed as
`c61a7ce360ffd50343bc8d5f25023fa4f714ab57`. It adds one read-only
constraint-kind helper and applies the strict margin/headway guard after every
existing v3 predicate. The equality boundary retains the hold. Focused unit
and integration verification is `43 passed`; Ruff format/check, Ty, and mypy
are clean.

The activation audit is preserved at
`.challenge/round1/results/port_involved_margin_guard_v11_20260817/activation_audit.json`
with SHA-256
`ad4bc3c55529bb6da42bd71515954f4b9c646af89f0bd49e681398223b4f8ec1`.
It confirms 48 v3 holds, 35 retained v11 holds, 13 low-margin delegations,
9,876 annual-TEU exposure proxy, no mutation, and no model advancement. These
counts are structural activation evidence only; no score has been observed.

## Selection scorecard

- Adjacent evidence: **2/2** — directly narrows the harmful broad v10 subset.
- Candidate-only activation: **2/2** — 13 real structural delegations and
  9,876 annual-TEU exposure proxy.
- Call-site fit: **2/2** — `None` naturally delegates uncertain initial
  booking to the organizer.
- Upside/downside: **1/2** — bounded exposure, but removed holds may help.
- Hidden-scenario generalization: **2/2** — no identities, dates, or fitted
  constants.
- Implementation/mutation safety: **2/2** — one read-only fail-closed guard.
- Novelty: **2/2** — distinct from v4's wait gate and v10's broad removal.
- Behavioral testability: **2/2** — synthetic boundary and real-context tests.

## Fixed control and run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- layout: one worktree, one local branch (`main`), no push/publication;
- starting HEAD: `17eb756cf71fb2fa96be3476925b871777e93ab8`;
- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT snapshot:
  `.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control mean ATT: `20.3675` days;
- control score: `19.084638612143134` over 72 periods;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- round/scenario: `round1` / `create_with_disruption`;
- seed/environment: `2026` / `PYTHONHASHSEED=0`;
- warm-up/measured horizon: `140 / 360` days;
- ATT interval/periods: `5` days / `72`;
- candidate evidence directory:
  `.challenge/round1/results/port_involved_margin_guard_v11_20260817/`;
- ignored aggregate:
  `experiments/results/round1_port_involved_margin_guard_v11_20260817.json`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

## TDD, preflight, and restoration contract

RED tests must fail only because untouched v3 holds the 13 below-headway
port-involved cases. GREEN must prove the strict/equality/headway boundaries,
pure-leg parity, malformed delegation, real-context activation, exact public
signatures, forbidden capabilities, and complete state immutability.

Before launch, lock/sync, Ruff, Ty, mypy, true branch coverage at least 90%,
unit/integration tests, Round 1 sync/cmp, smoke, deterministic package twice,
restricted scans, one-worktree/main cleanliness, and no-live-process checks
must pass. A non-overwriting manifest must pin the launch identities.

Exactly one full run is allowed. On equality, worsening, invalid output,
crash, timeout, stale/missing ATT, or any failed gate: preserve fresh evidence,
commit this result, revert only v11 implementation/tests in reverse order,
synchronize v3, restore the pinned ATT byte-for-byte, re-score exact control,
rerun every final gate, and update public records. No tuning, second candidate,
push, merge, PR, upload, submission, or history rewrite is allowed.
