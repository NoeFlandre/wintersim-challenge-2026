"""Overlay participant-owned response strategies onto the organizer tree.

The organizer source tree (``.challenge/<round>/source``) is the only place
where the simulation actually runs. ``sync`` copies the participant-owned
files from ``submission/response_strategies`` into that tree so the framework
sees the participant ``UserStrategy``.

Hard rules for the overlay:

* Only an explicit allowlist of participant-owned files is copied.
* Organizer-owned files (``__init__.py``, ``default_strategy.py``,
  ``strategy_validation.py``, anything not in the allowlist) are never deleted
  or overwritten by the overlay. (If a future participant file legitimately
  replaces an organizer file, that must be an explicit, reviewed change.)
* Well-known cache/OS artifacts (``__pycache__`` dirs, ``*.pyc``/``*.pyo``,
  ``.DS_Store``) are silently skipped, never copied.
* Any other non-allowlisted regular file (an unknown module, data file, test
  file, etc.) is a hard error: the overlay refuses rather than risk shipping
  unreviewed code.
* Symlinks are rejected.
* The overlay is idempotent and reports exactly which files were copied.
"""

from __future__ import annotations

import shutil
from pathlib import Path

__all__ = ["OverlayError", "overlay_response_strategies", "ALLOWED_OVERLAY_FILES"]


class OverlayError(Exception):
    """Raised when the participant overlay cannot be performed safely."""


# Participant-owned files that may be overlaid onto the organizer tree.
# Adding to this set is a reviewed decision: it expands the submission surface.
ALLOWED_OVERLAY_FILES: frozenset[str] = frozenset(
    {
        "user_strategy.py",
        "transshipment_readiness.py",
        "README.md",
    }
)

# Cache / OS artifacts that are never copied but do not abort the overlay.
_SKIP_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".DS_Store",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)
_SKIP_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo")


def _is_skip(entry: Path) -> bool:
    if entry.name in _SKIP_NAMES:
        return True
    return entry.suffix in _SKIP_SUFFIXES


def _check_tree(submission_dir: Path, dest_dir: Path) -> None:
    if not submission_dir.is_dir():
        raise OverlayError(f"submission source is not a directory: {submission_dir}")
    if not dest_dir.is_dir():
        raise OverlayError(f"overlay destination is not a directory: {dest_dir}")


def _validate_submission_contents(submission_dir: Path) -> list[Path]:
    """Return sorted allowlisted files; skip caches; raise on unknown files."""
    allowed: list[Path] = []
    disallowed: list[str] = []
    seen_allowlisted: set[str] = set()
    for entry in sorted(submission_dir.iterdir()):
        if entry.is_symlink():
            raise OverlayError(f"refusing symlink in submission response_strategies: {entry.name}")
        if _is_skip(entry):
            continue
        if entry.is_dir():
            # No subdirectories are part of the current submission surface.
            disallowed.append(f"{entry.name}/")
            continue
        if not entry.is_file():
            disallowed.append(entry.name)
            continue
        name = entry.name
        if name in ALLOWED_OVERLAY_FILES:
            allowed.append(entry)
            seen_allowlisted.add(name)
        else:
            disallowed.append(name)

    if disallowed:
        raise OverlayError(
            "refusing to overlay non-allowlisted submission files: "
            + ", ".join(sorted(disallowed))
            + f". Allowed files: {sorted(ALLOWED_OVERLAY_FILES)}"
        )
    if "user_strategy.py" not in seen_allowlisted:
        raise OverlayError(
            "submission response_strategies is missing required file "
            "'user_strategy.py'. The overlay refuses to run: running it "
            "would leave a stale strategy at the destination while the rest "
            "of the package is partially updated. Add user_strategy.py and "
            "retry."
        )
    missing_required = sorted(set(ALLOWED_OVERLAY_FILES) - seen_allowlisted)
    if missing_required:
        raise OverlayError(
            "submission response_strategies is missing required candidate files: "
            + ", ".join(missing_required)
            + ". The overlay refuses to run a partial copy: every approved "
            "participant file must be present so the destination is never "
            "left with a stale helper next to a fresh strategy. Add the "
            "missing file(s) and retry."
        )
    return allowed


def overlay_response_strategies(submission_dir: Path, dest_dir: Path) -> list[str]:
    """Copy allowlisted participant files from ``submission_dir`` to ``dest_dir``.

    Returns the sorted list of relative file names that were synchronized.
    Organizer-owned files in ``dest_dir`` are never modified or deleted.
    Idempotent: running twice yields the same result.

    The submission must contain ``user_strategy.py``; without it the overlay
    aborts before any file is copied, so the destination cannot be left in a
    partially-updated state.
    """
    submission_dir = Path(submission_dir)
    dest_dir = Path(dest_dir)
    _check_tree(submission_dir, dest_dir)

    files = _validate_submission_contents(submission_dir)

    copied: list[str] = []
    for src_file in files:
        target = dest_dir / src_file.name
        # Copy2 preserves mtime; write atomically enough for CLI use.
        shutil.copy2(src_file, target)
        copied.append(src_file.name)

    return sorted(copied)
