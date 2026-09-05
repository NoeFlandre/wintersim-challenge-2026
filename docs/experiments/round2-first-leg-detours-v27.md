# Round 2: book a temporary rotation only for the leg in front of the cargo (v27)

**Status: REJECTED on Round 2. It freed the vessel it targeted and cost far
more than the vessel was worth.**

## The remaining defect

A detour is withdrawn when the slowdown that justifies it lifts, but the
strategy writes chains onto it with no regard for when the cargo will get
there. A chain whose *third* booking is on a detour is cargo that will not
reach it for weeks — quite possibly after the fleet has gone home.

Those bookings are what pin the detour's last vessel. v23 established that a
rotation is owed a vessel only for legs the cargo has not passed yet, which
freed the vessels held by cargo already past. What is left holding them is
cargo that has genuinely not arrived: later legs written during the window that
keep arriving long after it.

v21 attacked this bluntly — refuse any ride that would end after the rotation is
withdrawn — and lost `1.68` inside the window, because near a window's end that
refuses the *first-leg* rides the detour exists for. This is the narrow form.

## Exact participant delta

In the path search, a rotation built for a disruption may only be used as the
**first** booking of a chain.

Cargo standing at its origin now boards within a headway, so a first leg is
safe and keeps everything the detour was built to deliver. A later leg is
reached only after at least one transfer, and cannot depend on a service that
may be gone by then. The network already knows which rotations are temporary —
they are the ones with a `source_service_route` — so the test is one flag on
one edge, with no constant and no timing arithmetic.

## Why this should generalise rather than overfit

It states a property a plan should always have had: a chain may only commit to
services that will still exist when the cargo needs them, and the only ones
that might not are the ones the strategy itself created for a disruption. It
does not reference any window length, so it behaves the same in the first hour
of a slowdown and the last.

Unlike v21 it never withholds the detour from the cargo standing in front of
it, which is where the measured value of building one lives.

## Predictions, fixed before the runs

- `brief`, `mild`, `undisrupted`: **exact ties** — no detour is ever built.
- Round 2: fewer bookings survive on a detour past its window, so its last
  vessel rejoins sooner. Expected better; a regression rejects.
- `inserted`, `long`, `twin`, `shifted`: expected better or unchanged.
- `unbooked` must stay `0`.

## Acceptance

- Round 2: `candidate_loss < 4.844560541925512 - 1e-9`;
- `brief` `6.767487342693513`, `undisrupted` `-5.030822520503106`, `mild`
  `5.363436801272705`: exact ties;
- `shifted` no worse than `41.62569844636167`, `long` no worse than
  `77.65274459580378`, `twin` no worse than `40.12987734887265`, `inserted` no
  worse than `15.534240459359498`;
- `unbooked == 0` on every arm.

## Result and decision

Authoritative run, 72 periods, `Simulation completed.`

- **candidate loss `5.660405309175495`** against `4.844560541925512`:
  `+0.8158447672499829` (`+16.84%`, worse);
- periods better/equal/worse: `29 / 14 / 29`.

Rejected.

## Why it failed

The mechanism worked exactly as designed. `S5-UALT-1`'s carried volume falls
from `332` to `232` TEU and its average capacity from `22,768` to `20,739`, so
fewer bookings pin its last vessel and it rejoins sooner.

That vessel is simply worth far less than the bookings given up to free it. The
detour is a fast service through the middle of the network, and forbidding
cargo to transfer onto it removes it from every chain that does not start at
one of its ports — a much larger population than the handful of late bookings
that were holding the vessel.

This is the third measurement of the same shape, after v21 (`+33%`) and v25's
sibling: **the booking value of a detour is large and fragile, and every
restriction on how cargo may use it costs several times the fleet inefficiency
it removes.** The mechanism is at a sharp optimum.

## Lessons

47. **Three failures of the same shape are a result about the search space.**
    v21, v27 and the family around them all traded detour bookings for fleet
    tidiness, and all lost by a factor. The detour's value is in the cargo it
    carries, not in the vessels it ties up, and the accepted policy already
    sits at that optimum.
