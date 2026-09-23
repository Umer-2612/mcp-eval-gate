from bedrock_eval_gate.models import CaseResult, Regression
from bedrock_eval_gate.report import exit_code_for


def test_exit_code_is_zero_when_everything_passes_and_no_regressions():
    results = [CaseResult("c1", 1.0, True, "ok")]

    assert exit_code_for(results, regressions=[]) == 0


def test_exit_code_is_one_when_a_case_fails_even_without_a_baseline():
    results = [CaseResult("c1", 0.0, False, "tool not called")]

    assert exit_code_for(results, regressions=[]) == 1


def test_exit_code_is_one_when_there_is_a_regression_even_if_all_cases_pass():
    results = [CaseResult("c1", 0.9, True, "ok")]
    regressions = [Regression("c1", baseline_score=1.0, current_score=0.9, detail="dropped")]

    assert exit_code_for(results, regressions=regressions) == 1


def test_write_html_report_includes_case_ids_and_status(tmp_path):
    from bedrock_eval_gate.report import write_html_report

    path = tmp_path / "report.html"
    results = [CaseResult("c1", 1.0, True, "ok"), CaseResult("c2", 0.0, False, "tool not called")]
    regressions = [Regression("c2", baseline_score=1.0, current_score=0.0, detail="tool not called")]

    write_html_report(results, regressions, path)
    html = path.read_text()

    assert "c1" in html and "c2" in html
    assert "PASS" in html
    assert "FAIL" in html
    assert "regression" in html
