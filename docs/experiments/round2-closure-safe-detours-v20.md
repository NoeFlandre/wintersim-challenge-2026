# Round 2: never detour through a port that is going to shut (v20)

**Status: ACCEPTED. Round 2 unchanged; the `inserted` failure removed.**

## What v19 established

A detour is built by inserting legs, so it calls ports the nominal rotation
does not. If one of those shuts while the fleet is on the detour, every choice
left is bad: stay and sail into a closed port (v18, `+51%` against doing
nothing on the `inserted` scenario) or go home and come back (v19, `+33%`,
four changeovers inside one window). See
`round2-hidden-round-hardening-v19.md`.

Both are downstream of one decision: the detour should never have been built
through that port in the first place.

## Exact participant delta

When a detour is built, the legs available to it exclude any leg touching a
port that will be shut at any point inside the window the detour is needed
for. Concretely:

1. The window is the slowdown's own remaining life — the same quantity the
   changeover gate already uses, the smallest `hours until this multiplier
   lifts` across the rotation's slowed legs.
2. A port is unavailable to the detour if it is shut now, or if any close-berth
   disruption plan overlaps `[now, now + that window]`. This reads the same
   published plan set that v12 reads to time a reopening, under the same epoch
   guard: if the plan arithmetic cannot be trusted, no port is claimed safe and
   no detour is built.
3. If no detour survives that restriction, the service stays on its own
   rotation — which is what v16 did, and what `inserted` shows is much the
   better answer there.

v19's runtime safety net is kept: a detour that somehow ends up calling a
closed port stops being the rotation to run, and the fleet goes home. It should
now be unreachable, and it costs nothing to leave in.

## Why this should generalise rather than overfit

The rule is a statement about feasibility, not a tuned exception: *a rotation
is only worth changing to if it can be sailed for as long as it is needed*.
That is the same sentence the changeover gate expresses in time; this expresses
it in geography. Neither introduces a constant.

Its verdicts were fixed before it was written:

- `inserted` must come back to roughly its v16 arm (`16.755`), because the only
  path from Shanghai to Kaohsiung that avoids the slowed leg goes through
  Shenzhen, and Shenzhen shuts inside the window — so there is no safe detour
  and nothing should move;
- Round 2 must be **bit-for-bit unchanged** at `4.912139391692661`. Its two
  detours insert Shenzhen (never closed in Round 2) and Piraeus and Tanger Med
  (Piraeus closes on days `260-274`, 160 days after the slowdown that builds
  that detour has ended), so no Round 2 detour has a closure inside its window;
- `long`, `twin`, `shifted` and `mild` must be unchanged too, none of them
  scheduling a closure inside a detour's window.

A rule whose predicted effect is "nothing changes anywhere except the scenario
that exposed the defect" is falsifiable in six places at once.

## Acceptance

Accepted only if all of the following hold:

- Round 2: `candidate_loss <= 4.912139391692661 + 1e-9`;
- `inserted` no worse than its v16 arm `16.754999739073277`;
- `brief` and `undisrupted` exact ties with their v16 arms;
- `long` no worse than `77.65274459580378`, `twin` no worse than
  `40.12987734887265`, `shifted` no worse than `41.62569844636167`, `mild` no
  worse than `5.363436801272705`;
- `unbooked == 0` on every arm.

## Results

Every scenario was run with a **do-nothing arm** (v16, which never moves a
vessel) alongside the candidate, because the question these scenarios exist to
answer is not "is v20 better than v18" but "does owning the fleet decision at
all still pay on a scenario nobody designed it for". 140-day warm-up plus 300
measured days each, organizer baseline supplying the period weights. Evidence:
`.challenge/round2/results/audit_2026090{3,4}/`.

