"""Guard: the unit suite must exercise the submission, not the runtime's copy.

The organizer's source tree carries its own synced copy of
``response_strategies.user_strategy``. Integration tests are collected first
and put that tree on ``sys.path``, so the name can already be cached by the
time a unit test imports it. Whenever the two files have drifted — an edit made
but not yet synced — the whole unit suite would then pass against the stale
copy and say nothing. This test fails instead.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_imported_strategy_is_the_submission() -> None:
    import response_strategies.user_strategy as strategy

    imported = Path(strategy.__file__ or "").resolve()
    submitted = (REPO / "submission/response_strategies/user_strategy.py").resolve()
    assert _sha256(imported) == _sha256(submitted), (
        f"the unit suite imported {imported}, which differs from {submitted}. "
        "Run 'wsc2026 sync --round round2' before the tests."
    )
