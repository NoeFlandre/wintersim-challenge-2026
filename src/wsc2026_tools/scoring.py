"""Resilience loss scorer.

Reproduces the dashboard formula exactly:

    ATT ratio    = baseline ATT / scenario ATT
    period loss  = (1 - ATT ratio) * inclusive number of days
    cumulative   = sum(period loss)

Lower Cumulative Resilience Loss is better. Negative loss is intentionally NOT
clamped: a scenario that outperforms the baseline on a period yields a negative
period loss.

Dashboard zero handling:
- scenario ATT <= 0 and baseline ATT <= 0  -> ratio is 1.
- scenario ATT <= 0 and baseline ATT > 0   -> ratio is 0.

The scorer parses ATT-per-period CSV files with the standard ``csv`` module.
Rows with no ``PeriodIndex`` (summary lines) are ignored. Period indices must
be unique integers, present in both files, and the ``StartDay``/``EndDay``
ranges must match between scenario and baseline. Missing, malformed,
non-finite, or duplicate values are rejected.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

__all__ = [
    "ScoringError",
    "ScoreResult",
    "compute_resilience_loss",
    "write_score_output",
]

_REQUIRED_COLUMNS = ("PeriodIndex", "StartDay", "EndDay", "AverageTransitTime")


class ScoringError(ValueError):
    """Raised when ATT CSVs are missing, malformed, or inconsistent."""


@dataclass(frozen=True)
class _PeriodRow:
    period_index: int
    start_day: int
    end_day: int
    att: float


@dataclass(frozen=True)
class ScoreResult:
    """Outcome of a resilience-loss computation."""

    cumulative_loss: float
    period_count: int
    per_period: tuple[float, ...] = field(default_factory=tuple)


def _parse_int(value: str, *, field_name: str, source: Path) -> int:
    value = value.strip()
    try:
        return int(value)
    except ValueError as exc:
        raise ScoringError(
            f"{source}: malformed {field_name} value {value!r} (not an integer)"
        ) from exc


def _parse_att(value: str, *, source: Path) -> float:
    value = value.strip()
    try:
        att = float(value)
    except ValueError as exc:
        raise ScoringError(
            f"{source}: malformed AverageTransitTime value {value!r} (not a number)"
        ) from exc
    if not math.isfinite(att):
        raise ScoringError(f"{source}: non-finite AverageTransitTime value {value!r}")
    return att


def _load_periods(path: Path) -> dict[int, _PeriodRow]:
    if not path.is_file():
        raise ScoringError(f"ATT file not found: {path}")
    rows: dict[int, _PeriodRow] = {}
    with path.open("r", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ScoringError(f"{path}: empty or headerless CSV")
        missing = [c for c in _REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ScoringError(f"{path}: missing required columns: {', '.join(missing)}")
        for raw in reader:
            index_field = (raw.get("PeriodIndex") or "").strip()
            if not index_field:
                # Summary row with no period index: ignore.
                continue
            idx = _parse_int(index_field, field_name="PeriodIndex", source=path)
            start_day = _parse_int(raw.get("StartDay", ""), field_name="StartDay", source=path)
            end_day = _parse_int(raw.get("EndDay", ""), field_name="EndDay", source=path)
            att = _parse_att(raw.get("AverageTransitTime", ""), source=path)
            if idx in rows:
                raise ScoringError(f"{path}: duplicate PeriodIndex {idx}")
            rows[idx] = _PeriodRow(idx, start_day, end_day, att)
    if not rows:
        raise ScoringError(f"{path}: no data rows with a PeriodIndex found")
    return rows


def _inclusive_days(start_day: int, end_day: int) -> int:
    return end_day - start_day + 1


def _ratio(scenario_att: float, baseline_att: float) -> float:
    """ATT ratio matching the dashboard zero handling."""
    if scenario_att <= 0:
        return 1.0 if baseline_att <= 0 else 0.0
    return baseline_att / scenario_att


def compute_resilience_loss(scenario_att_path: Path, baseline_att_path: Path) -> ScoreResult:
    """Compute cumulative resilience loss from two ATT-per-period CSVs."""
    scenario = _load_periods(Path(scenario_att_path))
    baseline = _load_periods(Path(baseline_att_path))

    scenario_indices = set(scenario)
    baseline_indices = set(baseline)
    if scenario_indices != baseline_indices:
        only_scenario = sorted(scenario_indices - baseline_indices)
        only_baseline = sorted(baseline_indices - scenario_indices)
        parts = []
        if only_scenario:
            parts.append(f"only in scenario: {only_scenario}")
        if only_baseline:
            parts.append(f"only in baseline: {only_baseline}")
        raise ScoringError(
            "period indices do not match between scenario and baseline (" + "; ".join(parts) + ")"
        )

    per_period: list[float] = []
    for idx in sorted(scenario_indices):
        s = scenario[idx]
        b = baseline[idx]
        if s.start_day != b.start_day or s.end_day != b.end_day:
            raise ScoringError(
                f"day range mismatch for PeriodIndex {idx}: "
                f"scenario StartDay/EndDay={s.start_day}/{s.end_day}, "
                f"baseline StartDay/EndDay={b.start_day}/{b.end_day}"
            )
        days = _inclusive_days(s.start_day, s.end_day)
        ratio = _ratio(s.att, b.att)
        per_period.append((1.0 - ratio) * days)

    cumulative = math.fsum(per_period)
    return ScoreResult(
        cumulative_loss=cumulative,
        period_count=len(per_period),
        per_period=tuple(per_period),
    )


def write_score_output(
    result: ScoreResult,
    scenario_att_path: Path,
    baseline_att_path: Path,
    *,
    as_json: bool,
    stream: TextIO | None = None,
) -> None:
    """Print the score result, either human-readable or full-precision JSON."""
    stream = stream or sys.stdout
    if as_json:
        payload = {
            "scenario_att_path": str(scenario_att_path),
            "baseline_att_path": str(baseline_att_path),
            "period_count": result.period_count,
            "per_period": list(result.per_period),
            "cumulative_loss": result.cumulative_loss,
        }
        # full precision, no premature rounding
        json.dump(payload, stream)
        stream.write("\n")
        return
    stream.write(f"Cumulative resilience loss: {result.cumulative_loss}\n")
    stream.write(f"Period count: {result.period_count}\n")
