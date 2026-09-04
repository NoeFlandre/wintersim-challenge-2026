# Round 2: a port closure is temporary, not a wall (v12)

**Status: ACCEPTED — complete. Passed both the Round 2 rule and the held-out
generalisation rule, and is now the active strategy.**

## Hypothesis

The accepted v10 policy treats any port whose berths are all unavailable as
permanently unusable: no ride may arrive there or call there on the way, and
cargo bound for it is delegated, which makes the organizer hold it at its
origin. But a closure has an end date, and that date is in
`context.disruption_plans`. Cargo that will not reach the port until after it
reopens loses nothing by being routed through it, and cargo bound for it is
better off sailing now and waiting at the far end than waiting at the origin
and sailing afterwards.

The held-out evidence says this is where the objective is most exposed. On a
structurally different scenario built for
[the v11 experiment](round2-live-departure-phase-v11.md) — congestion on
`Singapore->Colombo`, `Busan->Los Angeles` and `Rotterdam->Tanger Med`, plus
closures at **Singapore** and **Rotterdam** — the accepted v10 policy loses
`24.4653` over 30 measured periods, against roughly `6` over Round 2's first
30. ATT climbs from `13.7` to `24.9` days and stays there for nine periods.
Singapore is the hub of five of the nine services, so shutting it makes almost
every Asia-Europe and Asia-Indian-Ocean chain unroutable under a policy that
treats the closure as a wall, and the cargo simply ages at its origin.

Round 2's own closures are short (14 days at Piraeus, 7 at Tianjin), which is
exactly the regime where the timing matters most: much of the cargo planned
during those windows would arrive after they lift.

## Exact participant delta

1. `_closure_recovery` reads the hours from now until each port whose
   close-berth plan is active reopens.
2. An edge that calls at a shut port is no longer discarded. It carries
   `closed_calls`, the `(hours into the ride when the call happens, hours until
   that port reopens)` pairs, and `_edge_arrival` charges the wait: a call that
   would land before the reopening is held until it, and everything after it
   shifts by the same amount.
3. The path search costs an edge with `_edge_arrival` from the current label
   instead of adding a fixed duration, which makes the cost time-dependent in
   this one respect. The dependence is FIFO — setting off later never arrives
   earlier — so the search remains correct.
4. A closed destination is therefore routable, and cargo bound for one is
   booked rather than delegated.

**With no closure active the arrival reduces to `depart + edge.hours`, exactly
the v10 cost.** The behavioural delta is confined to the windows where a
closure is live, which keeps attribution clean and bounds the risk.

## Guarding the epoch assumption

Plan offsets are relative to the start of the simulation, which this code takes
to be `datetime.min`. Rather than trust that, a reopening time is used only
when the plan arithmetic and the live berth state agree: the port must be shut
according to `berth.is_available` *and* have a close-berth plan that the offset
arithmetic says is active. If a future round starts its clock elsewhere the two
disagree, no reopening time is produced, and the port falls back to being
treated as impassable — the v10 behaviour. A malformed plan, a non-datetime
`now`, and a congested-leg plan all produce no reopening time by the same route.

## Why this should generalise

The change adds no tuned constant. It replaces a categorical assumption that
is simply false — "a shut port is shut forever" — with the duration the model
itself publishes. It is inert on an undisrupted network, inert when closure
timing cannot be established, and its benefit grows with how short the closure
is relative to the transit time, which is a property of any scenario rather
than of this one.

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

Acceptance additionally requires no regression on the held-out `shifted`
scenario, scored against the organizer baseline over the same periods. Learning
from v11, the held-out runs are extended to 300 measured days so they cover
their disruption windows *and* the recovery tail; v11's misleading held-out
verdict came from a 150-day horizon that stopped before the effects landed.
Held-out candidates are ranked by cumulative loss, never by mean ATT, which
disagreed in sign for v11.

## Full-run result and decision

Exactly one authoritative run used the frozen configuration and the fixed
command, exiting `0` after `00:20:55` with Period 72, Simulation Day 360 and
`Simulation completed.` The ATT is proved fresh: the manifest pinned the stale
pre-run `Output` ATT at mtime `1788475552620326918` with the v10 control's
hash, and the scored file has mtime `1788499522215734574`.

