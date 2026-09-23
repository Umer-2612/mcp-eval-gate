import pytest

from mcp_eval_gate.judge import JudgeParseError, build_judge_prompt, parse_judge_response


def test_parses_well_formed_json_response():
    text = '{"score": 0.9, "reasoning": "Answer states 90 days and cites the retention doc."}'

    score, reasoning = parse_judge_response(text)

    assert score == 0.9
    assert "90 days" in reasoning


def test_parses_json_embedded_in_surrounding_prose():
    text = 'Here is my evaluation:\n{"score": 0.4, "reasoning": "Missing the citation."}\nDone.'

    score, reasoning = parse_judge_response(text)

    assert score == 0.4


def test_clamps_out_of_range_scores():
    text = '{"score": 1.7, "reasoning": "overzealous"}'

    score, _ = parse_judge_response(text)

    assert score == 1.0


def test_raises_when_no_json_found():
    with pytest.raises(JudgeParseError):
        parse_judge_response("I think this is pretty good, maybe an 8/10?")


def test_raises_when_score_field_missing():
    with pytest.raises(JudgeParseError):
        parse_judge_response('{"reasoning": "no score field"}')


def test_build_judge_prompt_includes_criteria_and_answer():
    prompt = build_judge_prompt(criteria="Must mention 90 days", answer="We retain data for 90 days.")

    assert "Must mention 90 days" in prompt
    assert "We retain data for 90 days." in prompt
    assert "score" in prompt.lower()


def test_judge_answer_calls_client_with_expected_shape_and_parses_result():
    from mcp_eval_gate.judge import judge_answer
    from tests.fakes import FakeAnthropicClient

    client = FakeAnthropicClient('{"score": 0.9, "reasoning": "covers 90 days"}')

    score, reasoning = judge_answer(
        client, model="claude-sonnet-4-5", criteria="must mention 90 days", answer="Data is retained for 90 days."
    )

    assert score == 0.9
    assert "90 days" in reasoning
    assert client.create_kwargs["model"] == "claude-sonnet-4-5"
    assert client.create_kwargs["messages"][0]["role"] == "user"
    assert "must mention 90 days" in client.create_kwargs["messages"][0]["content"]


def test_raises_when_json_object_is_malformed():
    from mcp_eval_gate.judge import JudgeParseError, parse_judge_response

    with pytest.raises(JudgeParseError, match="not valid JSON"):
        parse_judge_response("{score: 0.9, not valid json}")


def test_build_default_anthropic_client_returns_none_without_api_key(monkeypatch):
    from mcp_eval_gate.judge import build_default_anthropic_client

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert build_default_anthropic_client() is None


def test_build_default_anthropic_client_returns_a_client_when_key_is_set(monkeypatch):
    from mcp_eval_gate.judge import build_default_anthropic_client

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key")

    client = build_default_anthropic_client()

    assert client is not None
    assert hasattr(client, "messages")
