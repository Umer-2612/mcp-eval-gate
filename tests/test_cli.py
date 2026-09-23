import json

from click.testing import CliRunner

from bedrock_eval_gate import cli
from tests.fakes import FakeAgentRuntimeClient, FakeBedrockRuntimeClient


def _fake_boto3_client(service_name, region_name=None):
    if service_name == "bedrock-agent-runtime":
        return FakeAgentRuntimeClient()
    if service_name == "bedrock-runtime":
        return FakeBedrockRuntimeClient()
    raise AssertionError(f"unexpected service: {service_name}")


def test_init_writes_starter_golden_set(tmp_path):
    runner = CliRunner()
    out = tmp_path / "golden_set.yaml"

    result = runner.invoke(cli.main, ["init", "--out", str(out)])

    assert result.exit_code == 0
    assert out.exists()
    assert "cases:" in out.read_text()


def test_init_refuses_to_overwrite_existing_file(tmp_path):
    runner = CliRunner()
    out = tmp_path / "golden_set.yaml"
    out.write_text("existing content")

    result = runner.invoke(cli.main, ["init", "--out", str(out)])

    assert result.exit_code == 1
    assert out.read_text() == "existing content"


def test_run_exits_zero_when_all_cases_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.boto3, "client", _fake_boto3_client)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        "knowledge_base_id: KB1\n"
        "agent_id: A1\n"
        "agent_alias_id: AL1\n"
        "cases:\n"
        "  - id: retrieval-case\n"
        "    type: retrieval\n"
        "    query: q\n"
        "    expected_doc_ids: [doc-42, doc-7]\n"
    )
    runner = CliRunner()

    result = runner.invoke(
        cli.main, ["run", "--config", str(config_path), "--baseline", str(tmp_path / "baseline.json")]
    )

    assert result.exit_code == 0


def test_run_exits_nonzero_and_reports_regression(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.boto3, "client", _fake_boto3_client)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        "knowledge_base_id: KB1\n"
        "cases:\n"
        "  - id: retrieval-case\n"
        "    type: retrieval\n"
        "    query: q\n"
        "    expected_doc_ids: [doc-42, doc-7, doc-99]\n"
        "    min_recall: 1.0\n"
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"retrieval-case": 1.0}))
    runner = CliRunner()

    result = runner.invoke(cli.main, ["run", "--config", str(config_path), "--baseline", str(baseline_path)])

    assert result.exit_code == 1
    assert "regression" in result.output.lower()


def test_run_update_baseline_writes_current_scores(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.boto3, "client", _fake_boto3_client)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        "knowledge_base_id: KB1\n"
        "cases:\n"
        "  - id: retrieval-case\n"
        "    type: retrieval\n"
        "    query: q\n"
        "    expected_doc_ids: [doc-42, doc-7]\n"
    )
    baseline_path = tmp_path / "baseline.json"
    runner = CliRunner()

    result = runner.invoke(
        cli.main, ["run", "--config", str(config_path), "--baseline", str(baseline_path), "--update-baseline"]
    )

    assert result.exit_code == 0
    assert json.loads(baseline_path.read_text()) == {"retrieval-case": 1.0}


def test_run_exits_2_on_invalid_golden_set(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.boto3, "client", _fake_boto3_client)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text("cases:\n  - id: no-query-or-type\n")
    runner = CliRunner()

    result = runner.invoke(cli.main, ["run", "--config", str(config_path)])

    assert result.exit_code == 2
