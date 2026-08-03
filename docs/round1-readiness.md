# Round 1 readiness

**Status:** bootstrapped and smoke-tested; no Round 1 strategy experiment has
run yet.

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
  synchronized byte-for-byte into the Round 1 source.
- The one-day Round 1 smoke run completed with `SMOKE_OK`.
- Two validation packages were byte-identical. Each contained only
  `response_strategies/README.md` and `response_strategies/user_strategy.py`.
- The active strategy is still the no-op adapter: all four hooks return `None`
  and delegate to the organizer fallback.
- No Round 1 full run, optimization, candidate, or submission has been made.

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
