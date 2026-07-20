"""Command-line entry point for the WSC 2026 challenge tooling.

Usage:
    wsc2026 <command> [options]

Commands are added incrementally as their features are implemented. The entry
point resolves all paths relative to the repository root, never to the current
working directory, so behaviour is identical from any cwd.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from wsc2026_tools.artifacts import BootstrapError, bootstrap_round
from wsc2026_tools.overlay import OverlayError, overlay_response_strategies
from wsc2026_tools.packaging import PackagerError, package_submission
from wsc2026_tools.paths import (
    RoundConfigError,
    dist_submissions_dir,
    load_round,
    resolve_repo_path,
    round_source_dir,
    submission_strategies_dir,
)
from wsc2026_tools.scoring import ScoringError, compute_resilience_loss, write_score_output

__all__ = ["main", "run_smoke", "run_full", "SmokeResult", "SmokeError"]


class SmokeError(Exception):
    """Raised when smoke precondition checks fail (not when the sim fails)."""


@dataclass(frozen=True)
class SmokeResult:
    """Outcome of a smoke subprocess run."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


# In-process Python the smoke/full driver executes inside the spawned subprocess.
# It assumes the round source root and its o2despy directory are on PYTHONPATH.
# It deliberately constructs the disruption scenario + model and runs only a few
# days (no 140-day warm-up, no 360-day experiment) to catch import/wiring and
# immediate runtime failures.
_SMOKE_DRIVER = textwrap.dedent(
    """
    import datetime as dt
    import os
    import sys

    import scenario_builders
    from simulation_model import Model

    days = int(os.environ.get("WSC2026_SMOKE_DAYS", "1"))
    context = scenario_builders.create_with_disruption()
    sim = Model(context, seed=2026)
    for _ in range(days):
        sim.run(duration=dt.timedelta(days=1))
    print("SMOKE_OK")
    """
).strip()


def _driver_env(source_root: Path, extra_env: dict[str, str] | None = None) -> dict[str, str]:
    """Build a subprocess environment with PYTHONPATH set for the round source."""
    env = os.environ.copy()
    pythonpath_parts = [
        str(source_root),
        str(source_root / "o2despy"),
    ]
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath_parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    if extra_env:
        env.update(extra_env)
    return env


def _ensure_source(source: Path) -> None:
    if not source.is_dir():
        raise SmokeError(f"round source not found at {source}; run 'wsc2026 bootstrap' first.")
    if not (source / "o2despy").is_dir():
        raise SmokeError(f"o2despy missing under {source}; source tree looks incomplete.")


def run_smoke(
    source_root: Path,
    *,
    days: int = 1,
    timeout: float = 900.0,
) -> SmokeResult:
    """Run a very short smoke simulation against ``source_root`` in a subprocess.

    Uses the current (uv-managed) Python interpreter, sets PYTHONPATH to the
    round source and its o2despy directory, constructs the disruption scenario
    and model, and steps ``days`` days. Returns the subprocess outcome; does not
    raise on simulation failure (callers inspect ``returncode``).
    """
    _ensure_source(Path(source_root))
    env = _driver_env(Path(source_root), {"WSC2026_SMOKE_DAYS": str(int(days))})
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _SMOKE_DRIVER],
            env=env,
            cwd=str(source_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        msg = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return SmokeResult(
            returncode=124,
            stdout=out,
            stderr=msg + f"\nsmoke run timed out after {timeout}s",
            timed_out=True,
        )
    return SmokeResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        timed_out=False,
    )