- candidate ATT SHA-256: `d466899bacfa55c53469bea39879b46a7140e587b981efef1a0b44ad1a983954`;
- 72 numbered periods; candidate mean ATT `14.455` days against the control's
  `14.541944444444445`;
- **candidate cumulative resilience loss: `13.27493539992092`**;
- accepted v10 control loss: `14.897068731156086`;
- difference: `-1.6221333312351653`;
- relative improvement: `10.888943056579961%`;
- periods better/equal/worse: `15 / 55 / 2`.

```text
13.27493539992092 < 14.897068731156086 - 1e-9
```

is true, so the Round 2 rule is met.

## Held-out generalisation result

The `shifted` scenario — closures at **Singapore** and **Rotterdam**, and
congestion on `Singapore->Colombo`, `Busan->Los Angeles` and
`Rotterdam->Tanger Med` — was run for 60 measured periods with both arms
sharing the scenario and seed, and scored against the organizer baseline.

| arm | loss | mean ATT | completed | unbooked |
| --- | --- | --- | --- | --- |
| v10 control | `47.5856` | `16.8178` d | 383,616 / 413,312 | `0` |
| v12 candidate | `42.6751` | `16.4917` d | 385,294 / 413,312 | `0` |

Delta `-4.9105` (`-10.32%`), with 34 periods better, 18 equal and 8 worse, and
1,678 more shipments delivered.

The held-out improvement of `10.32%` is within half a point of the Round 2
improvement of `10.89%` on a scenario the change was never tuned against, with
different closed ports, different congested legs and different durations. That
is the evidence that this is a better policy rather than a better fit.

Both rules are met, so the candidate is **ACCEPTED**.

## Where the Round 2 gain comes from

| window | periods | changed | v10 | v12 | delta |
| --- | --- | --- | --- | --- | --- |
| no active disruption | 33 | 14 | `9.7485` | `8.7463` | `-1.0022` |
| Tianjin closure | 3 | 3 | `1.3131` | `0.6931` | `-0.6199` |
| Colombo->New Jersey congestion | 13 | 0 | `-0.8973` | `-0.8973` | `0.0000` |
| Shanghai->Kaohsiung congestion | 13 | 0 | `3.5510` | `3.5510` | `0.0000` |
| Qingdao->Busan congestion | 6 | 0 | `0.6122` | `0.6122` | `0.0000` |
| Piraeus closure | 4 | 0 | `0.5696` | `0.5696` | `0.0000` |

Only 17 of 72 periods change at all, and every one of them is period 56 or
later. The three congestion windows are untouched, exactly as designed: the
change is confined to closures.

The timing of the effect is worth understanding, because it looks wrong at
first. The Piraeus closure occupies periods 52-55 but those periods do not
move; the first change is period 56. ATT charges an unfinished shipment its
age at the period end whether it is sitting at its origin or sailing, so
booking cargo instead of holding it does not alter the metric while the cargo
is still in flight — it alters it when the cargo *completes*, which for
Europe-bound cargo is several periods later. The Tianjin closure improves
inside its own window (periods 64-66, `-0.6199`) because its cargo has shorter
transits and finishes sooner.

## Post-acceptance verification

- `uv lock --check`, locked sync, Ruff format and lint, mypy, ty: clean;
- 242 non-integration tests, `91.96%` branch coverage (gate `90%`), including
  eight new timed-closure behaviour tests that were each checked to
  discriminate against v10: for a hub reopening in 20 hours v10 takes the long
  way and v12 rides through, for one reopening in 100 hours both avoid it, and
  for a closed destination v10 delegates while v12 books;
- 6 real-context integration tests, including a contract that every planned
  call at a shut Piraeus is charged the wait it implies;
- participant and runtime `user_strategy.py` byte-identical at
  `3e7987b6dfd4a2b3ee0adce5004c0839da7d46b74525e43248630876e119da14`;
- Round 2 smoke: `smoke: OK`;
- deterministic participant-only package, twice, SHA-256
  `5e87c66dfa0fdf8a93d4690cd2413b20513fc4b6e1009f699b72bcd886dd2a41`;
- restricted-material scan clean; clean Git working tree.
