# Round 1 three-change mixed low-margin delegation v23

## Decision

Test one subtractive refinement of the accepted Round 1 v3
`assign_associated_bookings` policy. V3 holds a new shipment when its
disrupted direct service is estimated to recover sooner than a safe path with
at least two service-route changes. V17 delegated every three-change hold and
was worse, so v23 keeps those holds except for a narrower, semantically
fragile subset.

The candidate delegates a v3 hold only when all of the following are true:

1. the unchanged v3 predicate qualifies;
2. the nominal edge's matching active constraints contain exactly one leg and
   one closed-port constraint (`{"leg", "port"}`);
3. the safe shortest path has exactly three service-route identity changes;
4. the strict v3 timing margin (`detour_hours - hold_hours`) is smaller than
   the first safe route's full headway, both derived from live runtime data.

All other v3 holds remain unchanged. The comparison is strict: equality with
the first safe-route headway retains the v3 hold. Malformed, missing,
non-finite, non-positive, inactive, pure-leg, two-change, or four-plus-change
states delegate exactly as v3 already does.

## Rationale and strongest failure mode

The first safe service opportunity is the main uncertainty in a positive
recovery margin. A three-change detour has several connection opportunities;
when its computed advantage is less than one full first-route headway, a small
phase/capacity error may erase that advantage. Mixed leg-plus-port disruptions
add two simultaneous constraints, so this is a narrower operational guard than
v17's all-three-change removal or v11's broad port-margin guard.

The strongest failure mode is that even low-margin three-change holds are
valuable for the small cargo flows that reach them, and delegating them may
reintroduce fragmented detours. The complete 72-period scorer, not activation
counts or exposure, decides.

## Boundaries

Only the participant-owned `assign_associated_bookings` hook changes. The
other three hooks remain unconditional `None` delegates. The implementation
must be read-only and deterministic, use standard-library imports only, fail
closed on malformed data, preserve v3's exact public signatures, and contain
no organizer imports, I/O, environment/process/network access, wall-clock
use, randomness, mutable module state, identity/date/route tables, or fitted
scenario constants. The first safe headway is computed from the live route
profile; it is not a hard-coded number.

The experiment is separately named and receives one full run only after a
fresh same-observation activation audit, RED→GREEN tests, and all preflight
gates pass. Equality, worsening, invalid output, or a failed gate is rejection
and requires the standard v3 restoration procedure.

