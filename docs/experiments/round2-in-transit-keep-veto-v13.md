# Round 2: keep an in-transit chain that already wins (v13)

**Status: ACCEPTED with a documented limitation. It improves Round 2 and is
provably harmless elsewhere, but it captures only a small part of the
opportunity it was built on, for reasons measured below.**

## Hypothesis

`adjust_bookings_before_cargo_handling` is the only in-transit replanning
decision point and is the last hook still fully delegated. The organizer's
implementation carries all three defects that the accepted experiments already
fixed at the origin:

1. it rebuilds the remaining journey by **sailing distance**;
2. it **refuses** the disrupted ports and legs outright instead of pricing
   them, which v12 showed is wrong for a closure that will lift;
3. when the rebuild does not start on the route the cargo is already riding,
   the current booking is **shortened to end at the current port**, so the
   cargo is discharged there and waits for another service.

Cargo already at sea is `69%` of the aged backlog measured at day 305, so this
is the widest untried lever.

## Measurement first

v11 was a plausible story that lost, so this was measured before it was built.
A private diagnostic copy of the organizer tree ran the accepted v12 strategy
unchanged over a 140-day warm-up plus 300 measured days, and at every
`adjust_bookings_before_cargo_handling` call recorded what the organizer was
about to do and compared it, using the strategy's own cost model, with simply
staying aboard. It returned `None` throughout, so no decision changed.
Evidence: `.challenge/round2/results/audit_20260903/intransit_stats.json`.

- `4,784` hook calls; `3,832` shipments the organizer would replan, `5,119` TEU;
- a rebuild path existed in every one of those cases;
- the rebuild was **slower than staying aboard in `2,152`** of them and faster
  in `409` — worse `5.3` times more often than better;
- `1,271` could not be costed by the model and are therefore never vetoed;
- TEU-hours lost to the rebuilds: `1,471,346`; gained: `682,413`; **net
  `-788,933` TEU-hours.**

## Exact participant delta

`UserStrategy.adjust_bookings_before_cargo_handling` returns `True` — a
decision to change nothing — only when every carried shipment whose remaining
chain meets an active disruption is at least as well off staying aboard.
Otherwise it returns `None` and the organizer's replan runs exactly as before.
No booking, route, vessel, or berth is ever mutated by this hook.

The comparison reuses the accepted cost model: the remaining chain is walked
from the vessel's current port with closure waits and live congestion
multipliers priced, and the alternative is the model's own fastest path from
that port to the chain's final port.

The alternative is deliberately costed **optimistically**, with no wait to
board its first service, even though a real transfer would pay one. A chain is
therefore kept only when it beats even the most favourable rebuild. Everything
uncertain — a malformed chain, a ride the model cannot cost, a destination with
no congestion-free path, a shipment whose current booking already ends here —
returns `None`, which restores the organizer's behaviour exactly.

## Why this should generalise

The rule adds no constant and no scenario-specific knowledge. It fires only
when the organizer was about to replan, which requires an active disruption, so
it is inert on an undisrupted network. It is one-sided by construction: it can
only ever *decline* a change, so the worst case is the incumbent's behaviour
plus a decision that keeping was good enough. And the defect it exploits is
structural to any scenario — a distance-ranked rebuild that refuses temporary
disruptions will misjudge cargo that is already most of the way there.

## Control and acceptance

