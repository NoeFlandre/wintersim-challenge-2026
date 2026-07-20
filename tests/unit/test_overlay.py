"""Unit tests for the participant strategy overlay (wsc2026_tools.overlay).

The overlay copies participant-owned files from submission/response_strategies
into the local organizer tree (.challenge/<round>/source/response_strategies)
without touching organizer-owned files, caches, tests, or unknown artifacts.

These tests build synthetic source/destination trees in tmp_path; they never
touch real organizer code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wsc2026_tools.overlay import OverlayError, overlay_response_strategies


def _make_tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


# Files the participant owns and that may be overlaid.
SUBMISSION_FILES: dict[str, str] = {
    "user_strategy.py": "# participant user_strategy\n",
    "README.md": "# participant readme\n",
}

# Files that are organizer-owned and must be preserved untouched, never copied
# over or deleted by the overlay.
ORGANIZER_FILES: dict[str, str] = {
    "__init__.py": "# organizer package init\n",
    "default_strategy.py": "# organizer default strategy\n",
    "strategy_validation.py": "# organizer validation\n",
}


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    _make_tree(submission, SUBMISSION_FILES)

    dest = tmp_path / "source" / "response_strategies"
    dest.mkdir(parents=True)
    _make_tree(dest, ORGANIZER_FILES)
    # Pre-place an older participant file to prove overwrite works.
    (dest / "user_strategy.py").write_text("# STALE participant copy\n")
    return submission, dest


def test_overlay_copies_participant_files_and_preserves_organizer(tmp_path: Path) -> None:
    submission, dest = _setup(tmp_path)

    copied = overlay_response_strategies(submission, dest)

    assert set(copied) == {"user_strategy.py", "README.md"}
    # Participant files updated.
    assert (dest / "user_strategy.py").read_text() == "# participant user_strategy\n"
    assert (dest / "README.md").read_text() == "# participant readme\n"
    # Organizer files untouched.
    assert (dest / "__init__.py").read_text() == "# organizer package init\n"
    assert (dest / "default_strategy.py").read_text() == "# organizer default strategy\n"
    assert (dest / "strategy_validation.py").read_text() == "# organizer validation\n"


def test_overlay_is_idempotent(tmp_path: Path) -> None:
    submission, dest = _setup(tmp_path)

    first = overlay_response_strategies(submission, dest)
    second = overlay_response_strategies(submission, dest)

    assert first == second
    assert (dest / "user_strategy.py").read_text() == "# participant user_strategy\n"


def test_overlay_does_not_delete_organizer_files_when_submission_is_small(
    tmp_path: Path,
) -> None:
    submission, dest = _setup(tmp_path)
    # Remove README from submission side; overlay must not delete dest files.
    (submission / "README.md").unlink()

    overlay_response_strategies(submission, dest)

    # Organizer files still present.
    for name in ORGANIZER_FILES:
        assert (dest / name).exists(), f"overlay must not delete organizer file {name}"
    # Stale participant file still updated (not deleted just because README left).
    assert (dest / "user_strategy.py").read_text() == "# participant user_strategy\n"


def test_overlay_skips_caches_and_hidden_files_without_failing(tmp_path: Path) -> None:
    submission, dest = _setup(tmp_path)
    # Benign cache/OS artifacts that must be skipped, never copied, no failure.
    (submission / "__pycache__").mkdir()
    (submission / "__pycache__" / "x.pyc").write_text("pyc")
    (submission / "user_strategy.pyc").write_text("pyc")
    (submission / ".DS_Store").write_text("ds")

    copied = overlay_response_strategies(submission, dest)

    # Only allowlisted participant files synchronized.
    assert set(copied) == {"user_strategy.py", "README.md"}
    # Cruft never landed in dest.
    assert not (dest / "__pycache__").exists()
    assert not (dest / "user_strategy.pyc").exists()
    assert not (dest / ".DS_Store").exists()


def test_overlay_refuses_to_copy_unknown_source_files(tmp_path: Path) -> None:
    submission, dest = _setup(tmp_path)
    # Non-allowlisted source/data/test files must be a hard error.
    (submission / "helpers.py").write_text("# NOT allowlisted\n")
    (submission / "test_strategy.py").write_text("# test file\n")

    with pytest.raises(OverlayError, match="(?i)not allowlisted|disallowed|refus"):
        overlay_response_strategies(submission, dest)

    # The disallowed file must not have landed in dest.
    assert not (dest / "helpers.py").exists()
    assert not (dest / "test_strategy.py").exists()


def test_overlay_refuses_symlink_submission_file(tmp_path: Path) -> None:
    submission, dest = _setup(tmp_path)
    target = tmp_path / "evil.txt"
    target.write_text("evil")
    (submission / "README.md").unlink()
    (submission / "README.md").symlink_to(target)

    with pytest.raises(OverlayError, match="(?i)symlink"):
        overlay_response_strategies(submission, dest)


def test_overlay_requires_directories(tmp_path: Path) -> None:
    with pytest.raises(OverlayError, match="(?i)not a directory|missing"):
        overlay_response_strategies(tmp_path / "nope1", tmp_path / "nope2")


def test_overlay_rejects_subdirectory_in_submission(tmp_path: Path) -> None:
    submission, dest = _setup(tmp_path)
    (submission / "subpkg").mkdir()
    (submission / "subpkg" / "x.py").write_text("x")

    with pytest.raises(OverlayError, match="(?i)subpkg|not allowlisted|refus|disallow"):
        overlay_response_strategies(submission, dest)


def test_overlay_rejects_non_file_entry(tmp_path: Path) -> None:
    submission, dest = _setup(tmp_path)
    # A FIFO / socket entry triggers the `not entry.is_file()` branch.
    import os

    fifo_path = submission / "fifo"
    os.mkfifo(fifo_path)
    try:
        with pytest.raises(OverlayError, match="(?i)not allowlisted|refus|disallow"):
            overlay_response_strategies(submission, dest)
    finally:
        os.remove(fifo_path)


def test_overlay_skips_pycache_suffix_at_top_level(tmp_path: Path) -> None:
    submission, dest = _setup(tmp_path)
    # A loose .pyc next to allowlisted files must still be skipped via the
    # _SKIP_SUFFIXES branch of _is_skip (not just via the __pycache__ dir name).
    (submission / "user_strategy.pyc").write_text("pyc")
    copied = overlay_response_strategies(submission, dest)
    assert "user_strategy.py" in copied
    assert not (dest / "user_strategy.pyc").exists()
