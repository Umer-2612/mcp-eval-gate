"""End-to-end wiring test using an in-memory MCP server — no subprocess, no network."""

import pytest

from mcp_eval_gate.models import GoldenCase, GoldenSetConfig, MatchType, ServerTarget
from mcp_eval_gate.runner import run_case
from tests.fakes import FakeAnthropicClient
from tests.mcp_test_server import build_echo_server, connected_session


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _config(*cases: GoldenCase) -> GoldenSetConfig:
    return GoldenSetConfig(server=ServerTarget(command="unused"), cases=cases)


@pytest.mark.anyio
async def test_run_case_scores_a_contains_case_against_a_real_tool_call():
    case = GoldenCase(
        id="echo-case",
        tool_name="echo",
        tool_args={"message": "hello world"},
        match_type=MatchType.CONTAINS,
        expected_output="hello",
    )

    async with connected_session(build_echo_server()) as session:
        result = await run_case(case, session=session, config=_config(case), anthropic_client=None)

    assert result.passed is True


@pytest.mark.anyio
async def test_run_case_scores_structured_tool_output_via_exact_match():
    case = GoldenCase(
        id="add-case", tool_name="add", tool_args={"a": 2, "b": 3}, match_type=MatchType.EXACT, expected_output="5"
    )

    async with connected_session(build_echo_server()) as session:
        result = await run_case(case, session=session, config=_config(case), anthropic_client=None)

    assert result.passed is True


@pytest.mark.anyio
async def test_run_case_routes_judge_criteria_through_the_anthropic_client():
    case = GoldenCase(
        id="judge-case",
        tool_name="echo",
        tool_args={"message": "Data is retained for 90 days."},
        match_type=MatchType.JUDGE,
        judge_criteria="must mention 90 days",
        min_judge_score=0.8,
    )
    anthropic_client = FakeAnthropicClient('{"score": 0.95, "reasoning": "covers 90 days"}')

    async with connected_session(build_echo_server()) as session:
        result = await run_case(case, session=session, config=_config(case), anthropic_client=anthropic_client)

    assert result.passed is True
    assert result.score == 0.95
    assert "90 days" in result.detail


@pytest.mark.anyio
async def test_run_case_fails_judge_case_with_no_anthropic_client_configured():
    case = GoldenCase(
        id="judge-case",
        tool_name="echo",
        tool_args={"message": "hi"},
        match_type=MatchType.JUDGE,
        judge_criteria="anything",
    )

    async with connected_session(build_echo_server()) as session:
        result = await run_case(case, session=session, config=_config(case), anthropic_client=None)

    assert result.passed is False
    assert "ANTHROPIC_API_KEY" in result.detail


@pytest.mark.anyio
async def test_run_case_fails_judge_case_when_tool_itself_errors():
    case = GoldenCase(id="judge-case", tool_name="always_fails", match_type=MatchType.JUDGE, judge_criteria="x")
    anthropic_client = FakeAnthropicClient('{"score": 1.0, "reasoning": "n/a"}')

    async with connected_session(build_echo_server()) as session:
        result = await run_case(case, session=session, config=_config(case), anthropic_client=anthropic_client)

    assert result.passed is False
    assert "error" in result.detail.lower()


@pytest.mark.anyio
async def test_run_golden_set_connects_once_and_scores_every_case(monkeypatch):
    import mcp_eval_gate.runner as runner_module

    monkeypatch.setattr(runner_module, "connect", lambda target: connected_session(build_echo_server()))

    config = _config(
        GoldenCase(
            id="c1",
            tool_name="echo",
            tool_args={"message": "a"},
            match_type=MatchType.CONTAINS,
            expected_output="a",
        ),
        GoldenCase(
            id="c2",
            tool_name="echo",
            tool_args={"message": "b"},
            match_type=MatchType.CONTAINS,
            expected_output="b",
        ),
    )

    results = await runner_module.run_golden_set(config)

    assert [r.case_id for r in results] == ["c1", "c2"]
    assert all(r.passed for r in results)


@pytest.mark.anyio
async def test_run_case_fails_a_case_that_exceeds_its_timeout():
    import time

    case = GoldenCase(
        id="slow-case",
        tool_name="slow",
        tool_args={"seconds": 5},
        match_type=MatchType.CONTAINS,
        expected_output="done",
        timeout_seconds=0.3,
    )

    async with connected_session(build_echo_server()) as session:
        started = time.monotonic()
        result = await run_case(case, session=session, config=_config(case), anthropic_client=None)
        elapsed = time.monotonic() - started

    assert result.passed is False
    assert result.score == 0.0
    assert "timed out after 0.3s" in result.detail
    assert elapsed < 3


@pytest.mark.anyio
async def test_a_timeout_does_not_stop_later_cases_from_running():
    slow = GoldenCase(
        id="slow-case",
        tool_name="slow",
        tool_args={"seconds": 5},
        match_type=MatchType.CONTAINS,
        expected_output="done",
        timeout_seconds=0.3,
    )
    after = GoldenCase(
        id="after",
        tool_name="echo",
        tool_args={"message": "still alive"},
        match_type=MatchType.CONTAINS,
        expected_output="still alive",
    )
    config = _config(slow, after)

    async with connected_session(build_echo_server()) as session:
        first = await run_case(slow, session=session, config=config, anthropic_client=None)
        second = await run_case(after, session=session, config=config, anthropic_client=None)

    assert first.passed is False
    assert second.passed is True


@pytest.mark.anyio
async def test_a_case_that_finishes_within_its_timeout_is_scored_normally():
    case = GoldenCase(
        id="quick",
        tool_name="slow",
        tool_args={"seconds": 0.05},
        match_type=MatchType.EXACT,
        expected_output="done",
        timeout_seconds=5,
    )

    async with connected_session(build_echo_server()) as session:
        result = await run_case(case, session=session, config=_config(case), anthropic_client=None)

    assert result.passed is True


@pytest.mark.anyio
async def test_a_non_timeout_protocol_error_fails_the_case_instead_of_crashing(monkeypatch):
    from mcp.shared.exceptions import MCPError

    import mcp_eval_gate.runner as runner_module

    async def raising_call_tool(*args, **kwargs):
        raise MCPError(-32602, "Invalid params: missing required argument")

    monkeypatch.setattr(runner_module, "call_tool", raising_call_tool)
    case = GoldenCase(id="bad-params", tool_name="echo", match_type=MatchType.CONTAINS, expected_output="x")

    result = await runner_module.run_case(case, session=None, config=_config(case), anthropic_client=None)

    assert result.passed is False
    assert "-32602" in result.detail
    assert "Invalid params" in result.detail
