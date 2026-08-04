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
    (sub / "progress_first_berth.py").write_text("# participant helper\n")
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
    assert {
        member.rsplit("/", 1)[-1] for member in members if "/response_strategies/" in member
    } == {"user_strategy.py", "README.md", "progress_first_berth.py"}
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


def test_package_rejects_submission_missing_user_strategy(tmp_path: Path) -> None:
    """A submission without user_strategy.py is unpackageable.

    This matches the overlay contract: without user_strategy.py there is no
    participant strategy, so the submission is invalid by definition.
    """
    sub = tmp_path / "submission" / "response_strategies"
    sub.mkdir(parents=True)
    (sub / "README.md").write_text("# readme only\n")
    with pytest.raises(PackagerError, match=r"(?i)user_strategy\.py"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_package_walks_submission_root_directly_missing_user_strategy_rejected(
    tmp_path: Path,
) -> None:
    """Packager must inspect the *root* submission directory directly.

    This guards against an accidental regression where the walk is rooted at
    a parent that may not exist or may be the workspace itself.
    """
    sub = tmp_path / "response_strategies"
    sub.mkdir(parents=True)
    (sub / "README.md").write_text("# readme only\n")
    with pytest.raises(PackagerError, match=r"(?i)user_strategy\.py"):
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


def test_relative_import_to_missing_participant_module_rejected(tmp_path: Path) -> None:
    """``from .missing import x`` must fail if no 'missing' file is packaged."""
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from .missing import foo  # no such file in this submission\n"
        "class UserStrategy:\n    pass\n"
    )
    with pytest.raises(PackagerError, match=r"(?i)missing|relative"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_absolute_import_to_missing_participant_module_rejected(tmp_path: Path) -> None:
    """``from response_strategies.missing import x`` must fail."""
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from response_strategies.missing import foo  # not packaged\n"
        "class UserStrategy:\n    pass\n"
    )
    with pytest.raises(PackagerError, match=r"(?i)missing|response_strategies\.missing"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_relative_import_escaping_package_rejected(tmp_path: Path) -> None:
    """``from ..other import foo`` escapes the response_strategies package.

    It must fail because there is no parent package and certainly no packaged
    module called 'other' outside the submission.
    """
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from ..other import foo  # parent traversal\nclass UserStrategy:\n    pass\n"
    )
    with pytest.raises(PackagerError, match=r"(?i)relative|parent|escape"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_relative_import_to_existing_participant_module_allowed(tmp_path: Path) -> None:
    """A relative import whose target IS in the packaged set is allowed.

    A self-import from inside user_strategy.py resolves to
    ``response_strategies.user_strategy`` -- which is itself. This must be
    accepted: the validator should distinguish between 'relative to a missing
    module' and 'relative to a packaged module'.
    """
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from .user_strategy import UserStrategy  # self-reference; valid Python\n"
        "class UserStrategy:\n    pass\n"
    )
    archive = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")
    assert archive.exists()


def test_relative_import_level_above_package_depth_rejected(tmp_path: Path) -> None:
    """`from .. import x` from a top-level submission file escapes the package."""
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from ..other_pkg import foo  # level=2 from response_strategies itself\n"
        "class UserStrategy:\n    pass\n"
    )
    with pytest.raises(PackagerError, match=r"(?i)level|escapes|relative"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_relative_import_in_subpackage_allowed_when_packaged(tmp_path: Path) -> None:
    """A relative import whose target IS packaged is allowed.

    This is the canonical positive case: a self-reference inside
    user_strategy.py at the root resolves to a packaged module.
    """
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from .user_strategy import UserStrategy  # valid self-reference\n"
        "class UserStrategy:\n    pass\n"
    )
    archive = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")
    assert archive.exists()


def test_absolute_import_to_existing_participant_module_allowed(tmp_path: Path) -> None:
    """`from response_strategies.user_strategy import X` is allowed.

    The root 'response_strategies' is the local package; the submodule
    'user_strategy' IS in the packaged set. This must be accepted.
    """
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from response_strategies.user_strategy import UserStrategy  # absolute, valid\n"
        "class UserStrategy:\n    pass\n"
    )
    archive = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")
    assert archive.exists()


