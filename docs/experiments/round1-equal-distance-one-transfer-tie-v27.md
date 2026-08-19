# Round 1 equal-distance one-transfer tie v27

## Status

**INVALID — complete; v3 control restored after an environment disk-full failure.**

This experiment is a separately named, single-candidate trial from the
accepted v3 control. The design and implementation plan are:

- [`design`](../superpowers/specs/2026-08-19-round1-equal-distance-one-transfer-tie-v27-design.md);
- [`plan`](../superpowers/plans/2026-08-19-round1-equal-distance-one-transfer-tie-v27.md).

## Frozen control and gate

- round/scenario: `round1` / `create_with_disruption`;
- seed / `PYTHONHASHSEED`: `2026` / `0`;
- warm-up / measured horizon / ATT interval: `140` / `360` / `5` days;
- required numbered periods: `72`;
- accepted v3 strategy SHA-256:
  `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`;
- accepted v3 ATT SHA-256:
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`;
- authoritative baseline ATT SHA-256:
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- control loss: `19.084638612143134`;
- strict acceptance: `candidate_loss < 19.084638612143134 - 1e-9`.

Candidate evidence is private/ignored under
`.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/`,
with aggregate
`experiments/results/round1_equal_distance_one_transfer_tie_v27_20260819.json`.
No tuning, duplicate, second candidate, push, submission, or history rewrite
is authorized within this experiment.

## Hypothesis and exact delta

V25 combined exact-distance safe-path reductions of `1→0` and `2→1` route
changes and scored `21.779788584660977`. V27 isolates only the `2→1` shape:
preserve all v3 `False` recovery holds, then install a complete booking chain
only when the fallback safe path has exactly two adjacent service-route
changes and an exact-distance alternative has exactly one. The `1→0` shape,
all non-ties, all other route-change counts, and uncertain/malformed state
delegate `None`.

The candidate is participant-only, deterministic, standard-library-only, and
must install transactionally with complete rollback on anticipated failure.
The other three hooks remain unconditional `None` delegates.

## Pre-code activation audit

The fresh identity-free audit used 50 valid disruption midpoints and every
Round 1 demand (19,000 observations) on disposable contexts. It reproduced 48
v3 holds and found 50 candidate-only `2→1` opportunities, with annual-TEU
exposure proxy `22,150`. It found no candidate `1→0` behavior. Complete state
snapshots were unchanged (`no_mutation: true`), no model advanced, and Output
was not written. This is structural reachability evidence, not a score
prediction.

Ignored audit JSON:
`.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/activation_audit.json`

Audit SHA-256:
`e31f0582870f0ed6fa02b6ff2d929d1ec8a928736b1ba5ec9a4799b05329abd6`.

After the RED→GREEN implementation, a second audit invoked the actual public
participant hook on the same 19,000 disposable observations. It recorded 48
`False` v3 holds, 50 transactional `True` installs, and 18,902 `None`
delegates. Every install had exactly the declared `2→1` service-route-change
shape; all delegate/hold calls were mutation-free, reverse booking references
were present, and the Round 1 Output ATT remained byte-identical. This is still
structural evidence, not a score prediction.

The actual-hook audit is stored privately at
`.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/candidate_activation_audit.json`.
Its evidence SHA-256 is
`51858120df56696a3b05dbb851c23a773e6f7f5655c01724427eff9fae3c9d44`.
Its candidate strategy SHA-256 is
`f073e5b140f30d013eb5faaebefb7eeea629b85243d8c40ab685c586c29db3d1`; its
Output-before/after ATT SHA is
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`.

## Implementation and next gate

The RED contract was committed as `e956e8c`; the minimal GREEN implementation,
README update, and real-context contract correction were committed as
`3a9227d`. Focused GREEN, full non-integration coverage (90.67%), integration,
Ruff, Ty, and mypy checks pass. Only the complete preflight, immutable launch
manifest, and one full candidate run remain. The candidate ATT and raw log must
be preserved before scoring or restoration. Rejection requires a report-first
Git revert, v3 synchronization, byte-identical ATT restoration, exact re-score,
and all final gates.

## Preflight identity record

The complete preflight passed on the candidate implementation:

- `uv lock --check` and `uv sync --locked --all-groups` passed;
- Ruff format/check, Ty, and mypy passed;
- 235 non-integration tests passed with 90.67% branch coverage;
- 8 integration tests passed;
- Round 1 sync produced byte-identical participant/runtime files;
- Round 1 smoke returned `SMOKE_OK`;
- two `Round1_ValidationTeam.zip` packages were byte-identical at SHA-256
  `5249d839fa5e43934a0a97132c0a207dbd9022e65a2fc9c73fd39c908fa929bc`, with
  only `response_strategies/README.md` and `response_strategies/user_strategy.py`;
- the active pre-run Output ATT and pinned v3 ATT are both
  `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`, and
  the authoritative baseline at
  `.challenge/round1/source/Output/Baseline_ATT_By_Statistics_Interval.csv` is
  `2b26eab78b184a19e30447bbee6b4982f08e2b6323966b1f58ea5bcbc328873d`;
- the active control re-scored to `19.084638612143134` over 72 periods;
- the participant and synchronized runtime strategy SHA-256 is
  `f073e5b140f30d013eb5faaebefb7eeea629b85243d8c40ab685c586c29db3d1`;
- restricted-material scans were empty, there is one `main` worktree, and no
  simulator, smoke, or audit process remained live.

The package, hashes, stale Output metadata, control score, and exact launch
command are pinned in the ignored non-overwriting manifest before launch.

## Full-run outcome

The one authorized command was launched exactly once with the frozen manifest.
It exited with status `1` after reaching only Period 36 (Day 180); the log has
no Day 360, Period 72, CSV-write, or `Simulation completed` marker. The final
exception is `OSError: [Errno 28] No space left on device` while the organizer
was printing its completed-TEU statistics matrix. This is an invalid run, not
a performance result and not evidence that the hypothesis helped or hurt.

The raw log was preserved before restoration at
`.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/full_run.log`
with SHA-256
`15756551bf0af65ad8d1a11015eb3bb2826333bb990fd60256e877085e1a5745`.
The current Output ATT was preserved allocation-free at
`.challenge/round1/results/equal_distance_one_transfer_tie_v27_20260819/ATT_By_Statistics_Interval.csv`
with SHA-256
`5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`, size
`1262`, and the unchanged pre-run mtime. It is byte-identical to the pinned v3
ATT, proving that no fresh candidate output existed; it was not scored as a
candidate.

The candidate is therefore **INVALID/REJECTED** under the immutable protocol.
The v27 implementation and RED tests must be reverted, Round 1 synchronized to
the accepted v3 participant, and the pinned v3 ATT restored and rescored before
the final gates. No tuning, duplicate run, or second candidate is part of v27.
