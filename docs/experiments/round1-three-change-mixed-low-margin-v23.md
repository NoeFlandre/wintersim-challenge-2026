# Round 1 three-change mixed low-margin delegation v23

**Status: REJECTED — full run complete; v3 control restoration pending.**

V23 tests one narrow subtraction from the accepted Round 1 v3 recovery-hold
control. The exact policy, alternatives, tests, one-run protocol, and restore
steps are in the [design](../superpowers/specs/2026-08-19-round1-three-change-mixed-low-margin-v23-design.md)
and [plan](../superpowers/plans/2026-08-19-round1-three-change-mixed-low-margin-v23.md).

## Frozen control and acceptance

- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / interval: `140` / `360` / `5` days;
- required ATT periods: `72`;
- control strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control loss: `19.084638612143134`;
- strict acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Candidate evidence is private/ignored under
`.challenge/round1/results/three_change_mixed_low_margin_v23_20260819/`, with
aggregate `experiments/results/round1_three_change_mixed_low_margin_v23_20260819.json`.
No push, submission, archive publication, tuning, duplicate, or second
candidate belongs to this experiment.

## Audit gate

Before RED or candidate execution, the fresh identity-free audit must evaluate
50 valid disruption midpoints and all 19,000 demand observations on disposable
contexts. It must compare v3 and v23 on the same observations, preserve
context order, and prove no mutation, model advancement, or Output write. It
must reproduce 48 v3 holds and record every control-only v23 delegation,
including full-precision timing margin and first-route headway. A no-op or
malformed-only candidate is a no-go and consumes no full run.

## Fresh audit result

The identity-free audit completed before any candidate code was changed. It
used 50 valid disruption midpoints and all 19,000 demand observations, with a
fresh disposable context per timestamp and no model advancement or Output
write. It reproduced 48 v3 holds and found four v23 control-only delegations;
the v23 predicate retains 44 holds. Every suppressed observation is the same
structural shape (mixed leg+port, three safe route changes, four nominal
physical legs, annual demand proxy 39), with timing margins of
`2.726818181818146`, `26.726818181818146`, `50.726818181818146`, and
`74.72681818181815` hours against a first safe-route headway of
`75.175` hours. The control-only annual-TEU exposure proxy is `156`.

This is reachability evidence, not a score prediction. The audit observed
`no_mutation: true`, `model_advanced: false`, `output_written: false`, and
unchanged control ATT metadata. Its private JSON is
`.challenge/round1/results/three_change_mixed_low_margin_v23_20260819/activation_audit.json`
with SHA-256
`6f72ed9e2d8d13349419d52aff2a9483f5be6f94f01c951a6b3015842d779a07`.

The audit was a GO for RED→GREEN implementation and preflight. Those gates and
the fresh control identity check passed before the run.

## RED→GREEN implementation review

The implementation remains limited to the participant-owned
`assign_associated_bookings` hook. It first evaluates the unchanged v3 hold
predicate; only after v3 qualifies does it derive matching constraint kinds,
safe-path route-change count, and the live first-safe-route headway. It returns
`None` only for the strict mixed leg-plus-port / exactly-three-change /
margin-below-headway case, and returns the original v3 `False` for every
retained hold. All other hooks remain unconditional `None` delegates. The
code is read-only, deterministic, standard-library-only, fail-closed, and has
no mutable module state or organizer imports.

- RED contract: commit `1dcd9fb`; the new low-margin case failed against the
  untouched v3 control while the retained and malformed cases passed;
- GREEN implementation and participant documentation: commit `67c4eda`;
- focused unit/v3 contract: `45 passed`;
- real ignored-context integration sweep: `1 passed` over the derived
  Round 1 midpoint/demand observations, with mutation snapshots unchanged;
- participant strategy SHA-256 after implementation:
  `bdead22d1ff31fbb11b1dabc6a49d93508370710a434c752074ceb65d01a809c`;
- participant README SHA-256:
  `901b43183886b41681758d38065b496f7ef082af17c58ab2be27baa3f799080f`.

The complete locked preflight and non-overwriting manifest check passed before
the one authorized full run.

## Full-run result

The pre-run manifest matched immediately before launch. Exactly one fixed full
simulation ran with the manifest-pinned command and exited `0`. Its log proves
Period 72 (Days 356–360), simulation day 360, `Simulation completed`, and a
fresh CSV write. The raw log and ATT were preserved before scoring at:

- `.challenge/round1/results/three_change_mixed_low_margin_v23_20260819/full_run.log`
  (SHA-256 `e09eb240ad43e9320eb41062b7e9995cf12d5e6ff049be97e0ee78f1e670def0`);
- `.challenge/round1/results/three_change_mixed_low_margin_v23_20260819/ATT_By_Statistics_Interval.csv`
  (SHA-256 `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`).

The candidate scorer returned `19.084638612143134` over exactly 72 periods,
identical to the pinned v3 control. The strict acceptance rule requires a
value below `19.084638612143134 - 1e-9`; equality is therefore **REJECTED**.
The candidate ATT is byte-identical to control, so the experiment produced no
measurable improvement. The immutable aggregate is
`experiments/results/round1_three_change_mixed_low_margin_v23_20260819.json`.

The candidate implementation and tests must now be reverted in reverse order,
Round 1 synchronized back to the accepted v3 participant, the pinned v3 ATT
restored byte-for-byte, and the final gates rerun. No tuning, duplicate run,
or second candidate is permitted.
