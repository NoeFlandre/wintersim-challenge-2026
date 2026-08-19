# Plan: Round 1 pending-alternative activation v26

1. Freeze the v3 control identities, strict acceptance expression, private
   activation audit, evidence paths, and restoration order in the v26 design
   and experiment report.
2. Add RED unit tests for one matching vessel, queue order, active-window
   boundaries, disruption-key matching, carried/malformed data, inactive and
   empty delegation, no mutation, exact hook signatures, and unchanged v3
   booking behavior.
3. Implement only the v26 selector predicate in the participant adapter and
   add one real-context integration test that loads the file by path.
4. Run focused RED then GREEN, then all lock, format, Ruff, Ty, mypy, coverage,
   integration, sync, smoke, package, restricted-material, and Git gates.
5. Re-run the activation audit against the actual candidate, freeze the
   non-overwriting launch manifest, and review every identity before launch.
6. Run exactly one complete Round 1 simulation, preserve the fresh ATT/log,
   score all 72 periods, and apply the precommitted strict gate.
7. Retain an accepted candidate or commit the rejection report, revert v26,
   restore and re-score v3, rerun final gates, and leave `main` clean.
