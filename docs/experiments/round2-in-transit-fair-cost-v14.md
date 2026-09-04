# Round 2: cost the in-transit alternative fairly (v14)

**Status: ACCEPTED — complete. It improves Round 2, regresses neither held-out
scenario, and the intervention it belongs to now has positive held-out
evidence.**

## Hypothesis

v13 was accepted with two limitations that its own diagnostic counters
measured rather than guessed
([report](round2-in-transit-keep-veto-v13.md)). This experiment fixes the one
that is a modelling error, and leaves the structural one alone.

**The wrong yardstick.** v13 costs the alternative to staying aboard
*optimistically*, with no wait to board it. That was meant as caution, but it
is simply wrong: leaving the service the cargo is riding really does mean
waiting for the next one. Measured against that too-cheap yardstick, rebuilding
looked preferable `4:1` on Round 2, whereas measured against what the organizer
actually does, keeping was preferable `5.3:1`. v13 therefore hands back most of
the harmful rebuilds it was built to prevent.

**A requirement copied from the wrong decision.** v13 refuses to decide unless
a congestion-free path exists from the current port. That guard belongs to the
*booking* decision, where committing fresh cargo to a leg with no way round is
a real choice. Cargo already at sea has no such choice, and the guard fired
`5,142` times on the held-out scenario across only `68` qualifying vessel
calls — which, combined with v13's per-vessel all-or-nothing rule, is the
complete explanation for v13 being inert there.

## Exact participant delta

Two changes inside `_keep_booked_chains`, nothing else:

1. The congestion-free-path requirement is removed. Whatever alternative exists
   is costed and compared on its merits.
2. The alternative is charged the wait to board its first service, unless that
   service is the route the cargo is already riding — which is precisely the
   case the organizer's own merge handles without a transfer.

A destination with no alternative at all now counts as "keep", because the
organizer's rebuild would find none either and would leave the chain alone.

Everything else is untouched: the hook still never mutates a booking, route,
vessel, or berth; it still only ever *declines* a change; and it still
delegates on anything uncertain, including a chain riding a
disruption-alternative route, which this model does not carry and which the
organizer may withdraw at recovery.

## Why this should generalise better than v13

The change is a correction toward the truth, not a tuning step: the wait to
board a different service is real, and pretending otherwise made the comparison
wrong in a fixed direction. Removing the congestion-free requirement deletes a
condition that has no meaning for cargo already at sea, and it is exactly the
condition measured to be blocking the held-out scenario — so unlike v13 this
candidate should actually fire there and can be judged on evidence rather than
on inertness.

The one-sided safety property is unchanged and is what bounds the downside.

## Control and acceptance