def run_full(
    source_root: Path,
    *,
    timeout: float | None = None,
) -> SmokeResult:
    """Invoke the organizer's full run_simulation (no dashboard) in a subprocess.

    The full run is intentionally long (140-day warm-up + the experiment) and is
    NOT part of CI. ``timeout`` defaults to None (no limit).
    """
    _ensure_source(Path(source_root))
    env = _driver_env(Path(source_root))
    driver = "import main; main.run_simulation()"
    try:
        proc = subprocess.run(
            [sys.executable, "-c", driver],
            env=env,
            cwd=str(source_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        msg = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return SmokeResult(returncode=124, stdout=out, stderr=msg, timed_out=True)
    return SmokeResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        timed_out=False,
    )


def _sync_for_round(round_id: str) -> int:
    """Shared sync step used by smoke and run. Returns 0 on success, nonzero on error."""
    try:
        config = load_round(round_id)
    except RoundConfigError as exc:
        return _error(str(exc))
    source = round_source_dir(config.extract_dir_name)
    source_strategies = source / "response_strategies"
    if not source.is_dir():
        return _error(f"round {round_id!r} is not bootstrapped at {source}.")
    if not source_strategies.is_dir():
        return _error(f"organizer response_strategies missing at {source_strategies}.")
    submission = submission_strategies_dir()
    if not submission.is_dir():
        return _error(f"submission directory missing: {submission}")
    try:
        overlay_response_strategies(submission, source_strategies)
    except OverlayError as exc:
        return _error(str(exc))
    return 0


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


def _cmd_score(args: argparse.Namespace) -> int:
    try:
        scenario = resolve_repo_path(args.scenario_att)
        baseline = resolve_repo_path(args.baseline_att)
    except Exception as exc:
        return _error(str(exc))
    try:
        result = compute_resilience_loss(scenario, baseline)
    except ScoringError as exc:
        return _error(str(exc))
    write_score_output(result, scenario, baseline, as_json=bool(args.json))
    return 0


def _cmd_package(args: argparse.Namespace) -> int:
    submission = submission_strategies_dir()
    dist = dist_submissions_dir()
    try:
        package_submission(
            submission,
            team=args.team,
            round_id=args.round,
            dist_dir=dist,
            report=True,
        )
    except PackagerError as exc:
        return _error(str(exc))
    return 0


def _cmd_bootstrap(args: argparse.Namespace) -> int:
    try:
        dest = bootstrap_round(args.round, Path(args.archive))
    except (BootstrapError, RoundConfigError) as exc:
        return _error(str(exc))
    print(f"Bootstrapped round {args.round!r} to {dest}")
    return 0


def _cmd_smoke(args: argparse.Namespace) -> int:
    sync_rc = _sync_for_round(args.round)
    if sync_rc != 0:
        return sync_rc
    try:
        config = load_round(args.round)
    except RoundConfigError as exc:
        return _error(str(exc))
    source = round_source_dir(config.extract_dir_name)
    try:
        result = run_smoke(source, days=int(args.days), timeout=float(args.timeout))
    except SmokeError as exc:
        return _error(str(exc))
    sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.timed_out:
        return _error(f"smoke run timed out after {args.timeout}s")
    if result.returncode != 0:
        return _error(f"smoke run failed with exit code {result.returncode}")
    print("smoke: OK")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    if not args.full:
        return _error(
            "refusing to start a full simulation without --full "
            "(full runs are long and intentionally excluded from CI)."
        )
    print(
        "WARNING: full simulation runs are intentionally long and are NOT part of CI.",
        file=sys.stderr,
    )
    sync_rc = _sync_for_round(args.round)
    if sync_rc != 0:
        return sync_rc
    try:
        config = load_round(args.round)
    except RoundConfigError as exc:
        return _error(str(exc))
    source = round_source_dir(config.extract_dir_name)
    result = run_full(source)
    sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.timed_out:
        return _error("full run timed out")
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wsc2026",
        description="WSC 2026 Simulation Challenge participant tooling.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_bootstrap = sub.add_parser(
        "bootstrap",
        help="Verify and extract a challenge archive into the local ignored source tree.",
    )
    p_bootstrap.add_argument("--round", required=True, help="Round id (e.g. round0).")
    p_bootstrap.add_argument("--archive", required=True, help="Path to the round archive.")
    p_bootstrap.set_defaults(func=_cmd_bootstrap)

    p_sync = sub.add_parser(
        "sync",
        help="Overlay participant response_strategies onto the bootstrapped source tree.",
    )
    p_sync.add_argument("--round", required=True, help="Round id (e.g. round0).")
    p_sync.set_defaults(func=_cmd_sync)

    p_smoke = sub.add_parser(
        "smoke",
        help="Run a very short smoke simulation to validate imports and wiring.",
    )
    p_smoke.add_argument("--round", required=True, help="Round id (e.g. round0).")
    p_smoke.add_argument("--days", type=int, default=1, help="Simulation days to step (default 1).")
    p_smoke.add_argument(
        "--timeout", type=float, default=900.0, help="Subprocess timeout in seconds."
    )
    p_smoke.set_defaults(func=_cmd_smoke)

    p_run = sub.add_parser(
        "run",
        help="Run the organizer's full simulation (requires --full).",
    )
    p_run.add_argument("--round", required=True, help="Round id (e.g. round0).")
    p_run.add_argument(
        "--full",
        action="store_true",
        help="Required confirmation flag; full runs are long and excluded from CI.",
    )
    p_run.set_defaults(func=_cmd_run)

    p_score = sub.add_parser(
        "score",
        help="Compute cumulative resilience loss from two ATT-per-period CSVs.",
    )
    p_score.add_argument("--scenario-att", required=True, help="Scenario ATT CSV path.")
    p_score.add_argument("--baseline-att", required=True, help="Baseline ATT CSV path.")
    p_score.add_argument("--json", action="store_true", help="Emit full-precision JSON to stdout.")
    p_score.set_defaults(func=_cmd_score)

    p_package = sub.add_parser(
        "package",
        help="Build a compliant submission archive under dist/submissions/.",
    )
    p_package.add_argument("--team", required=True, help="Team name (non-placeholder).")
    p_package.add_argument(
        "--round",
        required=True,
        choices=["1", "2", "hidden"],
        help="Submission round (Round 0 is rejected).",
    )
    p_package.set_defaults(func=_cmd_package)

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
