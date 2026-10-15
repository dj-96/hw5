"""Append-only audit trail at output/audit_trail.json.

The file is a JSON array. Each run adds entries and never removes old ones.
One entry is written for every agent-loop step (prompt in, model response
with tool calls, tool results back, final output) plus delegations,
blocked actions, errors, and human approvals.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from pydantic_ai import CallToolsNode, ModelRequestNode, UserPromptNode
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import RunUsage
from pydantic_graph import End

from .config import AUDIT_PATH, AUDIT_TEXT_LIMIT

_lock = asyncio.Lock()


def _clip(value: Any) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= AUDIT_TEXT_LIMIT:
        return value
    return text[:AUDIT_TEXT_LIMIT] + f"... [clipped, {len(text)} chars]"


def _read() -> list[dict]:
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        return []
    try:
        data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Never overwrite a file we can't read: set it aside and start a new one.
        AUDIT_PATH.rename(AUDIT_PATH.with_suffix(f".corrupt-{datetime.now():%Y%m%d%H%M%S}.json"))
        return []
    return data if isinstance(data, list) else [data]


async def append(entry: dict) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **entry}
    async with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        entries = _read()
        entries.append(entry)
        text = json.dumps(entries, indent=2, default=str)
        tmp = AUDIT_PATH.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        # OneDrive (and antivirus) can hold the file for a moment while syncing,
        # which makes the atomic replace fail on Windows. Retry, then fall back
        # to writing in place so a sync lock never kills an agent run.
        for attempt in range(8):
            try:
                os.replace(tmp, AUDIT_PATH)
                return
            except PermissionError:
                await asyncio.sleep(0.1 * (attempt + 1))
        AUDIT_PATH.write_text(text, encoding="utf-8")
        tmp.unlink(missing_ok=True)


def usage_dict(usage: RunUsage) -> dict:
    return {
        "requests": usage.requests,
        "tool_calls": usage.tool_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }


def describe_node(node: Any) -> dict:
    """Turn one PydanticAI graph node into an auditable record."""
    if isinstance(node, UserPromptNode):
        return {"step": "user_prompt", "prompt": _clip(node.user_prompt)}
    if isinstance(node, ModelRequestNode):
        results, retries = [], []
        for part in node.request.parts:
            if isinstance(part, ToolReturnPart):
                results.append({"tool": part.tool_name, "call_id": part.tool_call_id, "content": _clip(part.content)})
            elif isinstance(part, RetryPromptPart):
                retries.append({"tool": part.tool_name, "error": _clip(part.content)})
        return {"step": "model_request", "tool_results": results, "retries": retries}
    if isinstance(node, CallToolsNode):
        resp = node.model_response
        return {
            "step": "model_response",
            "model": resp.model_name,
            "text": _clip("".join(p.content for p in resp.parts if isinstance(p, TextPart))) or None,
            "tool_calls": [
                {"tool": p.tool_name, "call_id": p.tool_call_id, "args": _clip(p.args_as_dict())}
                for p in resp.parts
                if isinstance(p, ToolCallPart)
            ],
            "response_tokens": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens},
        }
    if isinstance(node, End):
        # Not clipped: the dashboard rebuilds each agent's debrief from this
        # typed report, and max_tokens already bounds its size.
        output = node.data.output
        return {"step": "end", "output": output.model_dump(mode="json") if isinstance(output, BaseModel) else output}
    return {"step": type(node).__name__}
