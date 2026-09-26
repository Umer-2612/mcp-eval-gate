import json

import pytest

from mcp_eval_gate.baseline import BaselineError, diff_against_baseline, load_baseline, save_baseline
from mcp_eval_gate.models import CaseResult, ToolCallOutcome


def test_no_regressions_when_scores_match_baseline():
    baseline = {"case-1": 1.0, "case-2": 1.0}
    current = [
        CaseResult("case-1", score=1.0, passed=True, detail="ok"),
        CaseResult("case-2", score=1.0, passed=True, detail="ok"),
    ]

    regressions = diff_against_baseline(current, baseline)

    assert regressions == []


def test_no_regressions_when_score_improves():
    baseline = {"case-1": 0.5}
    current = [CaseResult("case-1", score=1.0, passed=True, detail="ok")]

    regressions = diff_against_baseline(current, baseline)

    assert regressions == []


def test_flags_regression_when_score_drops_beyond_threshold():
    baseline = {"case-1": 1.0}
    current = [CaseResult("case-1", score=0.5, passed=False, detail="missing doc-42")]

    regressions = diff_against_baseline(current, baseline, threshold=0.05)

    assert len(regressions) == 1
    assert regressions[0].case_id == "case-1"
    assert regressions[0].baseline_score == 1.0
    assert regressions[0].current_score == 0.5


def test_small_drop_within_threshold_is_not_a_regression():
    baseline = {"case-1": 1.0}
    current = [CaseResult("case-1", score=0.97, passed=True, detail="ok")]

    regressions = diff_against_baseline(current, baseline, threshold=0.05)

    assert regressions == []


def test_new_case_not_in_baseline_only_regresses_if_it_fails():
    baseline: dict[str, float] = {}
    passing = [CaseResult("case-new", score=1.0, passed=True, detail="ok")]
    failing = [CaseResult("case-new", score=0.0, passed=False, detail="tool not called")]

    assert diff_against_baseline(passing, baseline) == []
    regressions = diff_against_baseline(failing, baseline)
    assert len(regressions) == 1
    assert regressions[0].baseline_score == 1.0


def test_case_missing_from_current_run_but_present_in_baseline_is_a_regression():
    baseline = {"case-1": 1.0}
    current: list[CaseResult] = []

    regressions = diff_against_baseline(current, baseline)

    assert len(regressions) == 1
    assert regressions[0].case_id == "case-1"
    assert "missing" in regressions[0].detail.lower()


def test_load_baseline_is_empty_when_the_file_is_missing(tmp_path):
    baseline = load_baseline(tmp_path / "missing.json")

    assert baseline.scores == {}
    assert baseline.outcomes == {}
    assert baseline.contract is None


def test_save_then_load_round_trips_scores_and_raw_outcomes(tmp_path):
    path = tmp_path / "baseline.json"
    outcome = ToolCallOutcome(text="  72F\n", structured={"t": 72}, is_error=False)
    results = [
        CaseResult("c1", score=0.9, passed=True, detail="ok", outcome=outcome),
        CaseResult("c2", score=1.0, passed=True, detail="ok"),
    ]

    save_baseline(path, results, contract={"server_info": {"name": "s"}})
    loaded = load_baseline(path)

    assert loaded.scores == {"c1": 0.9, "c2": 1.0}
    assert loaded.outcomes == {"c1": outcome}
    assert loaded.contract == {"server_info": {"name": "s"}}


def test_saved_file_is_versioned_and_keeps_the_raw_text(tmp_path):
    path = tmp_path / "baseline.json"
    outcome = ToolCallOutcome(text="raw\n", structured=None, is_error=True)

    save_baseline(path, [CaseResult("c1", score=1.0, passed=True, detail="ok", outcome=outcome)])
    data = json.loads(path.read_text())

    assert data["version"] == 2
    assert data["cases"]["c1"] == {
        "score": 1.0,
        "outcome": {"is_error": True, "text": "raw\n", "structured": None},
    }


def test_a_legacy_score_only_baseline_still_loads(tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"c1": 1.0, "c2": 0.5}))

    loaded = load_baseline(path)

    assert loaded.scores == {"c1": 1.0, "c2": 0.5}
    assert loaded.outcomes == {}


def test_a_baseline_from_a_newer_version_is_rejected_with_a_clear_message(tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"version": 99, "cases": {}}))

    with pytest.raises(BaselineError, match="newer"):
        load_baseline(path)


def test_a_corrupt_baseline_gives_a_readable_error(tmp_path):
    path = tmp_path / "baseline.json"
    path.write_text("{not json")

    with pytest.raises(BaselineError, match="not valid JSON"):
        load_baseline(path)
