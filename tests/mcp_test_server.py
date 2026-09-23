"""An in-memory MCP server + connected client session, for testing mcp_client.py
without spawning a real subprocess. No network, no real server binary."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from mcp.client._memory import create_client_server_memory_streams
from mcp.client.session import ClientSession
from mcp.server.mcpserver import MCPServer


@asynccontextmanager
async def connected_session(server: MCPServer) -> AsyncIterator[ClientSession]:
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        async def run_server() -> None:
            await server._lowlevel_server.run(
                server_read, server_write, server._lowlevel_server.create_initialization_options()
            )

        async with anyio.create_task_group() as tg:
            tg.start_soon(run_server)
            async with ClientSession(client_read, client_write) as session:
                await session.initialize()
                yield session
            tg.cancel_scope.cancel()


def build_echo_server() -> MCPServer:
    server = MCPServer("echo-test-server")

    @server.tool()
    def echo(message: str) -> str:
        """Echo the message back."""
        return message

    @server.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @server.tool()
    def always_fails() -> str:
        """A tool that always raises."""
        raise RuntimeError("boom")

    return server
