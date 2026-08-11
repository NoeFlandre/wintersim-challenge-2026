# Autonomous WSC Strategy Guide

## Contents

1. Mission and scope
2. Essential vocabulary
3. First-pass orientation
4. Establish the live control
5. Build the experiment ledger
6. Generate and rank candidates
7. Prove candidate-only activation
8. Design the policy
9. Specify RED -> GREEN behavior
10. Freeze the experiment contract
11. Execute and decide
12. Continue safely
13. Rationalizations and stop conditions
14. Handoff template

Use this reference to decide **what to test**. Use
[experiment-protocol.md](experiment-protocol.md) to control **how to implement,
run, score, accept, reject, and restore it**. Read both completely before
changing strategy code.

Never replace fresh repository evidence with a value copied from this guide.
Numbers below illustrate reasoning from earlier runs; they are historical until
recomputed in the current checkout.

## 1. Mission and scope

Your job is not to produce a clever-looking policy or a favorable anecdote. Your
job is to complete one valid, falsifiable experiment that either establishes a
new best result or safely restores the existing best.

Use three separate scopes:

- The **program goal** may continue across several experiments until a better
  valid result exists.
- An **experiment** contains one named hypothesis, one frozen candidate, and at
  most one full candidate run.
- A **turn** may stop at a review, authority, safety, or external-state gate
  without declaring the program goal complete.

A rejected experiment is useful when its implementation was valid, its result
was preserved, and its policy difference was narrow enough to interpret. A run
that violates a rule, mixes several policy changes, uses stale output, or cannot
be restored is not useful evidence even if its score looks good.

Use this priority order:

1. challenge compliance and participant-boundary integrity;
2. a reproducible current control;
3. one interpretable policy difference;
4. valid RED -> GREEN evidence;
5. fresh complete-run evidence;
6. performance.

Do not trade an earlier item for a later one.

## 2. Essential vocabulary

| Term | Meaning |
| --- | --- |
| ATT | Average Transport Time: the organizer's reported cargo transport-time metric for each statistics period. Verify its unit from the current round's code/documentation. |
| Cumulative resilience loss | Repository scorer output across all required ATT periods. Lower is better and this value, not mean ATT, decides acceptance. |
| Baseline | Organizer-provided comparison ATT used by the scorer. It is not necessarily the active strategy's control. |
| Control | The best valid participant strategy currently being challenged, together with its pinned ATT bytes and score. |
| Candidate | One frozen strategy implementation tested against the control. |
| Hook | One public `UserStrategy` decision method invoked by the organizer. |
| Delegate | Return `None` without mutation so the organizer fallback makes the decision. |
| Activation | A context in which candidate behavior differs from control behavior. Activation proves the policy is live, not that it improves performance. |
| Exposure proxy | An anonymous structural weight, such as annual TEU associated with qualifying demand observations. It is not a score prediction. |
| TEU | Twenty-foot equivalent unit, the cargo-volume unit used by the maritime model. |
| Pinned evidence | Exact ignored bytes plus hashes and metadata used to identify a control or candidate result. |
| Participant boundary | Files under `submission/response_strategies/`, the only strategy surface intended for packaging. |

## 3. First-pass orientation

### 3.1 Read in this order

Do not begin with broad source browsing. Use this bounded route:

1. `git status --short --branch`, `git worktree list --porcelain`, local
   branches, upstream relationship, and live-process inspection.
2. `README.md`, `docs/challenge-rules.md`, `docs/architecture.md`, the active
   round readiness document, and both local technical PDFs.
3. The current `submission/response_strategies/user_strategy.py` and its
   participant README.
4. All four current-round organizer call sites, fallback implementations, and
   strategy validators.
5. `src/wsc2026_tools` implementations for round discovery, synchronization,
   smoke, run, scoring, and packaging.
6. The latest accepted experiment report and its ignored ATT, log, manifest,
   and aggregate evidence.
7. Earlier reports that changed the same hook, followed by reports for other
   hooks.
8. Unit and real-context integration tests around the active policy.

