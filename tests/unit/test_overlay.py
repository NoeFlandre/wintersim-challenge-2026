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

from wsc2026_tools.overlay import (
    ALLOWED_OVERLAY_FILES,
    REQUIRED_RUNTIME_FILES,
    OverlayError,
    overlay_response_strategies,
)


def _make_tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


# Files the participant owns and that may be overlaid.
SUBMISSION_FILES: dict[str, str] = {
    "user_strategy.py": "# participant user_strategy\n",
    "transshipment_readiness.py": "# participant readiness helper\n",
    "README.md": "# participant readme\n",
}

# Files that are organizer-owned and must be preserved untouched, never copied
# over or deleted by the overlay.
ORGANIZER_FILES: dict[str, str] = {
    "__init__.py": "# organizer package init\n",
    "default_strategy.py": "# organizer default strategy\n",
    "strategy_validation.py": "# organizer validation\n",
}


def test_transshipment_readiness_helper_is_allowlisted() -> None:
    assert "transshipment_readiness.py" in ALLOWED_OVERLAY_FILES


def test_readme_is_allowlisted_but_not_a_required_runtime_file() -> None:
    """README.md is documentation, not a runtime dependency.

    Missing README must not be a required-file failure; only the runtime
    helper pair must be present.
    """
    assert "README.md" in ALLOWED_OVERLAY_FILES
    assert "README.md" not in REQUIRED_RUNTIME_FILES
    assert "user_strategy.py" in REQUIRED_RUNTIME_FILES
    assert "transshipment_readiness.py" in REQUIRED_RUNTIME_FILES


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

    assert set(copied) == {
        "user_strategy.py",
        "transshipment_readiness.py",
        "README.md",
    }
    # Participant files updated.
    assert (dest / "user_strategy.py").read_text() == "# participant user_strategy\n"
    assert (dest / "transshipment_readiness.py").read_text() == "# participant readiness helper\n"
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


@pytest.mark.parametrize("missing", ["transshipment_readiness.py"])
def test_overlay_requires_complete_candidate_without_partial_copy(
    tmp_path: Path,
    missing: str,
) -> None:
    """Only the runtime helper is mandatory. ``README.md`` is optional.

    The overlay must abort on a submission missing the runtime helper, with
    the destination left byte-identical.
    """
    submission, dest = _setup(tmp_path)
    (submission / missing).unlink()
    before = {path.name: path.read_bytes() for path in dest.iterdir() if path.is_file()}

    with pytest.raises(OverlayError, match=missing.replace(".", r"\.")):
        overlay_response_strategies(submission, dest)

    after = {path.name: path.read_bytes() for path in dest.iterdir() if path.is_file()}
    assert after == before


def test_overlay_requires_destination_directory(tmp_path: Path) -> None:
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    (submission / "user_strategy.py").write_text("# user\n")
    (submission / "transshipment_readiness.py").write_text("# helper\n")
    (submission / "README.md").write_text("# readme\n")
    missing_dest = tmp_path / "missing-destination"

    with pytest.raises(OverlayError, match="not a directory|missing"):
        overlay_response_strategies(submission, missing_dest)


def test_overlay_skips_caches_and_hidden_files_without_failing(tmp_path: Path) -> None:
    submission, dest = _setup(tmp_path)
    # Benign cache/OS artifacts that must be skipped, never copied, no failure.
    (submission / "__pycache__").mkdir()
    (submission / "__pycache__" / "x.pyc").write_text("pyc")
    (submission / "user_strategy.pyc").write_text("pyc")
    (submission / ".DS_Store").write_text("ds")

    copied = overlay_response_strategies(submission, dest)

    # Only allowlisted participant files synchronized.
    assert set(copied) == {
        "user_strategy.py",
        "transshipment_readiness.py",
        "README.md",
    }
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


def test_overlay_rejects_submission_missing_user_strategy(tmp_path: Path) -> None:
    """A submission without user_strategy.py is unusable: refuse loudly."""
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    (submission / "README.md").write_text("# only readme\n")
    dest = tmp_path / "source" / "response_strategies"
    dest.mkdir(parents=True)
    (dest / "__init__.py").write_text("org init\n")

    with pytest.raises(OverlayError, match=r"(?i)user_strategy\.py"):
        overlay_response_strategies(submission, dest)


