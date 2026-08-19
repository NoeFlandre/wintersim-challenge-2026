# Round 1 multi-TEU missed-connection buffer v20

**Status: REJECTED — one full run completed; result preserved; v3 restoration
is pending.**

The accepted v3 policy remains the control at cumulative resilience loss
`19.084638612143134` over 72 periods and ATT SHA-256
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.

V20 preserves every v3 hold. It adds one bounded capacity-risk allowance only
for integer multi-TEU shipments on the same direct-versus-multi-transfer
topology: if the direct recovery estimate is not already faster, it may still
hold when it is faster than the detour plus one shortest safe-route headway.
The live headway represents one possible missed connection from insufficient
remaining vessel capacity. Exact equality and uncertainty delegate.

The complete frozen rationale, rejected alternatives, policy, audit contract,
run identity, strict acceptance expression, and restoration procedure are in
[`the design`](../superpowers/specs/2026-08-19-round1-multi-teu-missed-connection-buffer-v20-design.md)
and [`the implementation plan`](../superpowers/plans/2026-08-19-round1-multi-teu-missed-connection-buffer-v20.md).

## RED→GREEN record

- design: `b621248`;
- RED contract: `e79479a`;
- GREEN implementation: `2534b7f`;
- RED focused result against v3: exactly 2 intended failures and 53 passes;
- GREEN focused result: 55 passes;
- candidate participant SHA-256:
  `0ae8fe79212040a9a7384755cfd633783a77620d00b871808c851cfdc1f29134`.

The implementation adds one pure minimum-headway helper and one final strict
multi-TEU branch after the unchanged v3 comparison. It creates no bookings and
mutates no supplied state.

## Formal activation audit

The non-overwriting ignored audit sampled 50 derived timestamps and 19,000
demand-time observations with fresh organizer contexts. It reported:

- 48 one-TEU v3 control holds;
- 59 two-TEU v20 holds;
- 11 candidate-only decisions and zero control-only decisions;
- repeated annual-TEU exposure proxy `10,053`;
- `no_mutation: true`, unchanged Output, and no model advancement.

The audit JSON and private path/demand details remain ignored under
`.challenge/round1/results/multi_teu_missed_connection_buffer_v20_20260819/`.
These counts prove reachability only; the complete 72-period score decides.

## Pre-run verification

No full candidate simulation has started. Fresh gates passed from the committed
candidate:

- `uv lock --check` and locked all-group sync: passed (29 packages resolved);
- Ruff format and lint: passed (21 files);
- `ty` and mypy: passed;
- non-integration tests: 241 passed, 9 deselected, true branch coverage
  `90.50%` (minimum `90%`);
- integration tests: 9 passed; complete suite: 250 passed;
- Round 1 sync and participant/runtime byte comparisons: passed;
- one-day smoke: `SMOKE_OK`, with the active ATT bytes unchanged;
- two participant-only packages: byte-identical SHA-256
  `c3b96018bca7b8f52569eb39ddc76e20e371f08fedbc970b5a8d7d127131cff9`,
  6,272 bytes, containing only `README.md` and `user_strategy.py`;
- participant/runtime strategy SHA-256:
  `0ae8fe79212040a9a7384755cfd633783a77620d00b871808c851cfdc1f29134`;
- participant/runtime README SHA-256:
  `7c24bf691ec8223c48b244db63a3a91439fc6160b893e34679381f93a555f2bc`;
- pinned and active v3 control ATT: byte-identical SHA-256
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`,
  1,262 bytes, freshly re-scored to `19.084638612143134` over 72 periods;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- diff/restricted-material checks, one-worktree/one-branch layout, clean tracked
  state, and no-live-simulator check: passed.

The next step is to commit this pre-run record, write a non-overwriting ignored
manifest pinned to that final documentation HEAD, revalidate every pinned
identity, and run only the frozen command once. No tuning or second candidate
is authorized.

## Full-run result

The non-overwriting pre-run manifest had SHA-256
`3b3764ba055028b2ac367e8f201d462b9e6c49e99c2cd2f81cabf4f45ff19ed6`
and pinned launch HEAD `2b13a35398efb1f57f03cadaaa7745a284f6256d`.
Every pinned identity, the stale Output metadata, clean Git state, and the
no-live-process gate were revalidated immediately before launch.

Exactly one full candidate run started at `2026-08-19T12:15:57Z`. It exited
`0`; the log contains Day 360/360, Period 72 (Days 356-360), Output Simulation
Day 360, `Simulation completed.`, and the fresh CSV marker. The organizer's
final reported runtime was `00:23:54`.

The fresh ATT and raw log were copied to the predeclared ignored evidence
directory before scoring or any sync, smoke, package, or restoration action:

- candidate ATT SHA-256:
  `b3bdf7b59e477b1adfcb732e2a09f03d9c80ccb7bb83dc6acdedb88273ac3128`;
- raw-log SHA-256:
  `b747e03db841654245c7dc69e4ec3df71ebe9840179257c1d25ae0ecd740075a`;
- numbered periods: 72; candidate mean ATT: `20.68861111111111` days;
- candidate cumulative resilience loss: `24.207356508382723`;
- accepted v3 control loss: `19.084638612143134`;
- delta: `+5.122717896239589` (`+26.842100604305475%`, worse);
- candidate periods better/equal/worse than v3: `15 / 20 / 37`.

The immutable acceptance expression is
`candidate_loss < 19.084638612143134 - 1e-9`; it is false. **Decision:
REJECTED.** The result shows that the added capacity-risk holds delayed enough
multi-TEU cargo to outweigh their 15 improved periods. This conclusion applies
to the exact frozen policy and fixed scenario/seed; the activation audit alone
did not predict it.

No tuning, duplicate run, second candidate, score threshold change, push,
submission, or history rewrite occurred. The next required step is the frozen
rejection restoration: commit this result, revert candidate implementation and
tests in reverse order, restore/sync v3 and its pinned ATT, re-score exactly,
then rerun every final gate without another simulation.
