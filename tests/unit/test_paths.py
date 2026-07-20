"""Unit tests for the rounds.toml strict loader (wsc2026_tools.paths).

Covers fail-closed validation branches by pointing the loader at synthetic
TOML files in tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import wsc2026_tools.paths as paths
from wsc2026_tools.paths import RepoPathError, RoundConfig, RoundConfigError


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


# --- missing-fields surface as actionable RoundConfigError -------------------


def test_missing_expected_sha256_raises_actionable_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A round missing ``expected_sha256`` must NOT raise KeyError.

    The error must identify the field and the round id so the operator can fix
    config/rounds.toml without reading a traceback.
    """
    _use_config(
        monkeypatch,
        "[[rounds]]\nround_id='r0'\narchive_filename='a.zip'\nextract_dir_name='r0'\n"
        "practice_only=true\nmarker_relpaths=['main.py']\n",
        tmp_path,
    )
    with pytest.raises(RoundConfigError) as exc:
        paths.load_rounds()
    msg = str(exc.value).lower()
    assert "expected_sha256" in msg
    assert "r0" in msg


def test_missing_archive_filename_raises_actionable_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_config(
        monkeypatch,
        "[[rounds]]\nround_id='r0'\nextract_dir_name='r0'\n"
        "expected_sha256='" + "0" * 64 + "'\npractice_only=true\nmarker_relpaths=['main.py']\n",
        tmp_path,
    )
    with pytest.raises(RoundConfigError) as exc:
        paths.load_rounds()
    msg = str(exc.value).lower()
    assert "archive_filename" in msg


def test_missing_extract_dir_name_raises_actionable_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_config(
        monkeypatch,
        "[[rounds]]\nround_id='r0'\narchive_filename='a.zip'\n"
        "expected_sha256='" + "0" * 64 + "'\npractice_only=true\nmarker_relpaths=['main.py']\n",
        tmp_path,
    )
    with pytest.raises(RoundConfigError) as exc:
        paths.load_rounds()
    msg = str(exc.value).lower()
    assert "extract_dir_name" in msg


def test_load_round_unknown_id_raises_actionable_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_config(
        monkeypatch,
        "[[rounds]]\nround_id='r0'\narchive_filename='a.zip'\nextract_dir_name='r0'\n"
        "expected_sha256='" + "0" * 64 + "'\npractice_only=true\nmarker_relpaths=['main.py']\n",
        tmp_path,
    )
    with pytest.raises(RoundConfigError) as exc:
        paths.load_round("round42")
    msg = str(exc.value)
    assert "round42" in msg
    assert "r0" in msg


# --- resolve_repo_path containment ------------------------------------------


def test_resolve_repo_path_relative_inside_repo_works(tmp_path: Path) -> None:
    """A normal in-repo relative path resolves under the repo root."""
    # tmp_path is the cwd surrogate; the repo root is unchanged.
    repo = paths.repo_root()
    rel = "tests/fixtures_score_root/scenario.csv"
    assert (repo / rel).is_file()
    resolved = paths.resolve_repo_path(rel)
    assert resolved == (repo / rel).resolve()


def test_resolve_repo_path_traversal_outside_repo_rejected(tmp_path: Path) -> None:
    """``../outside.csv`` must raise RepoPathError even if the outside file exists."""
    outside = tmp_path / "outside.csv"
    outside.write_text("a,b\n1,2\n")
    repo = paths.repo_root()
    # From inside the repo, "../outside.csv" escapes.
    rel = f"../{outside.name}"
    # sanity: the literal path is not under the repo
    assert not (repo / rel).resolve().is_relative_to(repo.resolve()) if hasattr(  # noqa: E501
        Path(".").resolve(), "is_relative_to"
    ) else True
    with pytest.raises(RepoPathError, match=r"(?i)outside|containment|repository"):
        paths.resolve_repo_path(rel)


def test_resolve_repo_path_symlink_inside_repo_escaping_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relative path that is an in-repo symlink pointing outside is rejected."""
    # Build a synthetic layout: a directory X inside the repo with a symlink
    # inside it pointing at an outside file.
    repo = paths.repo_root()
    sandbox = repo / "tests" / "_containment_sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside.csv"
    outside.write_text("a,b\n1,2\n")
    link = sandbox / "escape.csv"
    try:
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink not supported in this environment")
    try:
        with pytest.raises(RepoPathError, match=r"(?i)outside|containment"):
            paths.resolve_repo_path("tests/_containment_sandbox/escape.csv")
    finally:
        if link.is_symlink() or link.exists():
            link.unlink()
        if sandbox.exists() and not any(sandbox.iterdir()):
            sandbox.rmdir()


def test_resolve_repo_path_absolute_outside_repo_accepted(tmp_path: Path) -> None:
    """Absolute user paths are not constrained to the repo root."""
    outside = tmp_path / "outside.csv"
    outside.write_text("a,b\n1,2\n")
    resolved = paths.resolve_repo_path(outside)
    assert resolved == outside.resolve()


def test_resolve_repo_path_empty_rejected() -> None:
    with pytest.raises(RepoPathError, match=r"(?i)empty"):
        paths.resolve_repo_path("")


def test_resolve_repo_path_whitespace_rejected() -> None:
    with pytest.raises(RepoPathError, match=r"(?i)empty"):
        paths.resolve_repo_path("   ")
