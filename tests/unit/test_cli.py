"""Unit tests for the CLI command dispatch (wsc2026_tools.cli).

Each command is exercised through ``main(argv)`` with synthetic inputs and
monkeypatched path helpers, so nothing depends on organizer source or the real
.challenge tree.
"""

from __future__ import annotations

import csv
import textwrap
from pathlib import Path

import pytest

import wsc2026_tools.cli as cli
from wsc2026_tools.cli import SmokeResult
from wsc2026_tools.paths import RoundConfig


def _round_config(round_id: str = "round0", extract_dir_name: str = "round0") -> RoundConfig:
    return RoundConfig(
        round_id=round_id,
        archive_filename="x.zip",
        expected_sha256="0" * 64,
        extract_dir_name=extract_dir_name,
        practice_only=True,
        marker_relpaths=("main.py",),
    )


def _setup_source_and_submission(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    (source / "response_strategies").mkdir(parents=True)
    (source / "o2despy").mkdir(parents=True)
    (source / "response_strategies" / "__init__.py").write_text("# organizer\n")
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    (submission / "user_strategy.py").write_text("class UserStrategy: ...\n")
    (submission / "README.md").write_text("# participant\n")
    return source, submission


# --- sync -------------------------------------------------------------------


def test_cli_sync_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, submission = _setup_source_and_submission(tmp_path)
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: source)
    monkeypatch.setattr(cli, "submission_strategies_dir", lambda: submission)

    rc = cli.main(["sync", "--round", "round0"])

    assert rc == 0
    assert (source / "response_strategies" / "user_strategy.py").exists()


def test_cli_sync_not_bootstrapped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "missing"
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: source)
    monkeypatch.setattr(cli, "submission_strategies_dir", lambda: submission)

    rc = cli.main(["sync", "--round", "round0"])
    assert rc != 0


def test_cli_sync_overlay_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, submission = _setup_source_and_submission(tmp_path)

    def boom(*a, **k):
        raise cli.OverlayError("nope")

    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: source)
    monkeypatch.setattr(cli, "submission_strategies_dir", lambda: submission)
    monkeypatch.setattr(cli, "overlay_response_strategies", boom)

    rc = cli.main(["sync", "--round", "round0"])
    assert rc != 0


def test_cli_sync_unknown_round(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(r):
        raise cli.RoundConfigError("unknown round id 'x'")

    monkeypatch.setattr(cli, "load_round", boom)
    rc = cli.main(["sync", "--round", "x"])
    assert rc != 0


# --- score ------------------------------------------------------------------


def _write_att(path: Path, rows: list[tuple[int, int, int, float]]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["PeriodIndex", "StartDay", "EndDay", "AverageTransportTime"])
        for idx, s, e, att in rows:
            w.writerow([idx, s, e, att])


def test_cli_score_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    s = tmp_path / "s.csv"
    b = tmp_path / "b.csv"
    _write_att(s, [(1, 0, 4, 100.0)])
    _write_att(b, [(1, 0, 4, 100.0)])
    rc = cli.main(["score", "--scenario-att", str(s), "--baseline-att", str(b)])
    assert rc == 0
    assert "Cumulative resilience loss" in capsys.readouterr().out


def test_cli_score_json(tmp_path: Path) -> None:
    s = tmp_path / "s.csv"
    b = tmp_path / "b.csv"
    _write_att(s, [(1, 0, 4, 100.0)])
    _write_att(b, [(1, 0, 4, 100.0)])
    rc = cli.main(["score", "--scenario-att", str(s), "--baseline-att", str(b), "--json"])
    assert rc == 0


def test_cli_score_error(tmp_path: Path) -> None:
    s = tmp_path / "s.csv"
    b = tmp_path / "b.csv"
    _write_att(s, [(1, 0, 4, 100.0)])
    _write_att(b, [(2, 0, 4, 100.0)])  # mismatched period
    rc = cli.main(["score", "--scenario-att", str(s), "--baseline-att", str(b)])
    assert rc != 0


# --- package ----------------------------------------------------------------


def test_cli_package_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    (submission / "user_strategy.py").write_text("class UserStrategy: ...\n")
    (submission / "README.md").write_text("# x\n")
    dist = tmp_path / "dist"
    monkeypatch.setattr(cli, "submission_strategies_dir", lambda: submission)
    monkeypatch.setattr(cli, "dist_submissions_dir", lambda: dist)

    rc = cli.main(["package", "--team", "ValidTeam", "--round", "1"])
    assert rc == 0
    assert (dist / "Round1_ValidTeam.zip").exists()


def test_cli_package_round0_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    (submission / "user_strategy.py").write_text("class UserStrategy: ...\n")
    monkeypatch.setattr(cli, "submission_strategies_dir", lambda: submission)
    monkeypatch.setattr(cli, "dist_submissions_dir", lambda: tmp_path / "dist")
    rc = cli.main(["package", "--team", "ValidTeam", "--round", "1"])  # sanity passes
    assert rc == 0


def test_cli_package_invalid_round_rejected() -> None:
    with pytest.raises(SystemExit):
        cli.main(["package", "--team", "ValidTeam", "--round", "0"])


# --- bootstrap --------------------------------------------------------------


def test_cli_bootstrap_archive_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    rc = cli.main(["bootstrap", "--round", "round0", "--archive", str(tmp_path / "nope.zip")])
    assert rc != 0


def test_cli_bootstrap_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dest = tmp_path / "extracted"
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "bootstrap_round", lambda r, a: dest)
    rc = cli.main(["bootstrap", "--round", "round0", "--archive", str(tmp_path / "a.zip")])
    assert rc == 0


