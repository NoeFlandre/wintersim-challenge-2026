# Round 1 pending-alternative berth activation v26

## Status

`PRE-RUN REVIEW` — participant implementation and the one-run decision are not
yet complete. No full simulation has been launched for v26.

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
