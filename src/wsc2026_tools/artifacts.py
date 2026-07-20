"""Verified, atomic, safe extraction of challenge archives.

The bootstrap step is the only place organizer source enters the workspace.
It must be defensive:

* Verify the published SHA-256 before doing anything else.
* Reject unsafe zip members (absolute paths, ``..`` traversal, symlinks, and
  any member that would escape the destination directory).
* Extract into a temporary sibling directory and only ``rename`` the validated
  tree into place once every required marker exists, so a failure never leaves
  a partial installation.
* Never modify the source archive.

All public functions raise :class:`BootstrapError` with concise, actionable
messages on any problem.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path

from wsc2026_tools.paths import load_round, repo_root, round_source_dir

__all__ = [
    "BootstrapError",
    "extract_archive",
    "bootstrap_round",
    "sha256_of_file",
]


class BootstrapError(Exception):
    """Raised when archive verification or extraction fails."""


def sha256_of_file(path: Path, *, chunk_size: int = 1 << 20) -> str:
    """Return the lowercase hex SHA-256 of ``path``."""
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_member(name: str, dest_root: Path) -> Path:
    """Return the safe destination path for a zip member, or raise.

    Rejects absolute members, ``..`` traversal, symlink entries, drive-anchored
    names, and any member that resolves outside ``dest_root``.
    """
    # Reject absolute paths on any OS. zipfile normalizes separators to "/",
    # but be defensive about backslashes and drive letters too.
    normalized = name.replace("\\", "/")
    if not normalized:
        raise BootstrapError(f"refusing zip member with empty name: {name!r}")
    if normalized.startswith("/"):
        raise BootstrapError(f"refusing absolute zip member: {name!r}")
    # Reject Windows drive-anchored members like "C:/..." or "C:\\...".
    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        raise BootstrapError(f"refusing drive-anchored zip member: {name!r}")

    # Resolve without following symlinks at the filesystem level by checking the
    # normalized components lexically first.
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if any(part == ".." for part in parts):
        raise BootstrapError(f"refusing traversal zip member: {name!r}")

    target = dest_root.joinpath(*parts)
    # Final defense: ensure the resolved path stays inside dest_root.
    dest_root_resolved = dest_root.resolve()
    # Use os.path.abspath-style join to evaluate without requiring the file to
    # exist yet (Path.resolve follows symlinks only for existing paths).
    target_abs = Path(os.path.normpath(os.path.join(str(dest_root_resolved), *parts)))
    if not _is_relative_to(target_abs, dest_root_resolved):
        raise BootstrapError(f"refusing zip member that escapes destination: {name!r}")
    return target


def _iter_safe_members(zf: zipfile.ZipFile, dest_root: Path):
    """Yield ``(info, target_path)`` for every safe regular-file member."""
    for info in zf.infolist():
        # Reject directory entries' content (nothing to write) but allow them
        # to imply parent dirs for subsequent files.
        is_dir = info.is_dir() or info.filename.endswith("/")
        # Detect symlink members via the unix mode stored in external_attr.
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise BootstrapError(f"refusing symlink zip member: {info.filename!r}")
        target = _validate_member(info.filename, dest_root)
        if is_dir:
            # Only allow directory entries that are themselves safe; we create
            # directories on demand for files, so skip pure-directory members.
            continue
        if mode != 0 and mode != stat.S_IFREG:
            raise BootstrapError(f"refusing non-regular zip member: {info.filename!r}")
        yield info, target


def extract_archive(
    archive: Path,
    expected_sha256: str,
    dest: Path,
    *,
    marker_relpaths: list[str] | tuple[str, ...],
) -> None:
    """Verify and extract ``archive`` into ``dest``.

    Steps:
      1. Verify the archive SHA-256 equals ``expected_sha256``.
      2. Open the archive and reject any unsafe member.
      3. Extract into a temporary sibling of ``dest``.
      4. Verify every marker path exists in the temp tree.
      5. Atomically rename the temp tree into ``dest``.

    The source archive is never modified. On any failure, the temporary tree
    is removed and ``dest`` is left untouched.
    """
    archive = Path(archive)
    dest = Path(dest)
    expected = expected_sha256.strip().lower()

    if not archive.is_file():
        raise BootstrapError(f"archive not found: {archive}")

    actual = sha256_of_file(archive)
    if actual != expected:
        raise BootstrapError(
            f"checksum mismatch for {archive.name}: expected {expected}, got {actual}"
        )

    dest_parent = dest.parent
    dest_parent.mkdir(parents=True, exist_ok=True)

    # Use a temporary sibling directory so an interrupted extraction cannot
    # leave a half-populated ``dest`` behind.
    tmp_root = Path(tempfile.mkdtemp(prefix=f".{dest.name}-extract-", dir=str(dest_parent)))
    try:
        tmp_dest = tmp_root / "source"
        tmp_dest.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive) as zf:
            bad = zf.testzip()
            if bad is not None:
                raise BootstrapError(f"corrupt zip member: {bad!r}")
            members = list(_iter_safe_members(zf, tmp_dest))
            for info, target in members:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("wb") as out:
                    shutil.copyfileobj(src, out)

        # Validate markers inside the temp tree before promoting it.
        missing = [m for m in marker_relpaths if not (tmp_dest / m).exists()]
        if missing:
            raise BootstrapError(
                "missing required marker paths after extraction: " + ", ".join(missing)
            )

        # Atomic promotion. If dest exists, fail loudly rather than clobber.
        if dest.exists():
            raise BootstrapError(f"destination already exists; refusing to overwrite: {dest}")
        os.replace(tmp_dest, dest)
    except Exception:
        # Clean up the temp tree on any failure.
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise
    finally:
        # Remove the temp wrapper if it still exists (success path renamed
        # tmp_dest out of it, leaving an empty wrapper).
        if tmp_root.exists():
            shutil.rmtree(tmp_root, ignore_errors=True)


def bootstrap_round(round_id: str, archive: Path) -> Path:
    """Bootstrap a configured round from a local archive.

    Resolves paths relative to the repository root (never the cwd). Returns the
    path to the freshly extracted source tree.
    """
    config = load_round(round_id)
    root = repo_root()
    archive = Path(archive)
    if not archive.is_absolute():
        archive = root / archive

    dest = round_source_dir(config.extract_dir_name)
    extract_archive(
        archive,
        config.expected_sha256,
        dest,
        marker_relpaths=list(config.marker_relpaths),
    )
    return dest
