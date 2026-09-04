# Round 2: a slowdown is temporary too (v15)

**Status: DESIGN — frozen before the authoritative run.**

## Hypothesis

v12 established that a port closure is temporary and should be *timed* rather
than treated as a wall: cargo that will not reach the port until after it
reopens loses nothing by being routed through it. That was worth `-10.89%`, and
it improved the held-out scenario by `-10.32%`.

A congestion multiplier is exactly as temporary, and the strategy still treats
it as permanent. Every leg is costed at the multiplier in force *now*, no
matter when the cargo would actually sail it. During a 60-day window, cargo
booked near the end is charged five times the true sailing time for a leg it
will cross at normal speed, and is detoured for no reason.

After v14 the congestion windows hold `4.23` of the remaining `10.35`, or
`41%`: `3.3504` in the Shanghai-Kaohsiung window and `0.8771` in
Qingdao-Busan. This is the last place the timing insight has not been applied.

## Exact participant delta

The two disruption kinds are unified into one per-leg schedule on each edge,
replacing the closure-only `closed_calls`:

```text
timeline[i] = (hours at normal speed,
               multiplier in force now,
               hours until that multiplier lifts,
               hours until the arrival port reopens)
```

`_edge_arrival` walks it: a leg entered after its slowdown has lifted runs at
normal speed, a call at a shut port waits for the reopening and shifts
everything after it, and the organizer's fixed berthing time separates the
legs. A ride with nothing disrupted on it carries `timeline = None` and costs a
single addition, so **an undisrupted network is costed exactly as before**.

`_congestion_recovery` supplies the clearing times from the active
congested-leg plans, guarded the same way as closures: the plan arithmetic is
only trusted where it agrees with live state, here that the leg's
`sailing_time_multiplier` really is raised. A different simulation epoch, a
malformed plan, an expired plan, a non-datetime `now`, or a plan whose leg is
no longer slowed all yield no clearing time, and a slowdown with no clearing
time is assumed **permanent** — the conservative reading, and the previous
behaviour exactly.

The route headway still uses the multipliers in force now, because the vessels
really are sailing slowly today; only the cargo's own future traversal is
re-timed.

## Why this should generalise

It is the same correction as v12, applied to the other disruption kind, and it
adds no constant. It is inert on an undisrupted network, inert wherever a
clearing time cannot be established, and its benefit grows with how short the
slowdown is relative to the time the cargo needs to reach that leg — a property
of any scenario rather than of this one. Only *active* plans are read, so the
policy stays reactive and never anticipates a disruption that has not started.

## Control and acceptance

- accepted control loss: `10.350669070475163` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `d6c3e6c75cb26e8eb6b2029c7077351f38d670b52186dfec1482926ace843cc6`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 10.350669070475163 - 1e-9
```

Acceptance additionally requires no regression on the held-out scenarios, where
the accepted control scores `42.6751` on `shifted` and `6.3748` on `mild`.
Unlike the in-transit hook, this change bites wherever congestion is active, so
both held-out scenarios can genuinely exercise it and a tie would be a warning.
