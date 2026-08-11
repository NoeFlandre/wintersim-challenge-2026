# Autonomous WSC agent guide design

## Status

Approved for implementation on 2026-08-11. This specification covers process
documentation only. It does not authorize a strategy change, simulation,
submission, upload, push, branch, worktree, or history rewrite.

## Goal

Enable a fresh, lower-cost coding agent to design and execute one valid WSC
2026 experiment autonomously, learn from prior results, maximize its chance of
finding a real improvement, and leave the repository in a verified accepted or
restored state.

The guide must reduce rediscovery work without turning historical observations
into hard-coded policy. It must help the agent reason well enough to choose a
falsifiable candidate while keeping fragile operational steps prescriptive.

## Success criteria

A fresh agent using the revised skill must be able to:

1. locate the authoritative challenge rules, runtime, tooling, current strategy,
   current-best evidence, and past experiment reports;
2. distinguish public rules, private organizer behavior, tracked documentation,
   ignored evidence, inference, and unverified claims;
3. derive the current round and current-best result from fresh evidence instead
   of copying stale values;
4. summarize prior experiments by policy difference and measured outcome;
5. generate multiple candidate hypotheses, eliminate unsafe or redundant ones,
   and select one using an evidence-based scorecard;
6. use a read-only activation audit to prove a candidate is live without
   claiming that activation proves performance;
7. precommit one exact policy, run identity, threshold, evidence path, and
   restoration procedure;
8. implement only participant-owned files with strict RED -> GREEN TDD;
9. pass all repository, type, test, coverage, integration, synchronization,
   smoke, packaging, Git, process, and restricted-material gates;
10. run exactly one candidate, preserve fresh evidence before any overwriting
    command, score all required periods, and apply the immutable decision rule;
11. retain an accepted strategy or revert a rejected strategy without losing
    its audit history;
12. interpret “continue until better” as a sequence of separately designed and
    controlled experiments, never post-result tuning inside one experiment;
13. stop or seek authority when the requested action exceeds the user's current
    authorization.

## Baseline pressure-test evidence

A fresh read-only agent was asked to select the next Round 1 experiment using
the current skill. It eventually found a plausible candidate, but had to
rediscover important rules and reported these gaps:

- the protocol hard-codes Round 0 commands and baseline values;
- it requires an isolated branch/worktree even though this repository has an
  explicit one-folder, one-`main` constraint;
- it omits Ty from the mandatory command list;
- it provides no reproducible activation-audit method or evidence schema;
- it does not explain how to reason about path identity, repeated routes,
  floating-point ties, or recovery aggregation;
- it does not clearly reconcile a persistent “continue until better” goal with
  the one-candidate-per-experiment limit.

The baseline agent also spent excessive time locating the relevant evidence.
The revised guide must therefore provide an ordered discovery route and
decision framework, not merely more prose.

## Chosen structure

Keep the existing skill as the concise entry point and split detail by purpose:

```text
.agents/skills/running-wsc-experiments/
├── SKILL.md
├── agents/openai.yaml
└── references/
    ├── experiment-protocol.md
    └── autonomous-strategy-guide.md
```

`SKILL.md` remains the always-loaded workflow summary. It must require:

- `experiment-protocol.md` for every implementation, run, scoring, acceptance,
  rejection, or restoration task;
- `autonomous-strategy-guide.md` when the agent must invent, compare, select,
  continue, or improve strategies.

This progressive-disclosure structure keeps routine review/scoring tasks small
while giving autonomous agents the richer reasoning guide they need.

## Autonomous strategy guide contents

### 1. Mission and operating contract

Define the agent's responsibility as evidence-driven experimentation, not
leaderboard storytelling. State that correctness, challenge compliance, and
clean restoration outrank a favorable number.

Separate three scopes:

- a **program goal** may continue until a better result exists;
- an **experiment** contains exactly one frozen candidate and one full run;
- a **turn** may end at a required approval or safety boundary without marking
  the program goal complete.

### 2. Fast orientation path

Give an ordered, bounded discovery sequence:

1. Git/process/restricted-material state;
2. `README.md`, rules, architecture, readiness, and technical PDFs;
3. active participant strategy and README;
4. all four organizer call sites and validators for the chosen round;
5. scorer, sync, smoke, run, and package implementations;
6. current accepted report, pinned ignored ATT/aggregate, then prior reports;
7. tests around the active hook.

