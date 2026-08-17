# Round 1 port-closure exclusion v10 design

## Goal

Test one narrow refinement of the accepted Round 1 v3
`assign_associated_bookings` policy: keep its recovery hold for direct cargo
whose disrupted nominal edge is affected only by slowed physical legs, but
delegate when a matching closed-port constraint is also present.

## Evidence and rationale

The accepted v3 policy has a fresh control score of
`19.084638612143134` and holds in 48 observations in the identity-free audit
sample. The preceding v9 experiment removed the 22 pure-leg holds (annual-TEU
exposure proxy `55,272`) and scored `22.38757990186231`, a `17.306805524824487%`
degradation. That result is direct evidence to retain the pure-leg subset; it
does not establish that the remaining 26 port-involved holds are beneficial.

The same audit found 26 port-involved v3 holds (16 with a two-change,
four-edge safe path and 10 with a three-change, five-edge safe path), with an
annual-TEU exposure proxy of `21,126`. V10 removes exactly that subset and
retains every pure-leg v3 hold. The audit covered 50 derived timestamps and
19,000 demand-time observations, used fresh contexts, and observed no
mutation. Activation is structural evidence only; the complete scorer decides.

## Frozen candidate policy

Only `UserStrategy.assign_associated_bookings` changes. After all existing v3
guards pass (new unbooked shipment, active valid disruption, one-edge nominal
path, safe path, at least two safe service-route changes, and finite strict
timing advantage), classify the active constraints intersecting the nominal
edge:

- if every matching constraint is a congested-leg constraint, preserve v3 and
  return `False`;
- if any matching constraint is a closed-port constraint, return `None` and
  delegate to the organizer fallback;
- if constraints are missing, malformed, or unsupported, fail closed with
  `None` as v3 already does.

The helper must use object identity for legs and normalized port names only for
the existing structural match. It must not add ports, routes, bookings,
vessels, files, environment reads, randomness, wall-clock access, subprocesses,
organizer imports, mutable module state, or numeric thresholds. All non-target
hooks remain unconditional `None` delegates. Delegate and handled paths must
be mutation-free and deterministic.

## Alternatives rejected

- Broad one-transfer recovery holds were tested in v2 and worsened the v3
  control when removed/refined; v6 and v8 specifically rejected pure-leg
  one-transfer additions.
- Removing pure-leg holds was tested directly in v9 and worsened sharply.
- Berth priority, in-transit rebooking, phase-aware routing, headway gates, and
  transfer-overhead changes were already rejected or had no measurable effect.
- A pure-port one-transfer hold was audited and dormant in the real topology.

V10 is therefore the smallest live complementary subset left by the v3/v9
evidence, not a fitted parameter or a combined-hook change.

## Verification and decision

The candidate must follow strict RED -> GREEN TDD. RED must fail only because
the current v3 adapter returns `False` for mixed leg+port holds. GREEN must
prove mixed and port-involved delegation, pure-leg retention, all inherited
v3 behavior, fail-closed malformed input, deterministic ties, exact public
signatures, forbidden-capability checks, and real-context no-mutation parity.

The fixed Round 1 identity is:

- scenario `create_with_disruption`, seed `2026`, `PYTHONHASHSEED=0`;
- 140-day warm-up, 360 measured days, five-day ATT interval, 72 periods;
- control ATT SHA-256
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control score `19.084638612143134` against baseline SHA-256
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Exactly one full run is allowed. Preserve fresh ATT/log bytes before scoring
or restoration. Equality, worsening, invalid output, crash, timeout, stale
output, failed gate, or incomplete periods is rejection. On rejection, commit
the result first, revert only the v10 implementation/tests in reverse order,
synchronize v3, restore the pinned v3 ATT, re-score exactly, and rerun every
final gate. No tuning, second candidate, push, merge, PR, upload, submission,
or history rewrite is part of this experiment.
