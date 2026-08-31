# OrtolanForever — WSC 2026 Round 2

This directory contains the participant-owned response strategy submitted by
team **OrtolanForever** for Round 2 of the WSC 2026 Simulation Challenge.

## Strategy

The policy is deliberately conservative. For newly generated cargo, it may
hold a shipment on its normal direct service when that service is temporarily
disrupted. The established recovery hold applies when the safe alternative
requires at least two service changes. Round 2 additionally permits a
one-change recovery hold only when all of these conditions are clear from the
live simulation context:

- the nominal service is affected only by an active port closure;
- the safe alternative requires exactly one service-route change; and
- the direct service is expected to recover more than three quarters of the
  maximum safe-route headway sooner than that alternative.

In every other case, including incomplete or ambiguous data, the organizer's
default decision is used. The strategy never creates, edits, or persists
bookings and makes no changes to simulation state.

## Runtime guarantees

- Compatible with Python 3.11 and newer.
- Deterministic and read-only.
- Uses only the Python standard library and documented simulation interfaces.
- Performs no network, subprocess, filesystem, environment, or wall-clock
  access, and uses no unseeded randomness or mutable cross-run state.

The organizer's framework supplies the remaining simulation components at
evaluation time. This archive intentionally contains only the participant
strategy and this explanation.
