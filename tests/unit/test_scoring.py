"""Unit tests for the resilience loss scorer (wsc2026_tools.scoring).

The scorer reproduces the dashboard formula exactly:

    ATT ratio    = baseline ATT / scenario ATT
    period loss  = (1 - ATT ratio) * inclusive number of days
    cumulative   = sum(period loss)

Zero handling matches the dashboard:
- scenario ATT <= 0 and baseline ATT <= 0 -> ratio is 1.
- scenario ATT <= 0 and baseline ATT > 0  -> ratio is 0.

Negative loss is NOT clamped: a scenario that beats baseline yields negative
period loss.

Tests use synthetic CSVs written into tmp_path; they never reference real
organizer output.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from wsc2026_tools.scoring import (
    ScoreResult,
    ScoringError,
    compute_resilience_loss,
    write_score_output,
)

# Canonical organizer ATT column name.
ATT_COLUMN = "AverageTransportTime"


def _write_att_csv(
    path: Path, rows: list[dict[str, str]], *, extra_rows: list[dict[str, str]] | None = None
) -> None:
    """Write an ATT-per-period CSV. ``rows`` are data rows (PeriodIndex set)."""
    fieldnames = ["PeriodIndex", "StartDay", "EndDay", ATT_COLUMN]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
        for row in extra_rows or []:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _period(idx: int, start: int, end: int, att: float) -> dict[str, str]:
    return {
        "PeriodIndex": str(idx),
        "StartDay": str(start),
        "EndDay": str(end),
        ATT_COLUMN: str(att),
    }


# --- core formula -----------------------------------------------------------


def test_basic_cumulative_loss_matches_formula(tmp_path: Path) -> None:
    # Two 5-day periods.
    scenario = [_period(1, 0, 4, 100.0), _period(2, 5, 9, 200.0)]
    baseline = [_period(1, 0, 4, 120.0), _period(2, 5, 9, 200.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    result = compute_resilience_loss(sp, bp)

    # period1: ratio=120/100=1.2 -> loss=(1-1.2)*5 = -1.0
    # period2: ratio=200/200=1.0 -> loss=0.0
    assert result.period_count == 2
    assert result.per_period[0] == pytest.approx(-1.0)
    assert result.per_period[1] == pytest.approx(0.0)
    assert result.cumulative_loss == pytest.approx(-1.0)


def test_inclusive_day_count_used(tmp_path: Path) -> None:
    # StartDay=0, EndDay=9 inclusive => 10 days.
    scenario = [_period(1, 0, 9, 100.0)]
    baseline = [_period(1, 0, 9, 50.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    result = compute_resilience_loss(sp, bp)

    # ratio=50/100=0.5 -> loss=(1-0.5)*10 = 5.0
    assert result.per_period[0] == pytest.approx(5.0)
    assert result.cumulative_loss == pytest.approx(5.0)


def test_negative_loss_not_clamped(tmp_path: Path) -> None:
    # Scenario outperforms baseline (lower ATT is better).
    scenario = [_period(1, 0, 4, 80.0)]
    baseline = [_period(1, 0, 4, 100.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    result = compute_resilience_loss(sp, bp)

    # ratio=100/80=1.25 -> loss=(1-1.25)*5 = -1.25
    assert result.per_period[0] == pytest.approx(-1.25)
    assert result.cumulative_loss == pytest.approx(-1.25)


# --- zero handling ----------------------------------------------------------


def test_zero_handling_both_zero_ratio_is_one(tmp_path: Path) -> None:
    scenario = [_period(1, 0, 4, 0.0)]
    baseline = [_period(1, 0, 4, 0.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    result = compute_resilience_loss(sp, bp)

    # ratio=1 -> loss=0
    assert result.per_period[0] == pytest.approx(0.0)


def test_zero_handling_scenario_zero_baseline_positive_ratio_zero(tmp_path: Path) -> None:
    scenario = [_period(1, 0, 4, 0.0)]
    baseline = [_period(1, 0, 4, 100.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    result = compute_resilience_loss(sp, bp)

    # ratio=0 -> loss=(1-0)*5 = 5.0
    assert result.per_period[0] == pytest.approx(5.0)


# --- validation failures ----------------------------------------------------


def test_mismatched_period_indices_rejected(tmp_path: Path) -> None:
    scenario = [_period(1, 0, 4, 100.0)]
    baseline = [_period(2, 0, 4, 100.0)]  # different index
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    with pytest.raises(ScoringError, match="(?i)period"):
        compute_resilience_loss(sp, bp)


def test_mismatched_day_ranges_rejected(tmp_path: Path) -> None:
    scenario = [_period(1, 0, 4, 100.0)]
    baseline = [_period(1, 0, 9, 100.0)]  # different EndDay
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    with pytest.raises(ScoringError, match="(?i)range|day"):
        compute_resilience_loss(sp, bp)


def test_duplicate_period_indices_rejected(tmp_path: Path) -> None:
    scenario = [_period(1, 0, 4, 100.0), _period(1, 0, 4, 110.0)]
    baseline = [_period(1, 0, 4, 100.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    with pytest.raises(ScoringError, match="(?i)duplicate|unique"):
        compute_resilience_loss(sp, bp)


def test_malformed_att_value_rejected(tmp_path: Path) -> None:
    scenario = [_period(1, 0, 4, 100.0)]
    baseline = [_period(1, 0, 4, "not-a-number")]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    with pytest.raises(ScoringError, match="(?i)malformed|invalid|non-finite|number"):
        compute_resilience_loss(sp, bp)


def test_summary_rows_without_period_index_ignored(tmp_path: Path) -> None:
    # A trailing summary line with no PeriodIndex must be ignored.
    summary = {"PeriodIndex": "", "StartDay": "", "EndDay": "", ATT_COLUMN: "mean"}
    scenario = [_period(1, 0, 4, 100.0)]
    baseline = [_period(1, 0, 4, 100.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario, extra_rows=[summary])
    _write_att_csv(bp, baseline, extra_rows=[summary])

    result = compute_resilience_loss(sp, bp)

    assert result.period_count == 1
    assert result.cumulative_loss == pytest.approx(0.0)


# --- output formatting ------------------------------------------------------


def test_write_score_output_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scenario = [_period(1, 0, 4, 100.0)]
    baseline = [_period(1, 0, 4, 100.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    result = compute_resilience_loss(sp, bp)
    write_score_output(result, sp, bp, as_json=True)

    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert payload["scenario_att_path"] == str(sp)
    assert payload["baseline_att_path"] == str(bp)
    assert payload["period_count"] == 1
    assert payload["cumulative_loss"] == pytest.approx(0.0)
    assert payload["per_period"] == [0.0]


def test_write_score_output_human_no_premature_round(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A loss that is not a round number must not be truncated in human output.
    scenario = [_period(1, 0, 0, 80.0)]  # 1 inclusive day
    baseline = [_period(1, 0, 0, 100.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)

    result: ScoreResult = compute_resilience_loss(sp, bp)
    write_score_output(result, sp, bp, as_json=False)

    captured = capsys.readouterr().out
    # loss = (1 - 100/80) * 1 = -0.25 ; must show full precision, not "0" or "-0".
    assert "-0.25" in captured


# --- additional validation branches -----------------------------------------


def test_malformed_period_index_rejected(tmp_path: Path) -> None:
    scenario = [
        {"PeriodIndex": "abc", "StartDay": "0", "EndDay": "4", "AverageTransportTime": "100"}
    ]
    baseline = [_period(1, 0, 4, 100.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)
    with pytest.raises(ScoringError, match="(?i)malformed|integer"):
        compute_resilience_loss(sp, bp)


def test_malformed_start_day_rejected(tmp_path: Path) -> None:
    scenario = [{"PeriodIndex": "1", "StartDay": "x", "EndDay": "4", "AverageTransportTime": "100"}]
    baseline = [_period(1, 0, 4, 100.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)
    with pytest.raises(ScoringError, match="(?i)malformed|StartDay"):
        compute_resilience_loss(sp, bp)


def test_malformed_end_day_rejected(tmp_path: Path) -> None:
    scenario = [{"PeriodIndex": "1", "StartDay": "0", "EndDay": "y", "AverageTransportTime": "100"}]
    baseline = [_period(1, 0, 4, 100.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)
    with pytest.raises(ScoringError, match="(?i)malformed|EndDay"):
        compute_resilience_loss(sp, bp)


def test_non_finite_att_rejected(tmp_path: Path) -> None:
    scenario = [_period(1, 0, 4, 100.0)]
    baseline = [_period(1, 0, 4, float("inf"))]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)
    with pytest.raises(ScoringError, match="(?i)non-finite|infinite"):
        compute_resilience_loss(sp, bp)


def test_nan_att_rejected(tmp_path: Path) -> None:
    scenario = [_period(1, 0, 4, 100.0)]
    baseline = [_period(1, 0, 4, float("nan"))]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)
    with pytest.raises(ScoringError, match="(?i)non-finite"):
        compute_resilience_loss(sp, bp)


def test_att_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(ScoringError, match="(?i)not found"):
        compute_resilience_loss(tmp_path / "nope_s.csv", tmp_path / "nope_b.csv")


def test_missing_required_columns_rejected(tmp_path: Path) -> None:
    sp = tmp_path / "s.csv"
    bp = tmp_path / "b.csv"
    sp.write_text("foo,bar\n1,2\n")
    bp.write_text("foo,bar\n1,2\n")
    with pytest.raises(ScoringError, match="(?i)missing required columns"):
        compute_resilience_loss(sp, bp)


def test_empty_headerless_csv_rejected(tmp_path: Path) -> None:
    sp = tmp_path / "s.csv"
    bp = tmp_path / "b.csv"
    sp.write_text("")
    bp.write_text("")
    with pytest.raises(ScoringError, match="(?i)empty|headerless"):
        compute_resilience_loss(sp, bp)


def test_no_data_rows_rejected(tmp_path: Path) -> None:
    sp = tmp_path / "s.csv"
    bp = tmp_path / "b.csv"
    header = f"PeriodIndex,StartDay,EndDay,{ATT_COLUMN}\n"
    sp.write_text(header)
    bp.write_text(header)
    with pytest.raises(ScoringError, match="(?i)no data rows"):
        compute_resilience_loss(sp, bp)


def test_load_round_zero_handling_both_zero_branch(tmp_path: Path) -> None:
    """Covers both-zero branch in _ratio."""
    scenario = [_period(1, 0, 0, 0.0)]
    baseline = [_period(1, 0, 0, -5.0)]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)
    result = compute_resilience_loss(sp, bp)
    # ratio for both <=0 returns 1.0; loss = (1-1)*1 = 0
    assert result.per_period[0] == 0.0


# --- canonical column name ---------------------------------------------------


def _header(field: str) -> str:
    return f"PeriodIndex,StartDay,EndDay,{field}\n"


def test_canonical_column_accepted(tmp_path: Path) -> None:
    """CSVs with the organizer's exact ``AverageTransportTime`` header work."""
    sp = tmp_path / "s.csv"
    bp = tmp_path / "b.csv"
    sp.write_text(_header("AverageTransportTime") + "1,0,4,100.0\n")
    bp.write_text(_header("AverageTransportTime") + "1,0,4,100.0\n")
    result = compute_resilience_loss(sp, bp)
    assert result.period_count == 1


