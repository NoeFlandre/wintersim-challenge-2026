# Round 2: pay for a rotation change only when the slowdown outlasts it (v18)

**Status: ACCEPTED. New best Round 2 cumulative resilience loss.**

## What v17 established

v17 moved a whole service onto a detour around a slowdown whenever the detour
still called every port the rotation called and its cycle was strictly shorter
at the multipliers in force. Held out, that rule *helped* on `shifted`
(`-1.0385`) and *hurt* on `mild` (`+2.0175`), and the `mild` damage landed
entirely after the disruption had recovered. See
`round2-whole-service-reroute-v17.md` for the evidence.

The split is the finding. A rotation change costs about one turn of the
rotation, twice — vessels move one at a time and only when empty, and the fleet
has to come home again — so a slowdown shorter than that turn cannot repay it.
On `shifted` the slowed legs last `45`, `40` and `30` days against cycles from
`24.65` days up; on `mild` the leg that reaches `S4` lasts `25` days against
`S4`'s `25.69`-day cycle.

## Exact participant delta

One condition is added to the v17 rule, and only for a service that has not
already begun its changeover:

> Start a rotation change only when the slowdown's remaining life exceeds one
> turn of the detour at normal speed.

Both sides are read from the runtime state. The remaining life is the smallest
`hours until this multiplier lifts` across the rotation's slowed legs, taken
from the same epoch-guarded disruption arithmetic v15 introduced; a slowdown
whose end cannot be established counts as permanent, exactly as the booking
cost model already treats it. The turn is the detour's own distance divided by
the mean speed of the service's vessels.

A service already part-way through a changeover is exempt: the cost has been
paid, and reversing on a shrinking remaining life would only pay it a third
time. That is the whole change — the detour construction, the
calls-every-port requirement, the cycle comparison, the closed-port rule, the
empty-vessel-only movement and the never-strand rule are all v17's, unchanged.

## Why this should generalise rather than overfit

The added term is a ratio of two runtime quantities, with no constant of any
kind: *is what is left of this slowdown longer than the time it takes this
fleet to change rotation?* It answers the question v17 got wrong — v17 compared
two steady states and ignored the transient between them — rather than
excluding the case that happened to fail.

Its two known verdicts were fixed before it was written: it must leave `mild`
alone (`25 < 25.69` days) and must still act on `shifted`'s 40-day
`Busan -> Los Angeles` slowdown against `S9`'s `24.65`-day cycle. On Round 2 it
allows the change during roughly the first half of the 60-day
`Shanghai -> Kaohsiung` window and refuses to start one later in it, which is
the correct answer for a fleet that would not finish moving before the leg
recovered.

## Control and acceptance

- accepted control loss: `9.762649496857325` over exactly 72 five-day periods;
- accepted control ATT SHA-256:
  `beace437a6c0d55bce87d35b38bfcfe25c897aa7749e17fc3425a2fa7e1de885`;
- authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:

```text
candidate_loss < 9.762649496857325 - 1e-9
```

Equality, worsening, invalid output, a crash, or a failed gate is rejection.
Acceptance additionally requires that neither held-out scenario regresses
(`shifted` control `42.664213029643555`, `mild` control `5.363436801272705`)
and that `unbooked` stays `0` on every arm. The held-out runs are taken first:
if `mild` does not return to at least its control, the candidate is rejected
without spending the authoritative run.

## Held-out results (taken before the authoritative run)

Both scenarios ran a 140-day warm-up plus 300 measured days, scored with the
organizer baseline supplying the period weights. Evidence:
`.challenge/round2/results/audit_20260903/v18_{shifted,mild}.json`.

| held-out scenario | v16 control | v17 | v18 | v18 vs control | unbooked |
| --- | --- | --- | --- | --- | --- |
| `shifted` | `42.664213029643555` | `41.6257` | `41.62569844636167` | `-1.0385` (`-2.43%`) | `0` |
| `mild` | `5.363436801272705` | `7.3809` | `5.363436801272705` | `0.0000` (exact tie) | `0` |

The gate did exactly what it was designed to do and nothing else: `shifted`
keeps the whole of v17's gain to the last digit, and `mild` returns to a
bit-for-bit tie with the control. That is the cleanest possible evidence that
the added term isolates the transient rather than suppressing the mechanism.

## Authoritative run and decision

The run completed all 72 periods with `Simulation completed.`

- candidate ATT SHA-256:
  `d6eb1590f3317d9f8a918efc8d3a188529dd99c6bcc82b04295deef001e00f22`;
