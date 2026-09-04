# Round 2: harden the fleet decision for a scenario we have not seen (v19)

**Status: REJECTED by its own precommitted rule. It found a real and much
larger defect than the one it set out to fix, and halved it rather than
removing it; v20 removes it.**

## Why this experiment exists at all

v18 scores `4.912139391692661` and is the accepted policy. This experiment is
not chasing that number; it is chasing a defect that Round 2 cannot show.

Two held-out scenarios have been in use since v12, and every candidate from v13
to v18 was measured against them. They are no longer held out in any meaningful
sense: the policy has been shaped by them. Round 2 itself has been the scored
scenario for eighteen experiments. So the only honest way to ask "will this
generalise?" is to build scenarios that stress the paths the policy has never
been run through, and to look for the ones that break it.

## The defect

v18's fleet decision refuses to route a rotation around a **shut port**, on the
grounds that a closure is a wait and dropping the call would abandon the cargo
booked there. That test is applied to the *nominal* rotation's ports only.

But a detour is built by inserting legs, so it calls ports the nominal rotation
does not. Nothing in v18 re-checks those inserted ports afterwards. A closure
that lands on one of them leaves the whole rerouted service sailing into a port
with no available berth, for as long as the closure lasts, while the rotation it
came from — which by construction has no closure on it — sits unused.

This is not hypothetical in Round 2's own network. The
`Shanghai -> Kaohsiung` detour routes through **Shenzhen**, and the
`Colombo -> New Jersey` detour routes through **Piraeus**, which Round 2 closes
on measured days `260-274`. Round 2 happens not to expose it only because the
`Colombo -> New Jersey` slowdown ends on day `100`, long before that closure,
so the fleet is home in time. A hidden scenario that overlaps a closure with a
slowdown on the same service would expose it immediately.

## Exact participant delta

1. The test that decides whether a built detour is the rotation to be running
   now also refuses any detour that calls a port with no available berth. The
   service then goes home to its own rotation and waits the closure out there,
   which is exactly what the nominal-rotation rule already does. No new
   concept, no constant: the same closed-port rule, applied to the rotation
   actually under consideration rather than only to the nominal one.
2. `_has_live_bookings` scans a rotation's bookings newest-first. A rotation
   still in use now answers on its first entry instead of its last, so the only
   full scan left is the one that finally finds it drained. This is a pure
   performance change with no effect on any decision.

Everything else is v18's, unchanged.

## The scenarios added, and what each is for

Four new held-out scenarios, none of which was used to design any accepted
candidate. All are built from the organizer's own baseline builder and
disruption helpers.

| scenario | what it stresses |
| --- | --- |
| `long` | two 120- and 90-day slowdowns overlapping in time on partly shared services, then a closure landing on those same rotations while their fleets are already on detours: the target flips home mid-changeover and the never-strand rule has to hold |
| `twin` | one slowed leg shared by two trunk services plus a third on another service, so three detours run concurrently — a shape neither Round 2 nor the older held-out set produces |
| `brief` | four slowdowns, every one shorter than the rotation it hits, so the changeover gate must refuse all four. Anything but a tie is the gate leaking |
| `inserted` | a closure on a port only the *detour* calls. This is the defect above, reproduced end to end |

`undisrupted` is also run: with nothing disrupted the fleet decision must be
provably inert, and a tie there is a check on the whole code path rather than
on the policy.

## Acceptance

This candidate is accepted only if **all** of the following hold:

- Round 2: `candidate_loss <= 9.762649496857325 - 1e-9`, and no worse than
  v18's `4.912139391692661` by more than nothing — the intended result is a
  bit-for-bit identical Round 2 ATT, since Round 2 never overlaps a closure
  with a live detour. A Round 2 *regression* rejects the candidate;
- `shifted` no worse than `41.62569844636167` and `mild` no worse than
  `5.363436801272705`;
- `brief` and `undisrupted` are exact ties with the v16 arm;
- `long`, `twin` and `inserted` are no worse than their v16 arms;
- `unbooked == 0` on every arm.

