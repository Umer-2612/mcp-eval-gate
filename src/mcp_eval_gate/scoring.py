"""Deterministic scoring for MCP tool-call outcomes.

No MCP calls happen here, this module only compares an already-captured
ToolCallOutcome against the expectation declared in a golden-set case. Keeping
it pure is what makes it unit-testable without a live server.
"""

from __future__ import annotations

from mcp_eval_gate.models import CaseResult, GoldenCase, MatchType, ToolCallOutcome
from mcp_eval_gate.text_diff import describe_difference, preview


def score_case(case: GoldenCase, outcome: ToolCallOutcome) -> CaseResult:
    if outcome.is_error:
        return CaseResult(
            case.id, score=0.0, passed=False, detail=f"tool call returned an error: {preview(outcome.text)}"
        )

    if case.match_type == MatchType.EXACT:
        return _score_exact(case, outcome)
    if case.match_type == MatchType.CONTAINS:
        return _score_contains(case, outcome)

    raise ValueError(f"case '{case.id}' has match_type=judge, score it via score_judge_case after a judge call")


def _score_exact(case: GoldenCase, outcome: ToolCallOutcome) -> CaseResult:
    matched = outcome.text.strip() == (case.expected_output or "").strip()
    expected = case.expected_output or ""
    detail = "exact match" if matched else describe_difference(expected.strip(), outcome.text.strip())
    return CaseResult(case.id, score=1.0 if matched else 0.0, passed=matched, detail=detail)


def _score_contains(case: GoldenCase, outcome: ToolCallOutcome) -> CaseResult:
    matched = (case.expected_output or "") in outcome.text
    detail = (
        "expected text found" if matched else f"expected output to contain {preview(case.expected_output or '')!r}"
    )
    return CaseResult(case.id, score=1.0 if matched else 0.0, passed=matched, detail=detail)


def score_judge_case(case: GoldenCase, *, judge_score: float, reasoning: str) -> CaseResult:
    passed = judge_score >= case.min_judge_score
    return CaseResult(case.id, score=judge_score, passed=passed, detail=reasoning)
