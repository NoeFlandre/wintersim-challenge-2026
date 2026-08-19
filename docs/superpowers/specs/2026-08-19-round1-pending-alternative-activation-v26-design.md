# Round 1 pending-alternative berth activation v26

## Decision

Test exactly one additive change to the accepted Round 1 v3 policy: override
only `UserStrategy.select_vessel_for_berth`. During an active disruption, the
hook selects the first waiting vessel, in the supplied queue order, that is
empty and already has a pending alternative route whose first segment departs
from the requested berth port. The pending route must belong to the same
active disruption key. Every other case delegates with `None`.

The accepted v3 initial-booking hold is left byte-for-byte unchanged. The other
three hooks remain delegates. The hypothesis is that the organizer already
reserves an empty vessel for a disruption alternative, but its berth score can
select another vessel. Activating that existing reservation at its actual
alternative departure port may reduce delay without constructing routes,
rewriting bookings, or changing cargo policy.

This is deliberately a new v3-complement experiment. The historical v1
pending-alternative experiment was run against the old no-op control and tied
that control; it does not establish the result of this exact interaction with
v3.

## Pre-code evidence

The private read-only audit used all 50 helper-derived structural timestamps.
For each fresh real `create_with_disruption()` context it let the organizer
fallback create pending alternatives, then evaluated every real pending route.
The explicit queue setup contained context-order vessels arriving at the
candidate port and appended the pending vessel when it was not already in that
queue. Waiting ages were deterministic from queue position, with earlier queue
members older. It observed 28 pending-route cases:

- v3 control activations: 0 (`select_vessel_for_berth` delegates);
- candidate predicate activations: 28;
- candidate-only activations: 28;
- candidate versus organizer-selector differences: 28;
- context and Output mutation: none.

This is a structural activation audit, not an event-history replay or a score
prediction. Its queue construction and waiting ages are explicit limitations.
The private evidence is
`.challenge/round1/results/pending_alternative_activation_v26_20260819/` and
is ignored, not tracked or packaged.

## Exact participant policy

1. Require a valid active disruption using the existing v3 fail-closed state
   parser and use its canonical `(closed ports, congested leg keys)` key.
2. Iterate `waiting_vessels` once in the supplied order.
3. A vessel qualifies only if `carried_shipments` is a list/tuple and empty;
   `pending_assigned_service_route` exists; its `source_service_route` is not
   `None`; its `disruption_key` equals the active key; its segments are a
   non-empty list/tuple with unique non-negative integer sequence indexes; and
   the first segment's departure port is the supplied `port` by identity.
4. Return that original vessel object. Return `None` for inactive, malformed,
   empty, mismatched, or uncertain data.

The policy never mutates context, vessels, routes, queues, bookings, or files;
it uses no organizer imports, constants, names, dates, seeds, I/O, environment,
randomness, wall-clock time, or mutable module-level state. It uses only the
standard library and preserves v3's other three hook results and signatures.

## Strongest failure mode

The selected vessel may not be at a real congestion decision point often
enough to matter, or activating an already-reserved alternative may disturb
the fallback's better berth ordering. The full score, not the audit count or
mean ATT, decides the experiment.

## Fixed run contract

- repository layout: canonical checkout and `main` branch only;
- starting HEAD: `6bc0208a1ddcc172d862b7ae24f37dfd6f88d8a7`;
- starting participant SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- round/scenario: `round1` / `create_with_disruption`;
- seed: `2026`; `PYTHONHASHSEED=0`;
- warm-up: 140 days; measured horizon: 360 days;
- ATT interval: 5 days; required numbered periods: 72;
- accepted v3 control loss: `19.084638612143134`;
- accepted v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative Round 1 baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`;
- candidate evidence: `.challenge/round1/results/pending_alternative_activation_v26_20260819/`;
- aggregate evidence: `experiments/results/round1_pending_alternative_activation_v26_20260819.json`.

The only full-run command is:

```bash
PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full
```

One candidate run is allowed. Equality, worsening, invalid output, incomplete
completion, or any failed gate is rejection. No tuning, duplicate run, push,
merge, PR, upload, submission, or history rewrite is authorized by this
experiment.

## Restoration

Before launch, freeze an ignored manifest with exact HEAD, participant/runtime
bytes, package members and hashes, control/baseline hashes, stale Output
metadata, gates, and no-live-process proof. Preserve fresh candidate ATT and
the raw log before scoring or any command that can overwrite Output.

On rejection, commit the result report first, revert only the v26 implementation
and candidate-test commits in reverse order, synchronize the restored v3
adapter, restore the pinned v3 ATT snapshot, re-score exactly, and rerun every
final gate. Never recreate v3 manually. On acceptance, retain v26 and run the
same final gates without a second candidate.