The v16 arm is included on every new scenario because the question these
scenarios exist to answer is not "is v19 better than v18" but "does owning the
fleet decision at all still pay on a scenario nobody designed it for".

## Results and decision

The new scenarios were run first, and `inserted` — the one built to reproduce
the defect — settled the matter before the rest were needed. Evidence:
`.challenge/round2/results/audit_20260904/v1{6,8,9}_inserted.json`.

| arm | `inserted` loss | vs v16 | unbooked |
| --- | --- | --- | --- |
| v16 (fleet never moves) | `16.754999739073277` | — | `0` |
| v18 (accepted) | `25.356597048659822` | `+8.6016` (`+51.34%`) | `0` |
| v19 | `22.23257671391118` | `+5.4776` (`+32.69%`) | `0` |

The precommitted rule requires `inserted` to be no worse than its v16 arm. It
is worse, so v19 is **rejected**, and the remaining arms were not run: a
candidate that has already failed a frozen condition does not get more runs
spent on it.

The authoritative Round 2 run was taken anyway, because it answers a separate
question — whether the change is inert where it should be. It is: the candidate
ATT is `d6eb1590f3317d9f8a918efc8d3a188529dd99c6bcc82b04295deef001e00f22`,
**byte-identical to v18's**, so Round 2's loss is unchanged at
`4.912139391692661`. Round 2 cannot see this defect at all.

## What `inserted` actually shows

The finding is much bigger than the bug v19 was written for: **on this
scenario, owning the fleet decision at all is a `51%` loss.** The accepted
policy is worse than doing nothing, by more than the entire margin v18 won on
Round 2, on a scenario shape Round 2 does not contain.

A static audit of Round 2's own detours (`.challenge/round2/` diagnostics)
shows how narrowly Round 2 avoids it:

| detour | rotation | inserted ports |
| --- | --- | --- |
| `S4-UALT-1` | `Shanghai -> Shenzhen -> Kaohsiung -> Los Angeles` | Shenzhen |
| `S5-UALT-1` | `Shanghai -> Shenzhen -> Singapore -> Colombo -> Piraeus -> Tanger Med -> New Jersey -> ...` | Piraeus, Tanger Med |

Round 2 closes **Piraeus** on measured days `260-274`. The
`Colombo -> New Jersey` slowdown that builds `S5-UALT-1` ends on day `100`, so
the fleet is home with 160 days to spare. Move that closure, or lengthen that
slowdown, and Round 2 would have shown the same `+51%`.

## Why halving it was not enough

v19 brings the fleet home when a port on its detour shuts, and recovers
`3.12` of the `8.60`. What is left is **thrashing**. On `inserted` the sequence
becomes: detour out (day 40), home (day 90, Shenzhen shuts), detour out again
(day 110), home (day 160, slowdown ends) — four changeovers inside one
120-day window, each costing about a turn of the rotation. v18 pays two
changeovers plus twenty days of sailing into a closed port; v19 pays four
changeovers. Neither is anywhere near as good as not moving.

That is the correct diagnosis and it points somewhere v19 does not go: the
detour should never have been built through a port that was going to shut.

## Lessons

28. **A held-out set that a policy has been developed against is not held out.**
    `shifted` and `mild` had shaped every candidate from v13 to v18, and both
    said v18 was fine. One genuinely new scenario said it was `51%` worse than
    doing nothing. Retire held-out scenarios as they are used, and keep adding
    adversarial ones.
29. **Ask "is owning this decision better than delegating it?" on every new
    scenario, not just "is the new version better than the old one".** Carrying
    the do-nothing arm through the audit is what made the size of this visible;
    comparing v19 only against v18 would have shown a `3.12` improvement and
    hidden a `5.48` regression.
30. **Fixing the symptom you predicted is not the same as fixing the defect.**
    v19 addressed exactly the failure mode named in its own design doc, and
    that failure mode turned out to be half the problem.
