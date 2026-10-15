"""The agents' only path to shop data: the campus-customs MCP server.

One stdio connection to `mcp_server/server.py` is shared by every agent.
Each agent sees a filtered view with just the tools its role needs, and a
second check at call time blocks anything outside that list. The
human-only payment tools are never exposed to an agent.
"""
import sys
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from pydantic_ai import RunContext
from pydantic_ai.mcp import CallToolFunc, MCPToolset

from .config import MCP_SERVER
from .models import TeamDeps

HUMAN_ONLY_TOOLS = frozenset({"approve_payment", "deny_payment"})

# Tools that take an `agent` argument; the backend fills it in with the real
# caller so an agent can't sign a change as someone else.
SIGNED_TOOLS = frozenset(
    {"update_ticket", "create_purchase_order", "draft_customer_message", "request_payment"}
)


def make_transport() -> PythonStdioTransport:
    return PythonStdioTransport(MCP_SERVER, python_cmd=sys.executable)


def human_client() -> Client:
    """MCP client for the human approval CLI (the only caller of approve/deny)."""
    return Client(make_transport())


async def _guard_and_sign(
    ctx: RunContext[TeamDeps], call_tool: CallToolFunc, name: str, args: dict[str, Any]
) -> Any:
    from .agents import ROLES  # avoid an import cycle

    caller = ctx.deps.chain[-1]
    if name in HUMAN_ONLY_TOOLS or name not in ROLES[caller].tools:
        raise PermissionError(f"{caller} is not allowed to call {name}.")
    if name in SIGNED_TOOLS:
        args = {**args, "agent": caller}
    return await call_tool(name, args)


shop_mcp = MCPToolset(Client(make_transport()), id="campus-customs", process_tool_call=_guard_and_sign)


def toolset_for(tools: frozenset[str]):
    allowed = tools - HUMAN_ONLY_TOOLS
    return shop_mcp.filtered(lambda ctx, tool_def: tool_def.name in allowed)
