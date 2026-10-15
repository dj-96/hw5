"""Human approval desk. The only way a payment request becomes a payment.

    python -m backend.approve list
    python -m backend.approve approve 1 --by "Jun Kim"
    python -m backend.approve deny 3 --by "Jun Kim" --note "Wait until after rent"

Goes through the same MCP server as the agents (no direct database access),
and logs every decision to output/audit_trail.json.
"""
import argparse
import asyncio
import json

from . import audit
from .mcp_tools import human_client


async def call(tool: str, args: dict) -> dict:
    async with human_client() as client:
        result = await client.call_tool(tool, args)
    return result.structured_content or json.loads(result.content[0].text)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for cmd in ("approve", "deny"):
        p = sub.add_parser(cmd)
        p.add_argument("request_id", type=int)
        p.add_argument("--by", required=True, help="Your name (the human approver).")
        if cmd == "deny":
            p.add_argument("--note", default="")
    args = parser.parse_args()

    if args.cmd == "list":
        result = await call("list_payment_requests", {"status": "pending"})
    elif args.cmd == "approve":
        result = await call("approve_payment", {"request_id": args.request_id, "approved_by": args.by})
    else:
        result = await call("deny_payment", {"request_id": args.request_id, "denied_by": args.by, "note": args.note})

    if args.cmd != "list":
        await audit.append(
            {"agent": "human", "step": f"payment_{args.cmd}", "request_id": args.request_id, "by": args.by, "result": result}
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
