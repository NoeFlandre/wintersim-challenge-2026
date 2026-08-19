# Round 1 pending-alternative berth activation v26

## Status

`REJECTED — EQUALITY; V3 RESTORATION IN PROGRESS`.

The one authorized full simulation completed and its evidence was preserved.
The candidate was not retained because the official score tied the accepted v3
control exactly.

The frozen implementation is committed on `main` as `0ca40d9`
(`feat: activate pending alternative vessels at berth`), with the test-module
correction in `1c81e96` (`test: avoid duplicate v26 test module names`). The
candidate participant SHA-256 is
`b04640e6ff3b42af0a7ed2e61b88042b7650cb5b20d9386d9f3c5c3aa21b5bb9`; the
synchronized Round 1 runtime is byte-identical. The design/RED contract is
committed as `f747dde`.

## Hypothesis

The organizer fallback can reserve an empty vessel for a disruption-avoiding
alternative route, while its normal berth score selects another waiting vessel.
Selecting the first already-reserved empty vessel when its pending route starts
at the requested berth port could activate that existing alternative sooner.
This changes only `select_vessel_for_berth`; the accepted v3 booking-hold logic
and the other three hooks remain unchanged.

## Control and fixed acceptance

The current accepted v3 control is the clean `main` checkout at
`6bc0208a1ddcc172d862b7ae24f37dfd6f88d8a7`. The participant strategy SHA-256 is
`f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`. Its pinned
ATT snapshot is
`.challenge/round1/results/multi_transfer_recovery_hold_v3_20260810/ATT_By_Statistics_Interval.csv`
with SHA-256
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`, 72
periods, and cumulative resilience loss `19.084638612143134`. The authoritative
Round 1 baseline ATT SHA-256 is
`2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`.

The only acceptance expression is:

```text
candidate_loss < 19.084638612143134 - 1e-9
```

The run contract is Round 1 `create_with_disruption`, seed 2026, warm-up 140
days, measured horizon 360 days, five-day ATT intervals, and exactly 72
numbered periods. The candidate evidence directory is
`.challenge/round1/results/pending_alternative_activation_v26_20260819/` and
the ignored aggregate is
`experiments/results/round1_pending_alternative_activation_v26_20260819.json`.

## Activation audit

The private pre-code audit used all 50 helper-derived structural timestamps and
fresh real organizer contexts. It observed 28 pending-route cases, 28
candidate-only selector activations, and 28 candidate-versus-fallback selection
differences, with no context or Output mutation. The queue and waiting ages
were an explicit deterministic structural setup rather than event-history
replay; activation is not causal score evidence. The audit JSON and script are
ignored private evidence and will not enter the package or Git history.

The actual candidate hook was rerun through the same audit after implementation
and reproduced those 28 activations and 28 fallback-selection differences. The
audit recorded the same pinned control ATT hash and no Output write. The two
deterministic validation packages contain only the two participant files and
both have SHA-256
`439938a567579d0b2be02b92e6288b479054e606708a1700d506d6085540b9b4`.

## Full-run result

The frozen command ran exactly once with exit code `0`. The raw log contains
Period 72 (Days 356–360), Output Simulation Day 360, `Simulation completed.`,
and `CSV output written`. The simulator runtime was `00:56:38`.

- candidate cumulative resilience loss: `19.084638612143134`;
- pinned v3 control loss: `19.084638612143134`;
- delta: `0.0` (`0.0%`);
- candidate ATT: 72 numbered periods, mean `20.3675` days;
- candidate ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- pinned v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- periods better/equal/worse than v3: `0 / 72 / 0`;
- raw log SHA-256:
  `ec64dfcef160c781418f34298167b74404fd485f56f9e4b1d1c047de33e0bf33`.

The strict expression `candidate_loss < 19.084638612143134 - 1e-9` is false,
so the decision is **REJECTED — EQUALITY**. The audit proved the hook is
structurally live, but this run produced no measurable trajectory difference.
The raw ATT, log, scorer JSON, comparison JSON, aggregate, launch manifest,
and activation audit remain in the ignored evidence directory; they are not
submission or public artifacts.

## Invariants and run rules

The participant must be standard-library-only, deterministic, read-only, and
fail closed. It may return only an original waiting vessel or `None`; it may
not construct routes, mutate state, inspect files/environment, or use
scenario-specific identities. The package must contain only participant-owned
`response_strategies` files. All mandatory gates must pass before launch.

Exactly one full candidate run is permitted. Fresh ATT and raw log bytes must
be preserved before scoring. Equality, worsening, invalid/incomplete output,
or failed final verification rejects v26. On rejection, the result is
committed, v26 implementation/tests are reverted, the pinned v3 adapter and
ATT are restored by provenance-preserving commands, and final gates are rerun.
No tuning, second candidate, push, merge, PR, upload, submission, or history
rewrite is part of this experiment.

## Restoration record

The rejection report is committed before restoration. The next steps are to
revert the v26 implementation and candidate-only tests in reverse order,
synchronize the restored participant adapter, restore the pinned v3 ATT
snapshot, re-score it exactly, and rerun all final gates. The v26 design,
activation audit, aggregate, and this result record remain as the audit trail.
