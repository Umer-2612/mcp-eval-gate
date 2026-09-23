from contextlib import asynccontextmanager

import anyio
import pytest
from mcp.client._memory import create_client_server_memory_streams

from mcp_eval_gate.mcp_client import call_tool
from tests.mcp_test_server import build_echo_server, connected_session


@pytest.mark.anyio
async def test_call_tool_returns_text_output():
    async with connected_session(build_echo_server()) as session:
        outcome = await call_tool(session, "echo", {"message": "hello"})

    assert outcome.text == "hello"
    assert outcome.is_error is False


@pytest.mark.anyio
async def test_call_tool_captures_structured_output():
    async with connected_session(build_echo_server()) as session:
        outcome = await call_tool(session, "add", {"a": 2, "b": 3})

    assert outcome.structured == {"result": 5}


@pytest.mark.anyio
async def test_call_tool_marks_is_error_when_tool_raises():
    async with connected_session(build_echo_server()) as session:
        outcome = await call_tool(session, "always_fails", {})

    assert outcome.is_error is True
    assert "always_fails" in outcome.text


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_connect_and_call_tool_over_a_real_stdio_subprocess():
    import sys
    from pathlib import Path

    from mcp_eval_gate.mcp_client import connect
    from mcp_eval_gate.models import ServerTarget

    server_script = Path(__file__).parent / "fixtures" / "stdio_test_server.py"
    target = ServerTarget(command=sys.executable, args=(str(server_script),))

    async with connect(target) as session:
        outcome = await call_tool(session, "echo", {"message": "hello over stdio"})

    assert outcome.text == "hello over stdio"
    assert outcome.is_error is False


@pytest.mark.anyio
async def test_connect_dispatches_to_streamable_http_when_target_has_a_url(monkeypatch):
    """Proves connect() picks the HTTP branch for a url target, using the same in-memory
    streams as the stdio tests (a real uvicorn round trip is SDK plumbing, not our logic)."""
    import mcp_eval_gate.mcp_client as mcp_client_module
    from mcp_eval_gate.mcp_client import connect
    from mcp_eval_gate.models import ServerTarget

    calls = []

    @asynccontextmanager
    async def fake_streamable_http_client(url):
        calls.append(url)
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            server_read, server_write = server_streams
            server = build_echo_server()

            async def run_server() -> None:
                await server._lowlevel_server.run(
                    server_read, server_write, server._lowlevel_server.create_initialization_options()
                )

            async with anyio.create_task_group() as tg:
                tg.start_soon(run_server)
                client_read, client_write = client_streams
                yield client_read, client_write, lambda: None
                tg.cancel_scope.cancel()

    monkeypatch.setattr(mcp_client_module, "streamable_http_client", fake_streamable_http_client)

    async with connect(ServerTarget(url="http://example.invalid/mcp")) as session:
        outcome = await call_tool(session, "echo", {"message": "hello over http"})

    assert calls == ["http://example.invalid/mcp"]
    assert outcome.text == "hello over http"
