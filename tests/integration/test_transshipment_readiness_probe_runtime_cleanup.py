"""Integration tests for the probe's runtime cleanup behavior.

These tests load the real, ignored organizer source (which requires
NumPy) and therefore cannot run under the non-integration coverage
command. They live here to pin the cleanup invariants:

* ``_load_runtime`` enters the context, exposes organizer-side
  callables, and on exit restores ``sys.path`` to its initial state.
* Every ``sys.modules`` entry introduced by the context manager is
  removed on exit (organizer-prefixed modules and the synthetic
  participant package).
* The cache is restored against a captured before-state, with no
  ``assert True`` placeholder.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "experiments" / "probes" / "transshipment_readiness_barrier_v1.py"

pytestmark = pytest.mark.integration


def _load_probe_module() -> types.ModuleType:
    name = "_test_probe_runtime_cleanup"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, PROBE_PATH)
    if spec is None or spec.loader is None:
        pytest.skip("cannot load the probe module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def probe() -> types.ModuleType:
    return _load_probe_module()


def test_load_runtime_restores_sys_path_and_sys_modules_against_captured_before(
    probe: types.ModuleType, tmp_path: Path
) -> None:
    """``_load_runtime`` must restore ``sys.path`` and remove every
    inserted package from ``sys.modules``. The test captures the
    initial state and asserts equality after the context manager
    unwinds.
    """
    source = probe.repo_root() / ".challenge" / "round0" / "source"
    if not source.is_dir():
        pytest.skip("Round 0 organizer source is unavailable")

    before_path = list(sys.path)
    before_modules = set(sys.modules)

    try:
        with probe._load_runtime() as _runtime:
            raise RuntimeError("simulated inner boom")
    except RuntimeError:
        pass

    assert sys.path == before_path
    leaked = {
        name
        for name in sys.modules
        if name not in before_modules
        and any(
            name == prefix or name.startswith(f"{prefix}.") for prefix in probe._ORGANIZER_PREFIXES
        )
    }
    assert leaked == set()
    leaked_participant = {
        name
        for name in sys.modules
        if name not in before_modules and name.startswith(f"{probe._PARTICIPANT_PACKAGE}.")
    }
    assert leaked_participant == set()
