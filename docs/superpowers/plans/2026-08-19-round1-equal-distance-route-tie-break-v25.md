# Plan: Round 1 equal-distance fewer-transfer tie-break v25

1. Run the ignored, identity-free activation oracle against the restored v3
   control and require 19,000 observations, 48 v3 holds, 100 candidate-only
   ties, no mutation, no model advance, and no Output write.
2. Add RED tests for exact tied-path selection, fewer-transfer preference,
   non-tie delegation, v3-hold precedence, transactional installation,
   malformed runtime fail-closed behavior, public signatures, and complete
   mutation snapshots.
3. Implement the smallest participant-only path/tie helpers and lazy
   transactional `Booking` installation; keep all other hooks delegated.
4. Run focused GREEN tests, then the complete lock, format, lint, Ty, mypy,
   coverage, integration, sync, smoke, packaging, restricted-material,
   clean-tree, and no-live-process gates.
5. Freeze a non-overwriting manifest and run exactly one monitored full Round 1
   candidate. Preserve its raw log and ATT before scoring or restoration.
6. Apply the unchanged strict score gate. Keep the candidate only on a strict
   improvement; otherwise record the result, revert the candidate, restore v3,
   re-score it exactly, rerun all final gates, and document the clean outcome.
