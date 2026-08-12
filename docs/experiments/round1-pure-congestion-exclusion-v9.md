# Round 1 pure-congestion exclusion v9

**Status: DESIGN FROZEN — no candidate implementation or full simulation has
started.**

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
