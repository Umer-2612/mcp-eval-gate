"""Deterministic scoring for MCP tool-call outcomes.

No MCP calls happen here, this module only compares an already-captured
ToolCallOutcome against the expectation declared in a golden-set case. Keeping
it pure is what makes it unit-testable without a live server.
"""

from __future__ import annotations

from mcp_eval_gate.models import CaseResult, GoldenCase, MatchType, ToolCallOutcome
from mcp_eval_gate.normalize import Normalizer, apply_normalizers, normalize_structured
from mcp_eval_gate.text_diff import describe_difference, preview


def score_case(
    case: GoldenCase,
    outcome: ToolCallOutcome,
    *,
    normalizers: tuple[Normalizer, ...] = (),
    recorded: ToolCallOutcome | None = None,
    recording: bool = False,
) -> CaseResult:
    mismatch = _error_state_mismatch(case, outcome)
    if mismatch:
        return _result(case, outcome, passed=False, detail=mismatch)

    if case.match_type == MatchType.SNAPSHOT:
        return _score_snapshot(case, outcome, normalizers, recorded, recording)
    if case.match_type == MatchType.EXACT:
        return _score_exact(case, outcome, normalizers)
    if case.match_type == MatchType.CONTAINS:
        return _score_contains(case, outcome, normalizers)

    raise ValueError(f"case '{case.id}' has match_type=judge, score it via score_judge_case after a judge call")


def _error_state_mismatch(case: GoldenCase, outcome: ToolCallOutcome) -> str | None:
    if outcome.is_error and not case.expect_error:
        return f"tool call returned an error: {preview(outcome.text)}"
    if case.expect_error and not outcome.is_error:
        return f"expected the tool call to return an error, but it succeeded: {preview(outcome.text)}"
    return None


def _result(case: GoldenCase, outcome: ToolCallOutcome, *, passed: bool, detail: str) -> CaseResult:
    return CaseResult(case.id, score=1.0 if passed else 0.0, passed=passed, detail=detail, outcome=outcome)


def _score_exact(case: GoldenCase, outcome: ToolCallOutcome, normalizers: tuple[Normalizer, ...]) -> CaseResult:
    expected = apply_normalizers(case.expected_output or "", normalizers)
    actual = apply_normalizers(outcome.text, normalizers)
    matched = actual == expected
    detail = "exact match" if matched else describe_difference(expected, actual)
    return _result(case, outcome, passed=matched, detail=detail)


def _score_contains(case: GoldenCase, outcome: ToolCallOutcome, normalizers: tuple[Normalizer, ...]) -> CaseResult:
    expected = apply_normalizers(case.expected_output or "", normalizers)
    matched = expected in apply_normalizers(outcome.text, normalizers)
    detail = "expected text found" if matched else f"expected output to contain {preview(expected)!r}"
    return _result(case, outcome, passed=matched, detail=detail)


def _score_snapshot(
    case: GoldenCase,
    outcome: ToolCallOutcome,
    normalizers: tuple[Normalizer, ...],
    recorded: ToolCallOutcome | None,
    recording: bool,
) -> CaseResult:
    if recording:
        return _result(case, outcome, passed=True, detail="recorded")
    if recorded is None:
        return _result(
            case,
            outcome,
            passed=False,
            detail="no recorded output for this case, run with --update-baseline to record it",
        )

    before = apply_normalizers(recorded.text, normalizers)
    after = apply_normalizers(outcome.text, normalizers)
    if before != after:
        return _result(case, outcome, passed=False, detail=describe_difference(before, after))
    structured_before = normalize_structured(recorded.structured, normalizers)
    if structured_before != normalize_structured(outcome.structured, normalizers):
        return _result(case, outcome, passed=False, detail="structured content differs from the recorded output")
    return _result(case, outcome, passed=True, detail="matches the recorded output")


def score_judge_case(case: GoldenCase, *, judge_score: float, reasoning: str) -> CaseResult:
    passed = judge_score >= case.min_judge_score
    return CaseResult(case.id, score=judge_score, passed=passed, detail=reasoning)
