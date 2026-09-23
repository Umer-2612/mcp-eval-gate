from pathlib import Path

import pytest

from bedrock_eval_gate.golden_set import GoldenSetError, load_golden_set
from bedrock_eval_gate.models import CaseType

FIXTURE = Path(__file__).parent / "fixtures" / "golden_set.yaml"


def test_loads_top_level_config():
    config = load_golden_set(FIXTURE)

    assert config.region == "us-east-1"
    assert config.knowledge_base_id == "KB123ABC"
    assert config.agent_id == "AGENT123"
    assert config.agent_alias_id == "TSTALIASID"


def test_loads_both_cases_with_correct_types():
    config = load_golden_set(FIXTURE)

    assert len(config.cases) == 2
    retrieval_case = next(c for c in config.cases if c.id == "refund-policy-lookup")
    agent_case = next(c for c in config.cases if c.id == "cancel-subscription-tool-call")

    assert retrieval_case.type == CaseType.RETRIEVAL
    assert retrieval_case.expected_doc_ids == ("doc-42", "doc-7")
    assert retrieval_case.k == 5

    assert agent_case.type == CaseType.AGENT
    assert agent_case.expected_tool == "cancel_subscription"
    assert agent_case.expected_params == {"immediate": True}


def test_missing_file_raises_golden_set_error(tmp_path):
    with pytest.raises(GoldenSetError, match="not found"):
        load_golden_set(tmp_path / "does_not_exist.yaml")


def test_case_missing_required_fields_raises_golden_set_error(tmp_path):
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("cases:\n  - id: no-type-or-query\n")

    with pytest.raises(GoldenSetError, match="no-type-or-query"):
        load_golden_set(bad_file)


def test_duplicate_case_ids_raise_golden_set_error(tmp_path):
    bad_file = tmp_path / "dup.yaml"
    bad_file.write_text(
        "cases:\n"
        "  - id: dup\n"
        "    type: retrieval\n"
        "    query: q1\n"
        "    expected_doc_ids: [doc-1]\n"
        "  - id: dup\n"
        "    type: retrieval\n"
        "    query: q2\n"
        "    expected_doc_ids: [doc-2]\n"
    )

    with pytest.raises(GoldenSetError, match="duplicate"):
        load_golden_set(bad_file)