Use `rg` and `rg --files`. Read complete relevant files, but do not recursively
dump the organizer tree or private inputs into logs.

### 3.2 Authority map

| Source | What it can establish | What it cannot establish alone |
| --- | --- | --- |
| Official public organizer page/email/docs | Public rules, deadlines, submission boundary | Exact behavior of the local executable checkout |
| Local ignored organizer source | Actual current call sites, validation, state transitions, clocks | Permission to publish or track that source |
| Tracked participant source | What the repository would package after synchronization | What the ignored runtime is currently executing until byte identity is checked |
| Ignored ATT/log/manifest/aggregate | Raw private run evidence for this checkout | Publicly shareable organizer data or current truth without hash checks |
| Tracked experiment report | Intended policy and audit narrative | Proof that files, scores, processes, or remote state still match |
| Test output | Covered contracts in that invocation | Performance, hidden-scenario generalization, or untested invariants |

Treat status reports and commit messages as leads. Verify material claims from
source, raw evidence, Git objects, or fresh commands.

### 3.3 Repository safety before analysis

Resolve the user's latest constraints before creating anything. This repository
has previously required a single canonical folder, one worktree, and only
`main`; recheck instead of assuming that constraint is unchanged. A Git-layout
override is active only when it comes from the current conversation, an
applicable repository instruction file, or another explicit current policy.
Historical experiment prose describing a former “standing” instruction is
evidence of past context, not present authority. Without a current override,
use the protocol's isolated branch/worktree default.

Before touching strategy code, establish:

- which checkout owns `.challenge`;
- whether another simulator, probe, or organizer `main.py` is live;
- whether tracked or reachable Git history contains a restricted archive, its
  known restricted blob, organizer `Input/` or `Output/`, organizer `main.py`,
  or `default_strategy.py`;
- whether ignored runtime files differ from tracked participant files;
- whether the working tree contains user changes.

Never print, commit, publish, upload, copy into tracked paths, or summarize
restricted input/source contents more specifically than the experiment needs.

## 4. Establish the live control

Do this from fresh evidence before generating candidates. Record the result in
your working plan.

### 4.1 Round identity

Derive rather than guess:

```text
round
scenario builder
organizer seed
PYTHONHASHSEED policy
warm-up days
measured days
statistics interval
required numbered ATT periods
```

Trace the configured round in repository tooling and the local organizer entry
point. Do not transplant Round 0 values into Round 1 or a future round.

### 4.2 Strategy identity

Record:

```text
participant strategy path and SHA-256
runtime strategy path and SHA-256
byte-comparison result
participant package member set
```

If participant and runtime differ, stop and determine which is the intended
active strategy. Synchronization is a write; perform it only when authorized
and only after preserving any runtime state that must not be lost.

### 4.3 Result identity

Locate the latest **accepted** report, then verify its ignored snapshot instead
of trusting the prose. Record:

```text
control experiment name
control score at full precision
control ATT path, SHA-256, size, period count, and mean
authoritative baseline ATT path and SHA-256
fresh re-score of the control snapshot
active Output ATT path/hash/mtime and whether it is merely stale
```

The acceptance rule for the next candidate is normally:

```text
candidate_cumulative_loss < control_cumulative_loss - 1e-9
```

Confirm the repository's current rule before freezing it. Equality is
rejection. Never lower the threshold after seeing a result.

### 4.4 Authority identity

Record what the user has and has not authorized:

- design and read-only audits;
- tracked edits and commits;
- synchronization or smoke writes;
- exactly one full run for the named candidate;
- local deletion or restoration;
- push, PR, upload, email, or submission.

“Continue experimenting” does not automatically authorize publication,
submission, history rewrite, or deletion. When approval is limited to a design
phase, stop before implementation or the full run as directed.

Interpret common scopes consistently:

| User instruction | Local authority |
| --- | --- |
| “Analyze,” “design,” or “propose” | Read-only investigation and a design; no strategy implementation or full run |
| “Implement” | Participant edits, TDD, local verification, and commits; no full run unless execution is also explicit |
| “Run this experiment end to end” | Implement and execute exactly one frozen candidate through decision/restoration |
| “Keep trying experiments until you beat the best” | A sequence of separately named, frozen, one-run experiments; no repeated approval is needed unless the user imposed a review gate |
| “Stop for review before running” | Implement and verify, then stop before synchronization/smoke or the full run at the stated boundary |

