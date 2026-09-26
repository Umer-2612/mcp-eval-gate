"""The commands that take a server directly: init --command, lint, compare."""

import yaml
from click.testing import CliRunner
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from mcp_eval_gate import cli, compare, discover
from mcp_eval_gate.golden_set import load_golden_set
from tests.mcp_test_server import build_echo_server, connected_session


def _catalog_server() -> MCPServer:
    server = MCPServer("catalog")

    @server.tool(annotations=ToolAnnotations(read_only_hint=True))
    def list_items() -> str:
        """List items."""
        return "a,b"

    @server.tool(annotations=ToolAnnotations(destructive_hint=True))
    def delete_all() -> str:
        """Delete everything."""
        return "gone"

    @server.tool()
    def search(query: str, limit: int = 5) -> str:
        """Search."""
        return query

    @server.tool()
    def ping() -> str:
        """Unannotated, no arguments."""
        return "pong"

    return server


def _patch(monkeypatch, module, server_for):
    monkeypatch.setattr(module, "connect", lambda target: connected_session(server_for(target)))


def test_init_from_a_server_writes_a_golden_set_that_loads(tmp_path, monkeypatch):
    _patch(monkeypatch, discover, lambda target: _catalog_server())
    out = tmp_path / "golden_set.yaml"

    result = CliRunner().invoke(cli.main, ["init", "--out", str(out), "--command", "my-server --flag"])

    assert result.exit_code == 0, result.output
    config = load_golden_set(out)
    assert config.server.command == "my-server"
    assert config.server.args == ("--flag",)
    enabled = {c.tool_name for c in config.cases}
    assert enabled == {"list_items", "ping"}
    assert all(c.match_type.value == "snapshot" for c in config.cases)


def test_init_from_a_server_leaves_stubs_for_tools_that_need_arguments_or_change_state(tmp_path, monkeypatch):
    _patch(monkeypatch, discover, lambda target: _catalog_server())
    out = tmp_path / "golden_set.yaml"

    CliRunner().invoke(cli.main, ["init", "--out", str(out), "--command", "my-server"])
    text = out.read_text()

    assert "# - id: search" in text
    assert "required: query" in text
    assert "# - id: delete_all" in text
    assert "changes state" in text
    assert yaml.safe_load(text)["server"]["command"] == "my-server"


def test_init_from_a_url_writes_a_url_server_block(tmp_path, monkeypatch):
    _patch(monkeypatch, discover, lambda target: _catalog_server())
    out = tmp_path / "golden_set.yaml"

    result = CliRunner().invoke(cli.main, ["init", "--out", str(out), "--url", "http://localhost:3000/mcp"])

    assert result.exit_code == 0, result.output
    assert load_golden_set(out).server.url == "http://localhost:3000/mcp"


def test_init_rejects_command_and_url_together(tmp_path):
    result = CliRunner().invoke(
        cli.main, ["init", "--out", str(tmp_path / "g.yaml"), "--command", "x", "--url", "http://y"]
    )

    assert result.exit_code != 0
    assert "only one" in result.output.lower()


def test_lint_reports_nothing_for_a_clean_server_and_exits_zero(tmp_path, monkeypatch):
    _patch(monkeypatch, discover, lambda target: build_echo_server())

    result = CliRunner().invoke(cli.main, ["lint", "--command", "my-server"])

    assert result.exit_code == 0, result.output
    assert "no contract warnings" in result.output.lower()


def test_lint_exits_one_and_lists_findings_for_a_risky_contract(tmp_path, monkeypatch):
    risky = {
        "protocolVersion": "2025-11-25",
        "serverInfo": {"name": "s"},
        "capabilities": {},
        "tools": {"t": {"name": "t", "inputSchema": {"type": "object", "allOf": [{}]}}},
        "toolOrder": ["t"],
    }

    async def fake_fetch(target):
        return risky

    monkeypatch.setattr(cli, "fetch_contract", fake_fetch)

    result = CliRunner().invoke(cli.main, ["lint", "--command", "my-server"])

    assert result.exit_code == 1
    assert "root-level allOf" in result.output


