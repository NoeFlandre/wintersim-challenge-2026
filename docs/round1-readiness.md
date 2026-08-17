# Round 1 readiness

**Status:** bootstrapped and smoke-tested; seventeen controlled Round 1
experiments have valid scores and one earlier attempt was incomplete. The
multi-transfer recovery-hold v3 policy is accepted and remains active.

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
  estimated to recover and deliver sooner than a safe detour requiring at least
  three service boardings. Simpler safe detours delegate to the organizer.
- The accepted candidate ATT SHA-256 is
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a` and its
  cumulative loss is `19.084638612143134` over 72 periods. This is
  `6.615707068353528%` lower than the pinned fallback and
  `3.7529484181856874%` lower than the preceding accepted v2 result.
- The pinned fallback ATT SHA-256 is
  `c2eead01e219b377babecc542b082d9de23563837d7b00ee081f14a580560c43` and its
  rescored cumulative loss is `20.436668751255972` over 72 periods.
- The latest controlled experiment, documented in
  [`docs/experiments/round1-multi-transfer-recovery-hold-v3.md`](experiments/round1-multi-transfer-recovery-hold-v3.md),
  executed exactly once and completed all 72 periods. It scored
  `19.084638612143134`; 24 period ATT values improved, 23 were equal, and 25
  worsened relative to accepted v2. The strict aggregate gate accepted it, so
  the candidate source/tests remain and no restoration was performed. Raw ATT,
  aggregate JSON, and the full log remain in ignored private evidence.
- The subsequent controlled experiment, documented in
  [`docs/experiments/round1-contiguous-same-service-normalization-v5.md`](experiments/round1-contiguous-same-service-normalization-v5.md),
  also ran exactly once and completed all 72 periods. Its contiguous
  same-service extension scored `22.392546553745177`, which was
  `17.33282986819197%` worse than the active v3 control, so it was rejected.
  Its fresh ATT, raw log, activation audit, and aggregate score remain in the
  ignored evidence directory; v3 was restored and rescored exactly.
- The latest controlled experiment, documented in
  [`docs/experiments/round1-multi-leg-congestion-hold-v6.md`](experiments/round1-multi-leg-congestion-hold-v6.md),
  also ran exactly once and completed all 72 periods. Its narrow pure-leg,
  multi-leg one-transfer extension scored `20.810481217905384`, which was
  `9.043098173544317%` worse than the active v3 control, so it was rejected.
  Its fresh ATT, raw log, score JSON, and activation audit remain in the
  ignored evidence directory; v3 was restored, synchronized, and rescored
  exactly at `19.084638612143134`.
- The subsequent controlled experiment, documented in
  [`docs/experiments/round1-transfer-berthing-overhead-v7.md`](experiments/round1-transfer-berthing-overhead-v7.md),
  executed exactly once and completed all 72 periods. Its transfer-berthing
  overhead extension scored `21.428353158559474`, which was `12.2806%` worse
  than the active v3 control and `4.8525%` worse than the pinned fallback. It
  was rejected by the strict aggregate gate; its candidate ATT, scorer JSON,
  and full log remain in the ignored evidence directory. The v3 strategy and
  ATT snapshot were restored, synchronized, and re-scored exactly at
  `19.084638612143134`.
- The subsequent controlled experiment, documented in
  [`docs/experiments/round1-pure-congestion-transfer-hold-v8.md`](experiments/round1-pure-congestion-transfer-hold-v8.md),
  executed exactly once and completed all 72 periods. Its narrow pure-leg,
  one-physical-leg, one-transfer extension scored
  `20.229520673897987`, which was `5.998971659994597%` worse than the active v3
  control. It was rejected by the strict aggregate gate; its candidate ATT and
  raw log remain in the ignored evidence directory. The v3 participant and
  pinned ATT were restored byte-for-byte, synchronized, and re-scored at
  `19.084638612143134`; final quality and safety gates passed.
- The subsequent controlled experiment, documented in
  [`docs/experiments/round1-pure-congestion-exclusion-v9.md`](experiments/round1-pure-congestion-exclusion-v9.md),
  executed exactly once and reached all 72 periods. Its subtraction of pure
  leg-congestion recovery holds scored `22.38757990186231`, which was
  `17.306805524824487%` worse than the active v3 control. It was rejected by
  the strict aggregate gate; its candidate ATT SHA is
  `b318b8e3ce2ff37e8d8f6c05834440b9af41539b5f2e43d9e366accee9048acd`, and its
  ATT, log, launch manifest, activation audit, and scorer JSON remain in the
  ignored evidence directories. The v3 participant and pinned ATT were
  restored byte-for-byte, synchronized, and re-scored at
  `19.084638612143134`.
- The subsequent controlled experiment, documented in
  [`docs/experiments/round1-port-closure-exclusion-v10.md`](experiments/round1-port-closure-exclusion-v10.md),
  executed exactly once and completed all 72 periods. Its port-involved
  recovery-hold exclusion scored `22.096980694905298`, which was
  `15.784119070745595%` worse than the active v3 control, so it was rejected.
  Its fresh ATT SHA is
  `6bba0842962a35ce457e2949658d49d0cd25055c950b15be63f7041919fb7085`; the
  candidate ATT and log remain in the ignored v10 evidence directory. The v3
  participant and pinned ATT were restored byte-for-byte, synchronized, and
  re-scored at `19.084638612143134`.
- The preceding accepted experiment, documented in
  [`docs/experiments/round1-recovery-aware-direct-service-hold-v2.md`](experiments/round1-recovery-aware-direct-service-hold-v2.md),
  scored `19.828803374740612`, which was `2.9743858155845607%` below fallback.
  Version 3 retains that policy only for fragmented safe detours and improves
  its aggregate result by `3.7529484181856874%`.
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
