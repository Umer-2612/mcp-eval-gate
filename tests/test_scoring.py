from mcp_eval_gate.models import GoldenCase, MatchType, ToolCallOutcome
from mcp_eval_gate.scoring import score_case, score_judge_case


def _case(**overrides) -> GoldenCase:
    defaults = dict(
        id="case-1",
        tool_name="get_weather",
        tool_args={"city": "New York"},
        match_type=MatchType.CONTAINS,
        expected_output="New York",
    )
    defaults.update(overrides)
    return GoldenCase(**defaults)


def test_contains_case_passes_when_expected_text_is_a_substring():
    case = _case(match_type=MatchType.CONTAINS, expected_output="New York")
    outcome = ToolCallOutcome(text="It's 72F in New York today.", structured=None, is_error=False)

    result = score_case(case, outcome)

    assert result.passed is True
    assert result.score == 1.0


def test_contains_case_fails_when_expected_text_is_missing():
    case = _case(match_type=MatchType.CONTAINS, expected_output="London")
    outcome = ToolCallOutcome(text="It's 72F in New York today.", structured=None, is_error=False)

    result = score_case(case, outcome)

    assert result.passed is False
    assert result.score == 0.0
    assert "London" in result.detail


def test_exact_case_passes_only_on_exact_match_ignoring_surrounding_whitespace():
    case = _case(match_type=MatchType.EXACT, expected_output="42")
    outcome = ToolCallOutcome(text=" 42 \n", structured=None, is_error=False)

    result = score_case(case, outcome)

    assert result.passed is True


def test_exact_case_fails_on_partial_match():
    case = _case(match_type=MatchType.EXACT, expected_output="42")
    outcome = ToolCallOutcome(text="42 (approx)", structured=None, is_error=False)

    result = score_case(case, outcome)

    assert result.passed is False


def test_tool_error_fails_regardless_of_match_type():
    case = _case(match_type=MatchType.CONTAINS, expected_output="New York")
    outcome = ToolCallOutcome(text="Internal server error", structured=None, is_error=True)

    result = score_case(case, outcome)

    assert result.passed is False
    assert result.score == 0.0
    assert "error" in result.detail.lower()


def test_judge_match_type_is_dispatched_separately_and_not_scored_deterministically():
    case = _case(match_type=MatchType.JUDGE, judge_criteria="must mention 90 days", expected_output=None)
    outcome = ToolCallOutcome(text="Data is retained for 90 days.", structured=None, is_error=False)

    import pytest

    with pytest.raises(ValueError, match="judge"):
        score_case(case, outcome)


def test_judge_case_passes_when_score_meets_threshold():
    case = _case(match_type=MatchType.JUDGE, judge_criteria="must mention 90 days", min_judge_score=0.8)

    result = score_judge_case(case, judge_score=0.9, reasoning="mentions 90 days")

    assert result.passed is True
    assert result.score == 0.9


def test_judge_case_fails_below_threshold():
    case = _case(match_type=MatchType.JUDGE, judge_criteria="must mention 90 days", min_judge_score=0.8)

    result = score_judge_case(case, judge_score=0.4, reasoning="missing the detail")

    assert result.passed is False


def test_exact_failure_detail_on_a_long_output_is_short_and_points_at_the_difference():
    case = _case(match_type=MatchType.EXACT, expected_output="a" * 1023 + "界")
    outcome = ToolCallOutcome(text="a" * 1023 + "���", structured=None, is_error=False)

    result = score_case(case, outcome)

    assert result.passed is False
    assert len(result.detail) < 300
    assert "first difference at char 1023" in result.detail


def test_contains_failure_detail_truncates_a_long_expected_value():
    case = _case(match_type=MatchType.CONTAINS, expected_output="needle" * 200)
    outcome = ToolCallOutcome(text="haystack", structured=None, is_error=False)

    result = score_case(case, outcome)

    assert result.passed is False
    assert len(result.detail) < 300
    assert "more chars" in result.detail


def test_tool_error_detail_truncates_a_long_error_message():
    case = _case()
    outcome = ToolCallOutcome(text="stack trace line\n" * 500, structured=None, is_error=True)

    result = score_case(case, outcome)

    assert result.passed is False
    assert len(result.detail) < 400
