# Round 1 multi-TEU missed-connection buffer v20

**Status: DESIGN FROZEN — implementation has not started.**

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

No full candidate simulation is permitted until RED→GREEN implementation,
formal real-context activation evidence, all quality/runtime/package/safety
gates, and a non-overwriting pre-run manifest are complete.
