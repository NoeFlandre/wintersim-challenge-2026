"""Command-line entry point for the WSC 2026 challenge tooling.

Usage:
    wsc2026 <command> [options]

Commands are added incrementally as their features are implemented. The entry
point resolves all paths relative to the repository root, never to the current
working directory, so behaviour is identical from any cwd.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from wsc2026_tools.overlay import OverlayError, overlay_response_strategies
from wsc2026_tools.paths import (
    RoundConfigError,
    load_round,
    round_source_dir,
    submission_strategies_dir,
)

__all__ = ["main"]


def _error(message: str) -> int:
    """Print an actionable error to stderr and return a nonzero exit code."""
    print(f"error: {message}", file=sys.stderr)
    return 2


def _cmd_sync(args: argparse.Namespace) -> int:
    round_id: str = args.round
    try:
        config = load_round(round_id)
    except RoundConfigError as exc:
        return _error(str(exc))

    source = round_source_dir(config.extract_dir_name)
    source_strategies = source / "response_strategies"
    if not source.is_dir():
        return _error(
            f"round {round_id!r} is not bootstrapped at {source}. "
            f"Run 'wsc2026 bootstrap --round {round_id} --archive <path>' first."
        )
    if not source_strategies.is_dir():
        return _error(
            f"organizer response_strategies missing at {source_strategies}; "
            "the source tree appears incomplete."
        )

    submission = submission_strategies_dir()
    if not submission.is_dir():
        return _error(f"submission directory missing: {submission}")

    try:
        copied = overlay_response_strategies(submission, source_strategies)
    except OverlayError as exc:
        return _error(str(exc))

    if not copied:
        print(f"No participant files synchronized for round {round_id!r}.")
    else:
        print(f"Synchronized participant files for round {round_id!r}:")
        for name in copied:
            print(f"  - response_strategies/{name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wsc2026",
        description="WSC 2026 Simulation Challenge participant tooling.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser(
        "sync",
        help="Overlay participant response_strategies onto the bootstrapped source tree.",
    )
    p_sync.add_argument("--round", required=True, help="Round id (e.g. round0).")
    p_sync.set_defaults(func=_cmd_sync)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:  # pragma: no cover - argparse enforces required subcommand
        parser.print_help(sys.stderr)
        return 2
    try:
        return int(func(args))
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
