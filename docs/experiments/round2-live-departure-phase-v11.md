# Round 2: read the first departure from live vessel positions (v11)

**Status: DESIGN — frozen before the authoritative run.**

## Hypothesis

v9 and v10 established that booking chains should be chosen by estimated time,
and that a boarding costs about one headway. Both charge that cost from a
*statistic*: `headway = cycle hours / deployed vessels`. A statistic cannot tell
the difference between a service whose vessel is about to arrive and an
identical service whose vessel has just left, even though those two differ by a
whole cycle for the cargo standing on the quay.

The information needed to tell them apart is in the context. Every vessel
exposes `current_segment` and `current_berth`, and every route exposes its
ordered segments, so the time until a route next departs a given segment can be
computed by walking each deployed vessel forward around the rotation and taking
the earliest.

This experiment uses that live phase for the **first** boarding only, which is
the one the cargo is actually standing in front of. Later boardings keep the
headway expectation, because sailing time carries ±5% variation and phase
information about a connection several days away has decayed to noise by the
time the cargo gets there. Pretending otherwise would be false precision.

## Exact participant delta

1. Each edge carries `first_wait_hours`, the hours until its route next departs
   that edge's departure segment, derived from live vessel positions:
   - a vessel alongside a berth is half a berthing time from departing;
   - a vessel at sea has, in expectation, half of its current leg left, then a
     port call;
   - thereafter each further segment costs a leg plus a port call.
   The earliest offer across the deployed vessels wins.
2. The path search charges `first_wait_hours` for the first service boarded
   instead of the headway. Transfers are unchanged.
3. The headway itself becomes the reciprocal of the combined departure rate,
   `1 / sum over vessels of (1 / cycle hours of that vessel)`, each vessel's
   cycle computed at its own speed. For the usual equal-speed deployment this
   is exactly `cycle / vessel count`, which a unit test pins as an identity, so
   it cannot perturb a settled result. It only starts to matter where a route
   mixes vessel classes of different speeds.

Everything else is untouched: edge construction, the closed-port and
congested-leg guards, nominal-routes-only, the `(port, route)` search, the
three-hour berthing per intermediate call, and all fail-closed delegation.

## Graceful degradation, on purpose

A route whose vessels cannot all be located on its own rotation — a vessel
mid-reassignment, or any shape this code has not seen — falls back to the
headway expectation for that route rather than being dropped from the graph or
failing the whole decision. This keeps the policy usable in scenarios that
differ from the one it was developed against, which matters more for the hidden
round than for this one.

## Why this should generalise rather than overfit

No constant in this change is fitted to Round 2. `first_wait_hours` is read
from the model's own state, and it *removes* a calibration rather than adding
one: the question v10 answered approximately ("how long is a boarding wait on
average?") stops being asked for the leg where it mattered most. The
mixed-speed headway is a strict generalisation that is provably an identity on
any equal-speed deployment. The remaining constants are the organizer's own
three-hour berthing time and the expectation that an unobservable progress
point through a leg is halfway.

Because a lower score on one scenario is weak evidence of a better strategy,
this candidate is also measured on held-out scenarios it was not developed
against: the same disruptions under a different seed, a structurally different
disruption set, and the undisrupted network. Those comparisons need no baseline
because both arms share a scenario, so the lower mean ATT is the better policy.

## Control and acceptance

- accepted control loss: `14.897068731156086` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `4f22259de77c2e77477ba21f0f7c36c988ee9c5e80cca425984fe65aa0ad6eb4`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 14.897068731156086 - 1e-9
```

Equality, worsening, invalid output, crash, or a failed final gate is
rejection. Acceptance additionally requires that the candidate does not lose
ground on the held-out scenarios; a candidate that wins Round 2 while losing
elsewhere is overfitting and is rejected on that ground alone.
