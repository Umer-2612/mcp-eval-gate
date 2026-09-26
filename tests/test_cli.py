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
    assert json.loads(baseline_path.read_text())["cases"]["echo-case"]["score"] == 1.0


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


def test_update_baseline_refuses_to_record_failing_cases(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        "server:\n  command: unused\ncases:\n"
        "  - id: good\n    tool_name: echo\n    tool_args: {message: hello}\n"
        "    match_type: contains\n    expected_output: hello\n"
        "  - id: broken\n    tool_name: echo\n    tool_args: {message: hello}\n"
        "    match_type: exact\n    expected_output: something else\n"
    )
    baseline_path = tmp_path / "baseline.json"
    runner_cli = CliRunner()

    result = runner_cli.invoke(
        cli.main, ["run", "--config", str(config_path), "--baseline", str(baseline_path), "--update-baseline"]
    )

    assert result.exit_code == 1
    assert not baseline_path.exists()
    assert "broken" in result.output
    assert "baseline not updated" in result.output.lower()


def test_a_server_that_cannot_start_gives_one_readable_error_not_a_traceback(tmp_path):
    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        "server:\n  command: definitely-not-a-real-command-xyz\ncases:\n"
        "  - id: c1\n    tool_name: echo\n    match_type: contains\n    expected_output: x\n"
    )
    runner_cli = CliRunner()

    result = runner_cli.invoke(
        cli.main, ["run", "--config", str(config_path), "--baseline", str(tmp_path / "b.json")]
    )

    assert result.exit_code == 2
    assert "could not run" in result.output.lower()
    assert "definitely-not-a-real-command-xyz" in result.output
    assert "Traceback" not in result.output
    assert len(result.output.splitlines()) < 10


def test_a_server_that_exits_immediately_gives_a_readable_error(tmp_path):
    import sys

    config_path = tmp_path / "golden_set.yaml"
    config_path.write_text(
        f"server:\n  command: {sys.executable}\n  args: ['-c', 'import sys; sys.exit(3)']\ncases:\n"
        "  - id: c1\n    tool_name: echo\n    match_type: contains\n    expected_output: x\n"
    )
    runner_cli = CliRunner()

    result = runner_cli.invoke(
        cli.main, ["run", "--config", str(config_path), "--baseline", str(tmp_path / "b.json")]
    )

    assert result.exit_code == 2
    assert "could not run" in result.output.lower()
    assert "Traceback" not in result.output


SNAPSHOT_SET = """\
server:
  command: unused
cases:
  - id: add-snap
    tool_name: add
    tool_args: {a: 2, b: 3}
    match_type: snapshot
"""


def _run(tmp_path, *extra):
    return CliRunner().invoke(
        cli.main,
        [
            "run",
            "--config",
            str(tmp_path / "golden_set.yaml"),
            "--baseline",
            str(tmp_path / "baseline.json"),
            *extra,
        ],
    )


def test_snapshot_case_is_recorded_by_update_baseline_then_gated_on_later_runs(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    (tmp_path / "golden_set.yaml").write_text(SNAPSHOT_SET)

    recorded = _run(tmp_path, "--update-baseline")
    saved = json.loads((tmp_path / "baseline.json").read_text())
    unchanged = _run(tmp_path)

    assert recorded.exit_code == 0
    assert saved["version"] == 2
    assert saved["cases"]["add-snap"]["outcome"]["text"] == "5"
    assert saved["contract"]["serverInfo"]["name"] == "echo-test-server"
    assert unchanged.exit_code == 0


def test_snapshot_case_fails_the_run_when_the_output_drifts_from_the_recording(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    (tmp_path / "golden_set.yaml").write_text(SNAPSHOT_SET)
    _run(tmp_path, "--update-baseline")
    baseline_file = tmp_path / "baseline.json"
    saved = json.loads(baseline_file.read_text())
    saved["cases"]["add-snap"]["outcome"]["text"] = "6"
    baseline_file.write_text(json.dumps(saved))

    result = _run(tmp_path)

    assert result.exit_code == 1
    assert "add-snap" in result.output
    assert "first difference" in result.output


def test_contract_drift_is_a_warning_by_default_and_a_failure_with_strict_contract(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    (tmp_path / "golden_set.yaml").write_text(SNAPSHOT_SET)
    _run(tmp_path, "--update-baseline")
    baseline_file = tmp_path / "baseline.json"
    saved = json.loads(baseline_file.read_text())
    saved["contract"]["serverInfo"]["version"] = "9.9.9"
    baseline_file.write_text(json.dumps(saved))

    lenient = _run(tmp_path)
    strict = _run(tmp_path, "--strict-contract")

    assert lenient.exit_code == 0
    assert "serverInfo.version" in lenient.output
    assert strict.exit_code == 1


def test_contract_ignore_silences_a_known_noisy_path(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    (tmp_path / "golden_set.yaml").write_text("contract_ignore: [serverInfo.version]\n" + SNAPSHOT_SET)
    _run(tmp_path, "--update-baseline")
    baseline_file = tmp_path / "baseline.json"
    saved = json.loads(baseline_file.read_text())
    saved["contract"]["serverInfo"]["version"] = "9.9.9"
    baseline_file.write_text(json.dumps(saved))

    result = _run(tmp_path, "--strict-contract")

    assert result.exit_code == 0
    assert "serverInfo.version" not in result.output


def test_run_writes_a_markdown_report_for_ci_summaries(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    (tmp_path / "golden_set.yaml").write_text(SNAPSHOT_SET)
    report = tmp_path / "summary.md"

    _run(tmp_path, "--update-baseline")
    _run(tmp_path, "--markdown-report", str(report))

    text = report.read_text()
    assert "add-snap" in text
    assert "| Case |" in text


def test_a_corrupt_baseline_exits_2_with_a_readable_error(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    (tmp_path / "golden_set.yaml").write_text(SNAPSHOT_SET)
    (tmp_path / "baseline.json").write_text("{oops")

    result = _run(tmp_path)

    assert result.exit_code == 2
    assert "not valid JSON" in result.output
    assert "Traceback" not in result.output


def test_update_baseline_can_repair_a_corrupt_baseline(tmp_path, monkeypatch):
    _patch_connect(monkeypatch)
    (tmp_path / "golden_set.yaml").write_text(SNAPSHOT_SET)
    (tmp_path / "baseline.json").write_text("<<<<<<< merge conflict")

    result = _run(tmp_path, "--update-baseline")

    assert result.exit_code == 0, result.output
    assert json.loads((tmp_path / "baseline.json").read_text())["version"] == 2
