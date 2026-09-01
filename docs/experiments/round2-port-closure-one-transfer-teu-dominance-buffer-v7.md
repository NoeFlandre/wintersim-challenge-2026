# Round 2: upper-quartile TEU half-headway closure hold (v7)

**Status: RUN COMPLETE — REJECTED; accepted v1 control restored and verified.**

## Hypothesis

The accepted Round 2 control holds a new direct shipment when a port-only
closure makes a one-transfer detour slower than waiting for direct recovery by
more than one full safe-route headway.  A read-only audit of the current Round
2 context found a second reachable group: the recovery margin is positive and
larger than half a safe-route headway, but not larger than the full headway.
There are 106 such one-transfer observations; 52 are upper-quartile annual-TEU
demands, and 39 of those also exceed the half-headway boundary.

Round 2's objective is TEU-weighted transport time.  This experiment tests
whether the conservative borderline group is worth holding only for the
highest-volume demand flows, where avoiding a detour has the greatest direct
objective exposure.  The accepted full-headway policy remains unchanged for
all demands, as does every multi-transfer decision.  The new rule is an
identity-free combination of live timing and demand data, not a scenario or
seed lookup.

The strongest failure mode is that even a positive timing advantage below one
full headway is not robust in the event-driven queue: retaining these extra
shipments may increase shared vessel congestion and downstream waiting more
than it reduces their direct service time.  The official 72-period cumulative
resilience-loss score, not the structural activation count, decides.

## Exact participant delta

Only `UserStrategy.assign_associated_bookings` changes.  Preserve the accepted
v1 predicate and all preconditions.  In its one-change, port-closure-only
branch:

1. keep returning `False` for the existing strict full-headway condition
   (`margin > max_safe_headway`) for every well-formed demand;
2. for a positive margin at or below one full headway, return `False` only when
   `margin > 0.5 * max_safe_headway` and the shipment demand is present in a
   well-formed `context.demands` sequence whose positive finite `annual_teus`
   is at or above the deterministic third quartile;
3. otherwise return `None` and delegate to the organizer fallback.

The half-headway comparison is strict at the lower boundary and the existing
full-headway decision is retained at its equality boundary.  A malformed or
missing demand population, non-finite/non-positive volume, or demand object not
present by identity delegates.  Multi-transfer holds, pure congestion, mixed
constraints, inactive windows, and every other hook remain exactly as in the
accepted control.  The strategy is read-only, deterministic, standard-
library-only, fail-closed, and never constructs or edits bookings, routes,
vessels, cargo, context, files, outputs, or model state.

## Challenge compliance

Only participant files under `submission/response_strategies/` are evaluated.
The candidate does not modify or bypass organizer event logic and uses the
normal origin waiting/retry lifecycle: `False` means no booking is assigned,
while `None` delegates to the organizer.  It uses no organizer imports,
filesystem/network/subprocess/environment access, wall-clock time, randomness,
mutable cross-run state, hard-coded ports/routes/dates/seeds, or extra package.

## TDD and activation gate

Commit this design before code.  RED tests must fail against the accepted v1
adapter only for the new upper-quartile half-headway behavior and must cover
strict lower/full boundaries, upper and below-quartile demands, malformed
populations, demand identity, preservation of existing full-headway and
multi-transfer holds, public signatures, and complete no-mutation behavior.
Add a real Round 2 integration test that derives a high-volume candidate-only
case and a lower-volume delegate from the organizer context.

Before any full run, perform a fresh non-mutating audit at every valid Round 2
disruption midpoint and every demand. Compare an independent accepted-v1
oracle with the candidate, require candidate-only holds in the declared
upper-quartile half-headway slice, verify zero control-only decisions and no
unexpected holds, and prove no participant mutation, model advancement, or
`Output` write. Activation is a GO gate only; it is not score evidence.

## Fixed control and run contract

- canonical checkout: `/Users/noeflandre/wintersim-challenge-2026`;
- one worktree and one local branch: `main`;
- round/scenario: `round2` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required numbered periods: `72`;
- accepted-control strategy SHA-256:
  `b4857197a73d7eae4a1d6d1bde3d31e50aa09aff8fcb9a08849d0ea53207ce41`;
- accepted-control ATT snapshot:
  `.challenge/round2/results/port_closure_one_transfer_full_headway_v1_20260831/ATT_By_Statistics_Interval.csv`;