| scenario | v16 (do nothing) | v18 | v20 | v20 vs v16 | unbooked |
| --- | --- | --- | --- | --- | --- |
| `shifted` | `42.6642` | `41.6257` | `41.62569844636167` | `-2.43%` | `0` |
| `mild` | `5.3634` | `5.3634` | `5.363436801272705` | tie | `0` |
| `long` | `79.2269` | `77.6527` | `77.65274459580378` | `-1.99%` | `0` |
| `twin` | `42.1737` | `40.1299` | `40.12987734887265` | `-4.85%` | `0` |
| `brief` | `6.7675` | — | `6.767487342693513` | exact tie | `0` |
| `undisrupted` | `-5.0308` | — | `-5.030822520503106` | exact tie | `0` |
| `inserted` | `16.7550` | `25.3566` | `16.17458575774183` | `-3.46%` | `0` |

Authoritative Round 2 run: `Simulation completed.`, 72 periods, candidate ATT
SHA-256 `d6eb1590f3317d9f8a918efc8d3a188529dd99c6bcc82b04295deef001e00f22` —
**byte-identical to v18's**, so the loss is `4.912139391692661`, unchanged.

Every frozen prediction held, including the negative ones. `shifted`, `mild`,
`twin` and Round 2 came back identical to v18 to the last digit, `brief` and
`undisrupted` came back identical to the do-nothing arm, and `inserted` — the
one scenario that schedules a closure inside a detour's window — moved from
`+51.34%` against doing nothing to `-3.46%`. All eight acceptance conditions
hold, so the candidate is **accepted**.

An independent run of an isolated copy of the whole tree reproduced the
candidate ATT byte-for-byte (`.challenge/round2/v20_check/`), so the result is
deterministic under the new code as well.

The submission archive's hash moved after the run
(`ff4a6378...` at launch, `b2f04d5b...` now) because the packaged README was
extended afterwards to document this rule. The strategy code itself is
byte-identical to what ran: `9e411ceeda1bf2c1969d97b0a46136c819a22f0c6cc8c570eeb4fd97ca462ba7`
in the submission, in the run's `strategy_at_launch.py`, and in the isolated
reproduction tree.

## Deep analysis

`inserted` slows `Shanghai -> Kaohsiung` by `5x` for 120 days from measured day
`40`, and shuts Shenzhen for 20 days from day `90`. The only path from Shanghai
to Kaohsiung that avoids the slowed leg goes through Shenzhen, so:

- **v18** builds that detour on day `40`, moves `S4`'s fleet onto it, and sails
  into a closed Shenzhen for twenty days from day `90`: `+8.60` against doing
  nothing.
- **v19** brings the fleet home on day `90` and sends it back out on day `110`,
  paying four changeovers of about a rotation each inside one window: `+5.48`.
- **v20** refuses to build the detour at all while Shenzhen's closure sits
  inside the window the detour would be needed for. Before day `90` there is no
  safe detour, so nothing moves. Once Shenzhen reopens on day `110` the
  remaining `50` days of slowdown contain no closure, the detour becomes safe,
  and the fleet moves once: `-0.58` against doing nothing.

That final `-0.58` is the mechanism doing exactly what it is for, on the part
of the window where it is sound, and standing down on the part where it is not.

## The scorecard that matters

Across seven held-out scenarios and Round 2, against the do-nothing arm:
**four wins, three ties, no losses**, and `unbooked == 0` everywhere. The one
loss that existed at the start of this audit was `+51%`, and it is gone.

## Lessons

31. **Feasibility before optimality.** v18 and v19 both argued about *whether*
    to change rotation and *when* to change back. Neither asked whether the
    rotation could be sailed for as long as it was needed. Adding that question
    made both of the earlier arguments moot on the scenario that exposed them.
32. **A rule whose predicted effect is "nothing changes anywhere except one
    scenario" is worth more than a rule that improves the score.** It is
    falsifiable in as many places as you have scenarios, and here it was
    checked in six of them and held in all six, to the last digit.
33. **Future disruption plans are readable, and using them is not an
    exploit.** v12 already timed a reopening from the same published plan set.
    Reading it to decide whether a rotation will stay sailable is the same
    information used for the same kind of decision.
