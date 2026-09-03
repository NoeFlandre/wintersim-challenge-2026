# Round 2: a boarding costs a full headway (v10)

**Status: ACCEPTED — complete. The candidate strictly improved the accepted
v9 control and is now the active strategy.**

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

## Full-run result and decision

Exactly one authoritative candidate run used the frozen configuration and the
fixed command, exiting `0` after `00:39:32` with Period 72, Simulation Day 360
and `Simulation completed.` The ATT was preserved before scoring and its write
is proved fresh: the manifest pinned the stale pre-run `Output` ATT at mtime
`1788472226137910850` with the v9 control's hash, and the scored file has mtime
`1788475552620326918`.

- candidate ATT SHA-256: `4f22259de77c2e77477ba21f0f7c36c988ee9c5e80cca425984fe65aa0ad6eb4`;
- raw log SHA-256: `834a1441616b3a0c7bcc2c37654367b3c200a99aa5325a3c40b3805372bbd86f`;
- 72 numbered periods; candidate mean ATT `14.541944444444445` days against the
  v9 control's `14.79388888888889` days;
- **candidate cumulative resilience loss: `14.897068731156086`**;
- accepted v9 control loss: `20.248013560766417`;
- difference: `-5.350944829610331`;
- relative improvement: `26.427011289535063%`;
- periods better/equal/worse: `54 / 2 / 16`.

The immutable acceptance rule was evaluated unchanged:

```text
14.897068731156086 < 20.248013560766417 - 1e-9
```

It is true, so the candidate is **ACCEPTED**.

The authoritative ATT is byte-identical to the exploratory run's ATT
(`4f22259d...`), so two independent full runs of this frozen candidate agree
exactly — as they did for v9.

## Where the improvement comes from

| window | periods | v9 loss | v10 loss | delta |
| --- | --- | --- | --- | --- |
| no active disruption | 33 | `12.6009` | `9.7485` | `-2.8524` |
| Shanghai->Kaohsiung congestion | 13 | `4.9317` | `3.5510` | `-1.3807` |
| Colombo->New Jersey congestion | 13 | `-0.0164` | `-0.8973` | `-0.8808` |
| Piraeus closure | 4 | `0.8916` | `0.5696` | `-0.3220` |
| Tianjin closure | 3 | `1.2781` | `1.3131` | `+0.0350` |
| Qingdao->Busan congestion | 6 | `0.5622` | `0.6122` | `+0.0500` |

The distribution confirms the hypothesis rather than merely rewarding it. The
prediction was that under-pricing each boarding makes the policy take transfers
it should decline, that this error is not disruption-specific, and that it
accumulates over the run. All three hold:

- the largest single gain, `-2.8524`, is in the `33` periods with **no active
  disruption**, which is where a general mis-costing of transfers should show
  up and where no disruption-specific policy could ever help;
- the v9 regression cluster the measurement was derived from — periods 56-63
  and 70-72 — improves from `9.8975` to `8.1145`, a `-1.7830` recovery of
  exactly the ground v9 had lost;
- the Piraeus closure window, the one window v9 made worse than the old v1 hold
  policy, improves by `-0.3220` and is now better than it was under v1. Pricing
  the wait correctly repaired that without any closure-specific rule.

The `16` worse periods (2, 4, 6, 12-14, 27, 35, 36, 46-50, 64, 69) are scattered
rather than clustered and total far less than the gains, with the two smallest
windows, Tianjin (`+0.0350`) and Qingdao-Busan (`+0.0500`), marginally worse.

## Post-acceptance verification

- `uv lock --check`, locked all-group sync, Ruff format and lint, mypy, ty:
  clean;
- 234 non-integration tests, `92.29%` branch coverage (gate `90%`), including
  a test whose fixture is decided by the coefficient: the half-headway costing
  picks the two-booking feeder/trunk chain, the full-headway costing picks the
  direct service;
- 6 real-context integration tests against the organizer's Round 2 scenario;
- participant and runtime `user_strategy.py` byte-identical at
  `a02c8d791d0624fe0ff23c6e30fd787624f47f3ceb40aae57cc1049f4b8fbe69`;
- Round 2 smoke: `smoke: OK`;
- deterministic participant-only package, twice, SHA-256
  `793617df6a47f2f96fc9952fc184a2effcf8edb04fb40f11e1b09c0bd917e232`, with only
  the two permitted `response_strategies` files;
- restricted-material scan of tracked files clean; clean Git working tree.
