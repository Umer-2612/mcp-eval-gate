"""Connect to an MCP server under test (stdio or HTTP) and call its tools.

This is what makes the tool protocol-generic: it speaks the MCP client side
directly, rather than a specific vendor's SDK, so it works against any
compliant MCP server regardless of the language or backend it's written in.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent

from mcp_eval_gate.models import ServerTarget, ToolCallOutcome


@asynccontextmanager
async def connect(target: ServerTarget) -> AsyncIterator[ClientSession]:
    if target.command:
        params = StdioServerParameters(command=target.command, args=list(target.args), env=target.env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
        return

    async with streamable_http_client(target.url) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def call_tool(session: ClientSession, tool_name: str, arguments: dict[str, object]) -> ToolCallOutcome:
    result = await session.call_tool(tool_name, arguments)
    return parse_call_tool_result(result)


def parse_call_tool_result(result: CallToolResult) -> ToolCallOutcome:
    text = "".join(block.text for block in result.content if isinstance(block, TextContent))
    return ToolCallOutcome(text=text, structured=result.structured_content, is_error=bool(result.is_error))
