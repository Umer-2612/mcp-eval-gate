from bedrock_eval_gate.models import AgentOutcome, CaseType, GoldenCase, RetrievalOutcome
from bedrock_eval_gate.scoring import score_agent_case, score_judge_case, score_retrieval_case


def _retrieval_case(**overrides) -> GoldenCase:
    defaults = dict(
        id="case-1",
        type=CaseType.RETRIEVAL,
        query="what is the refund window",
        knowledge_base_id="KB1",
        expected_doc_ids=("doc-42", "doc-7"),
        k=5,
        min_recall=1.0,
    )
    defaults.update(overrides)
    return GoldenCase(**defaults)


def test_recall_is_perfect_when_all_expected_docs_are_retrieved():
    case = _retrieval_case()
    outcome = RetrievalOutcome(retrieved_doc_ids=("doc-7", "doc-42", "doc-99"))

    result = score_retrieval_case(case, outcome)

    assert result.score == 1.0
    assert result.passed is True


def test_recall_drops_when_an_expected_doc_is_missing():
    case = _retrieval_case()
    outcome = RetrievalOutcome(retrieved_doc_ids=("doc-7", "doc-99"))

    result = score_retrieval_case(case, outcome)

    assert result.score == 0.5
    assert result.passed is False
    assert "doc-42" in result.detail


def test_only_top_k_retrieved_docs_count_toward_recall():
    case = _retrieval_case(k=1)
    outcome = RetrievalOutcome(retrieved_doc_ids=("doc-99", "doc-42", "doc-7"))

    result = score_retrieval_case(case, outcome)

    assert result.score == 0.0
    assert result.passed is False


def test_case_passes_when_score_meets_min_recall_threshold():
    case = _retrieval_case(min_recall=0.5)
    outcome = RetrievalOutcome(retrieved_doc_ids=("doc-7",))

    result = score_retrieval_case(case, outcome)

    assert result.score == 0.5
    assert result.passed is True


def _agent_case(**overrides) -> GoldenCase:
    defaults = dict(
        id="case-2",
        type=CaseType.AGENT,
        query="cancel my subscription now",
        agent_id="AGENT1",
        expected_tool="cancel_subscription",
        expected_params={"immediate": True},
    )
    defaults.update(overrides)
    return GoldenCase(**defaults)


def test_agent_case_passes_when_tool_and_params_match():
    case = _agent_case()
    outcome = AgentOutcome(
        called_tool="cancel_subscription",
        called_params={"immediate": True, "reason": "user_requested"},
        final_answer="Done, cancelled immediately.",
    )

    result = score_agent_case(case, outcome)

    assert result.passed is True
    assert result.score == 1.0


def test_agent_case_fails_when_wrong_tool_is_called():
    case = _agent_case()
    outcome = AgentOutcome(
        called_tool="pause_subscription",
        called_params={"immediate": True},
        final_answer="Paused instead.",
    )

    result = score_agent_case(case, outcome)

    assert result.passed is False
    assert "pause_subscription" in result.detail


def test_agent_case_fails_when_expected_param_value_differs():
    case = _agent_case()
    outcome = AgentOutcome(
        called_tool="cancel_subscription",
        called_params={"immediate": False},
        final_answer="Scheduled cancellation for period end.",
    )

    result = score_agent_case(case, outcome)

    assert result.passed is False
    assert "immediate" in result.detail


def test_agent_case_fails_when_no_tool_was_called_but_one_was_expected():
    case = _agent_case()
    outcome = AgentOutcome(called_tool=None, called_params={}, final_answer="I'm not sure how to help.")

    result = score_agent_case(case, outcome)

    assert result.passed is False
    assert result.score == 0.0


def _judge_case(**overrides) -> GoldenCase:
    defaults = dict(
        id="case-3",
        type=CaseType.AGENT,
        query="summarize our data retention policy",
        agent_id="AGENT1",
        judge_criteria="Answer must state data is retained for 90 days",
        min_judge_score=0.8,
    )
    defaults.update(overrides)
    return GoldenCase(**defaults)


def test_judge_case_passes_when_score_meets_threshold():
    case = _judge_case()

    result = score_judge_case(case, judge_score=0.9, reasoning="mentions 90 days and cites the doc")

    assert result.passed is True
    assert result.score == 0.9
    assert "90 days" in result.detail


def test_judge_case_fails_when_score_below_threshold():
    case = _judge_case()

    result = score_judge_case(case, judge_score=0.5, reasoning="missing the citation")

    assert result.passed is False
    assert result.score == 0.5