These local scopes never imply push, PR, upload, email, submission, publication,
history rewrite, or destructive cleanup. A newer user instruction replaces an
older conflicting scope.

## 5. Build the experiment ledger

Before proposing an idea, compress prior work into a ledger. This prevents a
cheaper agent from repeating attractive failures or comparing unrelated
policies as though they were controlled variants.

Use these columns:

| Experiment | Hook | Single policy delta | Control | Score/delta | Status | Activation evidence | Directly supported lesson | Unresolved question | Validity caveat |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### 5.1 How to populate it

For every relevant report:

1. Identify the exact implementation commit and its parent control.
2. Express the change in one sentence. If that requires “and” between
   independent behaviors, the experiment may be confounded.
3. Record the official cumulative score and full-precision delta, not just mean
   ATT.
4. Distinguish `ACCEPTED`, `REJECTED`, `INVALID`, `INCOMPLETE`, and `NO EFFECT`.
5. Record whether the candidate definitely activated and whether output was
   byte-identical to control.
6. State only the narrow lesson supported by the measured implementation.
7. Note defects that prevent generalizing from the policy result.

Start with the current accepted policy and its immediate predecessor/successor.
Then examine other candidates on the same hook. Only then scan other hooks.

### 5.2 Why adjacent comparisons matter

Historical Round 1 reports currently illustrate this pattern; reverify the
numbers before using them:

- no-op control -> recovery-aware hold v2 changed one initial-booking decision
  and improved from about `20.44` to `19.83`;
- v2 -> multi-transfer-only hold v3 removed one-transfer holds and improved
  further to about `19.08`;
- v3 -> safe-departure headway gate v4 removed a subset of v3 holds and worsened
  sharply to about `25.94`.

This supports a narrow reasoning direction: preserve the proven v3 mechanism
unless fresh evidence justifies changing it; prefer one additive semantic gap
over another broad subtraction. It does **not** prove that every v3 hold is
beneficial or that any particular untested addition will improve the score.

Read the actual reports under `docs/experiments/`. The example above is not a
current-control declaration and not an instruction to implement a particular
next candidate.

### 5.3 Separate no-effect from harmful behavior

- Byte-identical ATT means the candidate did not affect the measured trajectory
  under this run. Investigate dormancy or semantic equivalence; do not describe
  it as “safe improvement.”
- A worse but different ATT establishes that the exact candidate activated and
  degraded this scenario, assuming the implementation was valid.
- A failed validator, forbidden state, non-deterministic tie, incomplete run,
  or broken restoration invalidates broad performance conclusions.

## 6. Generate and rank candidates

### 6.1 Generate a small set

Create at least two and at most four candidates. Each must have:

- one hook;
- one policy delta from the current control;
- one causal mechanism;
- a structural reason it can activate;
- a general rule that does not encode this scenario's identities;
- a safe delegation/failure behavior;
- an obvious way to prove RED.

Favor, in order:

1. a representational or semantic gap inside the current best mechanism;
2. a small additive extension supported by adjacent experiments;
3. a narrow removal supported by direct evidence that its control subset was
   harmful;
4. a new hook only when the ledger shows a live, untested mechanism and the
   mutation/validation risk is justified.

Avoid combining hooks “to save a run.” One run with two changes cannot identify
which change helped or harmed.

### 6.2 Veto unsafe candidates first

Discard a candidate immediately if it needs any of these:

- port, route, vessel, demand, disruption, or seed-specific identities;
- calendar dates, output-period tables, fitted constants, or thresholds chosen
  from candidate results;
- filesystem, environment, network, subprocess, current-directory, wall-clock,
  or random behavior;
- mutable module or cross-run state;
- an organizer-owned import unavailable in the package;
- partial mutation without a complete plan and rollback;
- non-deterministic set/dict iteration for choices or equal-cost ties;
- validation weakening, root-guard bypass, or restricted material in the
  package;
