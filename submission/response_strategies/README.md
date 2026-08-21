# OrtolanForever — WSC 2026 Round 1

This directory contains the participant-owned response strategy submitted by
team **OrtolanForever** for Round 1 of the WSC 2026 Simulation Challenge.

## Strategy

The policy is deliberately conservative. For newly generated cargo, it may
hold a shipment on its normal direct service when that service is temporarily
disrupted, but only when all of these conditions are clear from the live
simulation context:

- the direct service is expected to recover;
- the safe alternative would require at least two service changes; and
- the direct service is expected to deliver sooner than that alternative.

In every other case, including incomplete or ambiguous data, the organizer's
default decision is used. The strategy does not create, edit, or persist
bookings and makes no changes to the simulation state.

## Runtime guarantees

- Compatible with Python 3.11 and newer.
- Deterministic and read-only.
- Uses only the Python standard library and documented simulation interfaces.
- Performs no network, subprocess, filesystem, environment, or wall-clock
  access, and uses no unseeded randomness or mutable cross-run state.

The organizer's framework supplies the remaining simulation components at
evaluation time. This archive intentionally contains only the participant
strategy and this explanation.