def test_lint_needs_exactly_one_server_source():
    result = CliRunner().invoke(cli.main, ["lint"])

    assert result.exit_code != 0


def _variant_server(add_offset: int) -> MCPServer:
    server = MCPServer("variant")

    @server.tool()
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b + add_offset

    return server


COMPARE_SET = """\
server:
  command: server-a
cases:
  - id: add-case
    tool_name: add
    tool_args: {a: 2, b: 3}
    match_type: contains
    expected_output: "5"
"""


def _server_by_command(target):
    return _variant_server(0 if target.command == "server-a" else 1)


def test_compare_exits_zero_when_both_servers_behave_the_same(tmp_path, monkeypatch):
    _patch(monkeypatch, compare.runner, lambda target: _variant_server(0))
    config = tmp_path / "golden_set.yaml"
    config.write_text(COMPARE_SET)

    result = CliRunner().invoke(cli.main, ["compare", "--config", str(config), "--against", "server-b"])

    assert result.exit_code == 0, result.output
    assert "same output" in result.output.lower()


def test_compare_exits_one_and_shows_the_difference_between_two_servers(tmp_path, monkeypatch):
    _patch(monkeypatch, compare.runner, _server_by_command)
    config = tmp_path / "golden_set.yaml"
    config.write_text(COMPARE_SET)

    result = CliRunner().invoke(cli.main, ["compare", "--config", str(config), "--against", "server-b"])

    assert result.exit_code == 1
    assert "add-case" in result.output
    assert "first difference" in result.output


def test_compare_ignores_a_case_pass_fail_and_only_looks_at_differences(tmp_path, monkeypatch):
    _patch(monkeypatch, compare.runner, lambda target: _variant_server(1))
    config = tmp_path / "golden_set.yaml"
    config.write_text(COMPARE_SET)

    result = CliRunner().invoke(cli.main, ["compare", "--config", str(config), "--against", "server-b"])

    assert result.exit_code == 0, result.output


def test_compare_reports_contract_differences(tmp_path, monkeypatch):
    def server_for(target):
        return _variant_server(0) if target.command == "server-a" else _catalog_server()

    _patch(monkeypatch, compare.runner, server_for)
    config = tmp_path / "golden_set.yaml"
    config.write_text(COMPARE_SET.replace("tool_name: add", "tool_name: ping").replace("a: 2, b: 3", ""))

    result = CliRunner().invoke(cli.main, ["compare", "--config", str(config), "--against", "server-b"])

    assert result.exit_code == 1
    assert "contract" in result.output.lower()
    assert "serverInfo.name" in result.output


def test_compare_needs_exactly_one_second_server(tmp_path):
    config = tmp_path / "golden_set.yaml"
    config.write_text(COMPARE_SET)

    result = CliRunner().invoke(cli.main, ["compare", "--config", str(config)])

    assert result.exit_code != 0


def test_run_with_no_enabled_cases_exits_2_and_says_what_to_do(tmp_path):
    (tmp_path / "golden_set.yaml").write_text("server:\n  command: node\ncases:\n  # - id: c1\n")

    result = CliRunner().invoke(cli.main, ["run", "--config", str(tmp_path / "golden_set.yaml")])

    assert result.exit_code == 2
    assert "no cases" in result.output.lower()
    assert "Traceback" not in result.output


def test_lint_works_from_a_config_that_has_no_enabled_cases(tmp_path, monkeypatch):
    _patch(monkeypatch, discover, lambda target: build_echo_server())
    (tmp_path / "golden_set.yaml").write_text("server:\n  command: node\ncases:\n")

    result = CliRunner().invoke(cli.main, ["lint", "--config", str(tmp_path / "golden_set.yaml")])

    assert result.exit_code == 0, result.output
