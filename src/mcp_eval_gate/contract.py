"""The server's contract: what it declares on the wire, separate from what its tools return.

A contract is the initialize result (protocol version, server info, capabilities) plus every
tool as listed by tools/list. It is captured from the wire objects, not from the client's
defaults, so an SDK upgrade on the client side does not show up as a server change.
Diffing two contracts and linting one catches the silent failures a smoke test misses:
a schema dialect some clients reject, a tool that vanishes from a client's list, a reordered list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jsonschema
from mcp.client.session import ClientSession
from mcp.shared.exceptions import MCPError
from mcp.types import PaginatedRequestParams

from mcp_eval_gate.models import ToolCallOutcome

SUPPORTED_DIALECT = "2020-12"
ROOT_COMPOSITION_KEYWORDS = ("allOf", "anyOf", "oneOf", "not", "if", "then", "else")
SCHEMA_FIELDS = ("inputSchema", "outputSchema")
MAX_TOOL_LIST_PAGES = 1000


@dataclass(frozen=True)
class ContractChange:
    path: str
    kind: str
    before: Any = None
    after: Any = None

    def describe(self) -> str:
        if self.kind == "added":
            return f"{self.path}: added"
        if self.kind == "removed":
            return f"{self.path}: removed"
        return f"{self.path}: {_short(self.before)} -> {_short(self.after)}"


async def capture_contract(session: ClientSession) -> dict:
    initialize = session.initialize_result.model_dump(mode="json", by_alias=True, exclude_unset=True)
    tools = await _list_all_tools(session)
    return {
        "protocolVersion": initialize.get("protocolVersion"),
        "serverInfo": initialize.get("serverInfo", {}),
        "capabilities": initialize.get("capabilities", {}),
        "tools": {t["name"]: t for t in tools},
        "toolOrder": [t["name"] for t in tools],
    }


async def _list_all_tools(session: ClientSession) -> list[dict]:
    tools: list[dict] = []
    seen_cursors: set[str] = set()
    cursor: str | None = None
    for _ in range(MAX_TOOL_LIST_PAGES):
        params = PaginatedRequestParams(cursor=cursor) if cursor else None
        page = await session.list_tools(params=params)
        tools.extend(t.model_dump(mode="json", by_alias=True, exclude_unset=True) for t in page.tools)
        cursor = page.next_cursor
        if not cursor:
            return tools
        if cursor in seen_cursors:
            raise MCPError(-32603, f"tools/list repeated the cursor {cursor!r} instead of finishing")
        seen_cursors.add(cursor)
    raise MCPError(-32603, f"tools/list did not finish after {MAX_TOOL_LIST_PAGES} pages")


def diff_contract(before: dict, after: dict, ignore: tuple[str, ...] = ()) -> list[ContractChange]:
    changes: list[ContractChange] = []
    _diff_value("", before, after, changes)
    return [c for c in changes if not _is_ignored(c.path, ignore)]


def _diff_value(path: str, before: Any, after: Any, changes: list[ContractChange]) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            child = f"{path}.{key}" if path else key
            if key not in after:
                changes.append(ContractChange(child, "removed", before[key]))
            elif key not in before:
                changes.append(ContractChange(child, "added", after=after[key]))
            else:
                _diff_value(child, before[key], after[key], changes)
    elif before != after:
        changes.append(ContractChange(path, "changed", before, after))


def _is_ignored(path: str, ignore: tuple[str, ...]) -> bool:
    return any(path == entry or path.startswith(f"{entry}.") for entry in ignore)


def lint_contract(contract: dict) -> list[str]:
    findings: list[str] = []
    for name, tool in contract.get("tools", {}).items():
        findings.extend(_lint_schema_dialect(name, tool))
        findings.extend(_lint_input_schema_shape(name, tool.get("inputSchema")))
    return findings


def _lint_schema_dialect(tool_name: str, tool: dict) -> list[str]:
    findings = []
    for field in SCHEMA_FIELDS:
        dialect = (tool.get(field) or {}).get("$schema")
        if dialect and SUPPORTED_DIALECT not in dialect:
            findings.append(
                f"tool '{tool_name}' {field} declares {dialect}. Clients that only support JSON Schema "
                f"{SUPPORTED_DIALECT} reject it and can make the whole server unusable"
            )
    return findings


def _lint_input_schema_shape(tool_name: str, schema: dict | None) -> list[str]:
    if not schema:
        return []
    findings = []
    if schema.get("type") != "object":
        findings.append(f"tool '{tool_name}' inputSchema root type is not object, some clients drop the tool")
    for keyword in ROOT_COMPOSITION_KEYWORDS:
        if keyword in schema:
            findings.append(
                f"tool '{tool_name}' inputSchema uses root-level {keyword}, some clients silently drop the tool"
            )
    return findings


def lint_call(tool_name: str, outcome: ToolCallOutcome, contract: dict) -> list[str]:
    output_schema = contract.get("tools", {}).get(tool_name, {}).get("outputSchema")
    if not output_schema or outcome.is_error:
        return []
    if outcome.structured is None:
        return [f"tool '{tool_name}' declares an outputSchema but returned no structuredContent"]
    try:
        jsonschema.validate(outcome.structured, output_schema)
    except jsonschema.ValidationError as exc:
        return [f"tool '{tool_name}' structuredContent does not match its outputSchema: {exc.message}"]
    except jsonschema.SchemaError as exc:
        return [f"tool '{tool_name}' outputSchema is not a valid JSON Schema: {exc.message}"]
    except Exception as exc:
        # A dangling $ref or another structural problem raises something outside jsonschema's own
        # exception hierarchy (e.g. a referencing.exceptions.Unresolvable). A broken outputSchema is
        # itself a finding, not a reason to crash the run.
        return [f"tool '{tool_name}' outputSchema could not be checked: {exc}"]
    return []


def _short(value: Any, limit: int = 80) -> str:
    text = repr(value)
    return text if len(text) <= limit else f"{text[:limit]}…"
