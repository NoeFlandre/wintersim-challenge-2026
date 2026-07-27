# WSC 2026 Experiment Protocol

## Contents

1. Authority and repository audit
2. Baseline and experiment contract
3. Strategy design and TDD
4. Mandatory preflight
5. Full-run monitoring
6. Scoring and evidence
7. Accept or reject
8. Final verification
9. Common failure modes

## 1. Authority and repository audit

Start read-only.

1. Read `README.md`, `docs/challenge-rules.md`, `docs/architecture.md`,
   `pyproject.toml`, `uv.lock`, current experiment reports, and tooling under
   `src/wsc2026_tools`.
2. Read the local technical PDFs completely. Visually inspect pages that define
   the metric, interfaces, submission boundary, and evaluation.
3. Verify current official information using primary sources. Start with the
   [official WSC 2026 challenge page](https://meetings.informs.org/wordpress/wsc2026/simulation-challenge/).
   Treat local executable organizer source as authoritative for runtime
   behavior and public organizer material as authoritative for public rules.
4. Trace all four `UserStrategy` call sites, their exact `None`/boolean/object
   semantics, strategy validation, default behavior, maritime entities,
   disruption clock, scorer, sync, smoke, run, and package commands.
5. Inspect branch, upstream, worktree cleanliness, ignored files, prior
   experiments, and any running simulator.
6. Confirm restricted organizer archives, input/output trees, `main.py`,
   `default_strategy.py`, and the known restricted blob are neither tracked nor
   reachable. Do not print or publish restricted contents.

Use `rg`/`rg --files` for discovery. Do not trust an earlier agent report
without fresh evidence.

## 2. Baseline and experiment contract

Create a new `codex/<experiment-name>` branch in an isolated worktree. If the
private `.challenge` directory is shared by symlink, ignore the symlink and
remember that repository-root containment may reject paths resolved into the
owning checkout.

Before implementation, commit an experiment document containing:

- hypothesis and evidence;
- one hook/policy scope;
- invariants and forbidden behavior;
- starting commit and strategy SHA;
- scenario, seed, warm-up, horizon, interval, and required period count;
- pinned fallback score, ATT SHA, mean, and snapshot path;
- historical reference as secondary evidence only;
- exact full-precision acceptance expression;
- ignored candidate ATT and metrics paths;
- failure/rejection/restoration procedure;
- explicit one-candidate/no-tuning rule;
- no-push/no-submit/no-history-rewrite rule.

For the current Round 0 checkout, verify rather than assume:

```text
scenario: create_with_disruption
seed: 2026
warm-up: 140 days
measured horizon: 360 days
interval: 5 days
periods: 72
fallback loss: 18.673577819840556
fallback ATT SHA-256:
10234375865c4f481ec2d931372417af8156d605bf416783ce5f516392488658
acceptance:
candidate < 18.673577819840556 - 1e-9
```

If current verified values differ, document the new environment; do not
silently relabel historical evidence.

## 3. Strategy design and TDD

Prefer the smallest general policy supported by runtime evidence:

- no port names, route IDs, seed-specific tables, dates, or tuned thresholds;
- no filesystem, environment, network, subprocess, cwd, wall-clock, or
  randomness;
- no mutable module/cross-run cache;
- only participant-owned `response_strategies` files;
- standard library plus imports explicitly accepted by the packager;
- deterministic ties from context order;
- complete planning before mutation and rollback/atomicity where mutation can
  fail;
- exact public signatures;
- delegation paths return `None` without mutation;
- non-`None` paths fully satisfy organizer validators.

Never import an organizer-owned `response_strategies` implementation merely
because it is present locally. The submitted archive must resolve every
participant import. Test the actual package early.

TDD:

1. Add synthetic contract tests and a real ignored Round 0 integration test.
2. Run and capture RED caused by missing candidate behavior, not a broken
   fixture.
3. Commit RED tests.
4. Implement the minimum policy.
5. Run focused GREEN.
6. Run Ruff and mypy.
7. Commit atomic implementation/correction steps.

When an old integration test asserts the fallback behavior being intentionally
replaced, update or supersede that assertion; preserve independent clock and
smoke coverage.

## 4. Mandatory preflight

Run from the experiment worktree with failure-on-first-error semantics:

```bash
uv lock --check
uv sync --locked --group dev --group simulation
uv run ruff format --check .
uv run ruff check .
uv run mypy src/wsc2026_tools submission
uv run pytest -m "not integration" \
  --cov=src/wsc2026_tools --cov=submission \
  --cov-report=term --cov-fail-under=90
uv run pytest -m integration -q
uv run wsc2026 sync --round round0
cmp submission/response_strategies/user_strategy.py \
  .challenge/round0/source/response_strategies/user_strategy.py
uv run wsc2026 smoke --round round0
git diff --check
```

Require true coverage `>= 90.00%`; do not accept a rounded display below the
configured threshold. Add tests only for meaningful behavior branches.

Package twice using a non-placeholder validation team and a non-practice
submission round:

```bash
uv run wsc2026 package --team ValidationTeam --round 1
```

Copy each generated archive to a temporary directory, compare bytes and
SHA-256, inspect members, then move the generated validation archive out of the
worktree. It must contain only allowlisted participant files. This validates
format; it is not authorization to submit.

Repeat restricted-material and Git-cleanliness checks. Do not weaken packager,
import, root-containment, or safety checks to admit a candidate.

## 5. Full-run monitoring

Immediately before starting:

- verify the exact candidate HEAD and strategy SHA;
- verify the synchronized strategy copy;
- verify fallback snapshot hash;
- record current Output ATT hash/mtime as stale-state evidence;
- prove no `wsc2026 run` or organizer `main.py` process exists.

Run exactly:

```bash
uv run wsc2026 run --round round0 --full
```

Use one managed process/session. Prefer an ignored or temporary log when live
tables are extremely large. Poll at intervals below 60 seconds. Report measured
day/period, elapsed runtime, liveness, and first causal error. Never start a
duplicate because `ps` output was ambiguous; confirm liveness with the process
handle or `kill -0`.

Wait for explicit completion, day 360, Period 72, and a fresh CSV write. A
timeout or user interruption does not authorize a second strategy.

## 6. Scoring and evidence

Before any restore or second command can overwrite Output:

1. Copy fresh `ATT_By_Statistics_Interval.csv` to the precommitted ignored
   candidate evidence directory.
2. Record SHA-256, byte size, mtime, header, period count, and mean ATT.
3. Score with `wsc2026 score --json` against the authoritative baseline ATT.
4. Record full-precision cumulative loss and per-period loss.
5. Compare candidate ATT values with the pinned fallback: better/equal/worse
   counts, delta, and relative percentage.
6. Write ignored aggregate JSON and a tracked experiment report.

When `.challenge` is a symlink outside the worktree, score from the owning
checkout or copy inputs into a root-contained ignored path. Never bypass the
scorer's repository-root guard.

Mean ATT is descriptive only. Acceptance uses the complete official loss
formula over exactly 72 numbered periods.

## 7. Accept or reject

Apply the committed expression without rounding.

Accepted:

- retain candidate code/tests;
- document evidence-limited success;
- rerun final gates;
- leave the branch clean and local unless publication is explicitly requested.

Rejected, equal, crashed, invalid, or incomplete:

1. Preserve ignored evidence.
2. Commit the tracked rejection report first.
3. Revert all candidate implementation/correction/test commits in reverse
   order with `git revert`; retain design and result history.
4. Do not recreate the baseline files manually.
5. Sync the restored no-op strategy.
6. Restore Output ATT from the verified fallback snapshot.
7. Verify byte-identical fallback SHA and exact fallback score.
8. Run final gates.
9. Do not attempt another candidate.

Mixed commits complicate restoration. Prefer separate code, tests, design, and
result commits. If a historical mixed commit must be reverted, preserve the
audit document explicitly and verify the final adapter against the known
baseline commit.

## 8. Final verification

Run fresh:

- lock/sync;
- Ruff format/check;
- mypy;
- unit tests with unrounded coverage threshold;
- all integration tests;
- strategy sync and byte comparison;
- smoke;
- deterministic packaging twice and member inspection;
- active fallback ATT SHA and score after rejection;
- `git diff --check`;
- clean `git status`;
- tracked and reachable restricted-material searches;
- process check proving no simulator remains.

Use `superpowers:verification-before-completion`. Then use
`superpowers:finishing-a-development-branch`; by default keep the clean local
experiment branch when push/merge/PR was not requested.

## 9. Common failure modes

| Failure | Required response |
| --- | --- |
| Package rejects organizer import | Redesign as a self-contained participant policy; never bypass the validator |
| Unit behavior passes but coverage is below 90 | Add meaningful boundary/lifecycle tests; do not lower or round the gate |
| Smoke passes | Continue to package and full-run gates; smoke is not acceptance |
| Existing Output has candidate hash before run | Treat as stale; require fresh mtime/write after explicit completion |
| Process status is ambiguous | Confirm the exact PID/session; never duplicate the run |
| Candidate equals fallback | Reject |
| Candidate improves mean but not official loss | Reject |
| Candidate performs worse | Preserve evidence, document, revert, restore |
| Root guard rejects symlinked `.challenge` | Use the owning repo or a root-contained copy; preserve the guard |
| Result suggests a parameter tweak | Stop; a new candidate requires a new explicit experiment |
| Causal explanation is not instrumented | State plausible categories only; do not claim proof |
