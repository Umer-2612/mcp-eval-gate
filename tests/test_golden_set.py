from pathlib import Path

import pytest

from mcp_eval_gate.golden_set import GoldenSetError, load_golden_set
from mcp_eval_gate.models import MatchType

FIXTURE = Path(__file__).parent / "fixtures" / "golden_set.yaml"


def test_loads_stdio_server_target():
    config = load_golden_set(FIXTURE)

    assert config.server.command == "node"
    assert config.server.args == ("dist/index.js",)
    assert config.server.url is None
    assert config.judge_model == "claude-sonnet-4-5"


def test_loads_all_cases_with_correct_match_types():
    config = load_golden_set(FIXTURE)

    assert len(config.cases) == 3
    weather = next(c for c in config.cases if c.id == "get-weather-nyc")
    cancel = next(c for c in config.cases if c.id == "cancel-subscription")
    judge = next(c for c in config.cases if c.id == "retention-policy-answer")

    assert weather.match_type == MatchType.CONTAINS
    assert weather.tool_name == "get_weather"
    assert weather.tool_args == {"city": "New York"}

    assert cancel.match_type == MatchType.EXACT
    assert cancel.expected_output == "cancelled"

    assert judge.match_type == MatchType.JUDGE
    assert judge.judge_criteria == "Answer must state data is retained for 90 days"
    assert judge.min_judge_score == 0.8


def test_loads_http_server_target(tmp_path):
    f = tmp_path / "http_golden_set.yaml"
    f.write_text(
        "server:\n  url: http://localhost:3000/mcp\ncases:\n"
        "  - id: c1\n    tool_name: t1\n    match_type: contains\n    expected_output: ok\n"
    )

    config = load_golden_set(f)

    assert config.server.url == "http://localhost:3000/mcp"
    assert config.server.command is None


def test_missing_file_raises_golden_set_error(tmp_path):
    with pytest.raises(GoldenSetError, match="not found"):
        load_golden_set(tmp_path / "does_not_exist.yaml")


def test_missing_server_block_raises_golden_set_error(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("cases:\n  - id: c1\n    tool_name: t1\n")

    with pytest.raises(GoldenSetError, match="server"):
        load_golden_set(f)


def test_server_with_both_command_and_url_raises_golden_set_error(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text(
        "server:\n  command: node\n  url: http://localhost:3000\ncases:\n"
        "  - id: c1\n    tool_name: t1\n    expected_output: ok\n"
    )

    with pytest.raises(GoldenSetError, match="exactly one"):
        load_golden_set(f)


def test_case_missing_tool_name_raises_golden_set_error(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("server:\n  command: node\ncases:\n  - id: no-tool-name\n    expected_output: ok\n")

    with pytest.raises(GoldenSetError, match="no-tool-name"):
        load_golden_set(f)


def test_duplicate_case_ids_raise_golden_set_error(tmp_path):
    f = tmp_path / "dup.yaml"
    f.write_text(
        "server:\n  command: node\ncases:\n"
        "  - id: dup\n    tool_name: t1\n    expected_output: a\n"
        "  - id: dup\n    tool_name: t2\n    expected_output: b\n"
    )

    with pytest.raises(GoldenSetError, match="duplicate"):
        load_golden_set(f)
