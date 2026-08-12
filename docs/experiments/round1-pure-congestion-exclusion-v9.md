# Round 1 pure-congestion exclusion v9

**Status: REJECTED — complete run finished and control restored.**

This report records the v9 hypothesis, fresh activation audit, fixed control,
strict acceptance gate, evidence paths, and restoration procedure. The
participant boundary remains only `submission/response_strategies/`; ignored
organizer source, inputs, outputs, and candidate evidence must never enter Git
history or a submission package.

## Hypothesis

The accepted v3 hold protects direct cargo when the safe detour needs at least
two service-route changes. Two later pure-congestion additions (v6 and v8)
made the full result worse, suggesting that a slowed but open direct service is
not a reliable reason to hold cargo at origin. v9 tests the smallest related
subtraction: delegate pure-leg v3 holds, while retaining v3 holds whenever a
closed berth also intersects the nominal direct edge.

Strongest failure mode: the pure-leg subset may contain the highest-value
fragmented detours, so delegating it could discard most of v3's benefit. The
full scorer, not the activation audit or mean ATT, decides.

## Fresh activation audit

The read-only audit used the midpoint of every integer day inside every valid
disruption window, a fresh `create_with_disruption` context per timestamp, the
organizer fallback route-preparation helper only as setup, and every demand in
context order. It examined 50 timestamps and 19,000 observations without
advancing a model, writing Output, or mutating a retained context.

The current v3 predicate held in 48 observations. The frozen v9 candidate
delegates exactly the 22 observations whose nominal edge constraints are all
`leg` constraints, with an annual-TEU exposure proxy of 55,272. The remaining
26 v3 activations include a `port` constraint and retain v3 behavior. Complete
observed state was unchanged. Activation and exposure are structural evidence,
not score predictions; the anonymous audit record will remain ignored at
`.challenge/round1/results/pure_congestion_exclusion_v9_20260812/activation_audit.json`.

## TDD and implementation review

The RED contract was committed as `2d11a58`. Against untouched v3, the focused
unit/real-context selection failed exactly five intended pure-leg assertions
and passed 37 independent checks. The failures were all the missing v9
delegation (`False` from v3 where v9 requires `None`), including one real
derived pure-leg activation; there were no fixture, collection, import, or
mutation errors.

The minimum implementation was committed as `45bc7e3`. It adds one
constraint-kind helper and one fail-closed gate; it does not alter path
construction, timing, route state, any other hook, or package dependencies.
Focused GREEN then passed `42` unit and real-context tests. Ruff format/check,
Ty, and mypy passed on the changed surface. The candidate participant SHA-256
is `d6e24a09904197959f225ca01a9b4964b36cce1697ee177522eb97ba190357b0`.

## Candidate contract

Only `assign_associated_bookings` changes. The candidate must be RED before
implementation and GREEN afterward with synthetic and real-context tests for:

- pure-leg multi-transfer delegation (the candidate-only behavior);
- mixed leg/closed-port hold retention;
- closed-port hold retention;
- inactive/end-boundary/equality and deterministic context-order ties;
- malformed, non-finite, incomplete, and unsupported state delegation;
- complete before/after state equality on every read-only path;
- exact public signatures, forbidden capabilities, and all retained v3 cases.

## Fixed control and run

- control: accepted v3; participant/runtime SHA-256
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- control ATT snapshot SHA-256
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- control score `19.084638612143134`, baseline SHA-256
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- `round1`, `create_with_disruption`, seed `2026`, `PYTHONHASHSEED=0`;
- warm-up `140`, measured horizon `360`, interval `5`, periods `72`;
- exact run: `PYTHONHASHSEED=0 uv run wsc2026 run --round round1 --full`;
- candidate ATT/log/manifest paths under
  `.challenge/round1/results/pure_congestion_exclusion_v9_20260812/`;
- aggregate path
  `experiments/results/round1_pure_congestion_exclusion_v9_20260812.json`;
- acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

The current canonical layout is one checkout, one `main` branch, and one
worktree. No full run is authorized until the tracked report records the
complete preflight and the ignored non-overwriting manifest pins the launch
HEAD, strategy/runtime hashes, package members, control/baseline identities,
stale Output metadata, exact command, and no-live-process proof.

No push, merge, PR, upload, email, submission, history rewrite, post-run
tuning, or second candidate is part of this experiment.

## Pre-run verification

The complete preflight passed before launch authorization on 2026-08-12. The
reviewed implementation/report HEAD before this preflight record was
`c7a390b`; the final launch HEAD will be pinned in the non-overwriting
manifest.

- participant and synchronized Round 1 strategy SHA-256:
  `d6e24a09904197959f225ca01a9b4964b36cce1697ee177522eb97ba190357b0`;
  `cmp` passed for both participant files;
