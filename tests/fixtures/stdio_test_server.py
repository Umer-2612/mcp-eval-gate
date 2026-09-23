"""A real MCP server run as a subprocess over stdio, for one genuine end-to-end test
of mcp_client.py's stdio path (everything else uses the faster in-memory transport)."""

from mcp.server.mcpserver import MCPServer

server = MCPServer("stdio-test-server")


@server.tool()
def echo(message: str) -> str:
    """Echo the message back."""
    return message


if __name__ == "__main__":
    server.run()
