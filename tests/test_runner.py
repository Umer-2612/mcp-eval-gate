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

    results = (await runner_module.run_golden_set(config)).results

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


def _patch_connect(monkeypatch):
    from mcp_eval_gate import runner

    monkeypatch.setattr(runner, "connect", lambda target: connected_session(build_echo_server()))


@pytest.mark.anyio
async def test_run_golden_set_returns_results_and_the_server_contract(monkeypatch):
    from mcp_eval_gate.runner import run_golden_set

    _patch_connect(monkeypatch)
    case = GoldenCase(id="e", tool_name="echo", tool_args={"message": "hi"}, expected_output="hi")

    run = await run_golden_set(_config(case))

    assert [r.passed for r in run.results] == [True]
    assert run.results[0].outcome.text == "hi"
    assert run.contract["serverInfo"]["name"] == "echo-test-server"


@pytest.mark.anyio
async def test_snapshot_cases_record_then_compare_against_the_recorded_outcome(monkeypatch):
    from mcp_eval_gate.runner import run_golden_set

    _patch_connect(monkeypatch)
    case = GoldenCase(id="s", tool_name="add", tool_args={"a": 2, "b": 3}, match_type=MatchType.SNAPSHOT)
    config = _config(case)

    recorded = await run_golden_set(config, recording=True)
    same = await run_golden_set(config, recorded_outcomes={"s": recorded.results[0].outcome})
    drifted_outcome = recorded.results[0].outcome.__class__(text="6", structured=None, is_error=False)
    drifted = await run_golden_set(config, recorded_outcomes={"s": drifted_outcome})

    assert recorded.results[0].passed is True
    assert same.results[0].passed is True
    assert drifted.results[0].passed is False


@pytest.mark.anyio
async def test_a_protocol_error_satisfies_an_expect_error_case_but_a_timeout_never_does(monkeypatch):
    from mcp_eval_gate.runner import run_golden_set

    _patch_connect(monkeypatch)
    unknown_tool = GoldenCase(
        id="bad", tool_name="no_such_tool", expected_output="", match_type=MatchType.SNAPSHOT, expect_error=True
    )
    hangs = GoldenCase(
        id="hang",
        tool_name="slow",
        tool_args={"seconds": 30},
        expected_output="x",
        expect_error=True,
        timeout_seconds=0.3,
    )

    run = await run_golden_set(_config(unknown_tool, hangs), recording=True)

    by_id = {r.case_id: r for r in run.results}
    assert by_id["bad"].passed is True
    assert by_id["hang"].passed is False
    assert "timed out" in by_id["hang"].detail


@pytest.mark.anyio
async def test_case_level_normalizers_are_applied_on_top_of_file_level_ones(monkeypatch):
    from mcp_eval_gate.normalize import parse_normalizers
    from mcp_eval_gate.runner import run_golden_set

    _patch_connect(monkeypatch)
    case = GoldenCase(
        id="n",
        tool_name="echo",
        tool_args={"message": "  hi  "},
        match_type=MatchType.EXACT,
        expected_output="hi",
        normalize=parse_normalizers(["tmp_paths"]),
    )
    config = GoldenSetConfig(
        server=ServerTarget(command="unused"), cases=(case,), normalize=parse_normalizers(["trim"])
    )

    run = await run_golden_set(config)

    assert run.results[0].passed is True
