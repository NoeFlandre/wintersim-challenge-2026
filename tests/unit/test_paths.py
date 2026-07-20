"""Unit tests for the rounds.toml strict loader (wsc2026_tools.paths).

Covers fail-closed validation branches by pointing the loader at synthetic
TOML files in tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import wsc2026_tools.paths as paths
from wsc2026_tools.paths import RoundConfig, RoundConfigError


def _use_config(monkeypatch: pytest.MonkeyPatch, content: str, tmp_path: Path) -> Path:
    cfg = tmp_path / "rounds.toml"
    cfg.write_text(content)
    monkeypatch.setattr(paths, "rounds_config_path", lambda: cfg)
    return cfg


def test_load_rounds_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "rounds_config_path", lambda: tmp_path / "nope.toml")
    with pytest.raises(RoundConfigError, match="(?i)not found"):
        paths.load_rounds()


def test_load_rounds_missing_top_level_array(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_config(monkeypatch, "rounds = []\n", tmp_path)
    with pytest.raises(RoundConfigError, match="(?i)empty top-level"):
        paths.load_rounds()

    _use_config(monkeypatch, "other = 1\n", tmp_path)
    with pytest.raises(RoundConfigError, match="(?i)missing or empty"):
        paths.load_rounds()


def test_load_rounds_non_table_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_config(monkeypatch, "rounds = [42]\n", tmp_path)
    with pytest.raises(RoundConfigError, match="(?i)table"):
        paths.load_rounds()


def test_load_rounds_missing_round_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_config(
        monkeypatch,
        "[[rounds]]\narchive_filename='a.zip'\nextract_dir_name='r0'\n"
        "expected_sha256='" + "0" * 64 + "'\npractice_only=true\nmarker_relpaths=['main.py']\n",
        tmp_path,
    )
    with pytest.raises(RoundConfigError, match="(?i)round_id"):
        paths.load_rounds()


def test_load_rounds_duplicate_round_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    block = (
        "[[rounds]]\nround_id='r0'\narchive_filename='a.zip'\nextract_dir_name='r0'\n"
        "expected_sha256='" + "0" * 64 + "'\npractice_only=true\nmarker_relpaths=['main.py']\n"
    )
    _use_config(monkeypatch, block + block, tmp_path)
    with pytest.raises(RoundConfigError, match="(?i)duplicate"):
        paths.load_rounds()


def test_load_rounds_bad_required_string(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_config(
        monkeypatch,
        "[[rounds]]\nround_id='r0'\narchive_filename=''\nextract_dir_name='r0'\n"
        "expected_sha256='" + "0" * 64 + "'\npractice_only=true\nmarker_relpaths=['main.py']\n",
        tmp_path,
    )
    with pytest.raises(RoundConfigError, match="(?i)archive_filename"):
        paths.load_rounds()


def test_load_rounds_bad_practice_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_config(
        monkeypatch,
        "[[rounds]]\nround_id='r0'\narchive_filename='a.zip'\nextract_dir_name='r0'\n"
        "expected_sha256='" + "0" * 64 + "'\npractice_only='yes'\nmarker_relpaths=['main.py']\n",
        tmp_path,
    )
    with pytest.raises(RoundConfigError, match="(?i)practice_only"):
        paths.load_rounds()


def test_load_rounds_bad_sha256(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_config(
        monkeypatch,
        "[[rounds]]\nround_id='r0'\narchive_filename='a.zip'\nextract_dir_name='r0'\n"
        "expected_sha256='ZZ'\npractice_only=true\nmarker_relpaths=['main.py']\n",
        tmp_path,
    )
    with pytest.raises(RoundConfigError, match="(?i)sha256"):
        paths.load_rounds()


def test_load_rounds_bad_markers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_config(
        monkeypatch,
        "[[rounds]]\nround_id='r0'\narchive_filename='a.zip'\nextract_dir_name='r0'\n"
        "expected_sha256='" + "0" * 64 + "'\npractice_only=true\nmarker_relpaths=[]\n",
        tmp_path,
    )
    with pytest.raises(RoundConfigError, match="(?i)marker_relpaths"):
        paths.load_rounds()


def test_load_rounds_marker_traversal_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_config(
        monkeypatch,
        "[[rounds]]\nround_id='r0'\narchive_filename='a.zip'\nextract_dir_name='r0'\n"
        "expected_sha256='" + "0" * 64 + "'\npractice_only=true\nmarker_relpaths=['../x']\n",
        tmp_path,
    )
    with pytest.raises(RoundConfigError, match="(?i)traverse"):
        paths.load_rounds()


def test_load_rounds_valid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_config(
        monkeypatch,
        "[[rounds]]\nround_id='r0'\narchive_filename='a.zip'\nextract_dir_name='r0'\n"
        "expected_sha256='" + "0" * 64 + "'\npractice_only=true\nmarker_relpaths=['main.py']\n",
        tmp_path,
    )
    rounds = paths.load_rounds()
    assert "r0" in rounds
    assert isinstance(rounds["r0"], RoundConfig)
    assert rounds["r0"].marker_relpaths == ("main.py",)


def test_path_helpers_under_repo_root() -> None:
    root = paths.repo_root()
    assert paths.challenge_dir() == root / ".challenge"
    assert paths.round_source_dir("round0") == root / ".challenge" / "round0" / "source"
    assert paths.dist_submissions_dir() == root / "dist" / "submissions"
    assert paths.submission_strategies_dir() == root / "submission" / "response_strategies"
    assert paths.downloads_dir() == root / ".challenge" / "downloads"
