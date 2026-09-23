from bedrock_eval_gate.baseline import diff_against_baseline, load_baseline, save_baseline
from bedrock_eval_gate.models import CaseResult


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


def test_load_baseline_returns_empty_dict_when_file_missing(tmp_path):
    assert load_baseline(tmp_path / "missing.json") == {}


def test_save_then_load_baseline_round_trips(tmp_path):
    path = tmp_path / "baseline.json"
    results = [
        CaseResult("c1", score=0.9, passed=True, detail="ok"),
        CaseResult("c2", score=1.0, passed=True, detail="ok"),
    ]

    save_baseline(path, results)
    loaded = load_baseline(path)

    assert loaded == {"c1": 0.9, "c2": 1.0}