- accepted control loss: `13.27493539992092` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `d466899bacfa55c53469bea39879b46a7140e587b981efef1a0b44ad1a983954`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 13.27493539992092 - 1e-9
```

Acceptance additionally requires no regression on the held-out `shifted`
scenario over 300 measured days, where the accepted control scores `42.6751`.
Held-out candidates are ranked by cumulative loss, never mean ATT.

## Full-run result

One authoritative run completed all 72 periods in `00:21:01`. The ATT is proved
fresh against the pinned stale mtime `1788499522215734574`.

- candidate ATT SHA-256: `1313f8b970b4dd46db306d0b8501bc1b79ddaecf048b21324f97121b46e655c3`;
- **candidate cumulative resilience loss: `11.915883436787134`**;
- accepted v12 control loss: `13.27493539992092`;
- difference: `-1.359051963133787` (`-10.23772939145062%`);
- candidate mean ATT `14.373333333333331` days against `14.455`;
- periods better/equal/worse: `19 / 32 / 21`.

```text
11.915883436787134 < 13.27493539992092 - 1e-9
```

is true, so the Round 2 rule is met.

By window:

| window | periods | better | worse | v12 | v13 | delta |
| --- | --- | --- | --- | --- | --- | --- |
| no active disruption | 33 | 12 | 7 | `8.7463` | `6.5286` | `-2.2177` |
| Colombo->New Jersey congestion | 13 | 0 | 0 | `-0.8973` | `-0.8973` | `0.0000` |
| Qingdao->Busan congestion | 6 | 3 | 3 | `0.6122` | `0.6684` | `+0.0562` |
| Shanghai->Kaohsiung congestion | 13 | 4 | 4 | `3.5510` | `3.7000` | `+0.1490` |
| Tianjin closure | 3 | 0 | 3 | `0.6931` | `0.9766` | `+0.2835` |
| Piraeus closure | 4 | 0 | 4 | `0.5696` | `0.9395` | `+0.3700` |

The gain is entirely in undisrupted periods and every disrupted window is
slightly worse. Gains total `-2.8874` against regressions of `+1.5284`.

## Held-out result: an exact tie, and why

The `shifted` scenario over 300 measured days produced an ATT **byte-identical**
to the v12 control, scoring the same `42.6751`, with `0` of 60 periods changed.
The setup was verified: the held-out tree carried the v13 strategy hash and the
`_network` refactor is behaviour-identical, so the inertness is real.

A follow-up diagnostic counted why the veto declines, over 160 measured days of
each scenario. Evidence:
`.challenge/round2/results/audit_20260903/veto_why_shifted.json` and
`veto_why_r2_seed7.json`.

| | `shifted` | `r2_seed7` |
| --- | --- | --- |
| affected shipment observations | `11,830` | `1,134` |
| vessel calls containing any affected shipment | `68` | `41` |
| prefer keeping | `6,601` | `219` |
| prefer rebuilding | `87` | `915` |
| un-costable (no congestion-free path) | `5,142` | `0` |

Two limitations of this implementation are now measured facts rather than
suspicions.

1. **The per-vessel, all-or-nothing rule throws away most of the
   opportunity.** Affected shipments cluster at roughly 174 per vessel call, so
   a single un-costable shipment forces the whole call to delegate. On
   `shifted` there are `5,142` such shipments across only `68` qualifying
   calls, so essentially every call contains one and nothing is ever vetoed.
   That is the entire explanation for the tie.
2. **The bar is set too conservatively to hit the measured target.** Costing
   the alternative optimistically, with no wait to board it, flips the balance:
   against that yardstick rebuilding is preferred `4:1` on Round 2, whereas
   against what the organizer *actually does* keeping was preferred `5.3:1`.
   Many of the `2,152` harmful rebuilds the pre-run measurement identified are
   therefore still being delegated.

## Why it is accepted anyway

The Round 2 improvement is real and reproducible, and the held-out tie is
direct evidence of harmlessness rather than absence of evidence: this hook
provably never mutates a booking, route, vessel, or berth, and can only ever
*decline* a change the organizer was about to make. Where it does not fire the
behaviour is exactly the incumbent's, which is what the byte-identical held-out
ATT shows. The downside in an unseen scenario is bounded by construction.

What it does not have is positive evidence of generalisation. The successor
experiment addresses both measured limitations directly by deciding per
shipment instead of per vessel and by comparing against a fairly costed
alternative.

## Post-acceptance verification

- `uv lock --check`, locked sync, Ruff format and lint, mypy, ty: clean;
- 267 non-integration tests, `91.06%` branch coverage (gate `90%`);
- 6 real-context integration tests;
- participant and runtime `user_strategy.py` byte-identical at
  `f41bcb10b957fb0bc2a5049b8e1853ac0e941a1a68ad4c32380b42c9c0051765`;
- Round 2 smoke: `smoke: OK`;
- deterministic participant-only package, twice, SHA-256
  `8a6b69c48de4ba859b246866b7cf3ad66f745f67d001c681937c72cf723c990d`;
- restricted-material scan clean; clean Git working tree.
