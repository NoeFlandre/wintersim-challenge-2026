# Round 2: time-aware booking assignment (v9)

**Status: ACCEPTED — complete. The candidate strictly improved the accepted
control and is now the active strategy.**

## Why a new architecture

Every Round 2 experiment so far (v1–v8) tuned one binary predicate: whether to
hold new cargo at its origin while a disruption is active. The accepted v1
policy gained `0.3997` (`1.13%`). Widening it (v2 half-headway, v3
three-quarter-headway, v7 upper-quartile half-headway) and narrowing it (v4
late-recovery, v6 TEU-dominance) both made the score worse, and the berth hook
(v5) produced a byte-identical ATT. That neighbourhood is exhausted: the hold
predicate is at a local optimum worth roughly 1% of the objective.

Stepping back, the incumbent never exercises the main power the organizer's
own interface grants. `assign_associated_bookings` is documented as:

> A custom strategy should create the required `Booking` objects, populate
> `shipment.associated_bookings` in sequence order, register each booking in
> its service route's `associated_bookings` collection, and set
> `shipment.current_booking_index`.

The incumbent only ever returns `False` (hold) or `None` (delegate). All actual
routing is therefore done by `DefaultStrategy`, which runs Dijkstra over
**sailing distance**. Distance is the wrong objective: it ignores service
frequency entirely.

## Measured diagnosis

A read-only audit built fresh disruption contexts, applied the runtime
disruption state exactly as `DisruptionManager` does, created the organizer's
alternative routes, and for every demand compared the default distance-optimal
booking path with a time-optimal path. Evidence is in the ignored directory
`.challenge/round2/results/audit_20260903/`.

- Across the 166 disruption days: 62,555 demand-time observations, of which
  **10,564 (16.9%)** have a strictly faster time-aware path. Median saving
  `53.7` hours; p90 `90.8` hours.
- On days with **no** active disruption the same defect is present:
  **70 of 380 demands (18.4%)** are improvable, and the TEU-weighted mean
  saving over *all* demands is `5.12` hours.

The defect is structural, not disruption-specific. Representative cases:

| OD | default path | time-optimal path | saving |
| --- | --- | --- | --- |
| Busan→Kaohsiung | S2 Busan→Shanghai, S4 Shanghai→Kaohsiung | S2 Busan→Kaohsiung | 52.1 h |
| Shanghai→Busan | S4 Shanghai→Kaohsiung, S2 Kaohsiung→Busan | S2 Shanghai→Busan | 52.1 h |
| Singapore→Busan | S1, S4, S2 (three bookings) | S1 Singapore→Shenzhen, S2 Shenzhen→Busan | 53.7 h |

In each case the default buys a marginally shorter distance at the price of an
extra transshipment, and each transfer costs roughly half of the next route's
headway. S4's headway is `154` hours, so a transfer added to save 33 nautical
miles costs about three days.

Capacity is not a binding constraint and cannot absorb the difference: the
control run reports service-route utilisation of `0.88%`–`6.12%` and an average
of `0.11` vessels waiting for a berth. Transport time in this scenario is
dominated by sailing time plus waiting for the next departure, which is exactly
what the default ignores.

## Frozen policy

`UserStrategy.assign_associated_bookings` builds the booking chain itself for
newly generated cargo, minimising **estimated transport time** instead of
distance. Every quantity is read from the live runtime objects.

Edge cost, for one booking on one service route:

```text
hours = sum over traversed legs of (sailing_distance * sailing_time_multiplier) / mean_deployed_speed
      + 3.0 * (traversed_legs - 1)
```

`3.0` is the organizer's own fixed `BerthBerthing` duration, charged once per
intermediate port call; it is not a tuned constant. Boarding a route costs the
expected wait for its next departure on the booked segment:

```text
headway  = route cycle hours / number of deployed vessels
wait     = 0.5 * headway
```