- behavior indistinguishable from the control in the activation audit.

### 6.3 Fixed qualitative scorecard

Score each surviving candidate `0`, `1`, or `2` on every dimension. Do not
change weights to make a favored idea win.

| Dimension | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Adjacent-experiment evidence | Contradicted or unrelated | Indirect | Direct controlled support |
| Candidate-only activation | None/unknown | Rare or weakly measured | Reproducibly live with meaningful exposure |
| Call-site semantic fit | Fights lifecycle | Plausible | Uses the hook's natural control point |
| Upside/downside | Downside dominates | Balanced uncertainty | Bounded downside, clear bottleneck relief |
| Hidden-scenario generalization | Scenario-shaped | Partly structural | Identity-free invariant |
| Implementation/mutation safety | Complex or non-atomic | Moderate | Small, read-only, fail-closed |
| Novelty | Repeats rejected policy | Partial refinement | New falsifiable delta |
| Behavioral testability | Requires full run to observe | Mostly synthetic | Synthetic plus real-context parity |

Select the highest-scoring non-vetoed candidate. Explain every `0` and every
tie-break; prefer the smaller, read-only, safer policy when totals are equal.
Do not override the result because another idea feels more interesting. If new
evidence changes a score, update the evidence and rerun the whole scorecard
before selection.

### 6.4 Write the hypothesis before code

Use this form:

```text
Because [specific adjacent evidence and runtime mechanism], changing only
[one decision] from [control behavior] to [candidate behavior] for
[identity-free qualifying context] should reduce [specific delay mechanism]
without [bounded major downside].
```

Also state the strongest reason it may fail. If the downside cannot be bounded
or observed, choose another candidate.

## 7. Prove candidate-only activation

An activation audit answers: “Can the candidate behave differently here, and
how broad is that difference?” It does not answer: “Will the score improve?”

### 7.1 Allowed audit behavior

The audit may:

- construct fresh organizer contexts using the configured scenario builder;
- derive sample times from disruption windows;
- inspect topology and anonymous demand attributes;
- call pure participant helpers or the public hook when complete snapshots prove
  no mutation;
- compare control and proposed decision predicates;
- aggregate anonymous counts and exposure proxies.

The audit must not:

- advance the event model or call the full-run entry point;
- write or overwrite organizer Output;
- reuse a context after a fallback/helper mutation unless that mutation is the
  explicit audited setup and the context is then discarded;
- expose organizer names, IDs, input rows, or source in tracked documentation;
- claim that activation, TEU exposure, or a timing estimate predicts score;
- search parameter values against completed candidate outputs.

### 7.2 Sampling rules

Predeclare a structural sampling rule, for example:

- every integer-day midpoint in the union of valid disruption windows;
- fixed fractions derived from each window;
- every demand in context order;
- no hand-selected identity.

Create a fresh context for each time whenever setup can mutate routes. Preserve
context order for ties. Record malformed/unsupported observations as delegated,
not silently dropped, unless the audit schema distinguishes them.

### 7.3 Evidence schema

Use an ignored, atomically written JSON record with at least:

```json
{
  "schema_version": 1,
  "round": "roundN",
  "created_at_utc": "ISO-8601 timestamp",
  "control_strategy_sha256": "full hash",
  "candidate_definition_sha256": "hash of frozen prose or predicate",
  "sample_rule": "identity-free structural rule",
  "observations": 0,
  "control_activations": 0,
  "candidate_activations": 0,
  "candidate_only_activations": 0,
  "candidate_only_exposure": 0,
  "boundary_counts": {},
  "delegation_counts": {},
  "no_mutation": true,
  "limitations": [
    "activation is not causal performance evidence"
  ]
}
```

The candidate definition hash must identify the exact rule being audited. Do
not pretend a prose hash is a future code hash.

### 7.4 Go/no-go rule

Proceed only when all are true:

- control and candidate predicates were evaluated on the same observations;
- at least one candidate-only activation exists in a structurally derived real
  context;
