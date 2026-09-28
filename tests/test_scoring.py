from mcp_eval_gate.models import GoldenCase, MatchType, ToolCallOutcome
from mcp_eval_gate.normalize import parse_normalizers
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


def test_exact_case_fails_on_surrounding_whitespace_and_shows_it_in_the_detail():
    case = _case(match_type=MatchType.EXACT, expected_output="42")
    outcome = ToolCallOutcome(text="42\n", structured=None, is_error=False)

    result = score_case(case, outcome)

    assert result.passed is False
    assert "'42\\n'" in result.detail


def test_exact_case_ignores_surrounding_whitespace_when_the_trim_normalizer_is_on():
    case = _case(match_type=MatchType.EXACT, expected_output="42")
    outcome = ToolCallOutcome(text=" 42 \n", structured=None, is_error=False)

    result = score_case(case, outcome, normalizers=parse_normalizers(["trim"]))

    assert result.passed is True


def test_normalizers_apply_to_contains_cases_on_both_sides():
    case = _case(match_type=MatchType.CONTAINS, expected_output="at 2026-01-01")
    outcome = ToolCallOutcome(text="saved at 2026-09-26 ok", structured=None, is_error=False)
    normalizers = parse_normalizers([{"regex": r"\d{4}-\d{2}-\d{2}", "replace": "<date>"}])

    result = score_case(case, outcome, normalizers=normalizers)

    assert result.passed is True


def test_expect_error_case_passes_when_the_tool_returns_an_error_with_matching_text():
    case = _case(expect_error=True, match_type=MatchType.CONTAINS, expected_output="Error executing tool")
    outcome = ToolCallOutcome(text="Error executing tool boom", structured=None, is_error=True)

    result = score_case(case, outcome)

    assert result.passed is True


def test_expect_error_case_fails_when_the_tool_succeeds():
    case = _case(expect_error=True, match_type=MatchType.CONTAINS, expected_output="x")
    outcome = ToolCallOutcome(text="x", structured=None, is_error=False)

    result = score_case(case, outcome)

    assert result.passed is False
    assert "expected the tool call to return an error" in result.detail


def test_snapshot_passes_when_output_matches_the_recorded_outcome():
    case = _case(match_type=MatchType.SNAPSHOT, expected_output=None)
    recorded = ToolCallOutcome(text="72F", structured={"t": 72}, is_error=False)
    current = ToolCallOutcome(text="72F", structured={"t": 72}, is_error=False)

    result = score_case(case, current, recorded=recorded)

    assert result.passed is True


def test_snapshot_fails_with_a_readable_diff_when_text_changes():
    case = _case(match_type=MatchType.SNAPSHOT, expected_output=None)
    recorded = ToolCallOutcome(text="72F sunny", structured=None, is_error=False)
    current = ToolCallOutcome(text="72F cloudy", structured=None, is_error=False)

    result = score_case(case, current, recorded=recorded)

    assert result.passed is False
    assert "first difference at char" in result.detail


def test_snapshot_fails_when_structured_content_changes():
    case = _case(match_type=MatchType.SNAPSHOT, expected_output=None)
    recorded = ToolCallOutcome(text="ok", structured={"t": 72}, is_error=False)
    current = ToolCallOutcome(text="ok", structured={"t": 71}, is_error=False)

    result = score_case(case, current, recorded=recorded)

    assert result.passed is False
    assert "structured content differs" in result.detail


def test_snapshot_fails_when_a_success_turns_into_an_error():
    case = _case(match_type=MatchType.SNAPSHOT, expected_output=None)
    recorded = ToolCallOutcome(text="ok", structured=None, is_error=False)
    current = ToolCallOutcome(text="boom", structured=None, is_error=True)

    result = score_case(case, current, recorded=recorded)

    assert result.passed is False


def test_snapshot_records_error_results_as_expected_errors():
    case = _case(match_type=MatchType.SNAPSHOT, expected_output=None, expect_error=True)
    recorded = ToolCallOutcome(text="Error executing tool boom", structured=None, is_error=True)
    current = ToolCallOutcome(text="Error executing tool boom", structured=None, is_error=True)

    result = score_case(case, current, recorded=recorded)

    assert result.passed is True


def test_snapshot_ignores_volatile_keys_through_normalizers():
    case = _case(match_type=MatchType.SNAPSHOT, expected_output=None)
    recorded = ToolCallOutcome(text='{"id": 1, "v": 3}', structured={"id": 1, "v": 3}, is_error=False)
    current = ToolCallOutcome(text='{"id": 9, "v": 3}', structured={"id": 9, "v": 3}, is_error=False)

    result = score_case(case, current, recorded=recorded, normalizers=parse_normalizers([{"ignore_keys": ["id"]}]))

    assert result.passed is True


def test_snapshot_without_a_recording_fails_and_says_how_to_record():
    case = _case(match_type=MatchType.SNAPSHOT, expected_output=None)
    current = ToolCallOutcome(text="ok", structured=None, is_error=False)

    result = score_case(case, current, recorded=None)

    assert result.passed is False
    assert "--update-baseline" in result.detail


def test_snapshot_passes_while_recording_and_keeps_the_outcome_for_the_baseline():
    case = _case(match_type=MatchType.SNAPSHOT, expected_output=None)
    current = ToolCallOutcome(text="ok", structured=None, is_error=False)

    result = score_case(case, current, recording=True)

    assert result.passed is True
    assert result.outcome == current


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


def test_snapshot_applies_text_normalizers_to_structured_content_too():
    case = _case(match_type=MatchType.SNAPSHOT, expected_output=None)
    recorded = ToolCallOutcome(text="at 2026-01-01", structured={"ts": "2026-01-01"}, is_error=False)
    current = ToolCallOutcome(text="at 2026-09-26", structured={"ts": "2026-09-26"}, is_error=False)
    normalizers = parse_normalizers([{"regex": r"\d{4}-\d{2}-\d{2}", "replace": "<date>"}])

    result = score_case(case, current, recorded=recorded, normalizers=normalizers)

    assert result.passed is True
