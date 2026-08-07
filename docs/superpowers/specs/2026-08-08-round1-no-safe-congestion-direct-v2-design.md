# Round 1 no-safe-path congestion-tail direct booking v2

## Decision

Run one isolated Round 1 candidate that changes only
`UserStrategy.assign_associated_bookings`.

## Evidence and hypothesis

The Round 1 fallback excludes every active congested sailing leg from its
initial booking graph. Static inspection of the private `create_with_disruption`
scenario shows short congestion-only windows in which an exact affected
origin-to-destination pair has no remaining safe booking path. In those cases
the fallback returns `False` and the origin activity waits for disruption
recovery. The earlier congestion-only direct-booking experiment allowed every
exact affected pair onto the slowed leg and scored `24.888361755688166`,
materially worse than the `20.436668751255972` fallback; its broad scope is the
confounder this experiment removes.

The falsifiable hypothesis is that allowing the original congested leg only
when the fallback-safe graph has no complete path reduces waiting backlog while
avoiding the harmful detour substitutions. The policy remains inactive during
any active berth closure and delegates whenever a safe path exists.

## Exact participant policy

At an active decision:

1. Validate disruption windows and collect active congested target legs and
   closed-berth ports. Any malformed or ambiguous state delegates with `None`.
2. If any berth closure is active, or no valid congested leg is active, return
   `None`.
3. For an exact demand endpoint match, find the original service-route segment
   representing that target leg and require a deployed vessel on that route.
4. Build the same deterministic contiguous booking graph used by the fallback,
   excluding active congested legs and closed ports, including only original
   routes and matching deployed alternatives. If a complete safe path exists,
   return `None` and preserve fallback behavior.
5. If no safe path exists, install one complete `Booking` for the matching
   original congested segment transactionally and return `True`.

The strategy never uses port names, route IDs, dates, seeds, thresholds,
randomness, I/O, environment, network, subprocesses, wall-clock time, mutable
module state, or organizer-owned imports. All other hooks remain unconditional
`None`. Delegation and malformed paths are read-only. Booking installation
must preserve old shipment and reverse-route references on any failure.

## TDD contract

RED tests must fail against the untouched no-op adapter for the no-safe-path
exact endpoint case. GREEN tests must cover:

- active-window start inclusive/end exclusive;
- exact affected endpoint with no safe path returns a valid one-segment booking;
- exact affected endpoint with a safe detour delegates unchanged;
- active closure, inactive plans, nonmatching endpoints, missing/deployed-empty
  route, malformed plans/routes, and ambiguous target legs delegate unchanged;
- deterministic original-route selection and no alternative-route misuse;
- transactional rollback when installation fails;
- all four public signatures and untouched-hook delegation;
- a real Round 1 context check with no context/shipment mutation.

## Fixed run contract

- branch: `codex/round1-no-safe-congestion-direct-v2`
- base: `3e9434974f16ea6df58ef5c24fecf268869620b2`
- round/scenario: `round1` / `create_with_disruption`
- seed: `2026`; `PYTHONHASHSEED=0`
- warm-up: `140` days; measured horizon: `360` days
- ATT interval: `5` days; required periods: `72`
- candidate command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- acceptance: `candidate_loss < 20.436668751255972 - 1e-9`
- candidate evidence directory (ignored):
  `.challenge/round1/results/no_safe_congestion_direct_v2_20260808/`
- ignored aggregate:
  `experiments/results/round1_no_safe_congestion_direct_v2_20260808.json`

The historical Round 0 score is not an acceptance threshold. The candidate
must be run exactly once after all preflight gates pass. Equality, worsening,
crash, incomplete output, invalid period count, or failed gates is rejection;
the result must be committed before reverting candidate code/tests in reverse
order, synchronizing the no-op adapter, restoring the pinned ATT, rescoring,
and rerunning every final gate. No tuning, second candidate, submission,
publication, push, merge, or history rewrite is part of this experiment.
