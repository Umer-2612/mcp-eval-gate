"""LLM-as-judge scoring for open-ended agent answers, via Bedrock's Converse API.

Used only for cases that declare `judge_criteria` — retrieval and exact
tool-call cases are scored deterministically in scoring.py and never need
a judge call.
"""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

JUDGE_PROMPT_TEMPLATE = """You are grading a support agent's answer against a rubric.

Rubric (must be satisfied):
{criteria}

Agent's answer:
{answer}

Respond with ONLY a JSON object of the form:
{{"score": <float between 0.0 and 1.0>, "reasoning": "<one sentence>"}}
A score of 1.0 means the rubric is fully satisfied; 0.0 means it is not satisfied at all."""


class JudgeParseError(ValueError):
    """Raised when the judge model's response can't be parsed into a score."""


def build_judge_prompt(*, criteria: str, answer: str) -> str:
    return JUDGE_PROMPT_TEMPLATE.format(criteria=criteria, answer=answer)


def parse_judge_response(text: str) -> tuple[float, str]:
    match = _JSON_OBJECT_PATTERN.search(text)
    if not match:
        raise JudgeParseError(f"no JSON object found in judge response: {text!r}")

    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise JudgeParseError(f"judge response was not valid JSON: {text!r}") from exc

    if "score" not in payload:
        raise JudgeParseError(f"judge response missing 'score' field: {payload!r}")

    score = max(0.0, min(1.0, float(payload["score"])))
    reasoning = str(payload.get("reasoning", ""))
    return score, reasoning


def judge_answer(client: Any, *, model_id: str, criteria: str, answer: str) -> tuple[float, str]:
    prompt = build_judge_prompt(criteria=criteria, answer=answer)
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0.0},
    )
    text = response["output"]["message"]["content"][0]["text"]
    return parse_judge_response(text)
