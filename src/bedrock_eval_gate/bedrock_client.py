"""Thin wrapper around bedrock-agent-runtime.

The boto3 client is always passed in rather than constructed here, so the
response-parsing logic (the part actually worth testing) can be exercised
with a plain fake instead of live AWS credentials.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from bedrock_eval_gate.models import AgentOutcome, RetrievalOutcome

_PARAM_COERCERS = {
    "integer": int,
    "number": float,
    "boolean": lambda v: str(v).lower() == "true",
}


def retrieve_from_knowledge_base(
    client: Any, *, knowledge_base_id: str, query: str, k: int, doc_id_metadata_key: str = "doc_id"
) -> RetrievalOutcome:
    response = client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": k}},
    )
    return parse_retrieve_response(response, doc_id_metadata_key=doc_id_metadata_key)


def parse_retrieve_response(response: dict, *, doc_id_metadata_key: str) -> RetrievalOutcome:
    doc_ids = tuple(
        _extract_doc_id(result, doc_id_metadata_key) for result in response.get("retrievalResults", [])
    )
    return RetrievalOutcome(retrieved_doc_ids=doc_ids)


def _extract_doc_id(result: dict, doc_id_metadata_key: str) -> str:
    metadata = result.get("metadata") or {}
    if doc_id_metadata_key in metadata:
        return str(metadata[doc_id_metadata_key])

    uri = result.get("location", {}).get("s3Location", {}).get("uri", "")
    return uri.rsplit("/", 1)[-1] if uri else ""


def invoke_agent(client: Any, *, agent_id: str, agent_alias_id: str, session_id: str, query: str) -> AgentOutcome:
    response = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        inputText=query,
        enableTrace=True,
    )
    return parse_agent_response(response["completion"])


def parse_agent_response(events: Iterable[dict]) -> AgentOutcome:
    called_tool: str | None = None
    called_params: dict[str, object] = {}
    answer_chunks: list[str] = []

    for event in events:
        if "trace" in event:
            action = _extract_action_group_invocation(event)
            if action is not None:
                called_tool, called_params = action
        if "chunk" in event:
            answer_chunks.append(event["chunk"]["bytes"].decode("utf-8"))

    return AgentOutcome(called_tool=called_tool, called_params=called_params, final_answer="".join(answer_chunks))


def _extract_action_group_invocation(event: dict) -> tuple[str, dict[str, object]] | None:
    try:
        invocation_input = event["trace"]["trace"]["orchestrationTrace"]["invocationInput"]
        action_group_input = invocation_input["actionGroupInvocationInput"]
    except KeyError:
        return None

    tool_name = action_group_input.get("function") or action_group_input.get("actionGroupName")
    if tool_name is None:
        return None

    params = {
        param["name"]: _coerce_param_value(param.get("type"), param.get("value"))
        for param in action_group_input.get("parameters", [])
    }
    return tool_name, params


def _coerce_param_value(param_type: str | None, value: str) -> object:
    coercer = _PARAM_COERCERS.get(param_type or "string")
    if coercer is None:
        return value
    try:
        return coercer(value)
    except (TypeError, ValueError):
        return value