def test_cli_bootstrap_unknown_round(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(r, a):
        raise cli.RoundConfigError("unknown")

    monkeypatch.setattr(cli, "bootstrap_round", boom)
    rc = cli.main(["bootstrap", "--round", "x", "--archive", "/tmp/a.zip"])
    assert rc != 0


# --- smoke ------------------------------------------------------------------


def test_cli_smoke_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    monkeypatch.setattr(cli, "_sync_for_round", lambda r: 0)
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: source)
    monkeypatch.setattr(cli, "run_smoke", lambda src, **kw: SmokeResult(0, "SMOKE_OK\n", "", False))
    rc = cli.main(["smoke", "--round", "round0"])
    assert rc == 0


def test_cli_smoke_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    monkeypatch.setattr(cli, "_sync_for_round", lambda r: 0)
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: source)
    monkeypatch.setattr(cli, "run_smoke", lambda src, **kw: SmokeResult(1, "", "boom", False))
    rc = cli.main(["smoke", "--round", "round0"])
    assert rc != 0


def test_cli_smoke_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    monkeypatch.setattr(cli, "_sync_for_round", lambda r: 0)
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: source)
    monkeypatch.setattr(cli, "run_smoke", lambda src, **kw: SmokeResult(124, "", "timeout", True))
    rc = cli.main(["smoke", "--round", "round0", "--timeout", "5"])
    assert rc != 0


def test_cli_smoke_source_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(src, **kw):
        raise cli.SmokeError("not found")

    monkeypatch.setattr(cli, "_sync_for_round", lambda r: 0)
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: tmp_path / "source")
    monkeypatch.setattr(cli, "run_smoke", boom)
    rc = cli.main(["smoke", "--round", "round0"])
    assert rc != 0


def test_cli_smoke_sync_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_sync_for_round", lambda r: 2)
    rc = cli.main(["smoke", "--round", "round0"])
    assert rc != 0


# --- run --------------------------------------------------------------------


def test_cli_run_without_full(tmp_path: Path) -> None:
    rc = cli.main(["run", "--round", "round0"])
    assert rc != 0


def test_cli_run_full_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    monkeypatch.setattr(cli, "_sync_for_round", lambda r: 0)
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: source)
    monkeypatch.setattr(cli, "run_full", lambda src, **kw: SmokeResult(0, "done\n", "", False))
    rc = cli.main(["run", "--round", "round0", "--full"])
    assert rc == 0


def test_cli_run_full_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    monkeypatch.setattr(cli, "_sync_for_round", lambda r: 0)
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: source)
    monkeypatch.setattr(cli, "run_full", lambda src, **kw: SmokeResult(1, "", "err", False))
    rc = cli.main(["run", "--round", "round0", "--full"])
    assert rc != 0


# --- run_full against a synthetic tree --------------------------------------


def test_run_full_invokes_organizer_run_simulation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "o2despy").mkdir(parents=True)
    (source / "main.py").write_text(
        textwrap.dedent(
            """
            def run_simulation():
                print("FULL_RAN")
            """
        )
    )
    result = cli.run_full(source, timeout=30.0)
    assert result.returncode == 0, result.stderr
    assert "FULL_RAN" in result.stdout


# --- defensive / branch coverage -------------------------------------------


def test_driver_env_appends_existing_pythonpath(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "/already/there")
    env = cli._driver_env(Path("/src"))
    parts = env["PYTHONPATH"].split(cli.os.pathsep)
    assert "/already/there" in parts


def test_ensure_source_rejects_missing_o2despy(tmp_path: Path) -> None:
    s = tmp_path / "source"
    s.mkdir()
    with pytest.raises(cli.SmokeError, match="(?i)o2despy"):
        cli._ensure_source(s)


def test_sync_for_round_rejects_missing_organizer_response_strategies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: source)
    monkeypatch.setattr(cli, "submission_strategies_dir", lambda: submission)
    rc = cli._sync_for_round("round0")
    assert rc != 0


def test_sync_for_round_rejects_missing_submission_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    (source / "response_strategies").mkdir(parents=True)
    monkeypatch.setattr(cli, "load_round", lambda r: _round_config())
    monkeypatch.setattr(cli, "round_source_dir", lambda name: source)
    monkeypatch.setattr(cli, "submission_strategies_dir", lambda: tmp_path / "nope")
    rc = cli._sync_for_round("round0")
    assert rc != 0


def test_sync_for_round_round_config_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(r):
        raise cli.RoundConfigError("nope")

    monkeypatch.setattr(cli, "load_round", boom)
    rc = cli._sync_for_round("round0")
    assert rc != 0


def test_run_full_source_missing_o2despy(tmp_path: Path) -> None:
    s = tmp_path / "source"
    s.mkdir()
    with pytest.raises(cli.SmokeError, match="(?i)o2despy"):
        cli.run_full(s, timeout=5.0)


def test_build_parser_help_does_not_crash(capsys: pytest.CaptureFixture[str]) -> None:
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--help"])


def test_main_without_subcommand_fails() -> None:
    with pytest.raises(SystemExit):
        cli.main([])
