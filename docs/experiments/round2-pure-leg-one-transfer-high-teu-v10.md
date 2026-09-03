# Round 2: upper-quartile pure-leg one-transfer recovery hold (v10)

**Status: DESIGN FROZEN — pre-run review.**

This document defines one new Round 2 candidate. It does not authorize a full
simulation, tuning, publication, or submission. The incumbent remains v8 until
the candidate passes the complete preflight and one controlled run.

## Incumbent

The verified incumbent is Round 2 v8, the upper-quartile pure-leg
multi-transfer recovery hold:

- cumulative resilience loss: `34.62237395179777`;
- ATT snapshot:
  `.challenge/round2/results/multi_transfer_leg_teu_guard_v8_20260901/ATT_By_Statistics_Interval.csv`;
- ATT SHA-256:
  `616a8b07870d9de0b2597cb317ee14d4743455f5d4b34f315adf15895fc95700`;
- participant strategy SHA-256:
  `7e9794843eae071186cfdff4d835fb5d3e645bbd3d09008c86ac7977af1a17ee`;
- authoritative Round 2 baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`.

## Read-only structural audit

A fresh-context audit evaluated all 166 valid disruption midpoints and 380
demands per context (63,080 observations). It found 350 delegated direct,
one-transfer pure-leg observations. Only 24 had a positive recovery margin;
18 of those demands are in the deterministic upper quartile of annual TEU
(threshold `1801.0`). They occur in seven anonymous origin/destination and
disruption slices. No model event was advanced and the Round 2 Output file was
unchanged.

The positive-margin rows are not a score prediction: the audit does not model
real shipment arrival times, queues, capacity competition, or endogenous
consequences. It is only evidence that the proposed branch is live and bounded.

## Hypothesis

The incumbent already retains high-TEU recovery holds when the safe alternative
requires at least two service-route changes. A one-transfer pure-leg detour can
still be slower than waiting for the congested direct leg to recover. Extending
the same demand-weighted policy to that narrow, positive-margin class may lower
TEU-weighted delay without opening the rejected broad one-transfer policies.

The main risk is that a positive service-time margin below a safe-route
departure opportunity is not sufficient in the event-driven queue. The upper
quartile guard limits exposure to the shipments that dominate the objective;
all lower-volume and non-positive-margin observations continue to use the
organizer fallback.

## Exact candidate policy

Only `UserStrategy.assign_associated_bookings` may change. Preserve every v8
precondition, graph construction, deterministic shortest-path order, timing
calculation, exception boundary, and all other hooks.

After the nominal path is a single edge and the safe path has exactly one
service-route change:

1. require that the nominal edge matches only active leg-congestion constraints
   (`matching constraint kinds == {"leg"}`);
2. require finite positive `hold_hours` and `detour_hours` and
   `hold_hours < detour_hours`;
3. require the shipment demand to be present in the context and at or above the
   deterministic upper-quartile annual-TEU threshold already used by v8;
4. return `False` (hold at origin) only when all conditions hold; otherwise
   return `None` and delegate to the organizer fallback.

No port-only, mixed-constraint, multi-transfer, lower-quartile, inactive,
malformed, non-finite, or non-positive-margin decision is changed. No route,
booking, vessel, shipment, file, environment, time, random source, or global
state is mutated by the participant hook.

## Alternatives considered

| Candidate | Expected value | Risk / evidence | Decision |
| --- | --- | --- | --- |
| Add every positive-margin pure-leg one-transfer hold | More direct recovery holds, 24 live observations | Exposes lower-volume cargo; not TEU-targeted | Reject |
| Add upper-quartile pure-leg one-transfer holds for any positive margin | 18 live observations and no arbitrary fraction | Could still be harmed by headway/queue effects; selected as the smallest direct extension of v8 | **Select** |
| Add only a half-headway-margin subset | At most a few live observations | Likely too sparse; v9 showed a structurally live half-headway refinement can be inert | Reject |
| Extend mixed or port-only one-transfer cases | Larger activation surface | Round 2 v2/v3/v7 and Round 1 analogues degraded the score | Reject |
| Change berth or in-transit hooks | Potential network effects | Prior experiments were no-effect or materially worse | Reject |

## TDD and activation contract

Implement RED -> GREEN -> REFACTOR:

- commit this design before implementation;
- add focused synthetic tests for pure-leg one-transfer positive-margin
  upper-quartile hold, exact upper-quartile equality, lower-quartile
  delegation, zero/negative margin, port/mixed preservation, malformed demand
  data, and complete no-mutation behavior;
- implement the smallest standard-library-only branch using the existing v8
  helpers; do not duplicate threshold or path logic;
- add a real ignored-context contract and a fresh activation audit comparing the
  independent v8 oracle with the candidate;
- require candidate-only activations, zero unexpected opposite decisions, no
  participant mutation, no model event advancement, and no Output write before
  the run may proceed.

The audit expectation is 18 candidate-only structural holds and zero
control-only decisions. If the live audit differs, stop and document the
discrepancy before any full simulation.

## Fixed run contract

- round/scenario: `round2` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required periods: `72`;
- candidate evidence directory:
  `.challenge/round2/results/pure_leg_one_transfer_high_teu_v10_20260903/`;
- acceptance expression:
  `candidate_loss < 34.62237395179777 - 1e-9`.

Run exactly one frozen candidate only after lock, sync, formatting, Ruff, Ty,
mypy, test/coverage, integration, sync/cmp, smoke, deterministic-package,
restricted-material, control-score, stale-Output, and no-live-process gates
pass. Preserve the fresh ATT and raw log before scoring, synchronization,
smoke, packaging, or restoration. Compare every period with v8 and record the
activation counts and mechanism.

Equality, worsening, invalid or stale output, incomplete completion, a failed
gate, or a compliance issue is rejection. On rejection, preserve ignored
evidence, commit the result report, revert only this candidate's implementation
and tests in reverse order, synchronize and re-score the pinned v8 ATT, rerun
the final gates, update the public ledger, and leave v8 active. No duplicate
run, tuning, second candidate within v10, push, merge, PR, upload, submission,
or history rewrite is authorized.
