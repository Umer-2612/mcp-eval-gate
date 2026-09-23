"""Wires golden-set cases to Bedrock calls and scoring functions."""

from __future__ import annotations

import uuid
from typing import Any

from bedrock_eval_gate.bedrock_client import invoke_agent, retrieve_from_knowledge_base
from bedrock_eval_gate.judge import judge_answer
from bedrock_eval_gate.models import CaseResult, CaseType, GoldenCase, GoldenSetConfig
from bedrock_eval_gate.scoring import score_agent_case, score_judge_case, score_retrieval_case

DEFAULT_JUDGE_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def run_golden_set(
    config: GoldenSetConfig,
    *,
    agent_runtime_client: Any,
    bedrock_runtime_client: Any,
    judge_model_id: str = DEFAULT_JUDGE_MODEL_ID,
) -> list[CaseResult]:
    return [
        run_case(
            case,
            config=config,
            agent_runtime_client=agent_runtime_client,
            bedrock_runtime_client=bedrock_runtime_client,
            judge_model_id=judge_model_id,
        )
        for case in config.cases
    ]


def run_case(
    case: GoldenCase,
    *,
    config: GoldenSetConfig,
    agent_runtime_client: Any,
    bedrock_runtime_client: Any,
    judge_model_id: str,
) -> CaseResult:
    if case.type == CaseType.RETRIEVAL:
        outcome = retrieve_from_knowledge_base(
            agent_runtime_client,
            knowledge_base_id=case.knowledge_base_id or config.knowledge_base_id,
            query=case.query,
            k=case.k,
            doc_id_metadata_key=config.doc_id_metadata_key,
        )
        return score_retrieval_case(case, outcome)

    outcome = invoke_agent(
        agent_runtime_client,
        agent_id=case.agent_id or config.agent_id,
        agent_alias_id=case.agent_alias_id or config.agent_alias_id,
        session_id=str(uuid.uuid4()),
        query=case.query,
    )

    if case.expected_tool is not None:
        return score_agent_case(case, outcome)

    if case.judge_criteria is not None:
        score, reasoning = judge_answer(
            bedrock_runtime_client,
            model_id=judge_model_id,
            criteria=case.judge_criteria,
            answer=outcome.final_answer,
        )
        return score_judge_case(case, judge_score=score, reasoning=reasoning)

    return CaseResult(case.id, score=1.0, passed=True, detail="no expectation declared on this case")
