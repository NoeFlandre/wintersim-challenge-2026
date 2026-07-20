"""Compliant submission packager.

Builds a deterministic ZIP archive under ``dist/submissions/`` containing a
single top-level directory that holds only allowlisted participant-owned
files. The archive is what a team would submit to the organizers.

Compliance enforced here:

* Round 0 is never packaged (it is a non-scored practice round).
* Team names must be non-empty and non-placeholder.
* Default archive names follow the current website convention:
  ``Round1_TEAM.zip``, ``Round2_TEAM.zip``, ``HiddenRound_TEAM.zip``.
  (The PDF uses ``TEAM_Round1.zip``; this must be reconfirmed with organizers.)
* The archive contains only ``response_strategies/user_strategy.py``,
  ``response_strategies/README.md``, and any future explicitly allowlisted
  participant-owned response modules/data. Organizer code, default_strategy.py,
  strategy_validation.py, inputs, outputs, tests, caches, ``.git`` files,
  ``.DS_Store``, pyc, secrets, and dev tooling are never included.
* Symlinks are rejected.
* Submission imports are inspected with ``ast``: code may import only the
  Python standard library, participant modules within ``response_strategies``,
  and documented organizer modules (``maritime_data_context``,
  ``simulation_model``).

The packager never sends or uploads the archive.
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
import zipfile
from pathlib import Path

__all__ = ["PackagerError", "package_submission", "team_to_slug"]


class PackagerError(ValueError):
    """Raised when a submission cannot be packaged compliantly."""


# Round id -> (archive prefix, top-level directory prefix).
_ROUND_AFFIXES: dict[str, tuple[str, str]] = {
    "1": ("Round1", "Round1"),
    "2": ("Round2", "Round2"),
    "hidden": ("HiddenRound", "HiddenRound"),
}

# Participant-owned files that may appear in the archive's response_strategies.
# Adding to this set is a reviewed decision that expands the submission surface.
_ALLOWED_SUBMISSION_FILES: frozenset[str] = frozenset(
    {
        "user_strategy.py",
        "README.md",
    }
)

# Cache / OS artifacts that must not exist anywhere in the submission tree.
_FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".DS_Store",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".git",
        ".gitignore",
        ".env",
    }
)
_FORBIDDEN_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo", ".pyd", ".so")

# Organizer-owned response_strategies files that must never be packaged.
_ORGANIZER_FILES: frozenset[str] = frozenset(
    {
        "default_strategy.py",
        "strategy_validation.py",
        "__init__.py",
    }
)

# Modules that submission code may import beyond the standard library and
# participant modules within response_strategies.
_ALLOWED_IMPORT_MODULES: frozenset[str] = frozenset(
    {
        "maritime_data_context",
        "simulation_model",
        "response_strategies",
    }
)

# stdlib module names that are forbidden in submission runtime code because
# they enable side effects the rules disallow (network, subprocess, filesystem,
# environment, wall-clock, cwd). This is a conservative denylist of the common
# offenders; the allowlist for third-party imports is "stdlib + documented
# organizer modules + participant modules".
_FORBIDDEN_STDLIB_MODULES: frozenset[str] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "http",
        "urllib",
        "requests",
        "socketserver",
        "asyncio",
        "multiprocessing",
        "threading",
        "ctypes",
        "pty",
        "pathlib",
        "io",
        "fcntl",
    }
)

_PLACEHOLDER_TEAMS: frozenset[str] = frozenset(
    {
        "",
        "placeholder",
        "your-team",
        "teamname",
        "team-name",
        "todo",
        "xxx",
        "test",
        "testteam",
    }
)


def team_to_slug(team: str) -> str:
    """Sanitize a team name into a conservative archive slug.

    Keeps ASCII letters, digits, and hyphens; collapses runs/edges. Uppercases
    the result for the default website naming convention.
    """
    cleaned = re.sub(r"[^A-Za-z0-9-]+", "-", team.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    if not cleaned:
        raise PackagerError(f"team name {team!r} has no usable characters after sanitizing")
    return cleaned


def _validate_team(team: str) -> str:
    if not isinstance(team, str):
        raise PackagerError("team name must be a string")
    stripped = team.strip()
    lowered = stripped.lower().replace("_", "-")
    if lowered in _PLACEHOLDER_TEAMS:
        raise PackagerError(
            f"team name {team!r} is empty or a placeholder; provide a real team name"
        )
    if lowered.startswith("placeholder") or lowered.endswith("placeholder"):
        raise PackagerError(
            f"team name {team!r} looks like a placeholder; provide a real team name"
        )
    if "todo" in lowered or "placeholder" in lowered:
        raise PackagerError(
            f"team name {team!r} looks like a placeholder; provide a real team name"
        )
    return team_to_slug(team)


def _validate_round(round_id: str) -> tuple[str, str]:
    if round_id == "round0":
        raise PackagerError("Round 0 is a practice round and must never be packaged or submitted.")
    if round_id not in _ROUND_AFFIXES:
        raise PackagerError(
            f"unknown round id {round_id!r}; expected one of {sorted(_ROUND_AFFIXES)}"
        )
    return _ROUND_AFFIXES[round_id]


def _walk_submission(submission_dir: Path) -> list[Path]:
    """Return the participant files; raise on any forbidden entry.

    ``submission_dir`` is the participant ``response_strategies`` directory
    itself. Allowed paths are relative POSIX names within the allowlist.
    """
    if not submission_dir.is_dir():
        raise PackagerError(f"submission directory not found: {submission_dir}")
    collected: list[Path] = []
    forbidden_seen: list[str] = []
    organizer_seen: list[str] = []
    for entry in sorted(submission_dir.rglob("*")):
        rel = entry.relative_to(submission_dir)
        parts = rel.parts
        # Skip well-known cache/OS artifacts: they are never in the allowlist and
        # must never enter an archive, but they should not abort packaging of an
        # otherwise-clean tree.
        if any(p in _FORBIDDEN_NAMES for p in parts):
            continue
        if entry.suffix in _FORBIDDEN_SUFFIXES:
            continue
        if entry.is_symlink():
            raise PackagerError(f"refusing symlink in submission: {rel}")
        if not entry.is_file():
            continue
        normalized = rel.as_posix()
        if entry.name in _ORGANIZER_FILES:
            organizer_seen.append(normalized)
            continue
        if normalized not in _ALLOWED_SUBMISSION_FILES:
            forbidden_seen.append(normalized)
            continue
        collected.append(entry)

    if organizer_seen:
        raise PackagerError(
            "refusing to package organizer-owned files: " + ", ".join(sorted(organizer_seen))
        )
    if forbidden_seen:
        raise PackagerError(
            "refusing to package disallowed submission entries: "
            + ", ".join(sorted(set(forbidden_seen)))
            + f". Allowed: {', '.join(sorted(_ALLOWED_SUBMISSION_FILES))}"
        )
    if not collected:
        raise PackagerError(
            "no allowlisted participant files found to package "
            f"(expected {', '.join(sorted(_ALLOWED_SUBMISSION_FILES))})"
        )
    if not any(f.name == "user_strategy.py" for f in collected):
        raise PackagerError(
            "submission response_strategies is missing required file "
            "'user_strategy.py'. A submission without a user strategy is "
            "not a valid package; add user_strategy.py and retry."
        )
    return collected


def _validate_imports(files: list[Path], submission_dir: Path) -> None:
    """Inspect every packaged .py file's imports with ast.

    Imports are validated against the actual set of packaged files:

    * ``ast.Import name`` may be a stdlib module or an entry in
      ``_ALLOWED_IMPORT_MODULES`` (the documented organizer modules).
    * ``ast.ImportFrom module=`` may be stdlib, allowed organizer, or a
      module that resolves to a packaged file in the submission.
    * ``ast.ImportFrom level > 0`` is a relative import; the level + module
      are resolved relative to the importing file's package (the submission
      ``response_strategies`` root). The resulting dotted name MUST be in the
      packaged module set, otherwise the import references a file that the
      packager will not ship. ``from ..escape`` (level > 1) is rejected
      outright because it leaves the submission package.
    """
    # Module names actually being packaged (dotted). The submission_dir IS
    # the `response_strategies` package when the archive is extracted into
    # the organizer tree, so every file in submission_dir is a submodule of
    # `response_strategies`. Self-imports like
    # `from .user_strategy import UserStrategy` resolve to a name in this set.
    packaged_modules: set[str] = {
        "response_strategies."
        + f.relative_to(submission_dir).with_suffix("").as_posix().replace("/", ".")
        for f in files
        if f.suffix == ".py"
    }
    # Also include the bare module name for files at the submission root
    # (no subpackage), because some Python import styles compare without the
    # response_strategies prefix; the relative-resolver will produce the full
    # form, so both keys must exist for comparisons to be symmetric.
    packaged_modules |= {
        f.relative_to(submission_dir).with_suffix("").as_posix().replace("/", ".")
        for f in files
        if f.suffix == ".py" and "/" not in f.relative_to(submission_dir).as_posix()
    }
    offenders: list[str] = []
    for f in files:
        if f.suffix != ".py":
            continue
        rel = f.relative_to(submission_dir)
        # The dotted "package" name of the file (everything except the last
        # component). For submission_root/user_strategy.py this is the bare
        # 'response_strategies' package. For submission_root/sub/x.py this is
        # 'response_strategies.sub'.
        parent_rel = rel.parent.as_posix()
        if parent_rel in ("", "."):
            file_pkg = "response_strategies"
        else:
            file_pkg = "response_strategies." + parent_rel.replace("/", ".")

        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError as exc:
            raise PackagerError(f"{f}: syntax error: {exc}") from exc
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    root = mod.split(".", 1)[0]
                    if root == "response_strategies" and mod != "response_strategies":
                        # An absolute 'import response_strategies.<x>' must name
                        # a real packaged module.
                        if mod not in packaged_modules:
                            offenders.append(
                                f"{f.name}: absolute import resolves to missing "
                                f"participant module {mod!r} (not in packaged "
                                f"files: {sorted(packaged_modules)})"
                            )
                        continue
                    if not _is_import_allowed(mod):
                        offenders.append(f"{f.name}: disallowed import {mod!r}")
                continue
            if isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    # Relative import. Resolve to a dotted name relative to
                    # this file's package, then check it against the packaged
                    # module set.
                    base_parts = file_pkg.split(".")
                    # level=1: anchor = file_pkg
                    # level=2: anchor = parent of file_pkg
                    # level=L: anchor = file_pkg with (L-1) trailing parts dropped
                    drop = node.level - 1
                    if drop >= len(base_parts):
                        offenders.append(
                            f"{f.name}: relative import level {node.level} "
                            f"from package {file_pkg!r} escapes the submission package"
                        )
                        continue
                    anchor_parts = base_parts[: len(base_parts) - drop]
                    anchor = ".".join(anchor_parts)
                    suffix = node.module
                    aliases = list(node.names)
                    if suffix:
                        # ``from .module import a, b`` -- a single target module.
                        resolved = f"{anchor}.{suffix}" if anchor else suffix
                        if not resolved:
                            offenders.append(f"{f.name}: relative import has empty anchor")
                            continue
                        if resolved not in packaged_modules:
                            offenders.append(
                                f"{f.name}: relative import resolves to missing "
                                f"module {resolved!r} (not in packaged files: "
                                f"{sorted(packaged_modules)})"
                            )
                    elif not anchor:
                        offenders.append(f"{f.name}: relative import has no anchor and no module")
                        continue
                    elif any(a.name == "*" for a in aliases):
                        offenders.append(f"{f.name}: relative star import is not allowed")
                        continue
                    else:
                        # ``from . import a, b`` -- each alias resolves to a
                        # submodule of ``anchor``.
                        for alias in aliases:
                            resolved = f"{anchor}.{alias.name}" if anchor else alias.name
                            if resolved not in packaged_modules:
                                offenders.append(
                                    f"{f.name}: relative import resolves to "
                                    f"missing module {resolved!r} (not in "
                                    f"packaged files: {sorted(packaged_modules)})"
                                )
                    continue
                # Absolute import.
                mod = node.module or ""
                if not mod:
                    # ``from x import a, b`` without a module attr is unusual;
                    # treat each alias as an absolute name and validate it.
                    for alias in node.names:
                        if not _is_import_allowed(alias.name):
                            offenders.append(f"{f.name}: disallowed import {alias.name!r}")
                    continue
                if any(a.name == "*" for a in node.names) and mod == "response_strategies":
                    offenders.append(
                        f"{f.name}: star import of the submission package is not allowed"
                    )
                    continue
                if mod == "response_strategies":
                    # ``from response_strategies import <name>`` treats each
                    # alias as a participant submodule; require each one to be
                    # a real packaged module.
                    for alias in node.names:
                        candidate = f"response_strategies.{alias.name}"
                        if candidate not in packaged_modules:
                            offenders.append(
                                f"{f.name}: absolute import resolves to missing "
                                f"participant module {candidate!r} (not in "
                                f"packaged files: {sorted(packaged_modules)})"
                            )
                    continue
                if not _is_import_allowed(mod):
                    offenders.append(f"{f.name}: disallowed import {mod!r}")
                    continue
                # The root is allowed (stdlib or organizer entry point).
                # If the root is the local 'response_strategies' package,
                # any submodule must resolve to a packaged file.
                root = mod.split(".", 1)[0]
                if (
                    root == "response_strategies"
                    and mod != "response_strategies"
                    and mod not in packaged_modules
                ):
                    offenders.append(
                        f"{f.name}: absolute import resolves to missing "
                        f"participant module {mod!r} (not in packaged files: "
                        f"{sorted(packaged_modules)})"
                    )
    if offenders:
        raise PackagerError(
            "submission import validation failed: " + "; ".join(sorted(set(offenders)))
        )


def _is_import_allowed(module_name: str) -> bool:
    """Apply the absolute-import rules to a top-level module name."""
    root = module_name.split(".", 1)[0]
    if root in _FORBIDDEN_STDLIB_MODULES:
        return False
    if root in _ALLOWED_IMPORT_MODULES:
        return True
    return bool(_is_stdlib(root))


def _is_stdlib(module_name: str) -> bool:
    """Best-effort stdlib membership check (target Python 3.11+)."""
    if module_name in sys.builtin_module_names:
        return True
    from sys import stdlib_module_names

    return module_name in stdlib_module_names


def _write_deterministic_zip(
    archive: Path, top_dir: str, files: list[Path], submission_dir: Path
) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        info_entries: list[tuple[str, bytes]] = []
        for f in sorted(files):
            rel = f.relative_to(submission_dir).as_posix()
            arcname = f"{top_dir}/response_strategies/{rel}"
            info_entries.append((arcname, f.read_bytes()))
        for arcname, data in info_entries:
            info = zipfile.ZipInfo(arcname)
            info.compress_type = zipfile.ZIP_DEFLATED
            # Fixed timestamp (1980-01-01) and permissions for determinism.
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.create_system = 3
            zf.writestr(info, data)


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def package_submission(
    submission_dir: Path,
    team: str,
    round_id: str,
    dist_dir: Path,
    *,
    report: bool = True,
) -> Path:
    """Build a deterministic submission archive and return its path."""
    slug = _validate_team(team)
    archive_prefix, top_prefix = _validate_round(round_id)
    archive_name = f"{archive_prefix}_{slug}.zip"
    top_dir = f"{top_prefix}_{slug}"

    submission_dir = Path(submission_dir)
    files = _walk_submission(submission_dir)
    _validate_imports(files, submission_dir)

    dist_dir = Path(dist_dir)
    archive = dist_dir / archive_name
    _write_deterministic_zip(archive, top_dir, files, submission_dir)

    if report:
        _print_report(archive, files, submission_dir)
    return archive


def _print_report(archive: Path, files: list[Path], submission_dir: Path) -> None:
    sha = _sha256_of(archive)
    size = archive.stat().st_size
    top = archive.name[: -len(".zip")]
    members: list[str] = []
    for f in sorted(files):
        rel = f.relative_to(submission_dir).as_posix()
        members.append(f"{top}/response_strategies/{rel}")
    print(f"archive: {archive}")
    print(f"sha256: {sha}")
    print(f"size_bytes: {size}")
    print("members:")
    for m in members:
        print(f"  - {m}")
    print(
        "NOTE: the current website uses the 'Round<N>_TEAM.zip' filename order; "
        "the PDF uses 'TEAM_Round<N>.zip'. Confirm with organizers before submitting."
    )
