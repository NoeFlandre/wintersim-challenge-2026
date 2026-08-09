# Round 1 readiness

**Status:** bootstrapped and smoke-tested; ten controlled Round 1 experiments
have valid scores and one earlier attempt was incomplete. The recovery-aware
direct-service hold policy is accepted and remains active.

## Private organizer archive

The Round 1 archive received from the organizers on 2026-08-03 is kept only in
the ignored local workspace:

```text
.challenge/downloads/SimulationChallenge2026_Py_Round1.zip
.challenge/round1/source/
```

Its SHA-256 is:

```text
15a9f792fb0bac548b2f4af3d1f835c86b303f904899e8a3d39e03597820a2bb
```

The archive and extracted source are organizer material. They must never be
tracked, copied into the public repository, or included in a submission.

## Verified local state

- The archive passed strict checksum and marker validation.
- The Round 1 source contains the expected `main.py`, `response_strategies`,
  `simulation_model`, `scenario_builders`, `Input`, `Output`, and `o2despy`
  components.
- The participant `response_strategies/user_strategy.py` and `README.md` are
  synchronized byte-for-byte into the Round 1 source; the accepted candidate is
  active.
- The one-day Round 1 smoke run completed with `SMOKE_OK`.
- Final validation packages were byte-identical. Each contained only
  `response_strategies/README.md` and `response_strategies/user_strategy.py`.
- The active strategy delegates three hooks. Its initial-booking hook may return
  `False` to hold new cargo only when a disrupted one-booking direct service is
  estimated to recover and deliver sooner than a safe multi-service transfer.
- The accepted candidate ATT SHA-256 is
  `d381b087f8d67124a8078b5afc795f5b59b08db90148614b43dcfdf351e7ac48` and its
  cumulative loss is `19.828803374740612` over 72 periods. This is
  `2.9743858155845607%` lower than the pinned fallback.
- The pinned fallback ATT SHA-256 is
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43` and its
  rescored cumulative loss is `20.436668751255972` over 72 periods.
- The latest controlled experiment, documented in
  [`docs/experiments/round1-recovery-aware-direct-service-hold-v2.md`](experiments/round1-recovery-aware-direct-service-hold-v2.md),
  executed exactly once and completed all 72 periods. It scored
  `19.828803374740612`; 28 period ATT values improved, 19 were equal, and 25
  worsened relative to fallback. The strict aggregate gate accepted it, so the
  candidate source/tests remain and no restoration was performed. Raw ATT,
  scorer JSON, and the full log remain in ignored private evidence.
- An earlier controlled experiment, documented in
  [`docs/experiments/round1-teu-delay-smith-priority-v2.md`](experiments/round1-teu-delay-smith-priority-v2.md),
  executed exactly once. Its TEU-delay Smith-priority berth policy produced a
  byte-identical ATT and the fallback loss `20.436668751255972`, so it was
  rejected by the strict improvement rule. Candidate ATT, log, score JSON,
  and package remain in the ignored evidence directory; the active fallback
  is restored.
- An earlier controlled experiment, documented in
  [`docs/experiments/round1-pending-alt-activation-v1.md`](experiments/round1-pending-alt-activation-v1.md),
  ran exactly once, produced the same ATT SHA and score as the fallback
  (`20.436668751255972`), and was rejected by strict equality. Its candidate
  ATT and log remain in the ignored evidence directory; the active fallback is
  restored.
- The preceding controlled experiment, documented in
  [`docs/experiments/round1-disruption-weighted-booking-v1.md`](experiments/round1-disruption-weighted-booking-v1.md),
  ran exactly once, scored `27.025393118568292` against the fallback
  `20.436668751255972`, and was rejected. Its candidate ATT and log remain in
  the ignored evidence directory; the active fallback is restored.
- An earlier controlled experiment, documented in
  [`docs/experiments/round1-phase-aware-valid-route-booking-v1.md`](experiments/round1-phase-aware-valid-route-booking-v1.md),
  ran exactly once with the fixed Round 1 configuration and completed all 72
  periods. Its phase-aware initial booking policy scored
  `24.21744876585007`, which was `18.499981873815628%` worse than the pinned
  fallback, so it was rejected. Its fresh ATT and log remain in the ignored
  evidence directory; the no-op fallback was restored and rescored at
  `20.436668751255972`.
- An earlier controlled experiment, documented in
  [`docs/experiments/round1-immediate-direct-next-leg-v1.md`](experiments/round1-immediate-direct-next-leg-v1.md),
  ran exactly once with the fixed Round 1 configuration and completed all 72
  periods. Its conservative immediate direct-next-leg booking policy scored
  `24.13140853958694`, which was `18.078972817445592%` worse than the pinned
  fallback, so it was rejected. Its fresh ATT and log remain in the ignored
  evidence directory; the no-op fallback was restored and rescored at
  `20.436668751255972`.
- An earlier controlled experiment, documented in
  [`docs/experiments/round1-no-safe-congestion-direct-v2.md`](experiments/round1-no-safe-congestion-direct-v2.md),
  ran exactly once with the fixed Round 1 configuration and completed all 72
  periods. Its no-safe-path congestion-tail direct-booking policy scored
  `25.80681018404835`, which was `26.27699014039333%` worse than the pinned
  fallback, so it was rejected. Its fresh ATT SHA is
  `6134e12aec44c54a282bc39bb6291a24626cf458c3b88a8020c883e554da2a20`; the
  no-op fallback was restored and rescored at `20.436668751255972`.
- An earlier controlled experiment, documented in
  [`docs/experiments/round1-dominance-carried-teu-berth-v1.md`](experiments/round1-dominance-carried-teu-berth-v1.md),
  ran exactly once with the fixed Round 1 configuration and completed all 72
  periods. Its fallback-gated carried-TEU berth-priority policy produced an
  ATT byte-identical to the pinned fallback and the same loss
  `20.436668751255972`, so it was rejected by strict equality. Its candidate
  ATT, raw log, and scorer JSON remain in the ignored results directory; the
  no-op fallback was restored, synchronized, and rescored.

## Round 1 commands

Run these from the repository root:

```bash
uv run wsc2026 bootstrap --round round1 \
  --archive .challenge/downloads/SimulationChallenge2026_Py_Round1.zip
uv run wsc2026 sync --round round1
uv run wsc2026 smoke --round round1
uv run wsc2026 package --team YourTeam --round 1
```

The full simulation is intentionally not part of readiness setup. It must be
authorized by a separate experiment contract with one hypothesis, pinned
acceptance criteria, and a review gate before execution.

## Official boundary

Round 1 opened on 2026-08-01 and closes on 2026-08-23. Only files under the
submission archive's `response_strategies/` directory are evaluated. Confirm
the final archive filename order with the organizers before sending it; the
public website and technical PDF use different orders. Send a new email rather
than replying to the announcement, as requested by the organizers.
