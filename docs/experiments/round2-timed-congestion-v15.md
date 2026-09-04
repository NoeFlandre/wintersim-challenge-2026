# Round 2: a slowdown is temporary too (v15)

**Status: ACCEPTED — complete. It barely moves Round 2, and improves a
held-out scenario by `15.79%`. That asymmetry is the hypothesis being
confirmed, not contradicted.**

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

## Full-run result

One authoritative run completed all 72 periods in `00:18:19`, with the ATT
proved fresh against the pinned stale mtime `1788506510153120028`.

- candidate ATT SHA-256: `a2084e82fc9badbd13542b9ebab183cfcdc8978da8a00d1065b807bd341bf4c6`;
- **candidate cumulative resilience loss: `10.347110679813037`**;
- accepted v14 control loss: `10.350669070475163`;
- difference: `-0.003558390662126598` (`-0.03437836373570047%`);
- periods better/equal/worse: `17 / 45 / 10`.

```text
10.347110679813037 < 10.350669070475163 - 1e-9
```

is true, so the Round 2 rule is met — but only just.

## Why Round 2 barely moves, and why that is the point

| window | length | v14 | v15 | delta |
| --- | --- | --- | --- | --- |
| Piraeus closure | 14 d | `0.4125` | `0.3711` | `-0.0414` |
| Qingdao->Busan congestion | 25 d | `0.8771` | `0.8436` | `-0.0335` |
| Tianjin closure | 7 d | `0.8402` | `0.8200` | `-0.0202` |
| Colombo->New Jersey congestion | 60 d | `-0.8973` | `-0.8973` | `0.0000` |
| Shanghai->Kaohsiung congestion | 60 d | `3.3504` | `3.3504` | **`0.0000`** |
| no active disruption | — | `5.7677` | `5.8592` | `+0.0916` |

Both 60-day congestion windows are **completely unchanged**, and that is
mechanically necessary rather than surprising. Cargo can only benefit if its
own traversal of a slowed leg falls after the slowdown lifts. The wait to board
plus the sailing time to reach that leg is at most a few days, so inside a
60-day window essentially no cargo is ever costed differently. The 25-day
Qingdao-Busan window is short enough to benefit, and it does.

Round 2 is therefore close to the worst case for this change. The value of
timing a slowdown scales with how short the slowdown is relative to the time
cargo needs to reach it, and Round 2's windows are long.

The two closure windows also improve slightly, and the undisrupted periods
worsen slightly, because a booking made during the Qingdao-Busan window
completes several periods later.

## Held-out results: the hypothesis, tested where it can bite

| held-out scenario | congestion windows | v14 | v15 | delta |
| --- | --- | --- | --- | --- |
| `shifted` | 45 / 40 / 30 days | `42.6751` | `42.6642` | `-0.0109` (`-0.03%`) |
| `mild` | 30 / 25 days | `6.3748` | **`5.3684`** | **`-1.0063` (`-15.79%`)** |

On `mild`, 27 periods improve, 32 are equal and 1 is worse. Every arm delivered
every shipment it booked and left `0` unbooked.

The ordering is the prediction: the shorter a scenario's congestion windows,
the larger the gain. Round 2's 60-day windows give `-0.03%`, `shifted`'s
45-to-30-day windows give `-0.03%`, and `mild`'s 25-to-30-day windows give
`-15.79%`. A change that produced a large Round 2 gain and nothing elsewhere
would be the overfitting signature; this is the opposite shape.

## Why it is accepted

- the Round 2 rule is met, if narrowly;
- neither held-out scenario regresses and one improves by `15.79%`, which is
  the largest held-out gain of any experiment this round;
- the change removes a false assumption — that a slowdown lasts forever —
  rather than adding a constant, and it is provably inert on an undisrupted
  network, where a ride carries no schedule and costs a single addition;
- everything uncertain fails closed to *assuming the slowdown persists*, which
  is both the conservative reading and the previous behaviour.

Accepting a `0.03%` Round 2 gain would be hard to justify on its own. It is
justified by the held-out evidence, and by the fact that the hidden round is
weighted at `50%` and its disruption lengths are unknown: a scenario with short
slowdowns is exactly where this change is worth the most, and Round 2 is where
it is worth the least.

## Post-acceptance verification

- `uv lock --check`, locked sync, Ruff format and lint, mypy, ty: clean;
- 282 non-integration tests, `91.22%` branch coverage (gate `90%`), including
  two verified to discriminate against v14: a slowdown clearing in 2 hours,
  where v14 detours and v15 sails direct, and one lasting 500 hours, where both
  detour;
- 6 real-context integration tests;
- participant and runtime `user_strategy.py` byte-identical at
  `f24cf3220e32413355ef8b69c15a169c14e42a72f408789d84f4ab69f5b9c8ba`;
- Round 2 smoke: `smoke: OK`;
- deterministic participant-only package, twice, SHA-256
  `2a5a0f27ed960f9899300f2400882d78b91f67adb40c73b062fe50206d3964cb`;
- restricted-material scan clean; clean Git working tree.