- **candidate cumulative resilience loss: `4.912139391692661`**;
- accepted v16 control loss: `9.762649496857325`;
- difference: `-4.8505101051646635` (`-49.684361880717745%`, better);
- candidate mean ATT `14.076944444444447` days against the control's
  `14.32513888888889`;
- periods better/equal/worse: `28 / 12 / 32`.

`candidate_loss < 9.762649496857325 - 1e-9` holds, neither held-out scenario
regressed, and no arm stranded cargo, so the candidate is **accepted**.

An independent run of an isolated copy of the whole tree reproduced the
candidate ATT byte-for-byte
(`.challenge/round2/v18_check/`), so the result is deterministic.

## Deep analysis

Losing on more periods than it wins is not a contradiction: the objective
weights a period by `baseline / ATT^2`, so one badly disrupted period is worth
many mildly better ones. By window:

| window | periods | v16 | v18 | delta |
| --- | --- | --- | --- | --- |
| Shanghai-Kaohsiung congestion | 13 | `7.7506` | `0.0129` | `-7.7377` |
| Tianjin closed | 3 | `0.4714` | `0.4102` | `-0.0613` |
| Colombo-New Jersey congestion | 13 | `-0.8973` | `-0.7061` | `+0.1912` |
| no disruption active | 33 | `3.9546` | `4.4675` | `+0.5129` |
| Piraeus closed | 4 | `-0.3479` | `0.4558` | `+0.8037` |
| Qingdao-Busan congestion | 6 | `-1.1689` | `0.2719` | `+1.4407` |

**The window that held 79% of v16's remaining loss is gone.** Where v16's ATT
climbed monotonically from `14.06` to `18.63` days across periods 29-38, v18
holds it between `13.2` and `14.7` and finishes the window at `-0.0194`. The
whole 60-day `5x` slowdown now costs `0.0129` against a flat baseline.

Two detours were built and carried cargo, which is visible in the run's own
route statistics: `S4-UALT-1` (`109` average TEU) for the Shanghai-Kaohsiung
window and `S5-UALT-1` (`332` average TEU) for the Colombo-New Jersey window.
Those are Round 2's two 60-day slowdowns; the 25-day and 14-day and 7-day
disruptions were all left alone, by the gate or by the closed-port rule.

## What it cost, and where the next experiment is

The `+2.94` spread across `QinBus`, `Piraeus` and the undisrupted periods is
one thing seen three times: the **return transient**. Periods 41-56 — the ten
weeks after the Shanghai-Kaohsiung leg recovers — carry `1.2764` of loss on
their own. When a service comes home, the never-strand rule keeps its last
vessel on the detour until no unfinished shipment still holds a booking there,
and that leftover cargo is served by one vessel on a rotation whose headway is
its entire cycle. The fleet is split, both halves are thin, and it takes weeks
to resolve.

The remaining loss profile says the same thing:

| window | periods | v18 loss | share |
| --- | --- | --- | --- |
| no disruption active | 33 | `4.4675` | `90.9%` |
| Piraeus closed | 4 | `0.4558` | `9.3%` |
| Tianjin closed | 3 | `0.4102` | `8.3%` |
| Qingdao-Busan congestion | 6 | `0.2719` | `5.5%` |
| Shanghai-Kaohsiung congestion | 13 | `0.0129` | `0.3%` |
| Colombo-New Jersey congestion | 13 | `-0.7061` | `-14.4%` |

Every disruption window is now at or below the undisrupted baseline except a
rounding error, and `91%` of what is left sits in periods with nothing active
at all. Draining a rotation without stranding its cargo and without leaving it
to a single vessel is the next lever, and it is worth up to about `1.3` on the
evidence above.

## Lessons

25. **Price the transient, then the steady state.** The same detour rule that
    was rejected at `+2.02` on a held-out scenario is worth `-49.68%` once it
    also asks whether the disruption will outlast the changeover. The
    difference between the two versions is one ratio of runtime quantities, and
    no constant.
26. **A held-out scenario that returns to a bit-for-bit tie is a strong
    result.** `mild` matching its control to the last digit proves the gate
    made the mechanism inert there rather than merely smaller, which is what
    distinguishes a corrected rule from a damped one.
27. **The cost of a policy can land entirely outside the window it acts in.**
    v18's whole price is paid in the ten weeks *after* the slowdown it fixes,
    in periods where nothing is disrupted. Attributing loss by window is what
    made that visible; the scalar alone would have hidden it.
