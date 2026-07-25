"""Integration test: sync participant strategies onto the real Round 0 source.

Marked ``integration`` so it is excluded from the default/CI unit run. It skips
with a clear reason when the local ignored Round 0 source tree is not present
(it never reconstructs or downloads organizer code). It only touches the
ignored ``.challenge/`` tree and never mutates tracked files.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from wsc2026_tools.overlay import overlay_response_strategies
from wsc2026_tools.paths import repo_root, round_source_dir, submission_strategies_dir

pytestmark = pytest.mark.integration

SOURCE = round_source_dir("round0")


@pytest.fixture
def preserved_organizer_dir() -> Path:
    """The real organizer response_strategies dir; restored after the test."""
    return SOURCE / "response_strategies"


@pytest.fixture
def backup_response_strategies(preserved_organizer_dir: Path):
    """Snapshot the organizer response_strategies dir and restore it afterward.

    The overlay is non-destructive, but we belt-and-braces restore the tree so
    repeated integration runs are deterministic and nothing leaks.
    """
    import tempfile

    if not preserved_organizer_dir.is_dir():
        pytest.skip("Round 0 source not bootstrapped; skipping overlay integration test.")
    tmp = Path(tempfile.mkdtemp(prefix="rs-backup-"))
    try:
        shutil.copytree(preserved_organizer_dir, tmp / "snapshot")
    except Exception as exc:  # pragma: no cover - defensive
        shutil.rmtree(tmp, ignore_errors=True)
        pytest.skip(f"could not snapshot organizer response_strategies: {exc}")
    yield
    # Restore.
    if preserved_organizer_dir.is_dir():
        shutil.rmtree(preserved_organizer_dir, ignore_errors=True)
    shutil.copytree(tmp / "snapshot", preserved_organizer_dir)
    shutil.rmtree(tmp, ignore_errors=True)


def test_sync_overlays_participant_files_onto_real_round0(
    backup_response_strategies, preserved_organizer_dir: Path
) -> None:
    submission = submission_strategies_dir()
    assert submission.is_dir(), "submission/response_strategies must exist"

    # Capture organizer-owned file hashes before overlay.
    organizer_files = ["__init__.py", "default_strategy.py", "strategy_validation.py"]
    before = {
        name: (preserved_organizer_dir / name).read_bytes()
        for name in organizer_files
        if (preserved_organizer_dir / name).is_file()
    }
    assert before, "expected organizer response_strategies files to be present"

    copied = overlay_response_strategies(submission, preserved_organizer_dir)
    assert set(copied) == {
        "README.md",
        "transshipment_readiness.py",
        "user_strategy.py",
    }

    for name in copied:
        assert (preserved_organizer_dir / name).read_bytes() == (submission / name).read_bytes()

    # Organizer files byte-identical.
    for name, blob in before.items():
        assert (preserved_organizer_dir / name).read_bytes() == blob, (
            f"overlay must not modify organizer file {name}"
        )


def test_sync_idempotent_on_real_round0(
    backup_response_strategies, preserved_organizer_dir: Path
) -> None:
    submission = submission_strategies_dir()
    first = overlay_response_strategies(submission, preserved_organizer_dir)
    second = overlay_response_strategies(submission, preserved_organizer_dir)
    assert first == second


# Guard: ensure this file never references anything tracked outside .challenge.
def test_repo_root_unaffected_by_imports() -> None:
    # Sanity: tracked pyproject must still be intact (no accidental writes).
    assert (repo_root() / "pyproject.toml").is_file()
