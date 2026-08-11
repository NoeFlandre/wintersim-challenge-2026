---
name: running-wsc-experiments
description: Use when designing, comparing, optimizing, continuing, implementing, reviewing, executing, scoring, accepting, rejecting, restoring, or packaging a WSC 2026 strategy experiment for any round in this repository.
---

# Running WSC Experiments

## Overview

Run one falsifiable, package-valid strategy experiment from a verified accepted
control to a clean accepted or restored state. Treat simulation output as
evidence, never as permission to tune after seeing the result.

**Violating a challenge rule, a precommitted gate, or the one-candidate limit
invalidates the experiment even when tests or score look favorable.**

**REQUIRED SUB-SKILLS:** Use `superpowers:brainstorming`,
`superpowers:test-driven-development`, `superpowers:systematic-debugging` for
unexpected failures, and `superpowers:verification-before-completion`.

Read [references/experiment-protocol.md](references/experiment-protocol.md)
completely before changing strategy code or starting a simulation.

When the task includes inventing, comparing, selecting, continuing, or
improving strategies, also read
[references/autonomous-strategy-guide.md](references/autonomous-strategy-guide.md)
completely before proposing a candidate.

## Non-Negotiable Sequence

1. Audit Git state, challenge rules, official sources, local technical PDFs,
   runtime call sites, scorer, packager, prior experiments, and pinned control.
2. Use a new `codex/` branch and isolated worktree by default. If the latest
   user or repository instruction explicitly requires one folder, worktree, or
   branch, obey and record that constraint instead. Never modify or publish
   ignored organizer material.
3. Choose one generalizable hypothesis from measured evidence. Precommit the
   exact policy, invariants, run identity, threshold, evidence paths, and
   reject/revert procedure.
4. Prove RED with behavior tests. Implement the minimum participant-owned
   change. Prove focused GREEN, real-context validity, and no forbidden state
   or I/O.
5. Run every preflight gate, including the actual packager twice. A smoke test
   cannot replace packaging or the full run.
6. Confirm no overlapping simulation, synchronize the reviewed strategy, pin
   the pre-run identities, then run exactly one complete candidate.
7. Monitor the live job at intervals under 60 seconds until explicit
   completion. Do not score stale, partial, or manually edited output.
8. Preserve raw ignored evidence first, then score all required periods with
   full precision.
9. Apply the precommitted rule unchanged. Equality is rejection.
10. If rejected or invalid, record the result, use `git revert` for candidate
    code/tests, synchronize the control, restore the pinned ATT, and rerun all
    final gates. Do not try a second idea inside that experiment.
11. Leave a clean branch with an evidence-limited report. Do not push, merge,
    open a PR, submit an archive, or rewrite history unless explicitly asked.

A persistent goal such as “continue until better” may start a separately
named experiment after the prior experiment reaches a clean accepted or
restored state. It never permits post-result tuning or another candidate under
the same frozen contract. When the active user instruction explicitly grants
autonomous continuation, separate local experiments do not need repeated
approval unless the user also imposed a design or pre-run review gate. External
actions remain unauthorized unless separately requested.

## Stop Conditions

Stop before the long run when any of these is unresolved:

- submission package fails or imports an unshipped organizer module;
- tracked or reachable restricted material is detected;
- strategy/runtime copies differ;
- unit, integration, lint, type, smoke, coverage, or deterministic-package
  gates fail;
- accepted-control score/hash/period count is unverified;
- another simulation is running;
- the hypothesis, acceptance threshold, or revert procedure is not committed.

After a run starts, fix no code and change no threshold. A crash, invalid
period count, validation error, or missing fresh ATT is a rejected candidate.

## Red Flags

- “The import exists in the organizer tree, so packaging will be fine.”
- “Coverage rounds to 90%, so 89.x is close enough.”
- “The mean ATT looks better; the full score is unnecessary.”
- “The candidate tied the control, so keep it.”
- “One quick tuning run is still the same experiment.”
- “The Output CSV exists, so it must be fresh.”
- “I can restore the control by rewriting the file manually.”
- “The worktree symlink guard can be bypassed.”

All mean: stop, return to the protocol, and preserve experiment integrity.

## Completion Report

Report branch/HEAD, candidate commits and strategy hash, fixed configuration,
package hash/members, runtime, score, ATT hash/mean/periods, delta and relative
change, period comparison, historical comparison, decision, evidence paths,
revert/restore commits when applicable, restored-control proof, every final
gate, Git cleanliness, restricted-material check, and forbidden-action
confirmation.
