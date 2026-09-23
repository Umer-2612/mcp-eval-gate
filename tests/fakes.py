"""Fake boto3-shaped clients shared across tests — no network, no AWS creds."""


class FakeAgentRuntimeClient:
    def retrieve(self, **kwargs):
        return {
            "retrievalResults": [
                {"metadata": {"doc_id": "doc-42"}, "location": {}},
                {"metadata": {"doc_id": "doc-7"}, "location": {}},
            ]
        }

    def invoke_agent(self, **kwargs):
        events = [
            {
                "trace": {
                    "trace": {
                        "orchestrationTrace": {
                            "invocationInput": {
                                "actionGroupInvocationInput": {
                                    "function": "cancel_subscription",
                                    "parameters": [{"name": "immediate", "type": "boolean", "value": "true"}],
                                }
                            }
                        }
                    }
                }
            },
            {"chunk": {"bytes": b"Cancelled."}},
        ]
        return {"completion": events}


class FakeBedrockRuntimeClient:
    def converse(self, **kwargs):
        return {"output": {"message": {"content": [{"text": '{"score": 0.95, "reasoning": "covers 90 days"}'}]}}}
