from bedrock_eval_gate.bedrock_client import (
    invoke_agent,
    parse_agent_response,
    parse_retrieve_response,
    retrieve_from_knowledge_base,
)


def test_parse_retrieve_response_prefers_doc_id_metadata():
    response = {
        "retrievalResults": [
            {"metadata": {"doc_id": "doc-42"}, "location": {"s3Location": {"uri": "s3://bucket/other.txt"}}},
            {"metadata": {}, "location": {"s3Location": {"uri": "s3://bucket/doc-7.txt"}}},
        ]
    }

    outcome = parse_retrieve_response(response, doc_id_metadata_key="doc_id")

    assert outcome.retrieved_doc_ids == ("doc-42", "doc-7.txt")


def test_parse_retrieve_response_handles_empty_results():
    outcome = parse_retrieve_response({"retrievalResults": []}, doc_id_metadata_key="doc_id")

    assert outcome.retrieved_doc_ids == ()


def test_parse_agent_response_extracts_tool_call_and_final_answer():
    events = [
        {
            "trace": {
                "trace": {
                    "orchestrationTrace": {
                        "invocationInput": {
                            "actionGroupInvocationInput": {
                                "actionGroupName": "SubscriptionActions",
                                "function": "cancel_subscription",
                                "parameters": [
                                    {"name": "immediate", "type": "boolean", "value": "true"},
                                ],
                            }
                        }
                    }
                }
            }
        },
        {"chunk": {"bytes": b"Done, "}},
        {"chunk": {"bytes": b"cancelled immediately."}},
    ]

    outcome = parse_agent_response(events)

    assert outcome.called_tool == "cancel_subscription"
    assert outcome.called_params == {"immediate": True}
    assert outcome.final_answer == "Done, cancelled immediately."


def test_parse_agent_response_with_no_tool_call():
    events = [{"chunk": {"bytes": b"I'm not sure how to help."}}]

    outcome = parse_agent_response(events)

    assert outcome.called_tool is None
    assert outcome.called_params == {}
    assert outcome.final_answer == "I'm not sure how to help."


def test_parse_agent_response_coerces_numeric_and_boolean_param_types():
    events = [
        {
            "trace": {
                "trace": {
                    "orchestrationTrace": {
                        "invocationInput": {
                            "actionGroupInvocationInput": {
                                "function": "set_seats",
                                "parameters": [
                                    {"name": "count", "type": "integer", "value": "3"},
                                    {"name": "priority", "type": "boolean", "value": "false"},
                                    {"name": "note", "type": "string", "value": "urgent"},
                                ],
                            }
                        }
                    }
                }
            }
        }
    ]

    outcome = parse_agent_response(events)

    assert outcome.called_params == {"count": 3, "priority": False, "note": "urgent"}


class _FakeAgentRuntimeClient:
    def __init__(self):
        self.retrieve_kwargs = None
        self.invoke_agent_kwargs = None

    def retrieve(self, **kwargs):
        self.retrieve_kwargs = kwargs
        return {"retrievalResults": [{"metadata": {"doc_id": "doc-1"}, "location": {}}]}

    def invoke_agent(self, **kwargs):
        self.invoke_agent_kwargs = kwargs
        return {"completion": [{"chunk": {"bytes": b"hello"}}]}


def test_retrieve_from_knowledge_base_calls_client_with_expected_shape():
    client = _FakeAgentRuntimeClient()

    outcome = retrieve_from_knowledge_base(client, knowledge_base_id="KB1", query="a query", k=3)

    assert client.retrieve_kwargs == {
        "knowledgeBaseId": "KB1",
        "retrievalQuery": {"text": "a query"},
        "retrievalConfiguration": {"vectorSearchConfiguration": {"numberOfResults": 3}},
    }
    assert outcome.retrieved_doc_ids == ("doc-1",)


def test_invoke_agent_calls_client_with_expected_shape_and_enables_trace():
    client = _FakeAgentRuntimeClient()

    outcome = invoke_agent(client, agent_id="A1", agent_alias_id="AL1", session_id="S1", query="hi")

    assert client.invoke_agent_kwargs == {
        "agentId": "A1",
        "agentAliasId": "AL1",
        "sessionId": "S1",
        "inputText": "hi",
        "enableTrace": True,
    }
    assert outcome.final_answer == "hello"


def test_coerce_param_value_falls_back_to_raw_string_on_bad_number():
    events = [
        {
            "trace": {
                "trace": {
                    "orchestrationTrace": {
                        "invocationInput": {
                            "actionGroupInvocationInput": {
                                "function": "set_count",
                                "parameters": [{"name": "count", "type": "integer", "value": "not-a-number"}],
                            }
                        }
                    }
                }
            }
        }
    ]

    outcome = parse_agent_response(events)

    assert outcome.called_params == {"count": "not-a-number"}
