"""Look at a live server and write a starting golden set from the tools it lists."""

from __future__ import annotations

import json

import yaml

from mcp_eval_gate.contract import capture_contract
from mcp_eval_gate.mcp_client import connect
from mcp_eval_gate.models import ServerTarget

PLACEHOLDER_BY_TYPE: dict[str, object] = {
    "string": "",
    "integer": 0,
    "number": 0,
    "boolean": False,
    "array": [],
    "object": {},
}


async def fetch_contract(target: ServerTarget) -> dict:
    async with connect(target) as session:
        return await capture_contract(session)


def render_golden_set(target: ServerTarget, contract: dict) -> str:
    header = (
        "# Generated from the server's tool list. Every enabled case calls the tool for real,\n"
        "# so read them before running. Cases are snapshots: run `mcp-eval-gate run --update-baseline`\n"
        "# once to record the current output, then `mcp-eval-gate run` gates on changes.\n"
    )
    server_block = yaml.safe_dump({"server": _server_dict(target)}, sort_keys=False)
    tools = [contract["tools"][name] for name in contract.get("toolOrder", [])]
    cases = "\n".join(_render_tool(tool) for tool in tools) or "  []"
    return f"{header}{server_block}\ncases:\n{cases}\n"


def _server_dict(target: ServerTarget) -> dict:
    if target.url:
        return {"url": target.url}
    server: dict = {"command": target.command}
    if target.args:
        server["args"] = list(target.args)
    return server


def _render_tool(tool: dict) -> str:
    name = tool["name"]
    required = tool.get("inputSchema", {}).get("required", [])
    if _changes_state(tool):
        return _stub(name, {}, note="the server marks this tool as one that changes state, enable it on purpose")
    if required:
        args = _placeholder_args(tool, required)
        return _stub(name, args, note=f"required: {', '.join(required)}")
    return "\n".join(
        [
            f"  - id: {name}",
            f"    tool_name: {name}",
            "    tool_args: {}",
            "    match_type: snapshot",
        ]
    )


def _changes_state(tool: dict) -> bool:
    annotations = tool.get("annotations") or {}
    return annotations.get("destructiveHint") is True or annotations.get("readOnlyHint") is False


def _placeholder_args(tool: dict, required: list[str]) -> dict:
    properties = tool.get("inputSchema", {}).get("properties", {})
    return {key: PLACEHOLDER_BY_TYPE.get(properties.get(key, {}).get("type"), "") for key in required}


def _stub(name: str, args: dict, *, note: str) -> str:
    return "\n".join(
        [
            f"  # {note}",
            f"  # - id: {name}",
            f"  #   tool_name: {name}",
            f"  #   tool_args: {json.dumps(args)}",
            "  #   match_type: snapshot",
        ]
    )
