"""Integration test: run the real Round 0 smoke simulation.

Marked ``integration`` (excluded from CI). Skips with a clear reason when the
local ignored Round 0 source tree is not bootstrapped. It only touches the
ignored ``.challenge/`` tree and never mutates tracked files.
"""

from __future__ import annotations

import pytest

from wsc2026_tools.cli import run_smoke
from wsc2026_tools.paths import round_source_dir

pytestmark = pytest.mark.integration

SOURCE = round_source_dir("round0")


def test_round0_smoke_imports_and_steps() -> None:
    if not SOURCE.is_dir():
        pytest.skip("Round 0 source not bootstrapped; skipping smoke integration test.")
    result = run_smoke(SOURCE, days=1, timeout=600.0)
    if result.returncode != 0:
        pytest.fail(
            f"smoke run failed (exit {result.returncode}).\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
    assert "SMOKE_OK" in result.stdout