A shipment loads only onto a vessel whose next segment equals the booking's
departure segment index, so departures on a given segment are separated by
exactly one headway and `0.5 * headway` is the expected wait. The path cost is
the sum of edge costs plus one boarding wait per service route used.

The chain is chosen by Dijkstra over `(port, service route)` states, so a route
change is priced correctly. Consecutive edges on the same route are forbidden;
this is lossless because the candidate set already contains the direct edge for
every ordered pair of distinct ports on a route, and it guarantees one booking
per route.

Guards, all fail-closed to `None` (organizer fallback):

- only newly generated cargo (`associated_bookings` empty and
  `current_booking_index is None`);
- only nominal service routes (`source_service_route is None`) with at least
  one deployed vessel, so a booking can never be orphaned when the organizer
  restores an alternative route's vessel at recovery;
- ports whose every berth is unavailable are excluded as an edge's arrival or
  intermediate port, read from live `berth.is_available`;
- congested legs are usable at their true `sailing_time_multiplier` cost, but
  only when a congestion-free path also exists. If the only path traverses a
  congested leg, the strategy delegates so the organizer's protective wait
  still applies;
- any malformed, non-finite, ambiguous, or incomplete runtime data delegates.

Bookings are constructed only after the whole path is validated, then appended
in one pass, so no partial chain can be left behind.

## What this replaces

The v1 one-transfer port-closure hold and the inherited multi-transfer
recovery hold are both removed. They exist to avoid a bad detour chosen by the
default; when the strategy chooses the detour itself the predicate is
redundant, and keeping both would confound the experiment. The `False` (hold)
outcome survives only through delegation in the guarded cases above.

## Compliance boundary

No organizer model, event logic, or scoring code is changed. Cargo moves only
through normal bookings, vessels, berths, and cargo handling; nothing is
completed early or teleported. `maritime_data_context` is already an allowlisted
submission import and supplies `Booking`. The strategy is deterministic
(no randomness, no wall clock, no iteration over unordered containers, integer
tie-breaks only), read-only apart from the booking chain the interface requires
it to create, performs no I/O, and keeps no cross-call state.

## Pre-run gates (recorded before the authoritative run)

Frozen implementation commit: `047895b`. Participant strategy SHA-256
`bc7989ffec898742e6805c3c99d5fba8b7f72abf38f36275b7831a50450af0a6`.

- `uv lock --check`, locked sync, Ruff format/lint, mypy, and ty all clean. A
  participant-owned stub under `stubs/` declares the organizer-supplied
  `Booking` surface so both type checkers can resolve an import that exists
  only in the evaluation runtime; it is never packaged.
- 233 non-integration tests pass with `92.29%` branch coverage
  (`96%` for the strategy itself).
- 6 real-context integration tests pass against the organizer's own Round 2
  disruption scenario. They assert that every assigned chain is valid against
  the organizer data model (contiguous sequence indexes, real segments,
  origin-to-destination port continuity, one route per booking, registered on
  its route), that no chain is ever slower than the organizer's own choice
  under the same cost model while at least one is strictly faster, that closed
  destinations delegate while transit cargo is still routed around the closure,
  and that no vessel, route, or `Output` file changes.
- Deterministic participant-only package, twice, SHA-256
  `b0eb25abae3669011931e248e84ce58b0df55240d8059f42924f1ed337459b41`, members
  `response_strategies/README.md` and `response_strategies/user_strategy.py`.

### Activation audit

A read-only audit loaded both the accepted control strategy and the candidate
by path, built a fresh context per sampled instant, applied the runtime
disruption state, and evaluated every demand at all 166 disruption days plus
10 undisrupted days. Evidence:
`.challenge/round2/results/audit_20260903/activation.json`.

| control decision | candidate decision | observations |
| --- | --- | --- |
| `None` (delegate) | `True` (own chain) | 66,070 |
| `False` (hold) | `True` (own chain) | 285 |
| `None` (delegate) | `None` (delegate) | 525 |

