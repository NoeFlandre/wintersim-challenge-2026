# Round 2: upper-quartile pure-leg multi-transfer recovery hold (v8)

**Status: ACCEPTED — strict improvement; incumbent Round 2 strategy.**

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

The design was committed before implementation. The initial RED file had an
escaped docstring and two topology fixtures that did not actually match their
declared constraints; commit `ac567dd` repaired those test-only defects. The
participant implementation is `dc47966`. The focused v8 suite is green, the
existing recovery-hold suite remains green, and
`tests/integration/test_round2_multi_transfer_leg_teu_guard_v8_real_context.py`
exercises the real Round 2 context.

Tests cover upper-quartile equality inclusion, lower-quartile delegation,
port-closure and mixed-constraint preservation, malformed/missing demand
populations, demand identity, no mutation, and the existing one-transfer and
timing contracts.

The fresh non-mutating activation audit is recorded privately at
`.challenge/round2/results/multi_transfer_leg_teu_guard_v8_20260901/`:

- 166 valid disruption midpoints × 380 demands = 63,080 observations;
- accepted-v1 holds: 285; candidate holds: 266;
- exactly 19 control-only decisions, all pure-leg multi-transfer holds below
  the 1,801-TEU third quartile; zero candidate-only or unexpected decisions;
- participant state was unchanged for every call and the pre-existing Output
  ATT file remained byte-identical.

This was a GO gate for the full run, not a prediction of the score.

## Full-run result

The frozen candidate was run once with the fixed Round 2 configuration:

- command: `PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache uv run wsc2026 run --round round2 --full`;
- exit `0`, Period 72 / Day 360, and `Simulation completed`;
- simulation runtime: `00:21:46`;
- candidate ATT SHA-256: `616a8b07870d9de0b2597cb317ee14d4743455f5d4b34f315adf15895fc95700`;
- candidate cumulative resilience loss: `34.62237395179777` over 72 periods;
- candidate mean ATT (the CSV's two-decimal period values): `15.532083333333333` days.

Against the accepted control (`35.1039547178493`, ATT SHA
`3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`), the
candidate is lower by `0.481580766051529`, a `1.3718704058339608%`
improvement. Fourteen periods improved, 52 were equal, and six worsened; the
net gain comes from the later disruption periods, including a `0.46`-day ATT
reduction in Period 58 and a `0.47`-day reduction in Period 63. The candidate
was therefore **accepted** under the strict rule
`candidate_loss < 35.1039547178493 - 1e-9` and remains active.

Private evidence is retained under
`.challenge/round2/results/multi_transfer_leg_teu_guard_v8_20260901/`:

- `full_run.log` (SHA-256 `ae83183f8b111cc8ad17aa93c0eb9e92e5db17361f4568b10c91df0fae08f0cb`);
- `ATT_By_Statistics_Interval.csv` (SHA-256 above);
- `score.json`, `comparison_to_control.json`, and the pre-run manifests.

The first invocation attempted before the run exited before simulator
initialization because `uv` selected an unwritable default cache; its
diagnostic is preserved as `preflight_uv_cache_failure.log`. It produced no
simulation, no Output write, and does not count as a candidate run.

The run checkpoint confirmed the participant/runtime hash
`7e9794843eae071186cfdff4d835fb5d3e645bbd3d09008c86ac7977af1a17ee`, the
candidate ATT in the active Round 2 Output, and no restricted material in Git.
The final verification below is rerun after this report is committed.

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
