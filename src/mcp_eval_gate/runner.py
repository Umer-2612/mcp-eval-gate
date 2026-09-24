"""Wires golden-set cases to a live MCP server and the scoring functions."""

from __future__ import annotations

from typing import Any

from mcp_eval_gate.judge import judge_answer
from mcp_eval_gate.mcp_client import call_tool, connect
from mcp_eval_gate.models import CaseResult, GoldenCase, GoldenSetConfig, MatchType
from mcp_eval_gate.scoring import score_case, score_judge_case
from mcp_eval_gate.text_diff import preview


async def run_golden_set(config: GoldenSetConfig, *, anthropic_client: Any | None = None) -> list[CaseResult]:
    async with connect(config.server) as session:
        results = []
        for case in config.cases:
            results.append(await run_case(case, session=session, config=config, anthropic_client=anthropic_client))
        return results


async def run_case(
    case: GoldenCase, *, session: Any, config: GoldenSetConfig, anthropic_client: Any | None
) -> CaseResult:
    outcome = await call_tool(session, case.tool_name, case.tool_args)

    if case.match_type != MatchType.JUDGE:
        return score_case(case, outcome)

    if outcome.is_error:
        return CaseResult(
            case.id, score=0.0, passed=False, detail=f"tool call returned an error: {preview(outcome.text)}"
        )

    if anthropic_client is None:
        return CaseResult(
            case.id,
            score=0.0,
            passed=False,
            detail="match_type=judge needs [judge] extras installed and ANTHROPIC_API_KEY set",
        )

    score, reasoning = judge_answer(
        anthropic_client, model=config.judge_model, criteria=case.judge_criteria or "", answer=outcome.text
    )
    return score_judge_case(case, judge_score=score, reasoning=reasoning)