- the candidate-only subset is not caused by malformed data or an identity
  lookup;
- complete observed state is unchanged;
- any applicable exposure proxy is recorded at full precision;
- the audit limitations are explicit.

A dormant candidate is discarded before TDD. Rarity lowers the activation
score but is not subject to a universal fitted minimum: precommit the exact
observed count/exposure and justify the run cost without inventing a threshold.
This is not a rejected full experiment and consumes no candidate run.

## 8. Design the policy

### 8.1 Trace the hook, never infer it from the method name

For the chosen round, trace:

1. the exact call site;
2. the `None` branch;
3. every non-`None` conversion or branch;
4. the validator's snapshot and accepted result shapes;
5. fallback mutations;
6. retry/re-entry lifecycle;
7. subsequent consumers of the decision.

For example, the current Round 1 initial-booking call site treats `None` as
fallback delegation, `False` as “no booking assigned” and may schedule a retry,
and truthy results as a claim that the participant already installed a valid
booking chain. This is an example only; re-trace it for the active round.

### 8.2 Prefer read-only control points

A read-only policy returning a valid primitive usually has lower risk than
creating routes, bookings, or other graph objects. If mutation is necessary:

- construct and validate the complete plan first;
- record every reverse reference that must be updated;
- apply atomically, or roll back every change on failure;
- prove both success and rollback with full snapshots;
- expect the organizer validator to reject partial consistency.

Never mutate on a path that returns `None`.

### 8.3 Determinism rules

- Use context list order for equal-cost decisions.
- Use sets/frozensets only for membership, never as choice order.
- Use stable structural attributes only when the organizer contract uses them;
  do not confuse display names with identity.
- Decide explicitly whether repeated adjacent edges on one route represent one
  service or multiple boardings; test both the intended case and re-entry/cycle
  cases.
- Aggregate all relevant disruption recoveries when a path contains more than
  one affected edge; define whether earliest, latest, or another invariant is
  semantically correct.
- Use `start <= now < end` unless the current runtime proves different
  boundaries.
- Reject boolean-as-number, NaN, infinities, non-positive speeds/distances, and
  malformed graph shapes.
- Catch only anticipated data-shape/arithmetic exceptions and delegate. Do not
  hide programmer errors with `except BaseException` or an unrestricted
  `except Exception`.

### 8.4 Package boundary

Everything imported by participant code must either be standard library or be
explicitly available and permitted in the evaluation package/runtime. Never
import organizer `default_strategy.py`, repository development tools, tests, or
ignored helpers just because local execution can see them.

Package early enough to expose boundary mistakes before the long run. Never
weaken the packager to admit a candidate.

## 9. Specify RED -> GREEN behavior

Use **REQUIRED SUB-SKILL:** superpowers:test-driven-development.

### 9.1 Minimum behavioral matrix

Write tests before production changes for:

1. one candidate-only qualifying decision;
2. the closest control case that must still delegate;
3. exact time boundaries and full-precision numeric equality;
4. malformed, missing, boolean-as-number, NaN, infinity, and non-positive data;
5. deterministic equal-cost topology ties using context order;
6. repeated-route, re-entry, and cycle behavior relevant to the policy;
7. aggregation across multiple relevant constraints;
8. complete before/after state equality on every read-only return path;
9. exact public method signatures;
10. static forbidden-capability and mutable-state checks;
11. a real-context candidate-only activation derived without names or IDs;
12. parity for every control decision intentionally retained.

Do not inflate coverage with trivial assertions. Every test should defend an
experiment invariant or a real failure boundary.

### 9.2 Valid RED

Run the smallest focused selection against untouched control code. RED is valid
only when:

- collection/import/fixtures succeed;
- the assertion fails because candidate behavior is absent;
- control behavior is exactly observed;
- mutation snapshots still pass;
- unrelated tests remain green.

A syntax error, fixture error, missing organizer tree, or wrong expected value
is not RED. Fix the test until it fails for the intended missing behavior, then
commit the RED contract separately.

### 9.3 Minimal GREEN