Explain what fact each source can establish and forbid trusting a status report
without fresh verification.

### 3. Round and control discovery

Provide a round-neutral procedure. The agent must derive and record:

- round, scenario, seed, warm-up, horizon, interval, and expected periods;
- active strategy hash and runtime-copy hash;
- current-best score, ATT hash, mean, and snapshot;
- authoritative baseline ATT;
- exact full-precision acceptance expression;
- current Git/worktree/branch constraints from the user's latest instructions.

Historical values may appear as examples only and must be labeled stale until
reverified.

### 4. Build an experiment ledger

Require a compact comparison table with:

- experiment name and hook;
- one-sentence policy delta from its control;
- score, delta, and accepted/rejected/invalid status;
- activation or no-effect evidence;
- what the result directly supports;
- what remains unproven;
- whether the implementation was valid enough to interpret.

The guide must teach the agent to compare adjacent policies, such as v2 -> v3
or v3 -> v4, because controlled deltas are more informative than unrelated
absolute scores.

### 5. Candidate generation and ranking

Require at least two and at most four candidates. Favor small additions or
subtractions from the current best with a single causal mechanism.

Rank candidates before implementation using a fixed qualitative scorecard:

- evidence from adjacent experiments;
- live activation and meaningful exposure;
- semantic correctness at the organizer call site;
- expected upside and plausible downside;
- generalization to undisclosed scenarios/seeds;
- implementation and mutation risk;
- novelty relative to already rejected policies;
- ability to test without simulator-specific identities.

Reject candidates that need names, IDs, dates, seed tables, output-derived
parameters, mutable state, forbidden I/O, unshipped imports, or multiple policy
changes.

### 6. Read-only activation audit

Define an audit as structural evidence only. It may create fresh organizer
contexts and call pure participant helpers, but must not advance the event
model, mutate shared runtime state, write organizer outputs, or become an
unregistered candidate run.

Record only anonymous aggregate facts needed for the decision: observations,
qualifying calls, unique structural classes, exposure proxy, boundaries,
decision split, and no-mutation proof. Do not publish organizer identities or
restricted input content.

Require the candidate to be measurably different from the control before TDD.
Dormant candidates are discarded without a full run.

### 7. Policy design rules

Explain the participant contract in operational terms:

- `None` delegates to the organizer fallback;
- any non-`None` result must satisfy the exact call-site and validator contract;
- delegation must be mutation-free;
- mutating hooks require complete planning and transactional safety;
- collection order supplies deterministic ties; sets are membership-only;
- exception handling is narrow and fail-closed;
- no cross-run cache, randomness, wall clock, environment, filesystem,
  network, subprocess, or current-working-directory dependency;
- only packaged participant files and permitted imports may be used.

Include specific reasoning prompts for topology, route identity, repeated-route
paths, boundary inclusivity, recovery aggregation, finite arithmetic, and
object identity versus display names.

### 8. TDD contract

Require one behavioral RED at a time and captured evidence that it fails for
the missing policy. The test matrix must include:

- qualifying candidate behavior;
- the closest control/delegation case;
- exact time and numeric boundaries;
- malformed and non-finite inputs;
- deterministic equal-cost ties;
- complete before/after mutation snapshots;
- exact public signatures and forbidden-capability checks;
- a real-context activation/delegation integration test derived without
  hard-coded organizer identities;
- regression proof that every intentionally retained control decision remains
  unchanged.

Production code must remain the minimum needed for GREEN.

### 9. Frozen experiment contract

Specify the tracked report and ignored manifest fields, including full hashes,
commands, configuration, package members, stale Output metadata, acceptance
rule, evidence paths, authorization, and reject/revert order.

The launch commit must be immutable. Any code, test, policy, or threshold
change after launch invalidates the candidate.

### 10. Preflight, run, and monitoring

Give a round-parameterized command checklist using `uv`, Ruff, Ty, mypy,
pytest with true branch coverage, integration tests, sync, byte comparison,
smoke, and deterministic packaging. Explain why each gate exists.

