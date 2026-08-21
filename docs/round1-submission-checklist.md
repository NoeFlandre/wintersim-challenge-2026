# Round 1 submission checklist

## Prepared archive

- File: `dist/submissions/Round1_NoeFlandre.zip`
- SHA-256: `5f63fce47a5dc3e5b84cc66660b7772826bdc9b169466796f9d0e327b6068d19`
- Size: 5,907 bytes
- Contents only:
  - `Round1_NoeFlandre/response_strategies/README.md`
  - `Round1_NoeFlandre/response_strategies/user_strategy.py`

The archive was built twice and was byte-identical both times. `NoeFlandre` is
the team-name assumption taken from the repository author metadata; replace it
only if the registered team name is different.

## Verified solution

- Round: Round 1 (Round 0 must never be submitted)
- Active strategy: accepted multi-transfer recovery-hold v3
- Cumulative resilience loss: `19.084638612143134` over 72 periods
- Participant/runtime strategy SHA-256: `f04bda9d85953686e0e413590baf69dd00067b7a007b7d7a6691ee655ffbcded`
- Control ATT SHA-256: `5838993882ca36ff91bebeecfd23865e1d612c8ac846c206ac81f732bbf1522a`

## Human steps before sending

1. Confirm the registered team name and roster (maximum five members; each
   participant may belong to only one team).
2. Confirm with the organizers whether the archive must be named
   `Round1_TeamName.zip` or `TeamName_Round1.zip`; the website and technical
   PDF currently disagree. The local tool uses the first form.
3. Confirm the current submission address and instructions. The Round 1
   announcement specifies `wsc2026simchallenge@gmail.com` and asks for a new
   email rather than a reply.
4. If the team name differs, rebuild from the repository root:

   ```bash
   uv run wsc2026 package --team YourRegisteredTeam --round 1
   ```

   Run it twice and compare the printed SHA-256 values.
5. Attach the ZIP only. Do not attach the repository, `.challenge` files,
   organizer archive/source/input/output, tests, or `dist` directory.
6. Send the new email before the organizer deadline: **23 August 2026**.
7. Keep the sent email, final ZIP, and SHA-256 as the submission receipt.

No further simulation or experiment is required for this submission.