Implement only the frozen policy. Do not refactor unrelated helpers, add
configuration, add a second hook, or “prepare” future candidates. Run the same
focused selection and require every test green. Then run changed-surface Ruff,
Ty, and mypy before the implementation commit.

If implementation reveals that the approved predicate is impossible or unsafe,
stop and return to design. Do not silently change the experiment while keeping
its name and threshold.

## 10. Freeze the experiment contract

Before any full run, commit a tracked report and write an ignored,
non-overwriting manifest.

### 10.1 Tracked report

Record:

- hypothesis and strongest failure mode;
- exact hook and one policy delta;
- activation-audit rule, anonymous result, and limitations;
- invariants and forbidden behavior;
- control commit/strategy/ATT/score identities;
- candidate test and implementation commits;
- candidate strategy hash;
- round/scenario/seed/warm-up/horizon/interval/periods;
- exact command and environment;
- exact full-precision acceptance expression;
- ignored evidence locations;
- reject/revert order;
- one-candidate/no-tuning constraint;
- external actions not authorized.

### 10.2 Ignored pre-run manifest

Use an atomic, refuse-overwrite write. Include:

```text
schema version and creation time
full launch HEAD
participant/runtime hashes and byte identity
package hashes, size, and exact members
control ATT and baseline ATT hashes
control score and period count
stale active Output hash, size, and mtime
all commands and gate results
run configuration and environment
acceptance expression
candidate ATT/log/aggregate destinations
no-live-process proof
authorization statement
```

The launch documentation commit is immutable. Any code, test, policy, package,
or threshold mismatch cancels the run.

## 11. Execute and decide

Follow [experiment-protocol.md](experiment-protocol.md) exactly for preflight,
launch, monitoring, preservation, scoring, acceptance/rejection, restoration,
and final gates.

Remember the order that prevents evidence loss:

1. complete preflight and freeze identities;
2. prove no simulator is live;
3. launch one managed process;
4. monitor that same process to explicit completion;
5. copy fresh ATT and log to the predeclared ignored evidence directory;
6. validate freshness, header, finite values, periods, and hashes;
7. score the preserved candidate bytes;
8. write ignored aggregate and tracked result;
9. apply the immutable expression;
10. retain accepted code or revert rejected code/tests;
11. restore and re-score the control when rejected;
12. rerun every final gate and leave Git clean.

Do not run sync, smoke, packaging, or restoration between full-run completion
and candidate evidence preservation if any of those operations can overwrite or
confuse active Output.

Mean ATT is descriptive. Better/equal/worse period counts explain distribution.
Only the official cumulative resilience loss over the required complete period
set decides acceptance.

## 12. Continue safely

### 12.1 After acceptance

- Keep the candidate active.
- Pin its ATT/log/manifest/aggregate and re-score after final smoke.
- Update current-best documentation without overstating hidden-scenario proof.
- Derive the next research question from the measured delta and its mixed
  per-period effects.
- Start another experiment only when the program goal and authority require it.

### 12.2 After rejection or invalidity

- Preserve evidence and commit the result before reversion.
- Revert implementation/correction/test commits in reverse order; keep design
  and audit history.
- Synchronize and restore the exact pinned control, never a hand-recreated file.
- Re-score the restored bytes and rerun all final gates.
- Derive only the lesson supported by the exact implementation.

### 12.3 Starting the next experiment

“Continue until better” permits a sequence like:

```text
experiment A -> decide -> clean accepted/restored state
new evidence review -> experiment B contract -> decide -> clean state
```

It never permits:

```text
experiment A run -> inspect result -> tweak A -> rerun A
```

The next candidate needs a new name, hypothesis, evidence audit, acceptance
control, design approval when required, RED commit, implementation commit,
manifest, and one-run budget. A rejected experiment's “do not attempt another
candidate” rule ends that experiment; it does not permanently end an explicitly
authorized multi-experiment program goal.

When the user authorized only one experiment or required a pre-run review, stop
at that boundary. No local success authorizes push, PR, upload, email,
submission, deletion, or history rewrite.

## 13. Rationalizations and stop conditions

