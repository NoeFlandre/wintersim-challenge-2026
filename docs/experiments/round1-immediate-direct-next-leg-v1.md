# Round 1 immediate direct-next-leg booking v1

**Status:** rejected; the candidate was run exactly once, evidence was
preserved, the no-op fallback was restored, and final gates passed.

## Hypothesis and policy

Earlier Round 1 route experiments changed many bookings using nominal distance,
disruption weights, or estimated fleet phase and performed worse. This pass
tested a narrower idea: during an active disruption, if a shipment's exact
origin-to-destination pair is one physical segment of an original service
route and a deployed vessel's next segment is already that exact leg, a direct
booking can avoid a transfer and its waiting/handling delay. The candidate
delegated in every other case, never changed berth or route hooks, never used
alternative routes, and skipped a direct leg that was itself congested, had a
non-unit live multiplier, or touched an actively closed berth.

The implementation used only standard-library code plus the runtime
`Booking` class, installed bookings transactionally, and failed closed on
malformed inputs. RED → GREEN unit tests covered active-window boundaries,
route/vessel identity, disruption exclusions, rollback, and untouched hooks;
the real Round 1 context test confirmed a ready original first leg could be
booked. The pre-run gates passed, including locked `uv`, Ruff, mypy, Ty,
coverage, integration, smoke, deterministic packaging, and restricted-history
checks.

## Fixed run and fallback

- scenario: `create_with_disruption`
- seed: `2026`; `PYTHONHASHSEED=0`
- warm-up: `140` days; measured horizon: `360` days
- ATT interval: `5` days; required periods: `72`
- candidate command: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`
- pinned fallback loss: `20.436668751255972`
- pinned fallback ATT SHA-256:
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43`
- strict acceptance: `candidate_loss < 20.436668751255972 - 1e-9`

The candidate completed normally. The raw log contains Day 360/360, Period
72 (Days 356–360), `Simulation completed`, and the output marker. The fresh
ATT and raw log were copied before any score, sync, or restoration:

```text
.challenge/round1/results/immediate_direct_next_leg_v1_20260807/
├── ATT_By_Statistics_Interval.csv
├── full_run.log
└── score.json
```

Evidence hashes and metrics:

- candidate ATT SHA-256: `94517c392960d77a306ecbaeb9e0875434c9b1f7061ac2e6a9343af5f2c6d79a`
- candidate ATT size: `1262` bytes
- raw log SHA-256: `51b3a174951d41dadd3e011724e5010bddfc02f469eaca30fd698e8fcaf3efba`
- candidate mean ATT: `20.679583333333333` days
- fallback mean ATT: `20.450972222222223` days
- periods better/equal/worse than fallback: `13 / 14 / 45`
- candidate cumulative resilience loss: `24.13140853958694`
- fallback cumulative resilience loss: `20.436668751255972`
- delta: `+3.694739788330967` (`+18.078972817445592%`)

The strict improvement gate was not met. The candidate is **REJECTED — worse
than fallback**. The candidate improved 13 individual periods, but its 45
worse periods outweighed them. Mean ATT is descriptive only; the decision uses
the complete scorer loss.

## Restoration and evidence

The candidate implementation and tests are reverted in the isolated branch.
The exact pre-run private `response_strategies` snapshot is restored, the
pinned fallback ATT is copied back from the verified ignored fallback snapshot,
and the output is rescored to the exact fallback loss before the final gates.
No second candidate, tuning, archive submission, organizer-material
publication, or history rewrite is allowed in this experiment.

The machine-readable aggregate remains ignored at
`experiments/results/round1_immediate_direct_next_leg_v1_20260807.json`.