def test_ast_import_forbidden_stdlib_rejected(tmp_path: Path) -> None:
    """`import os` style AST imports must be rejected via _is_import_allowed."""
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "import os  # forbidden\n"
        "import sys  # forbidden\n"
        "import requests  # forbidden\n"
        "class UserStrategy:\n    pass\n"
    )
    with pytest.raises(PackagerError, match=r"(?i)disallowed|import"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_ast_import_stdlib_allowed(tmp_path: Path) -> None:
    """Plain stdlib imports are allowed when the module is on the safe list."""
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "import math\n"
        "import statistics\n"
        "from collections import deque\n"
        "class UserStrategy:\n    pass\n"
    )
    archive = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")
    assert archive.exists()


def test_relative_import_without_module_rejected(tmp_path: Path) -> None:
    """`from . import *` (no module attr) at top of package is suspicious.

    A from-import with level > 0 but no module attribute is `from . import x`.
    For a top-level file in the response_strategies package, the anchor IS
    response_strategies itself, and 'response_strategies' must be a packaged
    module (it isn't a .py file). The validator should reject this.
    """
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from . import *  # suspicious; the package itself is not a .py module\n"
        "class UserStrategy:\n    pass\n"
    )
    with pytest.raises(PackagerError, match=r"(?i)missing|relative|import"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_placeholder_team_variants_rejected(tmp_path: Path) -> None:
    """Extra placeholder variants beyond the parameterized set are also rejected."""
    sub = _submission_dir(tmp_path)
    for name in ["placeholder2", "TODO-team", "my-placeholder"]:
        with pytest.raises(PackagerError, match=r"(?i)team"):
            package_submission(sub, team=name, round_id="1", dist_dir=tmp_path / "out")


# --- import validation: every participant import must resolve ----------------


@pytest.mark.parametrize(
    "body",
    [
        "import response_strategies.missing\n",
        "from response_strategies import missing\n",
        "from response_strategies.missing import value\n",
        "from .missing import value\n",
    ],
)
def test_packaging_rejects_imports_to_missing_participant_modules(
    tmp_path: Path, body: str
) -> None:
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(f"{body}class UserStrategy:\n    pass\n")
    with pytest.raises(PackagerError, match=r"(?i)disallowed|missing"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


@pytest.mark.parametrize(
    "body",
    [
        "import response_strategies.user_strategy\n",
        "from response_strategies import user_strategy\n",
        "from response_strategies.user_strategy import UserStrategy\n",
        "from . import user_strategy\n",
    ],
)
def test_packaging_accepts_imports_to_existing_participant_modules(
    tmp_path: Path, body: str
) -> None:
    """Imports whose target IS in the packaged set must be accepted."""
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(f"{body}class UserStrategy:\n    pass\n")
    archive = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")
    assert archive.exists()


def test_relative_import_above_package_rejected(tmp_path: Path) -> None:
    """``from ..other_pkg import foo`` from a top-level submission file escapes."""
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from ..other_pkg import foo\nclass UserStrategy:\n    pass\n"
    )
    with pytest.raises(PackagerError, match=r"(?i)level|escapes"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


def test_packaging_accepts_stdlib_and_organizer_allowlist(tmp_path: Path) -> None:
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "import math\n"
        "import statistics\n"
        "from collections import deque\n"
        "from maritime_data_context import MaritimeDataContext\n"
        "from simulation_model import Model\n"
        "class UserStrategy:\n    pass\n"
    )
    archive = package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")
    assert archive.exists()


def test_packaging_rejects_package_root_star_import(tmp_path: Path) -> None:
    """``from response_strategies import *`` is not justified; reject it.

    A bare star import at the package root forces every public name of the
    submission package into the importer's namespace, defeating the explicit
    allowlist. Reject unless the submission actually contains a sibling
    module that justifies the star; the default baseline does not.
    """
    sub = _submission_dir(tmp_path)
    (sub / "user_strategy.py").write_text(
        "from response_strategies import *\nclass UserStrategy:\n    pass\n"
    )
    with pytest.raises(PackagerError, match=r"(?i)disallowed|star"):
        package_submission(sub, team="ValidTeam", round_id="1", dist_dir=tmp_path / "out")


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
