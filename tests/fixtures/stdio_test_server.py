"""A real MCP server run as a subprocess over stdio, for one genuine end-to-end test
of mcp_client.py's stdio path (everything else uses the faster in-memory transport)."""

from mcp.server.mcpserver import MCPServer

server = MCPServer("stdio-test-server")


@server.tool()
def echo(message: str) -> str:
    """Echo the message back."""
    return message


@server.tool()
async def slow(seconds: float) -> str:
    """Sleep, then return."""
    import asyncio

    await asyncio.sleep(seconds)
    return "done"


if __name__ == "__main__":
    server.run()
