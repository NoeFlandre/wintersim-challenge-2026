# Round 2: port-closure one-transfer late-recovery hold (v4)

**Status: PRE-RUN FROZEN — one full run authorized by this protocol**
**Branch:** `main`  
**Scenario:** `create_with_disruption`  
**Seed:** `2026` with `PYTHONHASHSEED=0`

## Hypothesis

The accepted Round 2 control holds a new shipment when a port-only closure
would make a one-transfer detour more than one full safe-route headway slower
than waiting for the direct service to recover. Across the complete audit,
the control holds 285 observations: 31 inherited multi-transfer holds and 254
one-transfer holds. A structural timing audit found that 98 one-transfer
holds occur while the remaining recovery wait is at least one safe-route
headway, during the early part of the closure windows; 156 occur later, when
recovery is already within one headway.

Holding cargo early in a long closure can create an origin backlog and delay
later cargo even when the eventual direct route is attractive. This experiment
keeps every existing control decision except that one-transfer port-closure
holds are allowed only when the remaining recovery wait is **strictly less
than one maximum safe-route headway**. The strongest failure mode is that the
early holds are necessary to avoid the detour and removing them worsens the
aggregate score.

The observed counts are structural reachability evidence, not a score
prediction. The 72-period cumulative resilience-loss score remains the sole
acceptance criterion.

## Implementation and audit result

The RED contract was committed as `7397c05` and the real-context RED contract
as `630e414`. The minimal implementation is `d357602`: it adds only the
strict `wait_hours < max_safe_headway` check in the existing one-transfer,
port-closure-only branch and updates the participant explanation. No other
hook or organizer file changed.

The fresh read-only audit is stored privately at
`.challenge/round2/results/port_closure_one_transfer_late_recovery_v4_20260901/activation_audit.json`.
It covered 166 timestamps and 63,080 demand observations and proved:

- control holds: 285;
- candidate holds: 187;
- control-only delegations: 98;
- control-only annual-TEU exposure proxy: 219,695;
- candidate decisions are a subset of control decisions;
- no participant mutation, model advancement, or Output write.

The audit result is `go: true`. It demonstrates that the candidate is live;
it does not predict the score.

## Exact candidate policy

Only `UserStrategy.assign_associated_bookings` may differ. Preserve the
accepted full-headway policy and all multi-transfer behavior. In the existing
one-change, port-closure-only branch, retain the positive-margin test and add
one strict guard:

```text
hold only when wait_until_recovery < maximum_safe_route_headway
```

Equality delegates. All other hooks, topology checks, disruption validation,
path calculations, exception handling, deterministic tie rules, and
read-only/no-I/O guarantees remain unchanged. The rule uses no port, route,
date, demand, seed, output, or fitted constant.

## Challenge and compliance boundary

Round 2 scores TEU-weighted Average Transport Time (ATT) through the repository
scorer's cumulative resilience loss; lower is better. The accepted control is
`35.1039547178493` over exactly 72 five-day periods. Accept only:

```text
candidate_loss < 35.1039547178493 - 1e-9
```

The participant boundary remains only `submission/response_strategies/`.
Participant code is standard-library-only, deterministic, fail-closed, and
must not mutate organizer objects, use I/O/environment/network/process/random
APIs, import organizer modules, or bypass normal booking/retry behavior.

## Control identity

- control strategy SHA-256:
  `b4857197a73d7eae4a1d6d1bde3d31e50aa09aff8fcb9a08849d0ea53207ce41`;
- control ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- control score: `35.1039547178493` over 72 periods;
- control snapshot:
  `.challenge/round2/results/port_closure_one_transfer_full_headway_v1_20260831/ATT_By_Statistics_Interval.csv`.

## TDD and activation audit contract

Write RED tests before the implementation. They must cover a qualifying
late-recovery hold, an early-recovery full-headway case that now delegates,
exact wait/headway equality, inherited strict margin equality, malformed and
non-finite values, all retained control branches, public signatures, and
complete no-mutation snapshots. Add a real-context integration contract for a
candidate/control divergence without selecting identities.

The ignored audit must evaluate fresh `create_with_disruption()` contexts at
every integer-day midpoint in every valid disruption window and every demand in
context order. It must compare an independent full-headway control oracle with
the candidate hook, record anonymous wait/headway and exposure aggregates,
assert candidate decisions are a subset of control decisions, and prove no
model advancement, no Output write, and no participant mutation. The
recomputed structural result is 285 control holds, 187 candidate holds, 98
control-only delegations, and an annual-TEU removal proxy of 219,695.

All pre-run gates are green: `uv lock --check`, locked all-group sync, Ruff
format/check, Ty, mypy, 245 full tests, 236 non-integration tests at 90.36%
coverage, 9 integration tests, Round 2 sync, `SMOKE_OK`, deterministic
packaging, clean restricted-material scans, and a clean Git tree. The frozen
manifest is the ignored
`.challenge/round2/results/port_closure_one_transfer_late_recovery_v4_20260901/pre_run_manifest.json`.

## One-run contract

Before launch, freeze a non-overwriting manifest with the exact HEAD, strategy
and runtime hashes, control/baseline hashes and score, audit hash, package hash
and members, stale Output metadata, gate results, no-live-process proof, exact
command, and strict acceptance expression. Run exactly one full candidate with:

```bash
PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache \
uv run wsc2026 run --round round2 --full \
  > .challenge/round2/results/port_closure_one_transfer_late_recovery_v4_20260901/full_run.log 2>&1
```

Require exit code `0`, Period 72, simulation day 360, `Simulation completed`,
and a fresh ATT. Preserve the raw log and ATT before scoring or any sync,
smoke, packaging, or restoration. Compare the preserved score with the fixed
control using the expression above; equality, worsening, invalid output,
incomplete completion, or failed final gates is rejection.

## Rejection and restoration

Record the result before cleanup. Revert only the v4 implementation and RED
contract in reverse order with `git revert`, synchronize the accepted control,
restore and re-score the pinned ATT byte-for-byte, and rerun all final gates.
Candidate evidence remains ignored and private. No tuning, duplicate run,
second candidate inside v4, submission, publication, push, or history rewrite
is authorized.
