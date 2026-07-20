"""Unit tests for the compliant submission packager (wsc2026_tools.packaging).

The packager builds a deterministic ZIP under dist/submissions/ containing one
top-level directory that holds only allowlisted participant-owned files. It
rejects Round 0, placeholder team names, symlinks, caches, organizer code, and
disallowed imports.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from wsc2026_tools.packaging import (
    PackagerError,
    package_submission,
)


def _submission_dir(tmp_path: Path) -> Path:
    """A clean participant submission/response_strategies directory."""
    sub = tmp_path / "submission" / "response_strategies"
    sub.mkdir(parents=True)
    (sub / "user_strategy.py").write_text(
        "from __future__ import annotations\n"
        "from typing import Any\n"
        "class UserStrategy:\n"
        "    @staticmethod\n"
        "    def select_vessel_for_berth(a, b, c, d, e, f=None) -> Any: return None\n"
    )
    (sub / "README.md").write_text("# participant\n")
    return sub


def _read_members(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path) as zf:
        return zf.namelist()


# --- round / team validation -------------------------------------------------


def test_round0_rejected(tmp_path: Path) -> None:
    sub = _submission_dir(tmp_path)
    with pytest.raises(PackagerError, match="(?i)round0|round 0|practice|not packag"):
        package_submission(sub, team="SomeTeam", round_id="round0", dist_dir=tmp_path / "out")


@pytest.mark.parametrize(
    "team",
    ["", "   ", "placeholder", "PLACEHOLDER", "TODO", "your-team", "team_name", "TestTeam"],
)
def test_placeholder_or_empty_team_rejected(tmp_path: Path, team: str) -> None:
    sub = _submission_dir(tmp_path)
    with pytest.raises(PackagerError, match="(?i)team"):
        package_submission(sub, team=team, round_id="1", dist_dir=tmp_path / "out")


def test_unknown_round_rejected(tmp_path: Path) -> None:
    sub = _submission_dir(tmp_path)
    with pytest.raises(PackagerError, match="(?i)round"):
        package_submission(sub, team="SomeTeam", round_id="round99", dist_dir=tmp_path / "out")


# --- archive naming + members -----------------------------------------------


@pytest.mark.parametrize(
    "round_id,expected_prefix",
    [("1", "Round1"), ("2", "Round2"), ("hidden", "HiddenRound")],
)
def test_archive_naming_and_top_level_dir(
    tmp_path: Path, round_id: str, expected_prefix: str
) -> None:
    sub = _submission_dir(tmp_path)
    dist = tmp_path / "out"
    archive = package_submission(sub, team="ValidTeam", round_id=round_id, dist_dir=dist)
    assert archive.name == f"{expected_prefix}_ValidTeam.zip"
    assert archive.parent == dist

    members = _read_members(archive)
    # Exactly one top-level directory.
    tops = {m.split("/")[0] for m in members}
    assert len(tops) == 1
    top = tops.pop()
    assert top == f"{expected_prefix}_ValidTeam"
    # Every member lives under that directory.
    assert all(m.startswith(top + "/") for m in members)


def test_member_allowlist_excludes_disallowed_files(tmp_path: Path) -> None:
    sub = _submission_dir(tmp_path)
    # Drop organizer-style and dev files into the participant dir; they must be
    # rejected (packaging refuses rather than silently dropping them).
    (sub / "default_strategy.py").write_text("# organizer\n")
    (sub / "strategy_validation.py").write_text("# organizer\n")
    with pytest.raises(PackagerError, match="(?i)not allowlisted|disallowed|refus|organizer"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_caches_and_hidden_files_skipped_not_packaged(tmp_path: Path) -> None:
    sub = _submission_dir(tmp_path)
    (sub / "__pycache__").mkdir()
    (sub / "__pycache__" / "x.pyc").write_text("pyc")
    (sub / ".DS_Store").write_text("ds")

    archive = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")

    members = _read_members(archive)
    assert all("pycache" not in m for m in members)
    assert all(not m.endswith(".pyc") for m in members)
    assert all(".DS_Store" not in m for m in members)


def test_symlink_submission_file_rejected(tmp_path: Path) -> None:
    sub = _submission_dir(tmp_path)
    target = tmp_path / "secret.txt"
    target.write_text("secret")
    (sub / "README.md").unlink()
    (sub / "README.md").symlink_to(target)
    with pytest.raises(PackagerError, match="(?i)symlink"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


# --- determinism ------------------------------------------------------------


def test_packaging_is_deterministic(tmp_path: Path) -> None:
    sub = _submission_dir(tmp_path)
    dist = tmp_path / "out"
    a = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=dist)
    bytes_a = a.read_bytes()
    a.unlink()
    b = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=dist)
    bytes_b = b.read_bytes()
    assert bytes_a == bytes_b, "package_submission must be byte-deterministic"


# --- import validation ------------------------------------------------------


def test_disallowed_import_rejected(tmp_path: Path) -> None:
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "import os\n"  # os is stdlib but filesystem access is forbidden
        "class UserStrategy:\n    pass\n"
    )
    with pytest.raises(PackagerError, match="(?i)import|disallowed|forbidden"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_third_party_import_rejected(tmp_path: Path) -> None:
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "import numpy\n"  # third-party not allowed in submission runtime
        "class UserStrategy:\n    pass\n"
    )
    with pytest.raises(PackagerError, match="(?i)import|disallowed|third.party|numpy"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_documented_organizer_module_import_allowed(tmp_path: Path) -> None:
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from __future__ import annotations\n"
        "from maritime_data_context import MaritimeDataContext  # documented organizer module\n"
        "from simulation_model import Model  # documented organizer module\n"
        "class UserStrategy:\n    pass\n"
    )
    archive = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")
    assert archive.exists()


# --- report (path/sha/size) -------------------------------------------------


def test_report_contains_path_sha_size_and_members(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sub = _submission_dir(tmp_path)
    dist = tmp_path / "out"
    archive = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=dist, report=True)
    out = capsys.readouterr().out
    assert str(archive) in out
    assert "sha256" in out.lower() or "sha-256" in out.lower()
    assert str(archive.stat().st_size) in out
    # Member listing present.
    assert "response_strategies/user_strategy.py" in out
