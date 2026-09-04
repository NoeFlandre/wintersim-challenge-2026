# Round 2: read the first departure from live vessel positions (v11)

**Status: REJECTED — control restored. Rejected by both the Round 2 rule and
the held-out generalisation rule.**

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

## Held-out results (measured before the authoritative run finished)

Two held-out scenarios were built from the organizer's own baseline builder and
disruption helpers, each run for a 140-day warm-up plus 150 measured days with
both arms sharing the scenario and seed. Evidence:
`.challenge/round2/results/audit_20260903/holdout_*.json`.

Ranking by mean ATT alone made v11 look marginally better on both
(`-0.17%` and `-0.08%`). That was misleading. The objective weights a period by
`b / ATT^2`, so it cares more about a shipment-hour lost in a good period than
in a bad one, and v11's pattern was to win a lot on a few bad periods and lose
a little on many good ones. Scored properly against the organizer baseline:

| held-out scenario | v10 loss | v11 loss | delta |
| --- | --- | --- | --- |
| `shifted` (different legs and hub closures, seed 2026) | `24.4653` | `25.4562` | `+0.9909` |
| `r2_seed7` (Round 2 disruptions, seed 7) | `3.6526` | `3.4498` | `-0.2028` |

Both arms completed every shipment they booked and left `0` unbooked.

The `shifted` regression alone triggered the precommitted overfitting rule, so
v11 was already rejected before its Round 2 score was known.

## Full-run result and decision

The authoritative run completed all 72 periods with `Simulation completed.`

- candidate ATT SHA-256: `fbb6dc14e3f0810424184bbde799f24b0c46b717d0d531cb9a93c245d268aaf1`;
- raw log SHA-256: `a1653cbb71f9208482bc5d79c275d698f5712305f0339889fd86745e58c5bd8c`;
- **candidate cumulative resilience loss: `18.3386705330832`**;
- accepted v10 control loss: `14.897068731156086`;
- difference: `+3.4416018019271135` (`+23.102543621412345%`, worse);
- candidate mean ATT `14.694444444444445` days against the control's
  `14.541944444444445`;
- periods better/equal/worse: `30 / 0 / 42`.

Both rules fail, so the candidate is **REJECTED** and v10 is restored.

## Why it failed

The idea was sound but the estimator is biased, and the bias has a name.

The live phase for a route is taken as the **minimum** over its deployed
vessels of an estimate that is itself noisy: the progress of a vessel through
its current leg is not observable, so the code assumes it is halfway. Taking
the minimum of several noisy estimates is systematically optimistic — the
winner's curse. The more vessels a route has, the more draws are taken and the
more optimistic the minimum becomes. S1 has eight vessels and S5 has nine, so
exactly the busiest trunk services were made to look most imminent, and cargo
was pulled onto them regardless of whether the rest of the chain was any good.

The mixed costing made it worse. Charging the first boarding a live, optimistic
figure while charging every transfer a full headway is internally
inconsistent: it biases the search toward whichever route happens to look
imminent from the origin, rather than toward the best chain overall.

## Lessons

1. **A statistic beat live data here because the live data was read
   pessimistically-cheaply.** Reading state is only an improvement if the
   estimator built from it is unbiased. `min` over noisy per-vessel estimates
   is not.
2. **Mean ATT is not the objective and can disagree in sign.** v11 improved
   mean ATT on both held-out scenarios while making one of them worse on the
   actual metric. Rank candidates by the metric, never by a convenient average.
3. **Short held-out runs truncate the evidence.** The `r2_seed7` comparison ran
   only 150 measured days, so it barely entered the Shanghai-Kaohsiung window
   where most of v10's advantage accrues, and it wrongly favoured v11. The
   `shifted` scenario, whose disruptions all fall inside the measured window,
   agreed with the authoritative result. Future held-out runs must cover their
   disruption windows *and* the recovery tail.
4. **The held-out protocol earned its cost.** It rejected this candidate before
   the authoritative run finished, on independent evidence, and its verdict
   matched the authoritative one.
