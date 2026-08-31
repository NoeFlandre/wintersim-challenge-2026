# Round 2 port-closure one-transfer recovery hold v1

**Status: DESIGN / PRE-RUN.** No Round 2 candidate simulation has run.

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

The full audit, TDD evidence, preflight manifest, control score, candidate run,
decision, restoration, and final verification will be appended here only after
each corresponding step is independently verified.
