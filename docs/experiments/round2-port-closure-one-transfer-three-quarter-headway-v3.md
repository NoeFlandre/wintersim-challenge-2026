# Round 2: port-closure one-transfer three-quarter-headway hold (v3)

**Status: PRE-RUN FROZEN**  
**Branch:** `main`  
**Implementation commit:** `b5484cc`  
**Scenario:** `create_with_disruption`  
**Seed:** `2026` with `PYTHONHASHSEED=0`

## Why this experiment

The accepted Round 2 control holds direct cargo for port-only, one-transfer
detours only when the recovery margin exceeds one full safe-route headway. A
half-headway extension was tested immediately before this experiment. It added
76 structural activations but scored `35.6743500877092`, worse than the
control `35.1039547178493`, and was reverted.

The half-headway audit showed that its new population contained three distinct
margin bands. This experiment keeps the control unchanged and adds only the
highest-margin band: a one-transfer, port-closure-only hold whose positive
recovery margin is greater than **three quarters** of the maximum safe-route
headway. The narrower policy tests whether the strongest of the rejected
extension's cases are beneficial without reintroducing its lower-margin cases.

## Frozen policy

The participant strategy remains read-only, deterministic, standard-library
only, and fail-closed. It changes only the one comparison in the existing
one-change/port-only branch:

```text
hold when margin > 0.75 × maximum safe-route headway
```

The comparison is strict. Equality delegates. Existing multi-transfer holds,
full-headway one-transfer holds, all leg or mixed disruptions, invalid data,
unavailable paths, and all other hooks retain their control behavior.

## TDD and implementation

- RED contract commit: `cc8ed84` (synthetic boundaries plus a real organizer
  context contract);
- GREEN implementation commit: `b5484cc` (threshold, README, and boundary
  expectations only);
- focused GREEN result: 11 tests passed;
- participant/runtime strategy SHA-256:
  `b921ddbb65752c0b84ff66c99eac1a026cf212bd38d43127e083f046fbef96fc`.

The real-context contract loads the organizer runtime by path, samples every
integer-day midpoint in the port-closure windows until a qualifying case is
found, asserts no participant mutation, and asserts no ATT Output write.

## Non-operational audit

The private audit evaluated every integer-day midpoint in both port-closure
windows and every demand in each fresh context. It advanced no model and wrote
no organizer Output:

- 21 timestamps and 7,980 observations;
- 261 accepted-control activations;
- 287 candidate activations;
- 26 candidate-only activations, with annual-TEU exposure proxy 54,975;
- every candidate-only ratio was either approximately 0.8511 or 0.9063;
- mutation-free participant calls and unchanged ATT bytes/metadata.

This is structural evidence, not a score prediction. Evidence is retained in
the ignored directory
`.challenge/round2/results/port_closure_one_transfer_three_quarter_headway_v3_20260901/`.

## Control and acceptance

The pinned control is the accepted full-headway result:

- control loss: `35.1039547178493` over exactly 72 five-day periods;
- control ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`.

Acceptance is strict:

```text
candidate_loss < 35.1039547178493 - 1e-9
```

Exactly one full run is authorized. No tuning, duplicate run, second candidate,
or submission is part of this experiment.

## Fixed run command

After all gates and a final manifest check, run exactly:

```bash
PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache \
uv run wsc2026 run --round round2 --full \
  > .challenge/round2/results/port_closure_one_transfer_three_quarter_headway_v3_20260901/full_run.log 2>&1
```

Completion requires exit code 0, Period 72, simulation day 360,
`Simulation completed`, and a fresh ATT. Preserve the log and ATT before
scoring or any synchronization/restoration. Score the preserved ATT against
the authoritative baseline over all 72 periods, then compare it with the
pinned control.

## Rejection procedure

On rejection, invalid output, incomplete execution, or failed final gate, keep
the result evidence and report it first. Revert the implementation and RED
contract in reverse order, synchronize the accepted control, restore the
pinned control ATT, rescore exactly `35.1039547178493`, and rerun every final
gate. Candidate evidence remains ignored and is never packaged.

## Evidence

The ignored experiment directory will contain the audit, pre-run manifest,
raw log, preserved candidate ATT, score, control score, and final result
record. This tracked report is updated after the run with the immutable result
and final active state.
