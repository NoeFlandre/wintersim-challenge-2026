# Round 2: a boarding costs a full headway (v10)

**Status: DESIGN — frozen before the authoritative run.**

## Hypothesis

The accepted v9 strategy chooses booking chains by estimated transport time and
charges `0.5 * headway` for each service route boarded, the textbook expected
wait for a random arrival into a perfectly regular service.

The measurement in
[`round2-cost-model-fidelity.md`](round2-cost-model-fidelity.md) shows that
estimate is wrong in a specific, structured way. Over 171,129 completed
shipments the estimate is low by `+51.23` hours for a one-booking chain,
`+100.31` for two and `+139.43` for three: about `+45` hours **per boarding**,
against a network mean headway of `108.0` hours. The realized wait for a
departure is therefore close to a full headway, not half of one.

Two properties of the organizer's model explain it, and neither is a defect in
the estimate's arithmetic:

1. cargo is loaded only if it is already waiting when a vessel begins its port
   call, so cargo that becomes ready during the connecting vessel's handling
   misses that departure and waits another full headway;
2. sailing duration carries a ±5% random variation, so vessels on a rotation
   drift out of even spacing and bunch. For a random arrival the mean wait is
   `E[gap^2] / (2 * E[gap])`, which exceeds `headway / 2` for any variability in
   the gaps and rises toward a full headway as that variability grows.

A per-shipment constant would not change which chain is cheapest. A
per-*boarding* error does: it makes every transfer look cheaper than it is, so
the policy takes transfers it should decline. That is consistent with where v9
loses ground — its 22 worse periods cluster in 56-63 and 70-72, late in the run
and with no active disruption, which is what an error that accumulates over
many shipments looks like.

## Exact participant delta

One line of `_route_edges` changes:

```text
boarding_hours = 0.5 * cycle_hours / vessel_count   ->   cycle_hours / vessel_count
```

Nothing else changes: the same edge construction, the same closed-port and
congested-leg guards, the same nominal-routes-only restriction, the same
`(port, route)` search, the same fail-closed delegation, and the same three-hour
berthing charge per intermediate port call.

`1.0` is not a fitted coefficient. It is the mechanism value — wait one full
headway — and it is what the residual measurement independently points to. The
measurement was recorded and committed (`91af315`) before any run of this
policy, so the design is not a response to a score.

## Why not tune further

The residual analysis fits two shapes to the per-OD data: proportional to the
summed boarding headways (`a = 0.61` extra headway, `R2 = 0.21`) and a constant
per boarding (`b = 35`-`58` hours, `R2 = 0.32`). Both say the same thing and
neither is decisive, and most residual variance is OD-specific rather than
explained by boardings at all. Searching over coefficients would be fitting
noise; the next real gain is to stop estimating the wait statistically and read
the next departure from live vessel positions, which is a separate candidate.

## Compliance boundary

Unchanged from v9. No organizer model, event logic, input, or scoring code is
touched. Cargo moves only through normal bookings, vessels, berths and cargo
handling. The strategy remains deterministic, read-only apart from the booking
chain the interface requires it to create, standard-library-only plus the
allowlisted `Booking` import, and free of I/O and cross-call state.

## Control and acceptance

- accepted control loss: `20.248013560766417` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `cbde868e871b9dbe624e2aeeb222b6e4f9638375d6a5178dbf1bf571413e5a88`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 20.248013560766417 - 1e-9
```

Equality, worsening, invalid output, crash, or a failed final gate is
rejection. On rejection the candidate code and tests are reverted, the accepted
v9 control is synchronized, and its pinned ATT is restored and re-scored.

## Pre-run direction check

An exploratory full run of exactly this one-line change, in a separate copy of
the organizer tree, completed all 72 periods and produced ATT SHA-256
`4f22259de77c2e77477ba21f0f7c36c988ee9c5e80cca425984fe65aa0ad6eb4`. Scored
against the authoritative baseline it gives `14.897068731156086`, against the
v9 control's `20.248013560766417`: `-5.350944829610331` (`-26.43%`), with 54
periods better, 2 equal and 16 worse.

This is a direction check, not the decision. For v9 the same exploratory
method produced an ATT byte-identical to its authoritative run, which is why it
is trusted enough to be worth reporting; the acceptance decision still rests on
one authoritative run in the real round source under the frozen command.
