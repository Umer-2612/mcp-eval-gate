"""End-to-end wiring test using fake boto3-shaped clients — no network, no AWS creds."""

from bedrock_eval_gate.models import CaseType, GoldenCase, GoldenSetConfig
from bedrock_eval_gate.runner import run_golden_set
from tests.fakes import FakeAgentRuntimeClient, FakeBedrockRuntimeClient


def test_run_golden_set_scores_retrieval_and_agent_cases():
    config = GoldenSetConfig(
        knowledge_base_id="KB1",
        agent_id="AGENT1",
        agent_alias_id="ALIAS1",
        cases=(
            GoldenCase(
                id="retrieval-case",
                type=CaseType.RETRIEVAL,
                query="what is the refund window",
                expected_doc_ids=("doc-42", "doc-7"),
                k=5,
                min_recall=1.0,
            ),
            GoldenCase(
                id="tool-case",
                type=CaseType.AGENT,
                query="cancel my subscription",
                expected_tool="cancel_subscription",
                expected_params={"immediate": True},
            ),
        ),
    )

    results = run_golden_set(
        config,
        agent_runtime_client=FakeAgentRuntimeClient(),
        bedrock_runtime_client=FakeBedrockRuntimeClient(),
    )

    by_id = {r.case_id: r for r in results}
    assert by_id["retrieval-case"].passed is True
    assert by_id["retrieval-case"].score == 1.0
    assert by_id["tool-case"].passed is True


def test_run_golden_set_routes_judge_criteria_cases_through_the_judge_client():
    config = GoldenSetConfig(
        agent_id="AGENT1",
        agent_alias_id="ALIAS1",
        cases=(
            GoldenCase(
                id="judge-case",
                type=CaseType.AGENT,
                query="summarize our data retention policy",
                judge_criteria="must mention 90 days",
                min_judge_score=0.8,
            ),
        ),
    )

    results = run_golden_set(
        config,
        agent_runtime_client=FakeAgentRuntimeClient(),
        bedrock_runtime_client=FakeBedrockRuntimeClient(),
    )

    assert results[0].passed is True
    assert results[0].score == 0.95
    assert "90 days" in results[0].detail