def test_overlay_refuses_to_run_when_dest_stale_strategy_would_be_retained(
    tmp_path: Path,
) -> None:
    """If the submission is missing user_strategy.py the overlay must abort
    BEFORE copying anything, so the dest never silently keeps a stale file.

    This test is a guard against "we copy README.md, then fail, and now dest
    has a fresh README plus a stale user_strategy.py".
    """
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    (submission / "README.md").write_text("# new readme\n")
    # Deliberately no user_strategy.py.

    dest = tmp_path / "source" / "response_strategies"
    dest.mkdir(parents=True)
    (dest / "user_strategy.py").write_text("# STALE user_strategy\n")
    (dest / "README.md").write_text("# old readme\n")
    (dest / "__init__.py").write_text("org init\n")

    with pytest.raises(OverlayError):
        overlay_response_strategies(submission, dest)

    # The dest must not have a partially-overlaid state.
    assert (dest / "README.md").read_text() == "# old readme\n"
    assert (dest / "user_strategy.py").read_text() == "# STALE user_strategy\n"


def test_overlay_succeeds_when_readme_missing_and_preserves_dest_readme(
    tmp_path: Path,
) -> None:
    """README.md is optional. The overlay must copy the two runtime files,
    leave the destination README byte-identical if one exists, and never
    delete or rewrite unchanged files at the destination.
    """
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    (submission / "user_strategy.py").write_text("# new user_strategy\n")
    (submission / "transshipment_readiness.py").write_text("# new helper\n")
    # No README.md on submission side.

    dest = tmp_path / "source" / "response_strategies"
    dest.mkdir(parents=True)
    (dest / "README.md").write_text("# EXISTING destination README\n")
    (dest / "__init__.py").write_text("# organizer\n")

    copied = overlay_response_strategies(submission, dest)

    assert copied == ["transshipment_readiness.py", "user_strategy.py"]
    assert (dest / "user_strategy.py").read_text() == "# new user_strategy\n"
    assert (dest / "transshipment_readiness.py").read_text() == "# new helper\n"
    # The destination README is preserved byte-identical.
    assert (dest / "README.md").read_text() == "# EXISTING destination README\n"
    assert (dest / "__init__.py").read_text() == "# organizer\n"


def test_overlay_succeeds_when_readme_missing_and_dest_has_no_readme(
    tmp_path: Path,
) -> None:
    """README.md is optional. With no README on either side the overlay
    copies only the two runtime files and reports them.
    """
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    (submission / "user_strategy.py").write_text("# user_strategy\n")
    (submission / "transshipment_readiness.py").write_text("# helper\n")

    dest = tmp_path / "source" / "response_strategies"
    dest.mkdir(parents=True)
    (dest / "__init__.py").write_text("# organizer\n")

    copied = overlay_response_strategies(submission, dest)

    assert copied == ["transshipment_readiness.py", "user_strategy.py"]
    assert not (dest / "README.md").exists()


def test_overlay_atomically_rejects_missing_runtime_helper(tmp_path: Path) -> None:
    """transshipment_readiness.py is a required runtime file. If it is
    missing the overlay must abort BEFORE touching the destination, leaving
    any stale helper in place.
    """
    submission = tmp_path / "submission" / "response_strategies"
    submission.mkdir(parents=True)
    (submission / "user_strategy.py").write_text("# new user_strategy\n")
    (submission / "README.md").write_text("# new readme\n")
    # No transshipment_readiness.py.

    dest = tmp_path / "source" / "response_strategies"
    dest.mkdir(parents=True)
    (dest / "user_strategy.py").write_text("# STALE user_strategy\n")
    (dest / "transshipment_readiness.py").write_text("# STALE helper\n")
    (dest / "README.md").write_text("# old readme\n")
    (dest / "__init__.py").write_text("# organizer\n")

    with pytest.raises(OverlayError, match=r"transshipment_readiness\.py"):
        overlay_response_strategies(submission, dest)

    # Destination was not touched.
    assert (dest / "user_strategy.py").read_text() == "# STALE user_strategy\n"
    assert (dest / "transshipment_readiness.py").read_text() == "# STALE helper\n"
    assert (dest / "README.md").read_text() == "# old readme\n"
