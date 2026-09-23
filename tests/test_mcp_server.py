import json

from bedrock_eval_gate import mcp_server
from tests.fakes import FakeAgentRuntimeClient, FakeBedrockRuntimeClient


def _fake_boto3_client(service_name, region_name=None):
    if service_name == "bedrock-agent-runtime":
        return FakeAgentRuntimeClient()
    if service_name == "bedrock-runtime":
        return FakeBedrockRuntimeClient()
    raise AssertionError(f"unexpected service: {service_name}")


def _run_eval_gate_fn():
    return mcp_server.run_eval_gate


def test_run_eval_gate_returns_ok_true_when_everything_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server.boto3, "client", _fake_boto3_client)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        "knowledge_base_id: KB1\n"
        "cases:\n"
        "  - id: retrieval-case\n"
        "    type: retrieval\n"
        "    query: q\n"
        "    expected_doc_ids: [doc-42, doc-7]\n"
    )

    result = _run_eval_gate_fn()(config_path=str(config_path), baseline_path=str(tmp_path / "baseline.json"))

    assert result["ok"] is True
    assert result["cases"][0]["case_id"] == "retrieval-case"


def test_run_eval_gate_returns_error_for_invalid_config(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server.boto3, "client", _fake_boto3_client)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text("cases:\n  - id: bad\n")

    result = _run_eval_gate_fn()(config_path=str(config_path))

    assert result["ok"] is False
    assert "error" in result


def test_run_eval_gate_update_baseline_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server.boto3, "client", _fake_boto3_client)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        "knowledge_base_id: KB1\n"
        "cases:\n"
        "  - id: retrieval-case\n"
        "    type: retrieval\n"
        "    query: q\n"
        "    expected_doc_ids: [doc-42]\n"
    )
    baseline_path = tmp_path / "baseline.json"

    result = _run_eval_gate_fn()(
        config_path=str(config_path), baseline_path=str(baseline_path), update_baseline=True
    )

    assert result["baseline_updated"] is True
    assert json.loads(baseline_path.read_text()) == {"retrieval-case": 1.0}