The 285 former holds match the accepted v1 policy's documented hold count
exactly. Candidate chain lengths were 23,646 single bookings, 28,070 two-booking
chains, 14,304 three-booking chains and 335 four-booking chains, so the policy
still transfers when a transfer is genuinely faster. The audit reported
`mutation_free=true`, `model_advanced=false` and `output_written=false`.

### Isolated partial A/B pre-check

Two isolated copies of the organizer tree, identical except for
`response_strategies`, each ran the organizer's own measurement loop for a
140-day warm-up plus 60 measured days. This is a breakage and direction check
only; it is not the acceptance criterion.

- control: 170,517 of 188,300 shipments completed, `0` unbooked;
- candidate: 171,129 of 188,300 shipments completed, `0` unbooked;
- periods 1-12 cumulative loss: control `+0.21935`, candidate `-0.43175`,
  delta `-0.65110`.

Zero unbooked shipments in both arms is the important safety result: the chain
builder never strands cargo. The candidate's negative partial loss is the
predicted mechanism, since these early periods carry no active disruption and
the improvement therefore comes from routing quality alone.

## Control and acceptance

- accepted control loss: `35.1039547178493` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 35.1039547178493 - 1e-9
```

Equality, worsening, invalid output, crash, or a failed final gate is
rejection. On rejection the candidate code and tests are reverted, the accepted
control is synchronized, and its pinned ATT is restored and re-scored.

## Control reproduction

Before the candidate ran, the accepted control strategy was run once in this
environment with the frozen configuration. It reproduced the documented result
bit for bit, which establishes that the comparison is sound and that this
container is deterministic:

- control ATT SHA-256: `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`
  (byte-identical to the documented accepted control);
- control cumulative loss: `35.1039547178493` over 72 periods, equal to the
  documented value to the last digit;
- runtime `01:01:13`; evidence under
  `.challenge/round2/results/control_repro_20260903/`.

## Full-run result and decision

Exactly one authoritative candidate run used the frozen configuration and the
fixed command, exiting `0` after `00:39:37` with Period 72, Simulation Day 360,
`Simulation completed.` and the CSV-written marker. The ATT was preserved
before scoring, and its write is proved fresh: the manifest pinned the stale
pre-run `Output` ATT at mtime `1788469792234316665` with the control's hash,
and the scored file has mtime `1788472226137910850`.

- candidate ATT SHA-256: `cbde868e871b9dbe624e2aeeb222b6e4f9638375d6a5178dbf1bf571413e5a88`;
- raw log SHA-256: `a44e51370c4f709d40ac2312ac85a8d48c01c9d0a3f041aeb736dff1ad4a48e6`;
- 72 numbered periods; candidate mean ATT `14.79388888888889` days against the
  control's `15.557500000000001` days;
- **candidate cumulative resilience loss: `20.248013560766417`**;
- accepted-control loss: `35.1039547178493`;
- difference: `-14.855941157082881`;
- relative improvement: `42.3198505025677%`;
- periods better/equal/worse: `50 / 0 / 22`.

The immutable acceptance rule was evaluated unchanged:

```text
20.248013560766417 < 35.1039547178493 - 1e-9
```

It is true, so the candidate is **ACCEPTED**. No second candidate was run and
no threshold was altered after launch.

### Independent reproduction

An exploratory full run of the identical strategy in a separate copy of the
organizer tree, started before the authoritative run, produced ATT SHA-256
`cbde868e871b9dbe624e2aeeb222b6e4f9638375d6a5178dbf1bf571413e5a88` — byte
identical to the authoritative run — and therefore the same score. Two
independent runs of the frozen candidate agree exactly.

## Where the improvement comes from

| window | periods | control loss | candidate loss | delta |
| --- | --- | --- | --- | --- |
| Shanghai->Kaohsiung congestion | 13 | `16.7290` | `4.9317` | `-11.7973` |
| Colombo->New Jersey congestion | 13 | `1.2326` | `-0.0164` | `-1.2490` |
| Qingdao->Busan congestion | 6 | `1.6728` | `0.5622` | `-1.1107` |
| no active disruption | 33 | `13.4287` | `12.6009` | `-0.8278` |
| Tianjin closure | 3 | `1.5063` | `1.2781` | `-0.2283` |
| Piraeus closure | 4 | `0.5345` | `0.8916` | `+0.3571` |

The result matches the pre-run diagnosis rather than merely beating it. The
Shanghai-Kaohsiung congestion window alone accounts for `-11.7973` of the
`-14.8559` total, or 79% of the improvement. That window carries `47.7%` of the
control's entire loss and was never addressable by the v1-v7 hold family, which
only ever operated inside the two port closures worth `5.8%` between them.

The mechanism is the one the audit identified. While `Shanghai->Kaohsiung` is
congested, the organizer's distance-based fallback sends Shanghai->Los Angeles
cargo - the largest single demand in the matrix at `6,393` annual TEU - along
`S1 Shanghai->Shenzhen`, `S2 Shenzhen->Kaohsiung`, `S4 Kaohsiung->Los Angeles`:
three bookings and two transfers, chosen because it is 79 nautical miles shorter
than the two-booking `S2 Shanghai->Busan`, `S9 Busan->Los Angeles` path. At S4's
`154`-hour headway the extra transfer costs days. Control ATT peaks at `20.51`
days in period 39; the candidate holds it to `16.15`.

The `33` periods with no active disruption improve by `-0.8278`, confirming the
audit's finding that the defect is structural and not disruption-specific.

## Regressions and what they indicate

`22` periods are worse: 1, 6, 18, 19, 42, 52, 54, 55, 56-63, 66-68 and 70-72.
They are not scattered noise; they cluster in two places.

1. **Periods 56-63 and 70-72** (late run, no active disruption) contribute most
   of the loss added back. This is the signature of the cost model
   under-pricing transfers: the companion measurement in
   [`round2-cost-model-fidelity.md`](round2-cost-model-fidelity.md) shows the
   estimate is low by about `+45` hours per boarding, roughly half the network's
   `108`-hour mean headway, so chains with more transfers are chosen more often
   than they should be and the error accumulates through the run.
2. **The Piraeus closure window** is the only window that is worse overall
   (`+0.3571`). Closure handling is the one area where the retired v1 hold was
   doing useful work, so a closure-specific refinement is a separate candidate.

Both point to concrete, separately testable follow-ups rather than to a flaw in
the accepted result.

## Post-acceptance verification

The accepted candidate remained synchronized and active. All final gates were
rerun after the result was recorded:

- `uv lock --check`, locked all-group sync, Ruff format and lint, mypy, and ty:
  clean;
- 233 non-integration tests, `92.29%` branch coverage (gate `90%`);
- 6 real-context integration tests against the organizer's Round 2 scenario;
- Round 2 sync leaves participant and runtime `user_strategy.py` byte-identical
  at `bc7989ffec898742e6805c3c99d5fba8b7f72abf38f36275b7831a50450af0a6`;
- Round 2 smoke: `smoke: OK`;
- deterministic participant-only package, twice, SHA-256
  `022c0b3abcd2a5a9e5abbf31fb7ce7af1525772e10ea30b0f6861c8644845955`, members
  `response_strategies/README.md` and `response_strategies/user_strategy.py`
  only;
- restricted-material scan of tracked files: no archive, `Input/`, `Output/`,
  `main.py`, `default_strategy.py`, or `simulation_model/` path is tracked;
- clean Git working tree.

One bookkeeping correction: the `package_sha256` pinned in the pre-run manifest
(`b0eb25ab...`) was computed before the participant README was rewritten for
this policy, so it is stale. The manifest has been annotated with the final
package hash. Only `user_strategy.py` affects evaluated behaviour, and its hash
is identical across the manifest, the participant tree, the synchronized
runtime, and both completed full runs.