Before launch, require fresh identity, clean-status, restricted-material,
stale-output, and no-live-process checks. Monitor one managed process at
intervals below 60 seconds. Never infer exit from ambiguous `ps` output and
never launch a duplicate.

### 11. Evidence, decision, and restoration

Require fresh ATT/log preservation before sync, smoke, score-adjacent commands,
or restoration. Validate mtime, size, canonical header, finite values, period
count, and hashes. Score the preserved bytes, not an assumed active Output.

Apply the frozen expression exactly; equality is rejection. Record delta,
relative change, mean ATT, and better/equal/worse periods while keeping the
official cumulative loss authoritative.

For rejection, commit the result first, revert candidate commits in reverse
order, synchronize the accepted control, restore its pinned ATT bytes, re-score,
and rerun every final gate. Never manually recreate strategy code.

### 12. Autonomous continuation

After a complete accepted or rejected experiment:

1. update the ledger and current-best documentation;
2. derive lessons only within the evidence's scope;
3. leave the repository clean and the best valid strategy active;
4. start a separately named experiment only if the user's authority permits;
5. otherwise present the next design and stop for approval.

No outcome authorizes parameter tuning, a second candidate under the same
contract, publication, submission, push, or history rewrite.

### 13. Rationalization and stop tables

Add compact tables mapping common shortcuts to required responses, including:

- trusting stale current-best documentation;
- equating activation with improvement;
- changing two hooks “to save a run”;
- using a favorable mean instead of the scorer;
- retaining a tie;
- treating a crash as permission to patch and rerun;
- scoring before preserving output;
- weakening validation or package rules;
- continuing after a failed gate;
- assuming a persistent goal removes per-experiment controls.

### 14. Handoff template

Provide a concise completion template listing evidence an agent must report.
It must distinguish confirmed facts, inferences, unresolved issues, forbidden
actions not taken, and the precise next safe action.

## Existing protocol corrections

Update `SKILL.md` and `experiment-protocol.md` without duplicating the new
reference:

1. make triggering and examples round-neutral;
2. replace Round 0-only command literals with a verified `<round>` placeholder;
3. add Ty to mandatory preflight and final verification;
4. state that a dedicated branch/worktree is the default, but explicit user or
   repository one-folder/one-branch constraints override it;
5. define “do not attempt another candidate” as applying within the current
   experiment, not forever;
6. link the autonomous guide at every point where strategy selection or
   continued experimentation begins;
7. keep operational instructions in the protocol and reasoning instructions in
   the autonomous guide.

Do not change `agents/openai.yaml` unless validation proves its existing
metadata no longer matches the skill.

## Documentation TDD and validation

### RED

Preserve the baseline pressure-test findings above. They are the failing
behavior the revised guidance must address.

### GREEN

Give a fresh agent the revised skill and a realistic read-only continuation
request. Success requires the agent to:

- find the correct current Round 1 control without supplied values;
- produce a compact ledger before choosing a candidate;
- compare multiple candidates and explain its ranking;
- prove live candidate-only activation before proposing a run;
- specify RED/GREEN tests and all modern gates including Ty;
- preserve one-folder/one-`main` when that remains the active constraint;
- keep one candidate per experiment while explaining how a persistent program
  goal can continue;
- state the authority boundary for a full run and external actions.

### REFACTOR

Review the fresh-agent output for new loopholes. Add only the minimum explicit
counter needed, then repeat the affected pressure scenario.

### Mechanical checks

- validate the skill with the available skill validator;
- verify frontmatter and `agents/openai.yaml` consistency;
- check every relative Markdown link;
- scan for stale Round 0-only commands or missing Ty gates;
- run `git diff --check`;
- inspect the final diff for duplicated or contradictory instructions;
- confirm no strategy/runtime/ignored organizer file changed;
- commit with a Conventional Commit message;
- leave the sole `main` worktree clean and do not push.

## Files expected to change

- `.agents/skills/running-wsc-experiments/SKILL.md`;
- `.agents/skills/running-wsc-experiments/references/experiment-protocol.md`;
- `.agents/skills/running-wsc-experiments/references/autonomous-strategy-guide.md`;
- this design specification only if self-review finds an ambiguity.

No strategy, test, dependency, organizer source, ignored evidence, or public
challenge-result documentation is in scope.
