# Autonomous WSC Agent Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Equip a fresh lower-cost agent to select and execute valid WSC 2026
experiments autonomously without sacrificing challenge compliance, TDD,
evidence integrity, or clean restoration.

**Architecture:** Keep `.agents/skills/running-wsc-experiments/SKILL.md` as the
small trigger and workflow index. Put strategy-selection judgment in a new
progressively loaded reference, while correcting the existing operational
protocol to be round-neutral and consistent with the repository's explicit
one-folder/one-branch constraint.

**Tech Stack:** Markdown agent skills, Git, repository WSC tooling (`uv`, Ruff,
Ty, mypy, pytest, `wsc2026`), skill validation, fresh-agent pressure tests.

---

### Task 1: Preserve the documentation RED evidence

**Files:**
- Read: `.agents/skills/running-wsc-experiments/SKILL.md`
- Read: `.agents/skills/running-wsc-experiments/references/experiment-protocol.md`
- Read: `docs/superpowers/specs/2026-08-11-autonomous-wsc-agent-guide-design.md`
- Read: `docs/experiments/round1-multi-transfer-recovery-hold-v3.md`
- Read: `docs/experiments/round1-safe-departure-opportunity-gate-v4.md`

- [ ] **Step 1: Record the baseline pressure-test failures**

Use the committed design specification as the immutable RED record. Confirm it
contains all observed failures:

```text
Round 0 hard-coding
worktree/main conflict
missing Ty gate
no activation-audit recipe or schema
unclear topology/recovery reasoning prompts
unclear persistent-goal versus one-candidate boundary
excessive evidence rediscovery
```

- [ ] **Step 2: Verify the current skill still exhibits the RED gaps**

Run:

```bash
rg -n "round0|Round 0|worktree|ty check|activation|continue|another candidate" \
  .agents/skills/running-wsc-experiments/SKILL.md \
  .agents/skills/running-wsc-experiments/references/experiment-protocol.md
```

Expected: Round 0-specific commands and values are present, the worktree rule
is unconditional, Ty is absent from the mandatory command block, and no
strategy-selection reference exists.

- [ ] **Step 3: Confirm the repository scope before editing**

Run:

```bash
git status --short --branch
git worktree list --porcelain
git branch --format='%(refname:short)'
```

Expected: clean tracked state, exactly one worktree, and only `main`.

### Task 2: Write the autonomous strategy-selection reference

**Files:**
- Create: `.agents/skills/running-wsc-experiments/references/autonomous-strategy-guide.md`

- [ ] **Step 1: Create the guide with an explicit reading contract**

Start with this structure:

```markdown
# Autonomous WSC Strategy Guide

## Contents
1. Mission and scope
2. First-pass orientation
3. Establish the live control
4. Build the experiment ledger
5. Generate and rank candidates
6. Prove candidate-only activation
7. Design the policy
8. Specify RED -> GREEN behavior
9. Freeze the experiment contract
10. Execute and decide
11. Continue safely
12. Rationalizations and stop conditions
13. Handoff template
```

State at the top:

```text
Use this reference to choose what to test. Use experiment-protocol.md to
control how it is implemented and run. Never replace fresh repository evidence
with a value copied from this guide.
```

- [ ] **Step 2: Add the fast orientation and authority map**

Include the exact bounded reading order and distinguish:

```text
public organizer material -> public rules
ignored local organizer source -> executable runtime behavior
tracked participant source -> submitted behavior
ignored ATT/log/JSON -> raw private evidence
tracked experiment reports -> audit narrative, subject to fresh verification
```

Require `rg`/`rg --files`, bounded reads, exact call-site tracing, and fresh
Git/process/restricted-material checks. Explicitly forbid printing or tracking
restricted organizer inputs/source.

- [ ] **Step 3: Add round-neutral control discovery**

Require a live-control record with:

```text
round, scenario, seed, PYTHONHASHSEED
warm-up, measured horizon, interval, period count
active participant/runtime strategy hashes
control ATT path/hash/mean/score
authoritative baseline ATT path
acceptance: candidate_score < control_score - 1e-9
Git folder/branch/worktree constraints
authorization boundaries
```

Label every numeric example as historical and untrusted until reverified.

- [ ] **Step 4: Add the experiment-ledger method**

Define the ledger columns:

```text
experiment | hook | one policy delta | control | score/delta | status |
activation | supported lesson | unresolved question | validity caveat
```

Require comparison of adjacent experiments and instruct the agent to ignore an
invalid implementation when inferring policy performance.

- [ ] **Step 5: Add candidate generation and the fixed scorecard**

Require two to four candidates, then rank each from `0` (poor) to `2` (strong)
on:

