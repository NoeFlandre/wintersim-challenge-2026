# Round 1 immediate direct-next-leg booking design

## Status

This is one isolated Round 1 experiment starting from the restored no-op
fallback at `main` (`6ccbca8`). The full simulation is not authorized until
the RED tests, implementation, integration checks, and pre-run review are
green.

## Hypothesis

The organizer fallback minimizes nominal sailing distance, but it does not
prefer an already-positioned direct service over a shorter-looking chain that
requires a transfer. During a disruption, transfer handling and waiting can
dominate the small sailing-distance difference. A conservative participant
policy can remove that avoidable transfer only when a direct original service
is physically ready to sail the shipment's exact origin-to-destination leg.

The candidate will therefore assign one direct booking only when all of the
following are true:

1. The simulation clock is inside at least one valid disruption window.
2. The shipment has distinct origin and destination ports.
3. An original, non-alternative service route contains one segment whose
   physical leg is exactly origin → destination.
4. That route has a deployed vessel whose next segment is that exact segment,
   with no pending alternative assignment. This means the direct service is
   already at the origin and is the next sailing leg, rather than merely being
   nominally available somewhere in the network.
5. The direct segment is not an active congested leg, and neither endpoint is
   an actively closed berth. A non-unit live sailing multiplier also causes
   delegation.

Every other call returns `None` and leaves the organizer fallback in charge.
The policy never creates routes, changes vessel state, predicts an entire
trajectory, or returns `False` to hold cargo.

## Exact participant surface

Only `UserStrategy.assign_associated_bookings` can return a non-`None` value.
It installs exactly one complete `Booking` over the ready direct segment. The
installation is transactional: old shipment bookings, current index, and
reverse service-route references are restored if construction fails. The
other three hooks remain unconditional `None` delegates.

The participant implementation uses only standard-library modules and the
runtime `Booking` class. It has no organizer fallback import, file/network/
subprocess/environment access, wall-clock reads, randomness, or mutable
module-level state. All comparisons use object identity for organizer objects,
and malformed inputs fail closed to `None`.

## Why this is narrower than rejected experiments

Earlier Round 1 routing experiments replaced many initial paths using distance,
disruption multipliers, or estimated fleet phase; they increased loss. This
candidate does not replace a graph path globally. It changes only an exact
direct OD shipment with an actual next-leg vessel and only in an active
disruption window. Berth-priority experiments also tied or worsened; no berth
hook is changed here.

## Fixed experiment contract

- round: `round1`
- scenario: `create_with_disruption`
- seed: `2026`
- `PYTHONHASHSEED=0`
- warm-up: `140` days
- measured horizon: `360` days
- ATT interval: `5` days; required periods: `72`
- candidate command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- strict acceptance: `candidate_loss < 20.436668751255972 - 1e-9`
- ignored candidate evidence directory:
  `.challenge/round1/results/immediate_direct_next_leg_v1_20260807/`
- ignored aggregate:
  `experiments/results/round1_immediate_direct_next_leg_v1_20260807.json`

Exactly one full candidate run is permitted after the pre-run review. A
crash, incomplete CSV, invalid period count, equality, worsening score, or
failed final gate is rejection. Candidate output and log must be copied and
hashed before scoring, synchronization, smoke, or restoration can overwrite
the organizer `Output/` directory.

## Required gates before and after the run

Run locked `uv` dependency checks, Ruff format/lint, Ty, mypy, focused RED →
GREEN tests, the non-integration coverage gate (at least 90%), integration
tests, participant/runtime synchronization and comparison, Round 1 smoke,
deterministic participant-only packaging, restricted-material scans, diff
hygiene, and process checks. On rejection, preserve ignored evidence, revert
only candidate code/tests, synchronize the no-op adapter, restore the pinned
fallback ATT bytes, re-score exactly, rerun final gates, document the result,
remove the temporary worktree, and fast-forward/push only the public audit
commits to `main`. Do not submit an archive or publish organizer material.
