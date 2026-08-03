# Challenge rules and compliance

> **Last verified:** 2026-08-03.
>
> This document paraphrases the official challenge materials for quick
> reference. It is not the authoritative source. When anything here disagrees
> with the official materials, the official materials win.

## Sources and precedence

1. **Current official challenge website** - authoritative for current schedule,
   submission instructions, and archive naming.
   <https://meetings.informs.org/wordpress/wsc2026/simulation-challenge/>
2. **Technical document** (`docs/WSC-2026-Simulation-Challenge-Tech-Document.pdf`)
   - authoritative for the `UserStrategy` interfaces and the metric definition.
3. **Executable organizer source** (local only, in `.challenge/`) - authoritative
   for runtime contracts (how and when the strategy methods are called).

## Timeline and weights

- **Round 0** - warm-up / practice. Not scored. **Never submitted.**
- **Round 1** - August 1-23, 2026. Weight: **20%**.
- **Round 2** - September 1-23, 2026. Weight: **30%**.
- **Hidden round** - October 1-23, 2026. Weight: **50%**.
- Hidden scenarios and multiple random seeds are used for evaluation.
- Only successfully running code is eligible for scoring.

The organizers' Round 1 announcement opened the round on 2026-08-01, closes
submissions on 2026-08-23, and requires all evaluated changes to be under
`response_strategies`. It also asks participants to create a new submission
email rather than replying to the announcement.

## Performance criterion

**Lower Cumulative Resilience Loss is better** and is the technical document's
sole performance criterion. The current website also describes the objective as
minimizing total waiting plus service time while preserving simulation
integrity.

The dashboard computes, per period:

```
ATT ratio    = baseline ATT / scenario ATT
period loss  = (1 - ATT ratio) * inclusive number of days
cumulative   = sum(period loss)
```

Zero handling: if scenario ATT <= 0 and baseline ATT <= 0, the ratio is 1; if
scenario ATT <= 0 and baseline ATT > 0, the ratio is 0. Negative period loss is
not clamped (a scenario can outperform the baseline on a period).

Never manipulate outputs, the baseline, scoring code, or framework behavior to
exploit the metric.

## Submission scope

- Only modifications under **`response_strategies`** are considered for
  evaluation. Participant algorithms, helper modules, and required
  participant-owned data must all live under that directory.
- Do not depend on files elsewhere in the public repository at evaluation
  runtime.
- Submission runtime code is **standard-library-only** unless an
  organizer-provided dependency is demonstrably necessary and approved later.
- No network calls, subprocesses, environment-specific paths, current-working-
  directory assumptions, wall-clock time, unseeded randomness, or mutable
  cross-run global state in submission code.

The announced submission address is `wsc2026simchallenge@gmail.com`. Confirm
the final archive filename order with the organizers before sending it; the
public website and technical PDF currently show different conventions.

## The four `UserStrategy` interfaces

These names and signatures must be preserved exactly:

1. `select_vessel_for_berth(maritime_data_context, port, waiting_vessels,
   available_berths, current_time, waiting_since_by_vessel=None)` - may return
   `None` (organizer fallback) or exactly one object from `waiting_vessels`.
2. `create_alternative_service_routes(context, now, vessel=None)` - `None` means
   "not handled; use organizer fallback" and must leave `context` unchanged.
3. `assign_associated_bookings(context, now, shipment)` - `None` uses the
   organizer fallback; `True` means a complete valid booking chain was assigned;
   `False` means no booking can currently be assigned (may cause retry/wait).
4. `adjust_bookings_before_cargo_handling(context, now, vessel)` - `None` uses
   the organizer fallback; a non-`None` response prevents fallback and must keep
   all affected booking chains valid.

These methods are called in hot event paths, so implementations must be
deterministic and efficient.

## Redistribution restriction

Organizer software and data must not be published or redistributed. The public
repository may contain our own tools, tests, strategy code, derived aggregate
descriptions, and links to public organizer documentation only.

## Team membership

A team may have at most **five** members, and each participant may join only
**one** team.

## Filename-order discrepancy (must confirm)

The website and the technical document PDF disagree on the submission archive
filename order:

- **Current website:** `Round1_TeamName.zip` (round first).
- **Technical document PDF:** `TeamName_Round1.zip` (team first).

This tooling uses the website's **`Round<N>_TEAM.zip`** order. **Confirm the
required order with the organizers before your first real submission.**

## Must reconfirm before every official round

- [ ] Official round dates and any schedule changes on the website.
- [ ] Required archive filename order (`Round<N>_TEAM.zip` vs
      `TEAM_Round<N>.zip`).
- [ ] Current submission instructions and upload location.
- [ ] Whether any organizer-provided runtime dependency is permitted.
- [ ] Team roster (max five members; one team per participant).
- [ ] That the submitted archive contains only `response_strategies/` files and
      imports only allowed modules.
- [ ] That Round 0 is never submitted.
