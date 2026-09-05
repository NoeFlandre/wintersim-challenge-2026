# Round 2 experiment ledger

One row per controlled Round 2 experiment. Lower cumulative resilience loss is
better. Every score is the full 72-period result of exactly one authoritative
run (140-day warm-up, 360 measured days, five-day periods, seed `2026`,
`PYTHONHASHSEED=0`, scenario `create_with_disruption`) scored against the
authoritative baseline ATT
`1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`.

| # | Behavioural delta | Activation | Loss | vs incumbent | Periods B/E/W | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| ctl | Round 1 v3 multi-transfer recovery hold, synchronized fresh into Round 2 | 31 holds | `35.50366097019303` | — | — | control |
| v1 | + hold port-closure-only one-change detours when the recovery margin exceeds one full safe-route headway | +254 holds (285) | `35.1039547178493` | `-0.3997` (`-1.126%`) | 11/57/4 | **accepted** |
| v2 | v1 threshold relaxed to half a headway | +76 holds (337) | `35.6743500877092` | `+0.5704` (`+1.625%`) | 8/57/7 | rejected |
| v3 | v1 threshold relaxed to three quarters of a headway | +26 holds (287) | `35.535225309642755` | `+0.4313` (`+1.229%`) | 8/57/7 | rejected |
| v4 | v1 restricted to late-recovery windows (drops early holds) | fewer holds | `35.8691309610454` | `+0.7652` (`+2.180%`) | 4/59/9 | rejected |
| v5 | berth hook: prefer a vessel pending an alternative route during closures | 14 selections | `35.1039547178493` | `0.0000` (tie) | 0/72/0 | rejected (equality) |
| v6 | v1 holds dropped below the third-quartile annual-TEU threshold | 285 to 168 holds | `35.84344929789106` | `+0.7395` (`+2.107%`) | 10/59/3 | rejected |
| v7 | v1 plus upper-quartile-TEU half-headway holds | +39 holds (324) | `35.41374495066942` | `+0.3098` (`+0.882%`) | — | rejected |
| v8 | delegate lower-quartile pure-leg multi-transfer holds | — | design only | — | — | never run |
| v9 | **architecture change:** build the booking chain from estimated transport time instead of delegating to the organizer's distance-based shortest path | 66,070 chains where the incumbent delegated; 285 former holds now booked | `20.248013560766417` | `-14.8559` (`-42.320%`) | 50/0/22 | **accepted** |
| v10 | charge a full headway per boarding instead of half, the correction derived from the measured per-boarding residual | every chain re-costed; transfers priced twice as dearly relative to sailing | `14.897068731156086` | `-5.3509` (`-26.427%`) | 54/2/16 | **accepted** |
| v11 | read the first boarding wait from live vessel positions instead of the headway statistic | every first boarding re-costed | `18.3386705330832` | `+3.4416` (`+23.103%`) | 30/0/42 | rejected (also failed held-out) |
| v12 | treat a port closure as temporary: charge the wait until it reopens instead of deleting the port, and book cargo bound for one rather than holding it | 17 of 72 periods change; congestion windows untouched | `13.27493539992092` | `-1.6221` (`-10.889%`) | 15/55/2 | **accepted** (held-out `-10.32%`) |
| v13 | keep an in-transit chain when it already beats the best alternative, instead of letting the organizer rebuild it by distance | fires on Round 2; inert on the held-out scenario | `11.915883436787134` | `-1.3591` (`-10.238%`) | 19/32/21 | **accepted** (held-out exact tie) |
| v14 | charge the alternative the wait to board it, and drop the congestion-free requirement that has no meaning for cargo already at sea | repairs v13's closure regressions; 5 of 6 windows improve | `10.350669070475163` | `-1.5652` (`-13.136%`) | 28/33/11 | **accepted** (held-out `-0.74%` for the intervention) |
| v15 | time a congestion slowdown as v12 timed a closure: a leg sailed after it clears is costed at normal speed | both 60-day windows unchanged; the 25-day window improves | `10.347110679813037` | `-0.0036` (`-0.034%`) | 17/45/10 | **accepted** (held-out `-15.79%` on short windows) |
| v16 | keep every vessel on its rotation instead of letting the organizer reserve one per affected service onto a single-vessel avoiding route | no alternative routes exist; S4 regains 25% of its frequency | `9.762649496857325` | `-0.5845` (`-5.649%`) | 34/22/16 | **accepted** (held-out tie and `-0.09%`, no cargo stranded) |
| v17 | move a whole service onto a detour around a slowdown whenever the detour still calls every port and its cycle is shorter at the live multipliers | one detour built for `S4`, whole fleet reserved | not run | — | — | rejected on held-out (`shifted` `-1.0385`, `mild` `+2.0175`) |
| v18 | v17 plus the changeover cost: start a rotation change only when the slowdown's remaining life exceeds one turn of the detour, and never reverse one already under way | two detours built (`S4-UALT-1`, `S5-UALT-1`); both 60-day windows change, the 25-day one does not | `4.912139391692661` | `-4.8505` (`-49.684%`) | 28/12/32 | **accepted** (held-out `-2.43%` and an exact tie, no cargo stranded) |
| v19 | bring a rerouted fleet home when a port on its detour shuts | Round 2 bit-identical; `inserted` `22.2326` against a do-nothing `16.7550` | not accepted | — | — | rejected on held-out `inserted` (`+32.69%`) |
| v20 | never build a detour through a port that a disruption plan will shut inside the window the detour is needed for | Round 2 bit-identical; `inserted` `16.1746`, now `-3.46%` against doing nothing | `4.912139391692661` | `0.0000` (tie, by design) | 28/12/32 | **accepted** (7 held-out scenarios: 4 wins, 3 ties, 0 losses) |
| v21 | refuse a ride on a temporary rotation that would end after the rotation is withdrawn, so it drains before the fleet comes home | tapers the detour's intake near a window's end | `6.5457552167823945` | `+1.6336` (`+33.26%`) | 18/16/38 | rejected (cost `1.68` inside the window; the tail it targeted got `0.68` worse) |
| v22 | a fleet moves to escape a live disruption and never merely to come home: keep the incumbent rotation unless the disruptions hurt it more | fleets stay on their detours | `13.632583218221225` | `+8.7204` (`+177.53%`) | 15/24/33 | rejected (target window improved to `-0.4034`, but `33` undisrupted periods cost `+6.53` for a permanently split fleet; held-out `twin` `-2.60%` and `shifted` `-0.74%` disagreed with Round 2) |
| v23 | a rotation is owed a vessel only for bookings the cargo has not passed yet, not for every unfinished shipment that ever used it | all three congestion windows bit-identical; `S4-UALT-1` parked capacity `13,389` -> `11,768` | `4.844560541925512` | `-0.0676` (`-1.376%`) | 12/52/8 | **accepted** (6 held-out exact ties, `inserted` `-3.96%`) |
| v24 | own the in-transit rebuild: when a booked chain loses, rebuild it by time instead of handing it to the organizer's distance search | unreachable on Round 2; fires on `inserted` | `4.844560541925512` | `0.0000` (tie) | 0/72/0 | rejected (tie on Round 2, and `inserted` `+17.93%` where it did fire) |
| v25 | cost an in-transit ride on the rotation it is actually sailing, even when that rotation takes no new bookings | the veto keeps chains it used to delegate | `5.541576684632464` | `+0.6970` (`+14.39%`) | 14/30/28 | rejected (keeping cargo on a rotation the fleet is abandoning is worse than the organizer's rebuild) |
| v26 | v25 plus an honest headway: price every rotation by the vessels staying on it, not the ones already reserved away | the veto lets draining cargo go on the merits instead of by failing closed | `4.844560541925512` | `0.0000` (tie) | 0/72/0 | rejected (equality; converges on the incumbent's behaviour exactly) |
| v27 | a rotation built for a disruption may only be the *first* booking of a chain | `S5-UALT-1` carried `332` -> `232` TEU, its last vessel rejoins sooner | `5.660405309175495` | `+0.8158` (`+16.84%`) | 29/14/29 | rejected (the bookings given up are worth several times the vessel freed) |

Round 2 progression: `35.1039547178493` (v1) to `4.912139391692661` (v18,
unchanged by v20), a `-86.01%` reduction — `7.15x` lower.

## Held-out scorecard for the accepted policy

Every scenario carries a **do-nothing arm** (v16, which never moves a vessel),
so each row answers "does owning the fleet decision pay here?" rather than only
"is the new version better than the old one".

| scenario | do nothing | accepted (v20) | delta | unbooked |
| --- | --- | --- | --- | --- |
| Round 2 (scored) | `9.7626` | `4.844560541925512` | `-50.38%` | `0` |
| `twin` | `42.1737` | `40.12987734887265` | `-4.85%` | `0` |
| `inserted` | `16.7550` | `15.534240459359498` | `-7.29%` | `0` |
| `shifted` | `42.6642` | `41.62569844636167` | `-2.43%` | `0` |
| `long` | `79.2269` | `77.65274459580378` | `-1.99%` | `0` |
| `mild` | `5.3634` | `5.363436801272705` | tie | `0` |
| `brief` | `6.7675` | `6.767487342693513` | exact tie | `0` |
| `undisrupted` | `-5.0308` | `-5.030822520503106` | exact tie | `0` |

## Lessons carried forward

1. **The hold predicate is exhausted.** Relaxing the v1 margin (v2, v3, v7) and
   tightening it (v4, v6) both lose. v1 sits at a local optimum worth about
   `1.1%` of the objective, and the whole family only ever moves 15 of 72
   periods.
2. **Berth selection is inert here.** v5 changed 14 selections and produced a
   byte-identical ATT. The control run confirms why: an average of `0.11`
   vessels wait for a berth, so berth priority cannot matter.
3. **Structural activation counts do not predict score.** v2 added 76 holds and
   v7 added 39; both lost. v6 removed 117 and lost. Only the 72-period score
   decides.
4. **Backlog is what the metric punishes.** ATT counts every unfinished
   shipment's age at each period end, so a hold that does not pay off is
   charged in every period it spans. That is the mechanism behind v2/v3/v7:
   marginal-margin holds accumulate age faster than they save transit time.
5. **The loss was never where the experiments were looking.** Per-period
   attribution of the control run puts `47.7%` of the loss in the
   Shanghai-Kaohsiung congestion window and `38.3%` in periods with no active
   disruption. The two port closures, which are the only place the v1-v7 family
   could act, hold `5.8%` between them. Attribute the objective before
   choosing where to intervene.
6. **Capacity is not a constraint.** Service-route utilisation runs `0.88%` to
   `6.12%`. Transport time is dominated by sailing time plus waiting for the
   next departure, so re-routing cargo between services has no meaningful
   congestion cost — and choosing services by distance, which ignores departure
   frequency, leaves real time on the table. This is the observation v9 acts on.

## After v16

The incumbent is `9.762649496857325`, `72.19%` below the `35.1039547178493`
that started the round, and the first result under `10`.

7. **Measure the model against the simulation, then correct the mechanism.**
   v10 was a one-line change worth `-5.35`. It came from pairing each
   shipment's estimate with its realized transit time, finding a residual that
   scaled with boardings rather than with shipments, and matching its size to
   half the mean headway. Its per-window result then confirmed all three of its
   predictions, including recovering `-1.7830` of exactly the periods v9 had
   lost and repairing the Piraeus window without a closure-specific rule. This
   is the cheapest lever found so far per unit of effort.
8. **Resist coefficient search.** The residual admits both a proportional and a
   constant-per-boarding fit, neither decisive, with most variance OD-specific.
   `1.0` was taken because it is the mechanism value, not because it scored
   best; no sweep was run.

9. **Check the mechanism before building the fix.** The natural explanation
   for v10's late-run excursion was that vessels stuck at a closed port make
   the headway statistic lie. The run's own statistics refuted it: vessels
   waiting for a berth never exceed `0.22` on average while waiting cargo
   climbs steadily. A plausible-sounding correction would have addressed a
   cause that is not present.

Open questions are attributed with evidence in
[`round2-remaining-loss-attribution.md`](round2-remaining-loss-attribution.md):
`9.7485` of the remaining `14.897` sits in periods with no active disruption,
`0` unfinished shipments are unbooked, `69%` of aged backlog is already in
transit, and no OD pair exceeds `2.2%` of it. The two widest remaining levers
are reading the next departure from live vessel state instead of estimating it,
and taking over in-transit replanning.

## Generalisation protocol, added at v11

From v11 onward a candidate must also beat the incumbent on a **held-out
scenario** it was never developed against, built from the organizer's own
baseline builder and disruption helpers: the `shifted` scenario closes
**Singapore** and **Rotterdam** and congests `Singapore->Colombo`,
`Busan->Los Angeles` and `Rotterdam->Tanger Med`, with different durations and
multipliers from Round 2. Both arms share the scenario and seed, so the
organizer baseline supplies the weights and cumulative loss ranks them
directly.

The protocol has already changed two decisions:

10. **It rejected v11 on independent evidence** before the authoritative run
    finished, and the authoritative run agreed.
11. **Rank by the metric, never by mean ATT.** v11 improved mean ATT on both
    held-out scenarios while making one *worse* on cumulative loss. The
    objective weights a period by `baseline / ATT^2`, so it cares more about a
    shipment-hour lost in a good period than in a bad one, and a candidate that
    wins big on a few bad periods while losing a little on many good ones looks
    good on an average and bad on the score.
12. **Held-out runs must outlast their disruption windows.** v11's `r2_seed7`
    comparison ran 150 measured days, stopped before the Shanghai-Kaohsiung
    window where most of the incumbent's advantage accrues, and wrongly
    favoured the candidate. v12's held-out runs use 300 measured days.
13. **Watch when an effect can show up at all.** Booking cargo instead of
    holding it cannot move ATT while the cargo is unfinished, because ATT
    charges its age either way; it moves ATT when the cargo completes. v12's
    Piraeus window shows no change while the four periods after it do.

14. **A one-sided change can be banked on a tie.** v13's held-out ATT was
    byte-identical to its control. That is not absence of evidence but
    evidence of harmlessness, because the hook cannot mutate anything and can
    only decline a change; where it does not fire, behaviour is exactly the
    incumbent's. A change that could mutate state would not earn the same
    benefit of the doubt.
15. **Count why a rule declines, not just how often it fires.** v13's tie was
    fully explained by counting delegate reasons: affected shipments cluster
    at roughly 174 per vessel call, so its per-vessel all-or-nothing rule let a
    single un-costable shipment veto the whole call. The same counters showed
    its yardstick was wrong: costing the alternative optimistically flips
    keep-versus-rebuild from `5.3:1` for keeping to `4:1` against it.

16. **Ask whether a held-out scenario can even test the change.** Both held-out
    ties for the in-transit hook were explained by measurement, not argument:
    on `shifted` the organizer finds no replacement path for any of `10,959`
    affected shipments, so it keeps them itself and there is nothing to
    disagree about. A scenario has to be *mild enough for alternatives to
    exist* before it can exercise a replanning decision. The `mild` scenario
    was built for exactly that, and it is what produced the first positive
    held-out evidence for this line of work.
17. **Compare against the right control.** `mild` showed v13 and v14 identical,
    which says only that v14's refinements do not bite there. The informative
    comparison was v12 against v14 — with and without the intervention at all —
    which showed `-0.74%`. A tie between two variants of the same idea is not
    evidence about the idea.

18. **A tiny gain on the scored scenario is not the same as a tiny change.**
    v15 moves Round 2 by `0.03%` and a held-out scenario by `15.79%`. Both
    numbers come from one mechanism whose value scales with how short a
    slowdown is: inside a 60-day window no cargo ever reaches the slowed leg
    after it clears, so Round 2's two 60-day windows are literally unchanged,
    while 25-to-30-day windows pay off heavily. Judging that change by its
    Round 2 delta alone would have thrown away the largest held-out gain of the
    round.
19. **The overfitting signature has a shape, and so does its opposite.** A
    candidate that gains a lot on the scored scenario and nothing elsewhere is
    suspect; one that gains almost nothing on the scored scenario and a lot on
    an unseen one is the reverse, and is worth accepting on the strength of the
    mechanism.

20. **Check what the organizer's own response costs you.** The fallback's
    shipping-line response reserved one vessel per affected service onto an
    avoiding route that carried `2` and `0` TEU while the services losing those
    vessels gave up up to `25%` of their departures. Declining that trade was
    worth `-5.65%`. A delegated hook is not a neutral default; it is an active
    policy whose side effects are worth measuring.
21. **Name the failure mode before the run, then gate on it.** Suppressing
    avoiding routes could have stranded cargo whose only path needed one, so
    `unbooked == 0` was made an explicit acceptance condition and the held-out
    scenario chosen for having a hub closure. It came back `0`, which is a
    result rather than an assumption.
22. **The berth hook has nothing to sell.** A probe that wrapped
    `select_vessel_for_berth` and ran the real scenario recorded `0` calls in
    145 days: the organizer consults it only when waiting vessels reach three
    times the idle berths, and the run's own statistics put average vessels
    waiting at `0.19` of `41`. v5 had already measured a tie there. Two
    independent measurements agree that berth priority is not a lever in this
    network, so no further experiment should spend a run on it.
23. **Changing a fleet's rotation costs about one turn of it, twice.** v17
    moved whole services onto faster detours and was rejected because the cost
    of the changeover — vessels move one at a time and only when empty, and
    then have to come home — exceeded the benefit whenever the slowdown was
    shorter than a rotation. Any decision that reassigns vessels has to price
    the transient, not just compare the two steady states.
24. **Two held-out scenarios that disagree are worth more than two that
    agree.** `shifted` liked v17 and `mild` hated it, and the ratio that
    separates them (slowdown duration against rotation cycle) was exactly the
    term the rule was missing. Design the held-out set to differ along axes the
    candidate might be sensitive to, not to be uniformly hard.
25. **Price the transient, then the steady state.** The same whole-service
    detour rule that was rejected at `+2.02` on a held-out scenario is worth
    `-49.68%` once it also asks whether the disruption will outlast the
    changeover. The difference is one ratio of runtime quantities, no constant.
26. **A held-out scenario that returns to a bit-for-bit tie is a strong
    result.** `mild` matching its control to the last digit proves the gate
    made the mechanism inert there rather than merely smaller, which is what
    distinguishes a corrected rule from a damped one.
27. **The cost of a policy can land entirely outside the window it acts in.**
    v18's whole price is paid in the ten weeks *after* the slowdown it fixes,
    in periods where nothing is disrupted. Attributing loss by window is what
    made that visible; the scalar alone would have hidden it.
28. **A held-out set that a policy has been developed against is not held
    out.** `shifted` and `mild` shaped every candidate from v13 to v18, and
    both said v18 was fine. One genuinely new scenario said it was `51%` worse
    than doing nothing. Retire held-out scenarios as they are used, and keep
    adding adversarial ones.
29. **Carry a do-nothing arm on every new scenario.** Comparing v19 only
    against v18 would have shown a `3.12` improvement and hidden a `5.48`
    regression against delegating the decision entirely.
30. **Fixing the symptom you predicted is not the same as fixing the defect.**
    v19 addressed exactly the failure mode named in its own design doc, and
    that failure mode was half the problem.
31. **Feasibility before optimality.** v18 and v19 argued about whether and
    when to change rotation; neither asked whether the rotation could be sailed
    for as long as it was needed. That question made both earlier arguments
    moot.
32. **A rule whose predicted effect is "nothing changes anywhere except one
    scenario" is worth more than a rule that improves the score.** v20's
    prediction was checked in six places and held in all six, to the last digit.
33. **Future disruption plans are readable, and using them is not an exploit.**
    v12 already timed a reopening from the same published plan set.
34. **A negative result that relocates the cost is more informative than one
    that merely fails.** v21 was supposed to shrink periods `41-56` and made
    them worse, which ruled out the leftover pile as the cause.
35. **The detour's value inside its window is large and fragile.** Any rule
    that reduces how much cargo can use it gives back the `7.74` that building
    it won.
36. **A split fleet is much worse than either rotation.** v22 cost `+6.53`
    across `33` undisrupted periods for running two half-services. Judge a
    vessel-reassignment policy on whether the fleet ends up whole.
37. **Read the route statistics, not just the ATT.** `Avg Capacity TEU` split
    across a route and its detour identified both v22's failure and the
    residual defect in the accepted policy: about two of 41 vessels sit parked
    on withdrawn rotations for most of the run, worth the `1.2764` that periods
    `41-56` carry.
38. **Held-out scenarios can disagree with the scored one in sign, and the
    reason is usually structural.** v22 was better on `twin` and `shifted` and
    `+177%` worse on Round 2, because the cost of a permanently split fleet
    scales with how much undisrupted time follows the last window - about `200`
    days on Round 2 against `70` on `twin`. Check both, and know which
    structural feature separates them.
39. **Check whether a safety rule is stated as strongly as it is meant.** The
    never-strand rule was right; its predicate asked "is this shipment
    unfinished?" when the property it protects is "does this shipment still
    need this rotation?". The gap parked two of 41 vessels for most of a run.
40. **A change that alters no decision should leave every window identical, and
    that is testable.** v23's three congestion windows came back `0.0000` and
    `52` of `72` periods bit-identical.
41. **An inert result is still a result, and "why is it inert?" is the question
    worth asking.** v24's byte-identical ATT proved its branch unreachable, and
    finding out why located a live category error in the network the veto uses.
42. **Replacing a plan has a cost the comparison must carry.** Rebuilding onto a
    different service discharges the cargo to wait; comparing only the two
    journey estimates makes every marginal difference look worth acting on.
43. **A defect being real does not make the obvious fix right.** v25 corrected a
    genuine category error and cost `14%`, because a second error - pricing a
    rotation by the fleet it currently has - was cancelling it.
44. **Check what a vessel count will be, not what it is.** Every headway reads
    `deployed_vessels` at the instant of the estimate: correct for a stable
    service, wrong for one mid-changeover, which is when the veto fires most.
45. **Accidentally-right behaviour is still load-bearing.** The uncostable-ride
    delegation was firing "for the wrong reason" and was doing real work.
46. **Converging on the incumbent is evidence, not failure.** v26 reached the
    accepted policy's 72 identical periods by a completely different route,
    which says that behaviour is the model's considered answer rather than an
    artefact of a fail-closed path.
47. **Three failures of the same shape are a result about the search space.**
    v21 (`+33%`), v27 (`+17%`) and their siblings all traded detour bookings
    for fleet tidiness and all lost by a factor. A detour's value is the cargo
    it carries, not the vessels it ties up; the accepted policy sits at that
    optimum.
48. **Two core-model approximations were examined and left alone, on
    inspection rather than by running.** Charging a port call per boarding
    double-counts, because a headway already measures departure-to-departure.
    And the exact boarding wait implied by the simulation's own seven-day
    vessel-release schedule, `sum(gap^2) / (2 * cycle)`, comes out *below* a
    full headway - the direction v10 measured as `26%` worse. Deriving a
    quantity honestly is not enough; it has to survive the calibration that is
    already in evidence.
