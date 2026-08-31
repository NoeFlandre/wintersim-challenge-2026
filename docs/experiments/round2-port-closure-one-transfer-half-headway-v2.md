# Round 2: port-closure one-transfer half-headway hold (v2)

**Status: REJECTED — COMPLETE**  
**Branch:** `main`  
**Frozen implementation commit:** `3451042`  
**Scenario:** `create_with_disruption`  
**Seed:** `2026` with `PYTHONHASHSEED=0`

## Objective

Round 2 measures average transport time (ATT) and converts it into cumulative
resilience loss. Lower loss is better. The accepted Round 2 control is the
previous full-headway strategy:

- control loss: `35.1039547178493` over exactly 72 five-day periods;
- control ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`.

The candidate is accepted only when
`candidate_loss < 35.1039547178493 - 1e-9`. Equality, worsening, invalid
output, or incomplete execution is rejection.

## Frozen hypothesis and policy

The current strategy already holds a newly generated direct shipment when a
safe detour requires at least two service-route changes. It also holds a
one-change detour when the active disruption is port-only and the recovery
margin exceeds one full safe-route headway.

This experiment changes exactly one comparison: the one-change, port-only
branch now holds when the positive recovery margin exceeds **half** the
maximum safe-route headway. All other guards, route construction, hooks,
delegation behavior, and fail-closed handling are unchanged. No booking is
created or edited by the participant strategy.

The strict inequality preserves boundary delegation. Malformed data, mixed or
leg-only constraints, non-positive/non-finite timing, unavailable paths, and
all other cases return `None` so the organizer fallback remains in control.

## TDD and implementation record

- RED contract: `c8e0380`, including synthetic boundary cases and a real
  Round 2 context contract;
- GREEN implementation: `3451042`, changing only the threshold and the
  participant README (plus the corresponding boundary-test expectations);
- focused GREEN result: 11 tests passed;
- participant and synchronized organizer-runtime strategy hashes:
  `48d4a66efcfe2e85bc63109643c7063a993fdf5ee2e9ad0562fccae4b8e859fc`;
- participant and synchronized README hashes:
  `8eba9104c9b9ccc5e1d05e3a9bd352028056a8beb28ae3265316c6d941e9adfb`.

## Non-operational activation evidence

Before the run, a private audit evaluated every integer-day midpoint in the
two Round 2 port-closure windows, using a fresh organizer context and every
demand at each timestamp. It did not advance a model or write Output:

- 21 timestamps and 7,980 observations;
- 261 observations matched the accepted control policy;
- 337 observations matched the half-headway candidate;
- 76 candidate-only observations, with an annual-TEU exposure proxy of
  163,600;
- participant calls were mutation-free and the existing ATT file was
  byte/metadata unchanged.

The audit is structural evidence only; it is not a score prediction. Its
ignored evidence is under
`.challenge/round2/results/port_closure_one_transfer_half_headway_v2_20260831/`.

## Pre-run gates

All gates passed before freezing the run:

- `uv lock --check` and `uv sync --locked --all-groups`;
- Ruff format/lint, Ty, and mypy;
- full pytest: 246 passed;
- non-integration branch coverage: 237 passed, 90.36%;
- integration suite: 9 passed;
- Round 2 sync and smoke: `SMOKE_OK`;
- deterministic package twice: SHA-256
  `81b48fd6e774f83b181b3cc7773af152a033cca773c41ea886ebf2569c0168f9`,
  containing only `response_strategies/README.md` and
  `response_strategies/user_strategy.py`;
- clean Git state and no live simulation/process.

## Authorized run contract

Exactly one full run is authorized, with no tuning or duplicate run:

```bash
PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache \
uv run wsc2026 run --round round2 --full \
  > .challenge/round2/results/port_closure_one_transfer_half_headway_v2_20260831/full_run.log 2>&1
```

The raw log and newly written ATT must be preserved before scoring, sync,
smoke, packaging, or restoration. Completion requires exit code 0, Day 360,
Period 72, `Simulation completed`, and a fresh ATT write. The preserved ATT is
then scored against the authoritative Round 2 baseline over exactly 72
periods and compared with the pinned control.

If the candidate is rejected or invalid, the result is documented first; the
implementation and RED contract are reverted in reverse order, the accepted
control strategy is synchronized, the pinned control ATT is restored and
rescored, and every final gate is rerun. Candidate logs/ATT/evidence remain
ignored and are never submitted.

## Evidence locations

- audit script and JSON: `.challenge/round2/results/port_closure_one_transfer_half_headway_v2_20260831/`;
- candidate run log and ATT (created only by the authorized run): the same
  ignored directory;
- this tracked report records the immutable design, gates, acceptance rule,
  and final outcome after the run.

## Full-run outcome

The single authorized run completed successfully before scoring:

- exit code `0`, Period 72, simulation day 360, and `Simulation completed`;
- runtime `00:36:05`;
- fresh candidate ATT SHA-256:
  `4633263a8f0a829879eee88302f3afd0d210635f344e7cb08cee4114373191c7`;
- candidate loss: `35.6743500877092` over 72 periods;
- candidate mean ATT: `15.590555555555556` days;
- control loss: `35.1039547178493` and control mean ATT
  `15.557500000000001` days;
- delta: `+0.5703953698598999` (`+1.625240292291681%`), with 8 periods
  better, 57 equal, and 7 worse than control.

The candidate therefore **fails** the strict acceptance rule and is rejected.
The raw log SHA-256 is
`5934e5b1c6bf2d659939b9b8d99cbb967cf469aec7389f3b4c318ee69cea8854`.
Machine-readable results are in the ignored `result.json`, `score.json`, and
`control_score.json` files beside the preserved ATT and log.

The half-headway extension did not improve the aggregate score. The result is
not evidence that the policy is universally harmful; it is evidence that this
candidate is not an improvement under the fixed Round 2 run contract.

## Restoration record

After evidence preservation, the candidate implementation and RED-only test
surface were reverted by `a245abb` and `3f3b07b`. The accepted full-headway
control was synchronized back into the Round 2 runtime and its pinned ATT was
restored. The final active strategy hash is
`b4857197a73d7eae4a1d6d1bde3d31e50aa09aff8fcb9a08849d0ea53207ce41`; the
restored ATT hash is
`3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`, and it
rescores to exactly `35.1039547178493` over 72 periods. Candidate evidence
remains ignored for auditability and is not part of the submission.
