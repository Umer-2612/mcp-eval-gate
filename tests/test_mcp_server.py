import json

import pytest

from mcp_eval_gate import mcp_server, runner
from tests.mcp_test_server import build_echo_server, connected_session

GOLDEN_SET = """\
server:
  command: unused
cases:
  - id: echo-case
    tool_name: echo
    tool_args:
      message: "hello world"
    match_type: contains
    expected_output: "hello"
"""


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _patch_connect(monkeypatch):
    monkeypatch.setattr(runner, "connect", lambda target: connected_session(build_echo_server()))


@pytest.mark.anyio
async def test_run_eval_gate_returns_ok_true_when_everything_passes(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(GOLDEN_SET)

    result = await mcp_server.run_eval_gate(
        config_path=str(config_path), baseline_path=str(tmp_path / "baseline.json")
    )

    assert result["ok"] is True
    assert result["cases"][0]["case_id"] == "echo-case"


@pytest.mark.anyio
async def test_run_eval_gate_returns_error_for_invalid_config(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text("cases:\n  - id: bad\n")

    result = await mcp_server.run_eval_gate(config_path=str(config_path))

    assert result["ok"] is False
    assert "error" in result


@pytest.mark.anyio
async def test_run_eval_gate_update_baseline_writes_file(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(GOLDEN_SET)
    baseline_path = tmp_path / "baseline.json"

    result = await mcp_server.run_eval_gate(
        config_path=str(config_path), baseline_path=str(baseline_path), update_baseline=True
    )

    assert result["baseline_updated"] is True
    assert json.loads(baseline_path.read_text())["cases"]["echo-case"]["score"] == 1.0


@pytest.mark.anyio
async def test_run_eval_gate_returns_an_error_when_the_server_cannot_start(tmp_path):
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        "server:\n  command: definitely-not-a-real-command-xyz\ncases:\n"
        "  - id: c1\n    tool_name: echo\n    match_type: contains\n    expected_output: x\n"
    )

    result = await mcp_server.run_eval_gate(config_path=str(config_path))

    assert result["ok"] is False
    assert "could not run" in result["error"].lower()


@pytest.mark.anyio
async def test_run_eval_gate_reports_contract_changes_and_can_fail_on_them(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(GOLDEN_SET)
    baseline_path = tmp_path / "baseline.json"
    await mcp_server.run_eval_gate(
        config_path=str(config_path), baseline_path=str(baseline_path), update_baseline=True
    )
    saved = json.loads(baseline_path.read_text())
    saved["contract"]["serverInfo"]["version"] = "9.9.9"
    baseline_path.write_text(json.dumps(saved))

    lenient = await mcp_server.run_eval_gate(config_path=str(config_path), baseline_path=str(baseline_path))
    strict = await mcp_server.run_eval_gate(
        config_path=str(config_path), baseline_path=str(baseline_path), strict_contract=True
    )

    assert lenient["ok"] is True
    assert lenient["contract_changes"] == ["serverInfo.version: '9.9.9' -> ''"]
    assert strict["ok"] is False


@pytest.mark.anyio
async def test_run_eval_gate_declares_tool_annotations():
    tools = await mcp_server.mcp.list_tools()

    annotations = next(t for t in tools if t.name == "run_eval_gate").annotations

    assert annotations.read_only_hint is False
    assert annotations.destructive_hint is True
    assert annotations.idempotent_hint is True
    assert annotations.open_world_hint is True


@pytest.mark.anyio
async def test_run_eval_gate_refuses_to_record_a_baseline_while_a_case_fails(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(GOLDEN_SET.replace('expected_output: "hello"', 'expected_output: "never"'))
    baseline_path = tmp_path / "baseline.json"

    result = await mcp_server.run_eval_gate(
        config_path=str(config_path), baseline_path=str(baseline_path), update_baseline=True
    )

    assert result["ok"] is False
    assert "baseline not updated" in result["error"]
    assert not baseline_path.exists()


@pytest.mark.anyio
async def test_run_eval_gate_can_repair_a_corrupt_baseline_with_update_baseline(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(GOLDEN_SET)
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text("{oops")

    result = await mcp_server.run_eval_gate(
        config_path=str(config_path), baseline_path=str(baseline_path), update_baseline=True
    )

    assert result["ok"] is True
