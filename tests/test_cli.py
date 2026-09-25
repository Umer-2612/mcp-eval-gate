import json

from click.testing import CliRunner

from mcp_eval_gate import cli, runner
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


def _patch_connect(monkeypatch):
    monkeypatch.setattr(runner, "connect", lambda target: connected_session(build_echo_server()))


def test_init_writes_starter_golden_set(tmp_path):
    runner_cli = CliRunner()
    out = tmp_path / "golden_set.yaml"

    result = runner_cli.invoke(cli.main, ["init", "--out", str(out)])

    assert result.exit_code == 0
    assert out.exists()
    assert "cases:" in out.read_text()


def test_init_refuses_to_overwrite_existing_file(tmp_path):
    runner_cli = CliRunner()
    out = tmp_path / "golden_set.yaml"
    out.write_text("existing content")

    result = runner_cli.invoke(cli.main, ["init", "--out", str(out)])

    assert result.exit_code == 1
    assert out.read_text() == "existing content"


def test_run_exits_zero_when_all_cases_pass(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(GOLDEN_SET)
    runner_cli = CliRunner()

    result = runner_cli.invoke(
        cli.main, ["run", "--config", str(config_path), "--baseline", str(tmp_path / "baseline.json")]
    )

    assert result.exit_code == 0


def test_run_exits_nonzero_and_reports_regression(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        "server:\n  command: unused\ncases:\n"
        "  - id: echo-case\n    tool_name: echo\n    tool_args: {message: hello}\n"
        "    match_type: contains\n    expected_output: this-will-never-match\n"
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"echo-case": 1.0}))
    runner_cli = CliRunner()

    result = runner_cli.invoke(cli.main, ["run", "--config", str(config_path), "--baseline", str(baseline_path)])

    assert result.exit_code == 1
    assert "regression" in result.output.lower()


def test_run_update_baseline_writes_current_scores(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(GOLDEN_SET)
    baseline_path = tmp_path / "baseline.json"
    runner_cli = CliRunner()

    result = runner_cli.invoke(
        cli.main, ["run", "--config", str(config_path), "--baseline", str(baseline_path), "--update-baseline"]
    )

    assert result.exit_code == 0
    assert json.loads(baseline_path.read_text()) == {"echo-case": 1.0}


def test_run_writes_html_report_when_requested(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(GOLDEN_SET)
    html_path = tmp_path / "report.html"
    runner_cli = CliRunner()

    runner_cli.invoke(
        cli.main,
        [
            "run",
            "--config",
            str(config_path),
            "--baseline",
            str(tmp_path / "baseline.json"),
            "--html-report",
            str(html_path),
        ],
    )

    assert html_path.exists()
    assert "echo-case" in html_path.read_text()


def test_run_exits_2_on_invalid_golden_set(tmp_path):
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text("cases:\n  - id: no-server-block\n")
    runner_cli = CliRunner()

    result = runner_cli.invoke(cli.main, ["run", "--config", str(config_path)])

    assert result.exit_code == 2


def test_run_over_a_real_stdio_server_fails_a_hung_tool_and_exits_1(tmp_path):
    import sys
    from pathlib import Path

    server_script = Path(__file__).parent / "fixtures" / "stdio_test_server.py"
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        f"server:\n  command: {sys.executable}\n  args: ['{server_script}']\n"
        "cases:\n"
        "  - id: hangs\n    tool_name: slow\n    tool_args: {seconds: 30}\n"
        "    match_type: contains\n    expected_output: done\n    timeout_seconds: 0.5\n"
        "  - id: still-runs\n    tool_name: echo\n    tool_args: {message: hello}\n"
        "    match_type: contains\n    expected_output: hello\n"
    )
    runner_cli = CliRunner()

    result = runner_cli.invoke(
        cli.main, ["run", "--config", str(config_path), "--baseline", str(tmp_path / "b.json")]
    )

    assert result.exit_code == 1
    assert "timed out after 0.5s" in result.output
    assert "still-runs" in result.output
