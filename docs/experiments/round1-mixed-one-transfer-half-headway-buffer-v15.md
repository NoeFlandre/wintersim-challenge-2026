# Round 1 mixed one-transfer half-headway-buffer recovery hold v15

**Status: PRE-RUN REVIEW — no full simulation authorized yet.**

The accepted v3 policy holds only safe detours requiring at least two service
route changes. V12 added six mixed leg+port one-transfer cases and scored
`19.313383619092`, slightly worse than v3. The profile of those six cases shows
the same Shenzhen → Busan demand, with a positive hold-vs-detour margin from
`23.551818181818135` to `143.55181818181813` hours, while the first safe route
has a `154.76363636363635` hour headway. V15 adds only the subset with a
strict margin greater than half that headway. It preserves all v3 holds and
delegates all other states.

## Frozen policy

The only changed hook is `assign_associated_bookings`. In addition to every v3
condition, a new shipment may be held when:

1. the nominal shortest path is one disrupted direct edge;
2. the safe shortest path has exactly one service-route change;
3. the nominal edge matches both an active leg and active port constraint;
4. the v3 recovery-versus-detour estimate is strictly positive; and
5. `detour_hours - hold_hours > 0.5 * first_safe_route_headway_hours`.

The half-headway buffer is a conservative uncertainty margin: v3 already
models each service-route transition with half a headway, so a one-transfer
extension must have more than one such buffer before it overrides the
organizer's fallback. Equality delegates. Missing or invalid values delegate.
No v3 hold is removed. Other hooks remain unconditional delegates.

## Fixed control and acceptance

- checkout: `/Users/noeflandre/wintersim-challenge-2026`, one clean `main` worktree;
- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required periods: exactly `72`;
- v3 strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- v3 control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control loss: `19.084638612143134`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Equality, worsening, stale/invalid output, incomplete markers, mutation, or a
failed gate is rejection. Exactly one full simulation is allowed; no tuning or
second run belongs to v15. On rejection, revert the candidate and restore v3
participant, runtime, and ATT before final gates.

## Activation evidence

The preceding private v3 profile is retained at
`.challenge/round1/results/v3_activation_profile_v15_20260819/profile.json`.
The exact v15 oracle audit is
`.challenge/round1/results/mixed_one_transfer_half_headway_buffer_v15_20260819/activation_audit.py`;
its immutable JSON evidence is
`.challenge/round1/results/mixed_one_transfer_half_headway_buffer_v15_20260819/activation_audit.json`
(SHA-256
`f1e6cabaca4db9dbb91e30651b7b175d03e3877f1f9ab6215bb5958ad6149776`).
The audit must evaluate 50 valid timestamps and 19,000 demand observations on
disposable contexts. It reproduced 48 v3 holds, exposed exactly three
candidate-only activations with finite strict buffer margin, observed zero
control-only activations, and wrote no organizer Output (`no_mutation: true`,
`output_written: false`). A dormant or mismatched predicate is a NO-GO and
consumes no simulation.

## TDD and pre-run contract

Add RED tests for the exact mixed one-transfer case below, at equality, above
the half-headway buffer, and for malformed/invalid headway data; retain all v3
tests and no-mutation/public-hook/forbidden-capability checks. GREEN must be a
small local read-only guard with no mutable module state, organizer imports,
I/O, randomness, dates, identifiers, or changes to other hooks. Synchronize
only participant-owned `README.md` and `user_strategy.py` into the ignored
Round 1 runtime.

Before a full run, locked `uv` resolution/sync, Ruff, Ty, mypy, unit coverage
at least 90%, integrations, sync/cmp, one-day smoke, deterministic participant-
only packages, unchanged control score/ATT, restricted-material scans, clean
Git state, and no-live-process checks must pass. Freeze a non-overwriting
manifest with all hashes and the exact run command. Preserve raw log and ATT
before scoring or restoration. No push, merge, PR, upload, submission archive,
history rewrite, or second candidate is part of v15.