def test_obsolete_column_rejected(tmp_path: Path) -> None:
    """The obsolete ``AverageTransitTime`` header is NOT accepted."""
    sp = tmp_path / "s.csv"
    bp = tmp_path / "b.csv"
    sp.write_text(_header("AverageTransitTime") + "1,0,4,100.0\n")
    bp.write_text(_header("AverageTransitTime") + "1,0,4,100.0\n")
    with pytest.raises(ScoringError, match=r"(?i)AverageTransportTime"):
        compute_resilience_loss(sp, bp)


def test_error_message_uses_canonical_name(tmp_path: Path) -> None:
    sp = tmp_path / "s.csv"
    bp = tmp_path / "b.csv"
    sp.write_text("foo,bar\n1,2\n")
    bp.write_text(_header("AverageTransportTime") + "1,0,4,100.0\n")
    with pytest.raises(ScoringError) as exc:
        compute_resilience_loss(sp, bp)
    assert "AverageTransportTime" in str(exc.value)


def test_malformed_canonical_att_rejected(tmp_path: Path) -> None:
    scenario = [_period(1, 0, 4, 100.0)]
    baseline = [{**_period(1, 0, 4, 100.0), ATT_COLUMN: "not-a-number"}]
    sp, bp = tmp_path / "s.csv", tmp_path / "b.csv"
    _write_att_csv(sp, scenario)
    _write_att_csv(bp, baseline)
    with pytest.raises(
        ScoringError,
        match=r"(?i)AverageTransportTime.*malformed|malformed.*AverageTransportTime",
    ):
        compute_resilience_loss(sp, bp)