- `uv lock --check` and `uv sync --locked --all-groups`: passed;
- Ruff format/check, Ty, and mypy: passed;
- non-integration tests: `228 passed, 9 deselected`, true branch coverage
  `90.40%` (minimum `90.00%`);
- integration tests: `9 passed`;
- Round 1 smoke: `SMOKE_OK` and `smoke: OK`;
- two `ValidationTeam` participant-only packages: byte-identical SHA-256
  `df32d82ae3de5520ade608482e02910090823f07f83540a10a405b06dcb12772`,
  6,111 bytes, containing only
  `Round1_ValidationTeam/response_strategies/README.md` and
  `Round1_ValidationTeam/response_strategies/user_strategy.py`;
- control participant/runtime and pinned v3 ATT identities were verified;
  active Output remained byte-identical to the pinned control ATT
  (`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`,
  1,262 bytes, mtime `2026-08-12T09:54:19`), and fresh scoring returned exactly
  `19.084638612143134` over 72 periods against baseline SHA-256
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- restricted reachable-history/path scans, `git diff --check`, one-worktree /
  one-`main` layout, clean tracked status, and no live WSC simulator passed.

The non-overwriting launch manifest was written under the predeclared ignored
v9 evidence directory. The candidate run and scoring are now complete; the
candidate was rejected and the accepted v3 control was restored. No tuning,
push, merge, PR, upload, or submission occurred.

## Full-run result

The one authorized full run used the frozen command and configuration above.
The simulator reached every required completion marker: `Simulation Progress:
Day 360 / 360`, `Period Result Output: Period 72 (Days 356-360)`, `Output
Simulation Day: 360`, `Simulation completed.`, and `CSV output written`. The
managed shell wrapper emitted a teardown warning while assigning its exit
status, so the simulator's explicit completion markers and fresh output file,
rather than that wrapper variable, are the completion evidence. The complete
log is preserved at the ignored path below.

- candidate ATT: 72 periods, mean ATT `20.570138888888888` days;
  SHA-256 `b318b8e3ce2ff37e8d8f6c05834440b9af41539b5f2e43d9e366accee9048acd`;
- candidate evidence:
  `.challenge/round1/results/pure_congestion_exclusion_v9_20260812/ATT_By_Statistics_Interval.csv`
  and `full_run.log` (the preserved ATT is byte-identical to the fresh Output
  file before any restoration);
- scorer result: cumulative resilience loss
  `22.38757990186231` over 72 periods;
- control: `19.084638612143134`, so delta is `+3.3029412897191754`
  (`+17.306805524824487%`); 14 periods improved, 20 were equal, and 38 were
  worse than the v3 ATT;
- strict decision: **REJECTED** because acceptance requires
  `candidate_loss < 19.084638612143134 - 1e-9`;
- scorer JSON is recorded in the ignored aggregate path
  `experiments/results/round1_pure_congestion_exclusion_v9_20260812.json`.

The result is consistent with the hypothesis's strongest failure mode: the
22 pure-leg holds excluded by v9 contained useful recovery cases. The complete
score, not the structural activation audit, determines this rejection.

## Rejection and restoration

The result was documented before cleanup. Candidate-only implementation and
test commits `45bc7e3` and `2d11a58` were then reverted in reverse order of
their dependency (`45bc7e3`, then `2d11a58`). The design, audit, TDD evidence,
pre-run manifest, and this result report remain in history. Round 1 was
synchronized back to the accepted v3 participant strategy; its SHA-256 is
`f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`.
The pinned v3 ATT snapshot was restored byte-for-byte:
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`, and
the scorer again returned exactly `19.084638612143134` over 72 periods.

## Post-restoration verification

The restored checkout passed the final gates without another full simulation:

- `uv lock --check` and `uv sync --locked --all-groups` passed;
- Ruff format/check, Ty, and mypy passed (`8` source files for mypy);
- non-integration tests: `227 passed, 8 deselected`, true branch coverage
  `90.84%`; integration tests: `8 passed`; broad suite: `235 passed`;
- Round 1 smoke returned `SMOKE_OK` and `smoke: OK`;
- participant/source `cmp` passed for both participant files, and the active
  strategy SHA remained `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- two participant-only packages were byte-identical at SHA-256
  `a88fa1f534049cec96ffdf7d0204b2dc1fa3d685ceb438d9cecf45b4fcc5eef3`,
  containing only the required README and `user_strategy.py` members;
- restricted reachable-history/path scans, `git diff --check`, one-worktree /
  one-`main` layout, and no-live-simulation verification passed.

The canonical working tree is restored; no candidate process remains.