```text
adjacent-experiment evidence
candidate-only live activation
call-site semantic fit
upside relative to downside
hidden-scenario generalization
implementation/mutation safety
novelty versus rejected work
behavioral testability
```

Use total score only to organize reasoning. The agent must explain vetoes and
may not tune weights or thresholds to favor a desired candidate.

- [ ] **Step 6: Add the activation-audit recipe and schema**

Permit only fresh contexts and pure/helper calls. Forbid event-model advance,
Output writes, shared-state mutation, identity publication, and performance
claims. Require these anonymous fields:

```json
{
  "schema_version": 1,
  "round": "roundN",
  "control_strategy_sha256": "...",
  "candidate_definition_sha256": "...",
  "sample_rule": "derived structural sample rule",
  "observations": 0,
  "control_activations": 0,
  "candidate_activations": 0,
  "candidate_only_activations": 0,
  "candidate_only_exposure": 0,
  "boundary_counts": {},
  "no_mutation": true,
  "limitations": ["activation is not causal performance evidence"]
}
```

Require a candidate-only difference and discard dormant candidates before TDD.

- [ ] **Step 7: Add policy and TDD reasoning prompts**

Cover `None` delegation, non-`None` validator obligations, read-only versus
transactional hooks, context-order tie-breaking, identity versus names,
repeated-route paths, recovery aggregation, inclusive/exclusive time windows,
finite arithmetic, exception scope, package-valid imports, and forbidden
capabilities.

Require RED tests for positive behavior, nearest delegation case, boundaries,
malformed/non-finite data, ties, mutation snapshots, public signatures,
forbidden capabilities, real-context activation, and retained-control parity.

- [ ] **Step 8: Add experiment freeze, execution, continuation, and handoff**

Cross-reference the operational protocol instead of duplicating all commands.
Explain:

```text
program goal -> may span experiments
experiment -> one frozen candidate and one full run
candidate failure -> reject and restore, never patch/rerun in place
next candidate -> new name, evidence, contract, TDD cycle, and authority gate
```

Add rationalization/response and stop-condition tables plus a handoff template
covering confirmed facts, inferences, unresolved issues, actions not taken, and
next safe action.

- [ ] **Step 9: Inspect the guide against the design**

Run:

```bash
rg -n "TBD|TODO|FIXME|PLACEHOLDER|historical|candidate-only|Ty|one candidate|one full run" \
  .agents/skills/running-wsc-experiments/references/autonomous-strategy-guide.md
```

Expected: no placeholders; all required behavioral boundaries are present.

### Task 3: Integrate the guide into the skill entry point

**Files:**
- Modify: `.agents/skills/running-wsc-experiments/SKILL.md`
- Read: `.agents/skills/running-wsc-experiments/agents/openai.yaml`

- [ ] **Step 1: Make the trigger round-neutral**

Replace the Round 0-specific description with a trigger covering any WSC 2026
round and requests to design, optimize, continue, review, run, score, restore,
or package an experiment. Keep it as a “when to use” description, not a process
summary.

- [ ] **Step 2: Add conditional reference routing**

Add this requirement near the overview:

```markdown
Read [references/experiment-protocol.md](references/experiment-protocol.md)
completely before changing strategy code or starting a simulation.

When the task includes inventing, comparing, selecting, continuing, or
improving strategies, also read
[references/autonomous-strategy-guide.md](references/autonomous-strategy-guide.md)
completely before proposing a candidate.
```

- [ ] **Step 3: Correct the summary workflow boundaries**

Make branch/worktree isolation conditional on the latest explicit user and
repository constraint. Clarify that “do not try a second idea” means within the
current experiment; a persistent program goal continues through a newly named,
separately frozen experiment.

- [ ] **Step 4: Check interface metadata consistency**

Read `.agents/skills/running-wsc-experiments/agents/openai.yaml`. Keep it
unchanged if its display name, description, and default prompt still accurately
trigger the revised skill.

### Task 4: Correct and parameterize the operational protocol

**Files:**
- Modify: `.agents/skills/running-wsc-experiments/references/experiment-protocol.md`

- [ ] **Step 1: Parameterize round-specific values**

Replace fixed `round0` command paths with `<round>` and explicitly require the
agent to substitute a verified configured round such as `round1` before
execution. Keep historical Round 0 values only as a clearly labeled example,
or remove them when they do not help current execution.

- [ ] **Step 2: Correct repository isolation guidance**

Use this precedence rule:

```text
Default: isolated codex/<experiment> branch and worktree.
Override: if the user or repository explicitly requires one folder, one
worktree, or one branch, obey that constraint and record it in the contract.
Never create a worktree or branch in conflict with the active instruction.
```

- [ ] **Step 3: Add Ty and round-neutral commands**

