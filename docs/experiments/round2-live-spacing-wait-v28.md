# Round 2: price a boarding from where the vessels actually are (v28)

**Status: REJECTED, heavily. The second independent demonstration that live
vessel positions cannot be turned into an unbiased boarding estimate.**

## The approximation

Every estimate in the model charges a boarding `cycle / deployed vessels` — a
statistic that assumes the vessels are evenly spaced around their loop. The
code comment beside it has named the correct quantity since v10:

```text
the mean wait for a random arrival is E[gap^2] / (2 * E[gap])
```

and then used a full headway as a stand-in for it.

The assumption does not hold, and the reason is measurable. Sailing duration
carries `+/-5%` random variation per leg. A vessel on `S9` sails about `280`
legs over a run, each averaging `4.9` days, so its position random-walks with
a standard deviation of about `0.05 * 4.9 * sqrt(280) = 4.1` days — comparable
to the route's own `4.93`-day headway. Two vessels that started a week apart
are not a week apart by mid-run, and a statistic cannot see it.

## Exact participant delta

The boarding wait is computed from the live spacing:

1. Each deployed vessel's phase around the loop is read from
   `current_segment`, taking the unobservable progress through its current leg
   as half. Only differences matter, so any common offset cancels.
2. The gaps between consecutive phases, all the way round, give
   `sum(gap^2) / (2 * cycle)` — the mean wait of an arrival spread evenly
   through time. It equals half a headway for even spacing and rises to half
   the whole cycle as the vessels bunch.
3. The charge is **twice** that. v10 established the level empirically, so
   doubling reproduces v10 *exactly* on an evenly spaced loop and on a
   single-vessel loop, and charges more only as the spacing degrades. The
   factor is not a free parameter: it is fixed by the requirement to reduce to
   the accepted rule.
4. A loop whose vessels cannot all be located falls back to `cycle / count`,
   so anything unreadable behaves exactly as today.

## Why this is not v11

v11 also read live vessel positions and was rejected at `+23%`. Its defect was
named in its own report: it took the **minimum** over several noisy per-vessel
estimates, and the minimum of noisy draws is optimistically biased — the more
vessels a route had, the more optimistic it became, so the busiest trunks
looked most imminent.

This takes an **expectation over the gaps**, not a minimum over the vessels.
The halfway-through-the-leg assumption is still there, but its errors enter a
smooth average instead of being selected for, so there is no winner's curse.
It also keeps one costing rule for every boarding, where v11 mixed a live
figure for the first and a statistic for the rest.

## Predictions, fixed before the runs

- Nothing is inert: every boarding on every route is re-costed, so all seven
  held-out scenarios and Round 2 may move.
- Routes whose vessels have drifted together become dearer, which should push
  cargo towards genuinely frequent services rather than nominally frequent
  ones.
- `unbooked` must stay `0`.

## Acceptance

- Round 2: `candidate_loss < 4.844560541925512 - 1e-9`;
- `shifted` no worse than `41.62569844636167`, `mild` no worse than
  `5.363436801272705`, `long` no worse than `77.65274459580378`, `twin` no
  worse than `40.12987734887265`, `brief` no worse than `6.767487342693513`,
  `undisrupted` no worse than `-5.030822520503106`, `inserted` no worse than
  `15.534240459359498`;
- `unbooked == 0` on every arm.

## Result and decision

Authoritative run, 72 periods, `Simulation completed.`

- **candidate loss `11.19289995968686`** against `4.844560541925512`:
  `+6.348339417761348` (`+131.04%`, worse);
- periods better/equal/worse: `19 / 0 / 53`.

Rejected, and the held-out arms were not needed.

## Why it failed: a convexity bias, not a winner's curse

The estimator avoided v11's defect and fell into a different one.

`sum(gap^2) / (2 * cycle)` is **convex** in the phases. The phases carry error,
because progress through the current leg is unobservable and is taken as half.
Convexity plus unbiased input error gives an upward-biased output — Jensen's
inequality — so random error in the positions **reads as bunching**. Every
route looks more bunched than it is, every boarding is overcharged, and the
differences between routes become dominated by estimation noise rather than by
real spacing.

That is worse than a uniform overcharge would be. A uniform one preserves the
ranking between routes; this one scrambles it, which is why `53` of `72`
periods degrade and not one is unchanged.

Together with v11 this is now measured twice, by two different estimators:

| candidate | how it used live positions | result |
| --- | --- | --- |
| v11 | minimum over per-vessel arrival estimates | `+23.10%` |
| v28 | expectation over the gaps between them | `+131.04%` |

The generalised lesson is stronger than v11's: it is not enough for the
estimator to avoid taking a minimum. Any **non-linear** functional of noisy
position estimates inherits a bias, and the noise here — half a leg, on a route
whose legs are days long — is far too large for the functional to survive.

The `cycle / deployed vessels` statistic is biased too, in the sense that it
ignores real drift. But its error is *independent of the noise in the
positions*, and the empirical calibration v10 fixed on top of it absorbs the
drift on average. A noisy unbiased-looking formula is not an improvement on a
calibrated biased one.

## Lessons

52. **Convex functionals of noisy state are biased upward.** v11 established
    that a minimum over noisy per-vessel estimates is optimistic. v28 shows the
    complementary trap: `sum(gap^2)` is convex, so the same noise makes every
    route look bunched. Reading live state needs an estimator whose error does
    not survive the transform, and neither of the two natural ones does.
53. **A calibrated approximation can beat an exact formula fed noisy inputs.**
    The full-headway statistic ignores drift entirely and still beats a
    formula that measures drift with half-a-leg of error, by a factor of two
    on the objective.