- accepted control loss: `11.915883436787134` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `1313f8b970b4dd46db306d0b8501bc1b79ddaecf048b21324f97121b46e655c3`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 11.915883436787134 - 1e-9
```

Acceptance additionally requires no regression on the held-out `shifted`
scenario over 300 measured days, where the accepted control scores `42.6751`.
Unlike v13, an exact tie there would now be a warning rather than a pass, since
the condition that made v13 inert has been removed and the candidate is
expected to fire.

## Full-run result and decision

One authoritative run completed all 72 periods in `00:21:31`, with the ATT
proved fresh against the pinned stale mtime `1788503517215839031`.

- candidate ATT SHA-256: `d6c3e6c75cb26e8eb6b2029c7077351f38d670b52186dfec1482926ace843cc6`;
- **candidate cumulative resilience loss: `10.350669070475163`**;
- accepted v13 control loss: `11.915883436787134`;
- difference: `-1.5652143663119702` (`-13.1355293513512%`);
- candidate mean ATT `14.305416666666666` days against `14.373333333333331`;
- periods better/equal/worse: `28 / 33 / 11`, against v13's `19 / 32 / 21`.

```text
10.350669070475163 < 11.915883436787134 - 1e-9
```

is true, so the Round 2 rule is met.

### It repairs what v13 broke

| window | periods | v13 | v14 | delta |
| --- | --- | --- | --- | --- |
| no active disruption | 33 | `6.5286` | `5.7677` | `-0.7610` |
| Piraeus closure | 4 | `0.9395` | `0.4125` | `-0.5270` |
| Shanghai->Kaohsiung congestion | 13 | `3.7000` | `3.3504` | `-0.3495` |
| Tianjin closure | 3 | `0.9766` | `0.8402` | `-0.1364` |
| Colombo->New Jersey congestion | 13 | `-0.8973` | `-0.8973` | `0.0000` |
| Qingdao->Busan congestion | 6 | `0.6684` | `0.8771` | `+0.2086` |

Five of six windows improve. The Piraeus closure, which v13 made worse than
v12, now costs `0.4125` — better than v12's own `0.5696`. Charging the
boarding wait honestly fixed exactly what costing it at zero had broken.

## The design hypothesis was partly wrong

This must be recorded plainly. The stated reason for removing the
congestion-free-path requirement was that it was blocking the held-out
scenario. It was not the cause.

v14 produced an ATT **byte-identical** to v13 on `shifted`, exactly as v13 had
against v12. A probe of what the hook actually returns settled why. Evidence:
`.challenge/round2/results/audit_20260903/probe_shifted.json` and
`probe_r2_seed7.json`.

| | `shifted` | `r2_seed7` |
| --- | --- | --- |
| hook returned `True` (kept the chain) | `63` | `13` |
| affected shipments in those calls | `10,959` | `613` |
| where the organizer's replan would have been a **no-op** | `10,959` | `0` |
| where it would have **changed** the chain | `0` | `613` |

On `shifted` the veto fires, but the organizer's own rebuild finds **no
replacement path at all** for every affected shipment, so it leaves those
chains alone by itself. The veto agrees with it, and a byte-identical result is
the correct outcome rather than a symptom. That scenario is so heavily
disrupted — a hub closure on five services plus congestion — that it cannot
test this hook at all.

The removed guard was therefore not what made v13 inert on `shifted`. It was
still worth removing: v14 gains `13.14%` on Round 2 over v13, and the guard was
genuinely meaningless for cargo already at sea. But the prediction attached to
it was wrong, and the correction came from measurement rather than from
argument.

## Held-out evidence

Because `shifted` cannot exercise this hook, a third held-out scenario was
built deliberately milder than Round 2, so that replacement paths exist and an
in-transit decision has something to disagree about: `2.5x` congestion on
`Shenzhen->Singapore`, `2.0x` on `Kaohsiung->Los Angeles`, and short five- and
six-day closures at `Kaohsiung` and `Jebel Ali`, both non-hub ports. All arms
share the scenario and seed and were run for 300 measured days.

| held-out scenario | comparison | control | candidate | delta |
| --- | --- | --- | --- | --- |
| `shifted` | v13 -> v14 | `42.6751` | `42.6751` | `0.0000` |
| `mild` | v13 -> v14 | `6.3748` | `6.3748` | `0.0000` |
| `mild` | **v12 -> v14** | `6.4223` | `6.3748` | **`-0.0476` (`-0.74%`)** |

Every arm delivered every shipment it booked and left `0` unbooked.

The first two rows show the v14 refinements do not bite outside Round 2's
particular disruptions — no harm, but no signal. The third row is the one that
matters: comparing against v12, which does not touch the in-transit decision at
all, taking over that decision improves an unseen scenario by `0.74%` with 10
periods better, 44 equal and 6 worse. That is modest, but it is positive
evidence for the intervention rather than an absence of evidence.

## Why it is accepted

- the Round 2 gain is `13.14%` and has a cleaner profile than v13's;
- neither held-out scenario regresses, and one shows the intervention helping;
- the change is a correction toward the truth — the wait to board a different
  service is real — not a tuned constant;
- the hook remains **one-sided**: it never mutates a booking, route, vessel, or
  berth and can only ever decline a change the organizer was about to make, so
  the worst case in an unseen scenario is the incumbent's own behaviour.

## Post-acceptance verification

- `uv lock --check`, locked sync, Ruff format and lint, mypy, ty: clean;
- 269 non-integration tests, `91.12%` branch coverage (gate `90%`), including
  two tests verified to discriminate against v13: a fair-cost case where v13
  delegates and v14 keeps, and a fully congested network where v13 refuses to
  decide;
- 6 real-context integration tests;
- participant and runtime `user_strategy.py` byte-identical at
  `5d06bc92872e18432759951f887221db5fc8b71004c1a1345a907692a050341b`;
- Round 2 smoke: `smoke: OK`;
- deterministic participant-only package, twice, SHA-256
  `c156fcec14112462dd4ac6e8954a464d394d10779c7af5c14855fda444ba559b`;
- restricted-material scan clean; clean Git working tree.