The mandatory preflight must include:

```bash
uv lock --check
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run ty check src/wsc2026_tools submission
uv run mypy src/wsc2026_tools submission
uv run pytest -m "not integration" \
  --cov=src/wsc2026_tools --cov=submission \
  --cov-branch --cov-report=term-missing --cov-fail-under=90
uv run pytest -m integration -q
uv run wsc2026 sync --round <round>
cmp submission/response_strategies/user_strategy.py \
  .challenge/<round>/source/response_strategies/user_strategy.py
uv run wsc2026 smoke --round <round>
git diff --check
```

State that `<round>` is documentation notation and must never be pasted
literally into a shell command.

- [ ] **Step 4: Correct full-run and restoration language**

Parameterize the full command:

```bash
PYTHONHASHSEED=<verified-value> uv run wsc2026 run --round <round> --full
```

Clarify that the one-candidate ban applies to the current experiment and that a
new experiment requires a new hypothesis, contract, TDD evidence, and any
required authorization.

- [ ] **Step 5: Add autonomous-guide cross-references without duplication**

At strategy-selection points, direct the reader to
`autonomous-strategy-guide.md`. Keep execution mechanics here and reasoning
heuristics there.

### Task 5: Run the documentation GREEN pressure test

**Files:**
- Read: `.agents/skills/running-wsc-experiments/SKILL.md`
- Read: `.agents/skills/running-wsc-experiments/references/experiment-protocol.md`
- Read: `.agents/skills/running-wsc-experiments/references/autonomous-strategy-guide.md`

- [ ] **Step 1: Dispatch a fresh read-only agent**

Use this neutral task without leaking the expected candidate:

```text
Use $running-wsc-experiments in this repository. Continue Round 1 performance
work by selecting exactly one next experiment and writing an autonomous
end-to-end plan. Work read-only: do not edit, sync, package, simulate, commit,
push, or ask for approval. Derive current state and evidence yourself. Report
the candidate comparison, activation evidence needed, TDD contract, run gate,
decision/restoration flow, and authority boundaries.
```

- [ ] **Step 2: Evaluate the output against the GREEN rubric**

Require all of:

```text
fresh Round 1 control discovery
compact prior-experiment ledger
2-4 candidates with explicit ranking
candidate-only activation requirement
no hard-coded organizer identity or fitted threshold
RED/GREEN and real-context tests
Ty plus every operational gate
one folder / one main when currently required
one candidate per experiment
safe interpretation of persistent continuation
explicit run and external-action authority boundaries
```

- [ ] **Step 3: Refactor only observed loopholes**

If the agent violates a rubric item, add the smallest explicit counter to the
appropriate reference and repeat only the failed scenario. Do not expand the
guide for hypothetical omissions.

### Task 6: Validate and commit the completed guide

**Files:**
- Validate: `.agents/skills/running-wsc-experiments/`
- Modify only if required by validation:
  `.agents/skills/running-wsc-experiments/agents/openai.yaml`

- [ ] **Step 1: Run the skill validator**

Run the installed skill validation script against the skill directory.
Expected: valid frontmatter, naming, and structure.

- [ ] **Step 2: Verify references and protocol coverage**

Run bounded checks that prove:

```text
all Markdown relative links resolve
SKILL.md routes strategy-selection tasks to the new guide
protocol contains Ty and round placeholders
no executable example remains accidentally fixed to round0
no placeholders or contradictory second-candidate wording remain
```

- [ ] **Step 3: Run repository hygiene checks**

Run:

```bash
git diff --check
git status --short --branch
git worktree list --porcelain
git branch --format='%(refname:short)'
git diff --name-only
```

Expected: only the three approved skill files and this plan are involved,
exactly one worktree/`main`, and no strategy, test, organizer, dependency, or
ignored evidence file changed.

- [ ] **Step 4: Review the complete diff**

Check for duplicated instructions, stale current-best claims, accidental
publication of private organizer content, commands that can be pasted with a
literal placeholder, and any weakening of the experiment protocol.

- [ ] **Step 5: Commit the guide**

Run:

```bash
git add \
  .agents/skills/running-wsc-experiments/SKILL.md \
  .agents/skills/running-wsc-experiments/references/experiment-protocol.md \
  .agents/skills/running-wsc-experiments/references/autonomous-strategy-guide.md \
  docs/superpowers/plans/2026-08-11-autonomous-wsc-agent-guide.md
git commit -m "docs: add autonomous WSC experiment guide"
```

- [ ] **Step 6: Verify the committed state**

Run fresh status, diff, link, skill-validation, one-worktree/one-branch, process,
and restricted-material checks. Expected: clean local `main`, ahead of its
unchanged upstream, with no simulation or external action performed.
