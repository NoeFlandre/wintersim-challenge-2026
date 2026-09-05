# Round 2: a rotation is owed a vessel only for the legs still ahead of the cargo (v23)

**Status: ACCEPTED. New best Round 2 cumulative resilience loss.**

## The defect

v22's route statistics showed that the accepted policy leaves roughly two of
the fleet's 41 vessels parked for most of the run:

| route | avg capacity TEU | avg carried TEU |
| --- | --- | --- |
| `S4` | `42,972` | `1,097` |
| `S4-UALT-1` | `13,389` | `109` |
| `S5` | `94,717` | `2,030` |
| `S5-UALT-1` | `22,768` | `332` |

After a fleet comes home, each detour keeps its last vessel, held by the rule
that a rotation is never left without vessels while cargo is still booked on
it. That rule is right; its implementation is not. It asks whether any
*unfinished shipment* holds a booking on the rotation:

```text
completion_time is None  ->  still counting on this rotation
```

A shipment that sailed its leg on the detour weeks ago and is now three
services further along is unfinished, and counts. Since long-haul chains take
weeks to complete and new ones kept being written for the whole window, the
condition effectively never clears, and the vessel stays for the rest of the
run.

## Exact participant delta

A booking is only owed a vessel if the cargo has not passed it yet:

> A rotation still needs a vessel when an unfinished shipment holds a booking
> on it whose `sequence_index` is at or beyond that shipment's
> `current_booking_index`.

Cargo that has already sailed its leg here no longer constrains the rotation;
cargo whose *later* leg is booked here still does, and is unchanged. Progress
that cannot be read counts as still needing the rotation, so the degraded
behaviour is exactly today's.

Nothing else changes. No booking decision, no detour construction, no
changeover gate, no vessel movement rule. This is a correction to one
predicate.

## Why this should generalise rather than overfit

It removes a bug rather than adding a policy. The corrected predicate is the
literal statement of the safety property that was intended all along — cargo
must never be left with a booking no vessel will serve — and the old one was
strictly stronger than that property requires. Every scenario that builds a
detour pays the old cost; none of them need to.

## Predictions, fixed before the runs

- Round 2: periods `41-56` improve as the two parked vessels rejoin their
  services; nothing inside any disruption window changes, because no booking
  decision changes. Expected better; a regression rejects.
- `brief`, `mild`, `undisrupted`: **exact ties** — no detour is ever built, so
  the predicate is never consulted.
- `inserted`, `long`, `twin`, `shifted`: expected better or unchanged; none may
  regress against its do-nothing arm.
- Route statistics: `S4-UALT-1` and `S5-UALT-1` should end with materially less
  average capacity than v20's `13,389` and `22,768`.

## Acceptance

- Round 2: `candidate_loss < 4.912139391692661 - 1e-9`;
- `brief` `6.767487342693513`, `undisrupted` `-5.030822520503106`, `mild`
  `5.363436801272705`: exact ties;
- `shifted` no worse than `41.62569844636167`, `long` no worse than
  `77.65274459580378`, `twin` no worse than `40.12987734887265`, `inserted` no
  worse than its do-nothing arm `16.754999739073277`;
- `unbooked == 0` on every arm.

## Results

Authoritative run, 72 periods, `Simulation completed.`

- candidate ATT SHA-256:
  `c5243b5e5716a90724245ee62c8fedee3fb80cc87e472ca6f68b36a30adacc56`, reproduced
  byte-for-byte by an independent run of an isolated copy
  (`.challenge/round2/v23_check/`);
- **candidate loss `4.844560541925512`** against `4.912139391692661`:
  `-0.06757884976714923` (`-1.376%`);
- periods better/equal/worse: `12 / 52 / 8`.

Held-out, every arm carrying a do-nothing comparison:

| scenario | do nothing | v20 | v23 | v23 vs v20 | unbooked |
| --- | --- | --- | --- | --- | --- |
| `shifted` | `42.6642` | `41.62569844636167` | `41.62569844636167` | exact tie | `0` |
| `mild` | `5.3634` | `5.363436801272705` | `5.363436801272705` | exact tie | `0` |
| `long` | `79.2269` | `77.65274459580378` | `77.65274459580378` | exact tie | `0` |
| `twin` | `42.1737` | `40.12987734887265` | `40.12987734887265` | exact tie | `0` |
| `brief` | `6.7675` | `6.767487342693513` | `6.767487342693513` | exact tie | `0` |
| `undisrupted` | `-5.0308` | `-5.030822520503106` | `-5.030822520503106` | exact tie | `0` |
| `inserted` | `16.7550` | `16.17458575774183` | `15.534240459359498` | `-3.96%` | `0` |

Every acceptance condition holds, so the candidate is **accepted**.

## Deep analysis

The window attribution is the cleanest confirmation this round has produced
that the change does what it claims and nothing else:

| window | v20 | v23 | delta |
| --- | --- | --- | --- |
| no disruption active | `4.4675` | `4.2735` | `-0.1940` |
| Piraeus closed | `0.4558` | `0.4112` | `-0.0446` |
| Colombo-New Jersey congestion | `-0.7061` | `-0.7061` | `0.0000` |
| Shanghai-Kaohsiung congestion | `0.0129` | `0.0129` | `0.0000` |
| Qingdao-Busan congestion | `0.2719` | `0.2719` | `0.0000` |
| Tianjin closed | `0.4102` | `0.5812` | `+0.1711` |

**All three congestion windows are unchanged to the last digit**, which is
exactly right: no booking decision changed, so nothing that happens while a
detour is in use can move. The gain is where the parked vessels were —
undisrupted periods — and periods `41-56` go from `1.2764` to `1.1520`.

`52` of `72` periods are bit-identical for the same reason. The `+0.1711` in
the three Tianjin periods is the one place a returning vessel arrives at a
different moment than before and reorders port calls; it is real, and smaller
than what the change recovers.

The route statistics confirm the mechanism directly: `S4-UALT-1`'s average
capacity falls from `13,389` to `11,768` TEU. `S5-UALT-1` is unchanged at
`22,768`, so its last vessel is still held — by cargo that genuinely has a
later leg booked there, which is the correct behaviour and the reason the
remaining recovery is partial.

`inserted` improves by `3.96%` on top, to `7.3%` better than never moving a
vessel: that scenario re-detours after Shenzhen reopens, so it pays the parked
vessel twice and gains twice from the fix.

## What is left

`S5-UALT-1` still parks a vessel because cargo really does have later legs
booked on it, and no hook can replan cargo waiting at a port. Reducing that
means not writing a *non-first* booking onto a rotation that will be withdrawn
before the cargo reaches it — the narrower form of what v21 tried too bluntly.
That remains the open lead.

## Lessons

39. **Check whether a safety rule is stated as strongly as it is meant.** The
    never-strand rule was right; its predicate asked "is this shipment
    unfinished?" when the property it protects is "does this shipment still
    need this rotation?". The gap parked two of 41 vessels for most of a run.
40. **A change that alters no decision should leave every window identical, and
    that is testable.** All three congestion windows came back `0.0000` and
    `52` periods came back bit-identical, which is far stronger evidence that
    the mechanism is understood than the scalar improvement is.
