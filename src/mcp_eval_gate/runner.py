"""Wires golden-set cases to a live MCP server and the scoring functions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from mcp.shared.exceptions import MCPError
from mcp.types import REQUEST_TIMEOUT

from mcp_eval_gate.contract import capture_contract
from mcp_eval_gate.judge import judge_answer
from mcp_eval_gate.mcp_client import call_tool, connect
from mcp_eval_gate.models import (
    CaseResult,
    GoldenCase,
    GoldenSetConfig,
    MatchType,
    ToolCallOutcome,
)
from mcp_eval_gate.scoring import score_case, score_judge_case
from mcp_eval_gate.text_diff import preview


@dataclass(frozen=True)
class GoldenRun:
    results: list[CaseResult]
    contract: dict


async def run_golden_set(
    config: GoldenSetConfig,
    *,
    anthropic_client: Any | None = None,
    recorded_outcomes: Mapping[str, ToolCallOutcome] | None = None,
    recording: bool = False,
) -> GoldenRun:
    """Call every case's tool on one connection. `recorded_outcomes` feeds snapshot cases,
    `recording` makes them pass and keep their outcome so it can be saved as the baseline."""
    async with connect(config.server) as session:
        contract = await capture_contract(session)
        results = []
        for case in config.cases:
            results.append(
                await run_case(
                    case,
                    session=session,
                    config=config,
                    anthropic_client=anthropic_client,
                    recorded=(recorded_outcomes or {}).get(case.id),
                    recording=recording,
                )
            )
        return GoldenRun(results=results, contract=contract)


async def run_case(
    case: GoldenCase,
    *,
    session: Any,
    config: GoldenSetConfig,
    anthropic_client: Any | None,
    recorded: ToolCallOutcome | None = None,
    recording: bool = False,
) -> CaseResult:
    try:
        outcome = await call_tool(session, case.tool_name, case.tool_args, timeout_seconds=case.timeout_seconds)
    except MCPError as exc:
        if exc.code == REQUEST_TIMEOUT or not case.expect_error:
            return CaseResult(case.id, score=0.0, passed=False, detail=_describe_protocol_error(exc, case))
        outcome = ToolCallOutcome(text=exc.message, structured=None, is_error=True)

    if case.match_type != MatchType.JUDGE:
        normalizers = config.normalize + case.normalize
        return score_case(case, outcome, normalizers=normalizers, recorded=recorded, recording=recording)

    return _score_judge(case, outcome, config=config, anthropic_client=anthropic_client)


def _score_judge(
    case: GoldenCase, outcome: ToolCallOutcome, *, config: GoldenSetConfig, anthropic_client: Any | None
) -> CaseResult:
    if outcome.is_error:
        return CaseResult(
            case.id,
            score=0.0,
            passed=False,
            detail=f"tool call returned an error: {preview(outcome.text)}",
            outcome=outcome,
        )

    if anthropic_client is None:
        return CaseResult(
            case.id,
            score=0.0,
            passed=False,
            detail="match_type=judge needs [judge] extras installed and ANTHROPIC_API_KEY set",
            outcome=outcome,
        )

    score, reasoning = judge_answer(
        anthropic_client, model=config.judge_model, criteria=case.judge_criteria or "", answer=outcome.text
    )
    return replace(score_judge_case(case, judge_score=score, reasoning=reasoning), outcome=outcome)


def _describe_protocol_error(exc: MCPError, case: GoldenCase) -> str:
    if exc.code == REQUEST_TIMEOUT:
        return f"timed out after {case.timeout_seconds:g}s with no response"
    return f"MCP protocol error {exc.code}: {preview(exc.message)}"
