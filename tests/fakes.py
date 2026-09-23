"""Fake clients shared across tests — no network, no real API keys."""


class _FakeTextBlock:
    def __init__(self, text: str):
        self.text = text


class _FakeAnthropicResponse:
    def __init__(self, text: str):
        self.content = [_FakeTextBlock(text)]


class FakeAnthropicClient:
    """Stands in for anthropic.Anthropic(), shaped for judge_answer()'s use of client.messages.create()."""

    def __init__(self, response_text: str):
        self._response_text = response_text
        self.create_kwargs: dict | None = None
        self.messages = self

    def create(self, **kwargs):
        self.create_kwargs = kwargs
        return _FakeAnthropicResponse(self._response_text)
