import pytest

from mcp_eval_gate.contract import (
    capture_contract,
    diff_contract,
    lint_call,
    lint_contract,
)
from mcp_eval_gate.models import ToolCallOutcome
from tests.mcp_test_server import build_echo_server, connected_session


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _contract(**tools) -> dict:
    return {
        "protocolVersion": "2025-11-25",
        "serverInfo": {"name": "s", "version": "1.0"},
        "capabilities": {"tools": {"listChanged": False}},
        "tools": tools,
        "toolOrder": list(tools),
    }


@pytest.mark.anyio
async def test_capture_contract_reads_the_wire_level_server_surface():
    async with connected_session(build_echo_server()) as session:
        contract = await capture_contract(session)

    assert contract["serverInfo"]["name"] == "echo-test-server"
    assert contract["protocolVersion"]
    assert set(contract["tools"]) == {"echo", "add", "slow", "always_fails"}
    assert contract["tools"]["echo"]["inputSchema"]["required"] == ["message"]
    assert contract["toolOrder"][0] == "echo"


def test_identical_contracts_have_no_changes():
    contract = _contract(t={"inputSchema": {"type": "object"}})

    assert diff_contract(contract, contract) == []


def test_diff_reports_changed_added_and_removed_paths():
    before = _contract(t={"inputSchema": {"type": "object", "required": ["a"]}}, gone={"description": "x"})
    after = _contract(t={"inputSchema": {"type": "object", "required": ["a", "b"]}}, fresh={"description": "y"})

    changes = {(c.path, c.kind) for c in diff_contract(before, after)}

    assert ("tools.t.inputSchema.required", "changed") in changes
    assert ("tools.gone", "removed") in changes
    assert ("tools.fresh", "added") in changes


def test_diff_reports_a_reordered_tool_list():
    before = _contract(a={"description": "1"}, b={"description": "2"})
    after = {**before, "toolOrder": ["b", "a"]}

    changes = diff_contract(before, after)

    assert [c.path for c in changes] == ["toolOrder"]


def test_diff_skips_ignored_paths_and_everything_below_them():
    before = _contract(t={"description": "old"})
    after = {**_contract(t={"description": "new"}), "serverInfo": {"name": "s", "version": "2.0"}}

    changes = diff_contract(before, after, ignore=("serverInfo.version", "tools.t"))

    assert changes == []


def test_lint_flags_a_draft_07_schema_dialect():
    contract = _contract(
        t={"inputSchema": {"type": "object"}, "outputSchema": {"$schema": "http://json-schema.org/draft-07/schema#"}}
    )

    findings = lint_contract(contract)

    assert len(findings) == 1
    assert "'t'" in findings[0] and "draft-07" in findings[0]


def test_lint_accepts_a_2020_12_schema_dialect():
    contract = _contract(
        t={"inputSchema": {"type": "object", "$schema": "https://json-schema.org/draft/2020-12/schema"}}
    )

    assert lint_contract(contract) == []


def test_lint_flags_root_level_composition_keywords_that_make_clients_drop_the_tool():
    contract = _contract(t={"inputSchema": {"type": "object", "allOf": [{"required": ["a"]}]}})

    findings = lint_contract(contract)

    assert len(findings) == 1
    assert "allOf" in findings[0]


def test_lint_flags_an_input_schema_that_is_not_an_object():
    findings = lint_contract(_contract(t={"inputSchema": {"type": "array"}}))

    assert len(findings) == 1
    assert "object" in findings[0]


def test_lint_is_clean_for_an_ordinary_server():
    assert lint_contract(_contract(t={"inputSchema": {"type": "object", "properties": {}}})) == []


def test_lint_call_flags_structured_content_that_violates_the_output_schema():
    contract = _contract(
        t={"outputSchema": {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}}
    )
    outcome = ToolCallOutcome(text="x", structured={"n": "not a number"}, is_error=False)

    findings = lint_call("t", outcome, contract)

    assert len(findings) == 1
    assert "outputSchema" in findings[0]


def test_lint_call_flags_a_missing_structured_content_when_an_output_schema_is_declared():
    contract = _contract(t={"outputSchema": {"type": "object"}})
    outcome = ToolCallOutcome(text="x", structured=None, is_error=False)

    findings = lint_call("t", outcome, contract)

    assert len(findings) == 1
    assert "structuredContent" in findings[0]


def test_lint_call_is_quiet_for_valid_output_and_for_error_results():
    contract = _contract(t={"outputSchema": {"type": "object", "properties": {"n": {"type": "integer"}}}})

    assert lint_call("t", ToolCallOutcome(text="x", structured={"n": 1}, is_error=False), contract) == []
    assert lint_call("t", ToolCallOutcome(text="boom", structured=None, is_error=True), contract) == []
    assert lint_call("unknown", ToolCallOutcome(text="x", structured=None, is_error=False), contract) == []
