# Round 2 port-closure one-transfer recovery hold v1

**Status: ACCEPTED — complete.** The candidate strictly improved the fresh
Round 2 v3 control and remains active.

This report records one proposed Round 2 experiment. The private organizer
source, inputs, outputs, activation evidence, and run logs remain under the
ignored `.challenge/round2/` workspace and must never be tracked or packaged.

## Control and candidate

The starting control is the accepted Round 1 v3 strategy, synchronized into
the private Round 2 runtime. A fresh Round 2 control run must establish the
comparison score before the candidate launch; the Round 1 score is not a Round
2 threshold.

The candidate preserves v3 and adds one case to
`assign_associated_bookings`: a new shipment on a direct nominal edge affected
only by an active port closure may be held when its safe path has exactly one
service-route change and the recovery-versus-detour advantage exceeds the
maximum full headway of the safe-path routes. All malformed, ambiguous,
inactive, congested-leg, mixed, one-change-without-margin, and unrelated cases
delegate normally.

## Compliance boundary

The candidate changes no organizer model or event logic, uses no external
dependency, performs no I/O or random/environment access, and uses the normal
origin waiting/retry process. Only participant files under `response_strategies`
are eligible for evaluation.

## Read-only activation audit

The audit used fresh `create_with_disruption()` contexts at every integer-day
midpoint of each valid Round 2 disruption window and evaluated every demand in
context order. It did not advance a model, write `Output`, or retain a mutated
context. It observed 166 timestamps and 63,080 demand-time observations.

The unchanged v3 predicate held 31 observations. The candidate added 254
candidate-only holds (285 total candidate holds), with an annual-TEU exposure
proxy of 572,165. Every candidate-only observation was port-closure-only,
two-edge, and one-change; the computed timing margin ranged from 150.42 to
581.79 hours while the maximum safe-route headway was at most 154.14 hours.
These counts are structural evidence, not a score prediction. The audit
reported `no_mutation=true`, `model_advanced=false`, and `output_written=false`.
Its private ignored evidence is under
`.challenge/round2/results/port_closure_one_transfer_full_headway_v1_20260831/`.

## Fresh Round 2 control

The accepted v3 policy was run once with Round 2's fixed seed, 140-day warm-up,
360 measured days, five-day statistics, and `PYTHONHASHSEED=0`. The run exited
zero and reached Day 360, Period 72, and `Simulation completed.` The fresh
control ATT was preserved before scoring and has SHA-256
`abbf1442959f819bf79f8ed519368d835e864abcb09370f9cae3658ce08d2521`.
Scoring against the authoritative Round 2 baseline produced cumulative
resilience loss `35.50366097019303` over 72 periods. This fresh score is the
sole candidate comparison threshold; the Round 1 score is not reused.

## Frozen pre-run state

The candidate implementation is committed at launch HEAD
`86de176c0251d66eeef742e85ef042ffaa929d44`. Participant and Round 2 runtime
files are byte-identical. Locked UV resolution/sync, Ruff format/lint, Ty,
mypy, non-integration tests (234 passed, 8 deselected; 90.36% coverage), eight
integrations, Round 2 smoke, deterministic participant-only packaging, clean
restricted scans, clean Git state, and no-live-process checks all passed. The
participant-only package SHA-256 is
`f9d3bdccb5b273552f6543a0632bffe1596db27c3c700f136f6b95499b07551d` and its
members are only `response_strategies/README.md` and
`response_strategies/user_strategy.py`.

The non-overwriting private launch manifest is
`.challenge/round2/results/port_closure_one_transfer_full_headway_v1_20260831/pre_run_manifest.json`.
It pins the control, baseline, candidate/runtime hashes, audit evidence,
package, stale Output metadata, exact command, and strict acceptance rule:

```text
candidate_loss < 35.50366097019303 - 1e-9
```

## Full-run result and decision

Exactly one candidate run used the frozen configuration and completed with exit
code 0. The log contains Period 72 (Days 356–360), Simulation Day 360,
`Simulation completed.`, and the CSV-written marker. The fresh ATT was copied
before scoring.

- candidate ATT SHA-256: `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
- raw log SHA-256: `136b3212ce2a12984e1d9c3e7869c4a435e6c4cdcaf2d24c39bd18cc9f0d29ee`;
- 72 numbered periods; mean ATT: `15.5575` days;
- candidate cumulative resilience loss: `35.1039547178493`;
- fresh v3 control loss: `35.50366097019303`;
- difference: `-0.3997062523437336`;
- relative improvement: `1.1258170042782503%`;
- periods better/equal/worse than control: `11 / 57 / 4`.

The immutable acceptance rule was evaluated without alteration:

```text
35.1039547178493 < 35.50366097019303 - 1e-9
```

It is true, so the candidate is **ACCEPTED**. The private machine-readable
result and post-run manifest are under the ignored experiment evidence
directory. No second candidate, tuning, or restoration was performed.

## Post-acceptance verification

After the run, the candidate remained synchronized and active. The source ATT
and preserved candidate ATT are byte-identical. Locked `uv` resolution/sync,
Ruff format/lint, Ty, mypy, 234 non-integration tests (90.36% coverage), eight
integration tests, Round 2 sync, `SMOKE_OK`, deterministic participant-only
packaging, restricted-material scans, diff hygiene, no-live-process checks,
and clean Git status all passed. The final package SHA-256 is
`f9d3bdccb5b273552f6543a0632bffe1596db27c3c700f136f6b95499b07551d` and its
only members are:

```text
Round2_OrtolanForever/response_strategies/README.md
Round2_OrtolanForever/response_strategies/user_strategy.py
```

The accepted participant strategy is committed on `main` at
`86de176c0251d66eeef742e85ef042ffaa929d44`. The Round 2 archive remains
private; no organizer source, inputs, outputs, or evidence are tracked or
published.
