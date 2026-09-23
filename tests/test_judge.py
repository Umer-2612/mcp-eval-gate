import pytest

from bedrock_eval_gate.judge import JudgeParseError, build_judge_prompt, parse_judge_response


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
