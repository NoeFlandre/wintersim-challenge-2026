"""Workspace path resolution and public round-metadata loading.

This module knows where things live in the participant workspace:

* The repository root (all CLI paths resolve relative to the repo root, never
  to the current working directory, so commands behave identically everywhere).
* The local-only ``.challenge/`` scratch area (ignored, never tracked).
* The public ``config/rounds.toml`` metadata used to verify archives.

It also parses ``config/rounds.toml`` strictly (fail closed) into
:class:`RoundConfig` values. There is deliberately no "allow unverified"
escape hatch: an unknown round id or a checksum mismatch must abort.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class RepoPathError(ValueError):
    """Raised when a relative path cannot be resolved under the repo root."""


def repo_root() -> Path:
    """Return the workspace repository root.

    The root is located relative to this file (``src/wsc2026_tools/paths.py``)
    so that CLI behaviour does not depend on the caller's current working
    directory. The result is NOT resolved (no symlink following) to keep paths
    stable and comparable in messages.
    """
    # src/wsc2026_tools/paths.py -> up three levels to the repo root.
    return Path(__file__).resolve().parents[2]


def resolve_repo_path(path: str | Path, *, base: Path | None = None) -> Path:
    """Resolve a user-supplied path against the repository root.

    * Absolute paths are returned unchanged (still resolved as absolute paths).
    * Relative paths are resolved beneath ``base`` (default: the repo root).
      The caller’s current working directory is intentionally not consulted.

    Resolution rules:

    * Traversal operators (``..``) are honoured, so a relative ``../outside``
      path resolves to ``base/../outside`` and may leave the repo. The CLI
      caller is responsible for treating such paths as user errors.
    * Empty strings raise :class:`RepoPathError`.

    This helper makes the documented "paths resolve relative to the repo
    root, not the cwd" contract explicit and shared.
    """
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    text = str(path)
    if not text.strip():
        raise RepoPathError("empty path is not allowed")
    base_path = Path(base) if base is not None else repo_root()
    return (base_path / p).resolve()


def challenge_dir() -> Path:
    """Return the local-only ``.challenge/`` directory (gitignored)."""
    return repo_root() / ".challenge"


def round_source_dir(extract_dir_name: str) -> Path:
    """Return ``.challenge/<extract_dir_name>/source`` for a round."""
    return challenge_dir() / extract_dir_name / "source"


def downloads_dir() -> Path:
    """Return ``.challenge/downloads/`` where local archives are stored."""
    return challenge_dir() / "downloads"


def dist_submissions_dir() -> Path:
    """Return ``dist/submissions/`` where submission archives are written."""
    return repo_root() / "dist" / "submissions"


def submission_strategies_dir() -> Path:
    """Return the participant-owned submission source directory."""
    return repo_root() / "submission" / "response_strategies"


def rounds_config_path() -> Path:
    """Return the path to ``config/rounds.toml``."""
    return repo_root() / "config" / "rounds.toml"


@dataclass(frozen=True)
class RoundConfig:
    """Public, validated metadata for a single challenge round."""

    round_id: str
    archive_filename: str
    expected_sha256: str
    extract_dir_name: str
    practice_only: bool
    marker_relpaths: tuple[str, ...] = field(default_factory=tuple)


class RoundConfigError(ValueError):
    """Raised when public round metadata is missing, malformed, or unknown."""


def _coerce_markers(raw: object, round_id: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        raise RoundConfigError(f"round {round_id!r}: 'marker_relpaths' must be a non-empty list")
    markers: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item:
            raise RoundConfigError(
                f"round {round_id!r}: each marker path must be a non-empty string"
            )
        normalized = item.replace("\\", "/").lstrip("/")
        if ".." in normalized.split("/"):
            raise RoundConfigError(
                f"round {round_id!r}: marker path {item!r} must not traverse parents"
            )
        if not normalized:
            raise RoundConfigError(
                f"round {round_id!r}: marker path {item!r} is empty after normalization"
            )
        markers.append(normalized)
    return tuple(markers)


def _coerce_sha256(raw: object, round_id: str) -> str:
    if not isinstance(raw, str):
        raise RoundConfigError(f"round {round_id!r}: 'expected_sha256' must be a string")
    value = raw.strip().lower()
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise RoundConfigError(f"round {round_id!r}: 'expected_sha256' must be 64 hex characters")
    return value


def load_rounds() -> dict[str, RoundConfig]:
    """Load and validate all rounds from ``config/rounds.toml``.

    Raises :class:`RoundConfigError` if the file is missing, malformed, or
    contains an invalid round definition.
    """
    path = rounds_config_path()
    if not path.is_file():
        raise RoundConfigError(f"rounds config not found at {path}")
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover - defensive
        raise RoundConfigError(f"invalid TOML in {path}: {exc}") from exc

    raw_rounds = data.get("rounds")
    if not isinstance(raw_rounds, list) or not raw_rounds:
        raise RoundConfigError(f"{path}: missing or empty top-level 'rounds' array")

    result: dict[str, RoundConfig] = {}
    for entry in raw_rounds:
        if not isinstance(entry, dict):
            raise RoundConfigError("each entry under 'rounds' must be a table")
        round_id = entry.get("round_id")
        if not isinstance(round_id, str) or not round_id:
            raise RoundConfigError("each round must have a non-empty 'round_id'")
        if round_id in result:
            raise RoundConfigError(f"duplicate round id {round_id!r} in config")

        required_strings = ("archive_filename", "extract_dir_name")
        for key in required_strings:
            val = entry.get(key)
            if not isinstance(val, str) or not val:
                raise RoundConfigError(f"round {round_id!r}: '{key}' must be a non-empty string")

        practice = entry.get("practice_only", False)
        if not isinstance(practice, bool):
            raise RoundConfigError(f"round {round_id!r}: 'practice_only' must be a boolean")

        result[round_id] = RoundConfig(
            round_id=round_id,
            archive_filename=entry["archive_filename"],
            extract_dir_name=entry["extract_dir_name"],
            expected_sha256=_coerce_sha256(entry["expected_sha256"], round_id),
            practice_only=practice,
            marker_relpaths=_coerce_markers(entry.get("marker_relpaths"), round_id),
        )
    return result


def load_round(round_id: str) -> RoundConfig:
    """Load a single round by id; fail closed if unknown.

    Raises :class:`RoundConfigError` for an unknown round id.
    """
    rounds = load_rounds()
    if round_id not in rounds:
        raise RoundConfigError(
            f"unknown round id {round_id!r}; configured rounds: "
            f"{', '.join(sorted(rounds)) or '(none)'}"
        )
    return rounds[round_id]