### 13.1 Rationalization table

| Temptation | Reality and required response |
| --- | --- |
| “The report says this is current best.” | Reports drift. Verify snapshot hash, strategy hash, score, periods, and runtime identity. |
| “The audit shows many activations, so this will win.” | Activation is not causal evidence. Describe it only as proof the candidate is live. |
| “Two small changes save a 30-minute run.” | They confound the result. Select one policy delta. |
| “This threshold is derived from the scenario, not hard-coded.” | If selected after comparing candidate outcomes, it is tuning. Start a new precommitted experiment or discard it. |
| “The mean ATT improved.” | Score every required period; mean ATT does not decide. |
| “It tied, so keeping it is harmless.” | Equality is rejection. Restore the simpler valid control. |
| “The run crashed before output, so it does not count.” | A launched candidate that crashes is rejected/invalid. Preserve evidence and restore; do not patch and rerun in place. |
| “Output exists, so scoring is safe.” | It may be stale or partial. Require completion markers and a fresh write, then preserve bytes first. |
| “Smoke proves package validity.” | Smoke and packaging test different boundaries. Both are mandatory. |
| “The organizer helper imports locally.” | Local visibility does not make it shippable. Validate the actual package. |
| “I can copy the old strategy back manually.” | Manual recreation loses provenance. Use predeclared Git reverts and pinned bytes. |
| “Continue until better means no more review gates.” | It broadens duration, not authority or experiment integrity. Each experiment remains separately frozen. |
| “Coverage is nearly 90%.” | The unrounded branch-coverage gate must be at least 90.00%. |
| “The package validator is too strict for this good idea.” | Redesign the candidate. Never weaken safety or submission boundaries. |

### 13.2 Stop before implementation when

- the current control is not reproducible;
- participant/runtime identity is unresolved;
- candidate behavior duplicates a prior valid rejection;
- candidate selection depends on restricted identities or fitted output values;
- the audit is dormant, mutating, or non-reproducible;
- the policy changes more than one independent behavior;
- call-site or validator semantics remain unclear;
- the latest user/repository authority conflicts with the planned Git layout.

### 13.3 Stop before the full run when

- any lock, format, lint, Ty, mypy, test, coverage, integration, sync, byte
  comparison, smoke, package, Git, process, restricted-material, control-score,
  or manifest gate fails;
- the launch HEAD or strategy hash differs from the reviewed candidate;
- another simulator may be live;
- active Output cannot be identified as stale before launch;
- the candidate evidence destinations already exist;
- authorization for this exact run is absent or a review stop was requested.

### 13.4 Stop after launch when

Do not edit candidate code or threshold after launch. Monitor the same process.
If it crashes, times out, is interrupted, lacks final markers, produces invalid
periods, or fails freshness validation, classify it according to the frozen
contract and restore. Never launch a duplicate based on ambiguous process
output.

## 14. Handoff template

Use this structure after every experiment or review stop:

```markdown
## State
- Repository / branch / HEAD:
- Experiment and control:
- Active strategy SHA-256:
- Working tree / worktrees / live process:

## Confirmed evidence
- Candidate policy difference:
- RED -> GREEN evidence:
- Package SHA-256 and members:
- Run configuration and completion markers:
- Candidate ATT/log hashes and period count:
- Candidate score, control score, delta, relative change:
- Better/equal/worse periods and mean ATT:
- Acceptance expression and decision:

## Final active state
- Accepted candidate retained, or control revert/restoration commits:
- Active ATT hash and fresh score:
- Final gate results:
- Ignored evidence paths:

## Interpretation
- Directly supported:
- Plausible but unproven:
- Invalid or out-of-scope conclusions:

## Actions not taken
- No second candidate/tuning:
- No push/PR/upload/email/submission/history rewrite unless authorized:

## Next safe action
- Exact design, approval, restoration, or publication step still required:
```

Be concise in the handoff, but never omit failed gates, ambiguity, stale-state
risk, restoration evidence, or external actions. “Clean” means a fresh Git
check, no live process, valid active strategy/output, and no required work left
inside the completed experiment.
