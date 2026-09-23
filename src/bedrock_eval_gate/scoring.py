"""Deterministic scoring for retrieval and agent test cases.

No Bedrock/AWS calls happen here — this module only compares an already-captured
outcome against the expectation declared in a golden-set case. Keeping it pure
is what makes it unit-testable without AWS credentials.
"""

from __future__ import annotations

from bedrock_eval_gate.models import AgentOutcome, CaseResult, GoldenCase, RetrievalOutcome


def score_retrieval_case(case: GoldenCase, outcome: RetrievalOutcome) -> CaseResult:
    expected = set(case.expected_doc_ids)
    retrieved_top_k = set(outcome.retrieved_doc_ids[: case.k])

    if not expected:
        return CaseResult(case.id, score=1.0, passed=True, detail="no expected doc ids declared")

    hits = expected & retrieved_top_k
    recall = len(hits) / len(expected)
    missing = expected - hits

    passed = recall >= case.min_recall
    detail = (
        "all expected docs retrieved"
        if not missing
        else f"missing from top-{case.k}: {', '.join(sorted(missing))}"
    )
    return CaseResult(case.id, score=recall, passed=passed, detail=detail)


def score_agent_case(case: GoldenCase, outcome: AgentOutcome) -> CaseResult:
    if case.expected_tool is None:
        return CaseResult(case.id, score=1.0, passed=True, detail="no expected tool declared")

    if outcome.called_tool is None:
        return CaseResult(
            case.id, score=0.0, passed=False, detail=f"expected tool '{case.expected_tool}', none was called"
        )

    if outcome.called_tool != case.expected_tool:
        return CaseResult(
            case.id,
            score=0.0,
            passed=False,
            detail=f"expected tool '{case.expected_tool}', got '{outcome.called_tool}'",
        )

    mismatches = [
        f"{key}={value!r} (got {outcome.called_params.get(key)!r})"
        for key, value in case.expected_params.items()
        if outcome.called_params.get(key) != value
    ]
    if mismatches:
        return CaseResult(case.id, score=0.0, passed=False, detail=f"param mismatch: {', '.join(mismatches)}")

    return CaseResult(
        case.id, score=1.0, passed=True, detail=f"'{case.expected_tool}' called with matching params"
    )


def score_judge_case(case: GoldenCase, *, judge_score: float, reasoning: str) -> CaseResult:
    passed = judge_score >= case.min_judge_score
    return CaseResult(case.id, score=judge_score, passed=passed, detail=reasoning)