- accepted-control ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
- accepted-control cumulative loss: `35.1039547178493`;
- authoritative Round 2 baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`;
- strict acceptance expression:
  `candidate_loss < 35.1039547178493 - 1e-9`;
- private ignored candidate evidence directory:
  `.challenge/round2/results/port_closure_one_transfer_teu_dominance_buffer_v7_20260901/`.

After the full preflight, freeze an immutable non-overwriting manifest with the
exact HEAD, strategy/runtime hashes, accepted-control/baseline hashes, audit
counts, package members/hash, stale Output metadata, and run command. Exactly
one full candidate run is allowed. Preserve the fresh ATT and raw log before
scoring or any sync, smoke, package, or restoration command. Equality,
worsening, incomplete output, crash, timeout, mutation, or failed final gate
rejects the candidate. On rejection, document first, revert only v7 code/tests
with `git revert`, synchronize the accepted v1 control, restore its pinned ATT,
re-score exactly, rerun all final gates, and leave `main` clean. No tuning,
duplicate run, second candidate, push, merge, submission, or history rewrite
belongs to v7.

## Pre-run freeze record

The candidate is frozen on the single canonical checkout and has passed the
pre-run gates. No simulation has been launched for v7.

- Implementation HEAD: `8483d95` (`test: add real TEU half-headway v7 contract`).
- Participant strategy SHA-256:
  `745af10409c11ee55d9ad31db7cf7fea6b4608c497e66b922bc66cb2de513021`.
- Participant README SHA-256:
  `2985e74081052ee9b757623a9120e8eccce6deefd53e610645924f25c291ab37`.
- `wsc2026 sync --round round2` produced byte-identical participant files in
  `.challenge/round2/source/response_strategies/` (strategy SHA
  `745af10409c11ee55d9ad31db7cf7fea6b4608c497e66b922bc66cb2de513021`).
- Activation audit script SHA-256:
  `e34cfa9e740cbab97ce31074984b7a90563d7327278968cc15ba74ffda4b5157`.
- Activation evidence SHA-256:
  `6d1c585df26bf5fb87a4d17d09c03e32cd03d04243d5dff364ba4ee5e3d6cda2`.
- Activation audit result: GO. It covered 166 disruption midpoints × 380
  demands = 63,080 observations; accepted-v1 holds were 285, candidate holds
  were 324, with 39 declared upper-quartile half-headway candidate-only holds,
  zero control-only decisions, zero unexpected decisions, zero malformed
  classifications, no mutation, no model advancement, and no Output write.
- Stale active Output ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`;
  size 1,262 bytes; modification time (nanoseconds)
  `1788200950277334004`. The pinned control snapshot has the same SHA.
- Authoritative baseline ATT SHA-256:
  `1dc6e2dc9067f6b9f34760c65aba85d9431de2f187d8704100b7e018d9edfa3f`.
- Deterministic package (two identical runs) SHA-256:
  `91932c2614ba61e48d2056a0845c70137095b0555d4cdd93c71e2d11005e797e`;
  members are only `response_strategies/README.md` and
  `response_strategies/user_strategy.py` under the package root.
- Quality gates: `uv lock --check`, locked `uv sync`, Ruff format/check, Ty,
  mypy, 245 non-integration tests with 90.47% branch coverage, and 9
  integration tests all pass.

The audit JSON was normalized after its atomic write to replace a literal
escape in its final newline; this changed serialization only, not the audit
logic, observations, or result. The final script hash above is the hash to
retain with the pre-run manifest.

The exact manifest command is:

```text
PYTHONHASHSEED=0 UV_CACHE_DIR=/tmp/wsc-uv-cache uv run wsc2026 run --round round2 --full > .challenge/round2/results/port_closure_one_transfer_teu_dominance_buffer_v7_20260901/full_run.log 2>&1
```

## Full-run result (rejected)

The manifest recheck passed and exactly one full run was executed with the
command above. The log contained `Period Result Output: Period 72 (Days
356-360)`, `Output Simulation Day: 360`, `Simulation completed.`, and a fresh
CSV write with exit code 0. The fresh ATT was copied before scoring.

- Candidate ATT SHA-256:
  `1cfa99659bc5df7703a8a6ef2b7a60b90e817acd5d241fa011e1f4234cb4f2ed`;
  72 numbered periods; mean ATT 15.573472222222222 days.
- Raw log SHA-256:
  `4233c42a720ed0582ac9c6d8d1507e036483f0b7fb6eea3e9038043024a99122`.
- Candidate cumulative resilience loss: `35.41374495066942`.
- Accepted-control loss: `35.1039547178493`.
- Delta: `+0.3097902328201201` (`+0.8824938252971285%`; higher is worse).
- Acceptance expression `candidate_loss < 35.1039547178493 - 1e-9` was not
  met. The candidate is therefore rejected; no tuning or duplicate run is
  permitted.
- Preserved evidence: `ATT_By_Statistics_Interval.csv`, `raw_run.log`,
  `full_run.log`, and `score.json` in the ignored v7 evidence directory.

The result indicates that extending the hold to the high-volume half-headway
band increased network-wide loss despite 39 structurally isolated candidate-
only activations. The control restoration and final gates below are required.

## Final restoration and verification

The rejected candidate was restored without manual reconstruction. The three
v7 commits were reverted in dependency order (integration test, implementation,
then RED tests), the accepted v1 participant was synchronized into the ignored
Round 2 runtime, and the pinned control ATT snapshot was copied back to
`Output/`.

- Revert commits: `e7c2eed`, `5e27106`, `db99628`.
- Final control strategy SHA-256 (submission and runtime):
  `b4857197a73d7eae4a1d6d1bde3d31e50aa09aff8fcb9a08849d0ea53207ce41`.
- Final control README SHA-256 (submission and runtime):
  `37c083c9fc4b6ee16a87783f503c4fb07e12bfa77ea40fa27839b31985434f3d`.
- Active Output ATT SHA-256:
  `3d02322b340136474319f3e6cf6bce2120676e2e6ad50eef293e02ed618643e5`.
- Re-score after restoration: 72 periods, cumulative loss
  `35.1039547178493` (exact control value).
- Final deterministic control package (two identical runs) SHA-256:
  `f9d3bdccb5b273552f6543a0632bffe1596db27c3c700f136f6b95499b07551d`;
  it contains only `response_strategies/README.md` and
  `response_strategies/user_strategy.py` under the package root.
- Final gates: lock/check and locked sync, Ruff format/check, Ty, mypy, 234
  non-integration tests with 90.36% branch coverage, 8 integration tests,
  smoke, deterministic packaging, diff check, restricted-material scans, and
  no-live-process check all pass.
- Final Git state before this documentation commit: clean on `main`; no
  simulator, probe, or audit process remains live.

The v7 candidate evidence remains ignored and preserved for audit. No tuning,
duplicate run, second candidate, push, merge, submission, or history rewrite
was performed.
