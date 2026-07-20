"""Unit tests for the challenge artifact bootstrap (wsc2026_tools.artifacts).

These tests use only synthetic ZIPs, sentinel objects, and temporary folders.
They never touch organizer source or real challenge data.
"""

from __future__ import annotations

import hashlib
import stat
import zipfile
from pathlib import Path

import pytest

from wsc2026_tools.artifacts import BootstrapError, extract_archive
from wsc2026_tools.paths import RoundConfig, RoundConfigError, load_round, repo_root


def _make_zip(
    path: Path, members: dict[str, bytes], *, symlink_members: list[str] | None = None
) -> None:
    """Build a synthetic zip at ``path``.

    ``members`` maps archive-relative names to file bytes. ``symlink_members``
    is a list of names from ``members`` that should be stored as symlinks
    (their bytes are interpreted as ``"target\x00linkname"`` style targets via
    the zip external_attr mechanism).
    """
    symlink_set = set(symlink_members or ())
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            if name in symlink_set:
                # Mark as a symlink: S_IFLNK + 0777.
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            else:
                info.external_attr = (stat.S_IFREG | 0o644) << 16
            zf.writestr(info, data)


VALID_MEMBERS: dict[str, bytes] = {
    "main.py": b"# synthetic main\n",
    "requirements.txt": b"loguru\n",
    "response_strategies/__init__.py": b"",
    "response_strategies/user_strategy.py": b"class UserStrategy: ...\n",
    "response_strategies/default_strategy.py": b"class DefaultStrategy: ...\n",
    "response_strategies/strategy_validation.py": b"# validation\n",
    "o2despy/pyproject.toml": b"[project]\nname='o2despy'\n",
    "maritime_data_context/__init__.py": b"",
}


def _valid_zip(tmp_path: Path) -> Path:
    archive = tmp_path / "sample.zip"
    _make_zip(archive, VALID_MEMBERS)
    return archive


def _hash_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# --- valid extraction --------------------------------------------------------


def test_extract_valid_archive_copies_markers(tmp_path: Path) -> None:
    archive = _valid_zip(tmp_path)
    digest = _hash_of(archive)
    dest = tmp_path / "out"

    extract_archive(archive, digest, dest, marker_relpaths=["main.py", "o2despy/pyproject.toml"])

    assert (dest / "main.py").read_text() == "# synthetic main\n"
    assert (dest / "o2despy" / "pyproject.toml").read_text() == "[project]\nname='o2despy'\n"


def test_extract_does_not_modify_source_archive(tmp_path: Path) -> None:
    archive = _valid_zip(tmp_path)
    original = archive.read_bytes()
    digest = _hash_of(archive)
    dest = tmp_path / "out"

    extract_archive(archive, digest, dest, marker_relpaths=["main.py"])

    assert archive.read_bytes() == original


def test_extract_is_atomic_on_missing_marker(tmp_path: Path) -> None:
    archive = _valid_zip(tmp_path)
    digest = _hash_of(archive)
    dest = tmp_path / "out"

    with pytest.raises(BootstrapError):
        extract_archive(
            archive,
            digest,
            dest,
            marker_relpaths=["main.py", "does_not_exist.py"],
        )

    # A failed extraction must not leave a partial installation behind.
    assert not dest.exists()


# --- checksum failure --------------------------------------------------------


def test_extract_rejects_checksum_mismatch(tmp_path: Path) -> None:
    archive = _valid_zip(tmp_path)
    dest = tmp_path / "out"

    with pytest.raises(BootstrapError, match="(?i)checksum"):
        extract_archive(archive, "0" * 64, dest, marker_relpaths=["main.py"])


# --- traversal / absolute / symlink ------------------------------------------


def test_extract_rejects_absolute_member(tmp_path: Path) -> None:
    members = dict(VALID_MEMBERS)
    members["/etc/evil"] = b"pwned"
    archive = tmp_path / "abs.zip"
    _make_zip(archive, members)
    dest = tmp_path / "out"

    with pytest.raises(BootstrapError, match="(?i)absolute|unsafe"):
        extract_archive(archive, _hash_of(archive), dest, marker_relpaths=["main.py"])


def test_extract_rejects_dotdot_traversal(tmp_path: Path) -> None:
    members = dict(VALID_MEMBERS)
    members["../escape.txt"] = b"escape"
    archive = tmp_path / "traversal.zip"
    _make_zip(archive, members)
    dest = tmp_path / "out"

    with pytest.raises(BootstrapError, match="(?i)traversal|unsafe|escape"):
        extract_archive(archive, _hash_of(archive), dest, marker_relpaths=["main.py"])


def test_extract_rejects_symlink_member(tmp_path: Path) -> None:
    members = dict(VALID_MEMBERS)
    members["link.py"] = b"/etc/passwd"
    archive = tmp_path / "symlink.zip"
    _make_zip(archive, members, symlink_members=["link.py"])
    dest = tmp_path / "out"

    with pytest.raises(BootstrapError, match="(?i)symlink"):
        extract_archive(archive, _hash_of(archive), dest, marker_relpaths=["main.py"])


# --- rounds.toml loading -----------------------------------------------------


def test_load_round_round0_has_expected_metadata() -> None:
    config = load_round("round0")
    assert isinstance(config, RoundConfig)
    assert config.round_id == "round0"
    assert config.archive_filename == "SimulationChallenge2026_Py_Round0.zip"
    assert (
        config.expected_sha256 == "224e176b2c5eeee20c492f5b0cb44d02a8cb7281521f6d3a3800045bbbda256b"
    )
    assert config.extract_dir_name == "round0"
    assert config.practice_only is True
    # Marker paths must be relative and platform-normalized.
    for marker in config.marker_relpaths:
        assert not marker.startswith("/")
        assert ".." not in marker


def test_load_round_unknown_round_fails_closed() -> None:
    with pytest.raises(RoundConfigError, match="(?i)unknown round"):
        load_round("round42")


def test_repo_root_points_at_workspace() -> None:
    root = repo_root()
    assert (root / "pyproject.toml").exists()
    assert (root / "src" / "wsc2026_tools" / "__init__.py").exists()
