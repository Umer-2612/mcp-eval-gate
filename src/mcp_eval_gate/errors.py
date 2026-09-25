"""Turn the exceptions raised when a server can't be started or reached into one readable line."""

from __future__ import annotations

from collections.abc import Iterator

from mcp.shared.exceptions import MCPError

from mcp_eval_gate.models import ServerTarget


def friendly_run_error(exc: BaseException, server: ServerTarget) -> str | None:
    """Returns a one-line explanation, or None if the error isn't a start-up or connection problem."""
    leaves = list(_leaf_exceptions(exc))
    if not leaves or not all(isinstance(leaf, OSError | MCPError) for leaf in leaves):
        return None

    reasons = ", ".join(dict.fromkeys(_reason(leaf) for leaf in leaves))
    return (
        f"could not run the golden set against the MCP server ({_describe_server(server)}): {reasons}. "
        "Check the `server` block in your golden set and that the server starts on its own."
    )


def _leaf_exceptions(exc: BaseException) -> Iterator[BaseException]:
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            yield from _leaf_exceptions(sub)
    else:
        yield exc


def _reason(exc: BaseException) -> str:
    if isinstance(exc, FileNotFoundError):
        return f"command not found ({exc.filename or exc})"
    if isinstance(exc, MCPError):
        return exc.message
    return f"{type(exc).__name__}: {exc}"


def _describe_server(server: ServerTarget) -> str:
    if server.command:
        return " ".join([server.command, *server.args])
    return server.url or "no server configured"
