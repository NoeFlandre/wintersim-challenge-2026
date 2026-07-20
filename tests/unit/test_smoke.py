"""Unit tests for the smoke and full-run commands.

These tests build small SYNTHETIC organizer trees (fake scenario_builders,
simulation_model, o2despy) in tmp_path and drive the subprocess-based smoke
runner against them. They never touch the real organizer source.

The synthetic trees satisfy the same contract the smoke driver assumes:
``scenario_builders.create_with_disruption()`` returns a context object and
``simulation_model.Model(context, seed=2026)`` returns an object with a
``run(duration=...)`` method.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from wsc2026_tools.cli import build_parser, run_smoke


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))


def _synthetic_tree(
    root: Path,
    *,
    model_run_body: str = "pass",
    create_body: str = "return {'kind': 'context'}",
) -> Path:
    """Build a synthetic organizer source tree rooted at ``root``."""
    # scenario_builders
    _write(
        root / "scenario_builders" / "__init__.py",
        f"""
        def create_with_disruption():
            {create_body}
        """,
    )
    # simulation_model
    _write(
        root / "simulation_model" / "__init__.py",
        f"""
        class Model:
            def __init__(self, context, seed=2026):
                self.context = context
                self.seed = seed
                self.run_calls = []
            def run(self, *, duration=None):
                self.run_calls.append(duration)
                {model_run_body}
        """,
    )
    # o2despy/o2des so PYTHONPATH source/o2despy resolves `import o2des`
    _write(
        root / "o2despy" / "o2des" / "__init__.py",
        """
        # synthetic o2des stub
        __all__ = []
        """,
    )
    return root


# --- smoke success ----------------------------------------------------------


def test_smoke_success_on_synthetic_tree(tmp_path: Path) -> None:
    source = _synthetic_tree(tmp_path / "source")
    result = run_smoke(source, days=1, timeout=30.0)
    assert result.returncode == 0, result.stderr
    assert "SMOKE_OK" in result.stdout
    assert not result.timed_out


def test_smoke_runs_exactly_requested_days(tmp_path: Path) -> None:
    # The synthetic Model writes its run-call count to a file we can inspect.
    counter = tmp_path / "calls.txt"
    source = _synthetic_tree(
        tmp_path / "source",
        model_run_body=f"open({str(counter)!r}, 'a').write('x\\n')",
    )
    result = run_smoke(source, days=2, timeout=30.0)
    assert result.returncode == 0, result.stderr
    assert counter.read_text().count("x") == 2


def test_smoke_o2des_importable_via_pythonpath(tmp_path: Path) -> None:
    # A synthetic tree that imports o2des inside create_with_disruption proves
    # the subprocess PYTHONPATH includes source/o2despy.
    source = _synthetic_tree(
        tmp_path / "source",
        create_body="import o2des; return {'o2des': True}",
    )
    result = run_smoke(source, days=1, timeout=30.0)
    assert result.returncode == 0, result.stderr


def test_smoke_does_not_run_warmup(tmp_path: Path) -> None:
    # If the driver accidentally invoked a warmup path, this marker would fire.
    marker = tmp_path / "warmup_called.txt"
    _synthetic_tree(
        tmp_path / "source",
        model_run_body=(
            f"import os; "
            f"(open({str(marker)!r}, 'w').write('warmup') "
            f"if 'warmup' in str(duration).lower() else None)"
        ),
    )
    result = run_smoke(tmp_path / "source", days=1, timeout=30.0)
    assert result.returncode == 0, result.stderr
    assert not marker.exists()


# --- smoke failure / timeout ------------------------------------------------


def test_smoke_returns_nonzero_on_construction_failure(tmp_path: Path) -> None:
    source = _synthetic_tree(
        tmp_path / "source",
        create_body="raise RuntimeError('boom: scenario construction failed')",
    )
    result = run_smoke(source, days=1, timeout=30.0)
    assert result.returncode != 0
    assert "boom" in result.stderr or "boom" in result.stdout


def test_smoke_timeout_returns_nonzero_and_flag(tmp_path: Path) -> None:
    source = _synthetic_tree(
        tmp_path / "source",
        model_run_body="import time; time.sleep(30)",
    )
    result = run_smoke(source, days=1, timeout=1.0)
    assert result.timed_out is True
    assert result.returncode != 0


def test_smoke_requires_existing_source(tmp_path: Path) -> None:
    from wsc2026_tools.cli import SmokeError

    with pytest.raises(SmokeError, match="(?i)not found|missing|bootstrapped"):
        run_smoke(tmp_path / "does_not_exist", days=1, timeout=5.0)


# --- full run requires --full flag ------------------------------------------


def test_run_requires_full_flag() -> None:
    from wsc2026_tools.cli import main

    # Without --full the command must not start a full simulation.
    rc = main(["run", "--round", "round0"])
    assert rc != 0


def test_run_accepts_full_flag() -> None:
    parser = build_parser()
    ns = parser.parse_args(["run", "--round", "round0", "--full"])
    assert ns.round == "round0"
    assert ns.full is True


def test_smoke_subprocess_uses_current_python(tmp_path: Path) -> None:
    # The runner must invoke sys.executable (the uv-managed venv python), not a
    # bare 'python'. We assert via the synthetic tree reporting sys.executable.
    report = tmp_path / "py.txt"
    _synthetic_tree(
        tmp_path / "source",
        create_body=f"import sys; open({str(report)!r}, 'w').write(sys.executable); return {{}}",
    )
    result = run_smoke(tmp_path / "source", days=1, timeout=30.0)
    assert result.returncode == 0, result.stderr
    assert report.read_text() == sys.executable


# --- precondition hardening -------------------------------------------------


def test_smoke_rejects_days_zero() -> None:
    """Smoke must reject days < 1; zero days is a meaningless simulation."""
    from wsc2026_tools.cli import SmokeError

    with pytest.raises(SmokeError, match=r"(?i)days|positive|>=1"):
        run_smoke(Path("/tmp"), days=0, timeout=30.0)


def test_smoke_rejects_negative_days() -> None:
    from wsc2026_tools.cli import SmokeError

    with pytest.raises(SmokeError, match=r"(?i)days|positive|>=1"):
        run_smoke(Path("/tmp"), days=-1, timeout=30.0)


def test_smoke_rejects_zero_timeout() -> None:
    """timeout=0 means 'kill instantly' which is almost certainly a bug."""
    from wsc2026_tools.cli import SmokeError

    with pytest.raises(SmokeError, match=r"(?i)timeout|>0|positive"):
        run_smoke(Path("/tmp"), days=1, timeout=0.0)


def test_smoke_rejects_negative_timeout() -> None:
    from wsc2026_tools.cli import SmokeError

    with pytest.raises(SmokeError, match=r"(?i)timeout|>0|positive"):
        run_smoke(Path("/tmp"), days=1, timeout=-5.0)


# --- full-run construction is non-launching ---------------------------------


def test_run_full_constructs_subprocess_without_capturing(tmp_path: Path, monkeypatch) -> None:
    """The full runner must stream stdout/stderr live (no capture_output).

    We assert by patching subprocess.run and inspecting the kwargs. The patched
    call returns a fake CompletedProcess with returncode 0 so the runner exits
    cleanly.
    """
    import subprocess

    from wsc2026_tools.cli import run_full

    source = _synthetic_tree(tmp_path / "source")
    captured_kwargs: dict = {}

    class _FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured_kwargs["cmd"] = cmd
        captured_kwargs.update(kwargs)
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = run_full(source, timeout=None)
    assert result.returncode == 0
    # The runner must NOT buffer output (no capture_output, no text=True).
    assert "capture_output" not in captured_kwargs
    assert "text" not in captured_kwargs
    # The runner must invoke sys.executable and use the driver string.
    assert captured_kwargs["cmd"][0] == sys.executable
    assert "main.run_simulation" in captured_kwargs["cmd"][2]


def test_run_full_uses_timeout_when_provided(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    from wsc2026_tools.cli import run_full

    source = _synthetic_tree(tmp_path / "source")
    captured_kwargs: dict = {}

    class _FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured_kwargs.update(kwargs)
        return _FakeProc()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    run_full(source, timeout=600.0)
    assert captured_kwargs["timeout"] == 600.0
