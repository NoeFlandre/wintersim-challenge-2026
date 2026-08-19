# Round 1 multi-TEU missed-connection buffer v20

**Status: IMPLEMENTED AND AUDITED — full-run preflight is pending.**

The accepted v3 policy remains the control at cumulative resilience loss
`19.084638612143134` over 72 periods and ATT SHA-256
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.

V20 preserves every v3 hold. It adds one bounded capacity-risk allowance only
for integer multi-TEU shipments on the same direct-versus-multi-transfer
topology: if the direct recovery estimate is not already faster, it may still
hold when it is faster than the detour plus one shortest safe-route headway.
The live headway represents one possible missed connection from insufficient
remaining vessel capacity. Exact equality and uncertainty delegate.

The complete frozen rationale, rejected alternatives, policy, audit contract,
run identity, strict acceptance expression, and restoration procedure are in
[`the design`](../superpowers/specs/2026-08-19-round1-multi-teu-missed-connection-buffer-v20-design.md)
and [`the implementation plan`](../superpowers/plans/2026-08-19-round1-multi-teu-missed-connection-buffer-v20.md).

## RED→GREEN record

- design: `b621248`;
- RED contract: `e79479a`;
- GREEN implementation: `2534b7f`;
- RED focused result against v3: exactly 2 intended failures and 53 passes;
- GREEN focused result: 55 passes;
- candidate participant SHA-256:
  `0ae8fe79212040a9a7384755cfd633783a77620d00b871808c851cfdc1f29134`.

The implementation adds one pure minimum-headway helper and one final strict
multi-TEU branch after the unchanged v3 comparison. It creates no bookings and
mutates no supplied state.

## Formal activation audit

The non-overwriting ignored audit sampled 50 derived timestamps and 19,000
demand-time observations with fresh organizer contexts. It reported:

- 48 one-TEU v3 control holds;
- 59 two-TEU v20 holds;
- 11 candidate-only decisions and zero control-only decisions;
- repeated annual-TEU exposure proxy `10,053`;
- `no_mutation: true`, unchanged Output, and no model advancement.

The audit JSON and private path/demand details remain ignored under
`.challenge/round1/results/multi_teu_missed_connection_buffer_v20_20260819/`.
These counts prove reachability only; the complete 72-period score decides.

No full candidate simulation is permitted until all remaining quality,
runtime, package, safety, control-identity gates, and the non-overwriting
pre-run manifest are complete.
