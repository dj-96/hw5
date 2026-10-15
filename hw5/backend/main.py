"""Campus Customs backend API for the React ticket board.

Start it from the backend/ folder:

    uvicorn main:app --reload --port 8000

Then open http://localhost:8000/docs to try every route.

All shop data still goes through the campus-customs MCP server. This file
only adds HTTP routes on top: it reads tickets and cash through MCP tools,
starts agent runs, serves the audit trail as events, and is the one place a
human's "Approve" click turns a payment request into a real payment.
"""
import asyncio
import json
import shutil
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

# `uvicorn main:app` imports this file as a top-level module, so make the
# backend package importable from the project folder.
PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from backend import audit  # noqa: E402
from backend.config import AUDIT_PATH, MODEL_NAME, llm_gateway  # noqa: E402
from backend.mcp_tools import make_transport, shop_mcp  # noqa: E402
from backend.team import new_session_id, run_team, ticket_task  # noqa: E402

ORIGINAL_DB = PROJECT_DIR / "data" / "campus_customs.db"
WORKING_DB = PROJECT_DIR / "data" / "campus_customs_new.db"
DONE_STATUSES = {"resolved", "declined"}

# Agent runs started from the API, by session id (kept in memory).
runs: dict[str, dict[str, Any]] = {}
active_run: dict[str, Any] = {"session_id": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One MCP connection for the API's own reads/approvals, and one kept open
    # for the agents, so neither restarts the MCP server on every request.
    app.state.mcp = Client(make_transport())
    async with app.state.mcp, shop_mcp:
        yield


app = FastAPI(title="Campus Customs API", version="1.0", lifespan=lifespan)
# The React desk (Vite) runs on port 5173. Its origin is listed explicitly;
# the regex also covers Vite picking another local port if 5173 is busy.
VITE_ORIGINS = [
    "http://localhost:5173",
    "https://localhost:5173",
    "http://127.0.0.1:5173",
    "https://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=VITE_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp(tool: str, args: dict | None = None) -> dict:
    try:
        result = await app.state.mcp.call_tool(tool, args or {})
    except ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.structured_content or json.loads(result.content[0].text)


def require_ok(result: dict) -> dict:
    if result.get("ok") is False or result.get("found") is False:
        raise HTTPException(status_code=400, detail=result.get("message", "Request refused."))
    return result


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

def read_audit() -> list[dict]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else []


def ticket_runs() -> dict[int, dict]:
    """Latest agent run per ticket since the last database reset, from the audit trail."""
    latest: dict[int, dict] = {}
    for e in read_audit():
        step = e.get("step")
        if step == "database_reset":
            latest.clear()
        elif step == "session_start" and e.get("ticket_id") is not None:
            latest[e["ticket_id"]] = {"session_id": e["session_id"], "state": "running", "started_at": e["ts"]}
        elif step == "session_end" and e.get("ticket_id") is not None:
            run = latest.get(e["ticket_id"])
            if run and run["session_id"] == e["session_id"]:
                run.update(state="done" if e.get("ok") else "failed", ended_at=e["ts"])
    for run in latest.values():
        # A run with no end entry that isn't the live one was cut off (server stopped).
        if run["state"] == "running" and run["session_id"] != active_run["session_id"]:
            run["state"] = "interrupted"
    return latest


@app.get("/api/tickets")
async def list_tickets():
    """Every ticket, with `state` = open or resolved.

    A ticket is resolved when its status is resolved/declined, or when the
    agent team finished a run on it since the last reset. `status` still shows
    what the agents left it at (e.g. waiting_on_approval), and `last_run` links
    to that run's events.
    """
    data = await mcp("list_tickets", {"status": None})
    runs_by_ticket = ticket_runs()
    tickets = []
    for t in data["tickets"]:
        run = runs_by_ticket.get(t["id"])
        resolved = t["status"] in DONE_STATUSES or (run is not None and run["state"] == "done")
        tickets.append({**t, "state": "resolved" if resolved else "open", "last_run": run})
    return {"shop_today": data["shop_today"], "tickets": tickets}


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    """One ticket with its linked records and the work agents have done on it."""
    data = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not data.get("found"):
        raise HTTPException(status_code=404, detail=f"No ticket {ticket_id}.")
    return data


# ---------------------------------------------------------------------------
# Agent runs
# ---------------------------------------------------------------------------

async def _run(session_id: str, ticket_id: int) -> None:
    run = runs[session_id]
    try:
        report = await run_team(ticket_task(ticket_id), session_id=session_id, ticket_id=ticket_id)
        run.update(status="done", report=report.model_dump(mode="json"))
    except Exception as exc:  # reported to the board instead of crashing the server
        run.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        run["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        active_run["session_id"] = None


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int):
    """Start the agent team on one ticket. Returns at once; poll /api/runs/{session_id} and /api/events."""
    if active_run["session_id"]:
        raise HTTPException(status_code=409, detail=f"Run {active_run['session_id']} is still going.")
    if not (await mcp("get_ticket", {"ticket_id": ticket_id})).get("found"):
        raise HTTPException(status_code=404, detail=f"No ticket {ticket_id}.")
    session_id = new_session_id()
    active_run["session_id"] = session_id
    runs[session_id] = {
        "session_id": session_id,
        "ticket_id": ticket_id,
        "status": "running",
        "model": MODEL_NAME,
        "gateway": llm_gateway(),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "report": None,
        "error": None,
    }
    runs[session_id]["task"] = asyncio.create_task(_run(session_id, ticket_id))
    return {k: v for k, v in runs[session_id].items() if k != "task"}


@app.get("/api/runs/{session_id}")
async def get_run(session_id: str):
    """Status of an API-started run (running / done / failed) and the Boss's report when done."""
    if session_id not in runs:
        raise HTTPException(status_code=404, detail=f"No run {session_id} since the server started.")
    return {k: v for k, v in runs[session_id].items() if k != "task"}


# ---------------------------------------------------------------------------
# Agent events (from the audit trail)
# ---------------------------------------------------------------------------

def _event(e: dict) -> dict:
    """Board-friendly view of one audit entry: who acted, what they said, which tools."""
    out = {k: e.get(k) for k in ("ts", "session_id", "agent", "step", "step_no")}
    out["chain"] = "/".join(e.get("chain") or [])
    step = e.get("step")
    if step == "model_response":
        out["said"] = e.get("text")
        out["tools"] = [c["tool"] for c in e.get("tool_calls", [])]
        out["tool_calls"] = e.get("tool_calls", [])
    elif step == "model_request":
        out["tools"] = [r["tool"] for r in e.get("tool_results", [])]
        out["tool_results"] = e.get("tool_results", [])
        out["retries"] = e.get("retries") or None
    elif step == "delegate":
        out.update(to=e.get("to"), said=e.get("task"), allowed=e.get("allowed"), blocked_reason=e.get("blocked_reason"))
    elif step == "end":
        out["output"] = e.get("output")
    elif step == "user_prompt":
        out["said"] = e.get("prompt")
    elif step == "error":
        out["error"] = e.get("error")
    else:
        out["detail"] = {k: v for k, v in e.items() if k not in out}
    return out


@app.get("/api/events")
async def events(
    limit: int = Query(50, ge=1, le=500),
    session_id: str | None = None,
    agent: str | None = None,
):
    """Most recent agent events, oldest first. Filter by session_id or agent."""
    entries = read_audit()
    if session_id:
        entries = [e for e in entries if e.get("session_id") == session_id]
    if agent:
        entries = [e for e in entries if e.get("agent") == agent]
    return {"total": len(entries), "events": [_event(e) for e in entries[-limit:]]}


# ---------------------------------------------------------------------------
# Human approvals: the only routes that move cash
# ---------------------------------------------------------------------------

class Approval(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the human approving.")


class Denial(BaseModel):
    denied_by: str = Field(min_length=1)
    note: str = ""


@app.get("/api/payments")
async def payment_requests(status: str | None = "pending"):
    """Payment requests the agents prepared. status=pending (default), approved, denied, or omit for all."""
    return await mcp("list_payment_requests", {"status": status or None})


@app.post("/api/payments/{request_id}/approve")
async def approve_payment(request_id: int, body: Approval):
    """Human approves a payment request: writes `payments`, lowers checking, updates the bill."""
    result = require_ok(await mcp("approve_payment", {"request_id": request_id, "approved_by": body.approved_by}))
    await audit.append(
        {"agent": "human", "step": "payment_approve", "request_id": request_id, "by": body.approved_by, "result": result}
    )
    return result


@app.post("/api/payments/{request_id}/deny")
async def deny_payment(request_id: int, body: Denial):
    """Human denies a payment request. No money moves."""
    result = require_ok(
        await mcp("deny_payment", {"request_id": request_id, "denied_by": body.denied_by, "note": body.note})
    )
    await audit.append({"agent": "human", "step": "payment_deny", "request_id": request_id, "by": body.denied_by})
    return result


@app.get("/api/purchase-orders")
async def purchase_orders(status: str | None = None):
    """Purchase orders the agents drafted, with any payment request attached."""
    return await mcp("list_purchase_orders", {"status": status})


@app.post("/api/purchase-orders/{po_id}/approve")
async def approve_purchase(po_id: int, body: Approval):
    """Human approves a drafted purchase order: pays it and places the order (status -> ordered, with ETA).

    Uses the PO's pending payment request if Accounting made one; otherwise
    files the request on the human's behalf, then approves it.
    """
    pos = (await mcp("list_purchase_orders", {}))["purchase_orders"]
    po = next((p for p in pos if p["id"] == po_id), None)
    if po is None:
        raise HTTPException(status_code=404, detail=f"No purchase order {po_id}.")
    if po["status"] != "draft":
        raise HTTPException(status_code=400, detail=f"Purchase order {po_id} is already {po['status']}.")

    pending = (await mcp("list_payment_requests", {"status": "pending"}))["requests"]
    request = next((r for r in pending if r["kind"] == "purchase_order" and r["ref_id"] == po_id), None)
    if request is None:
        request = require_ok(
            await mcp(
                "request_payment",
                {
                    "kind": "purchase_order",
                    "ref_id": po_id,
                    "reason": f"Approved from the dashboard by {body.approved_by}.",
                    "agent": f"human:{body.approved_by}",
                    "ticket_id": po["ticket_id"],
                },
            )
        )
        request_id = request["request_id"]
    else:
        request_id = request["id"]

    result = await mcp("approve_payment", {"request_id": request_id, "approved_by": body.approved_by})
    if result.get("ok") is False:
        # Don't leave a stray pending request behind if approval was refused.
        if request is not None and "request_id" in request:
            await mcp("deny_payment", {"request_id": request_id, "denied_by": body.approved_by, "note": result.get("message", "")})
        raise HTTPException(status_code=400, detail=result.get("message", "Approval refused."))
    await audit.append(
        {"agent": "human", "step": "purchase_approve", "po_id": po_id, "request_id": request_id, "by": body.approved_by, "result": result}
    )
    return {"po_id": po_id, "request_id": request_id, **result}


# ---------------------------------------------------------------------------
# Cash and reset
# ---------------------------------------------------------------------------

@app.get("/api/cash")
async def cash():
    """Current checking balance from cash_accounts, plus what's waiting on approval."""
    data = await mcp("get_cash_position")
    return {
        "account": data["account"],
        "balance": data["balance"],
        "shop_today": data["shop_today"],
        "pending_total": data["pending_total"],
        "balance_after_pending": data["balance_after_pending"],
    }


@app.post("/api/reset")
async def reset():
    """Copy the original database over the working copy for a fresh run. The audit trail is kept."""
    if active_run["session_id"]:
        raise HTTPException(status_code=409, detail="Can't reset while an agent run is going.")
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    await audit.append({"agent": "human", "step": "database_reset", "source": ORIGINAL_DB.name})
    return {"ok": True, "working_db": WORKING_DB.name, "reset_from": ORIGINAL_DB.name, "cash": await cash()}


@app.get("/api/health")
async def health():
    return {"ok": True, "model": MODEL_NAME, "gateway": llm_gateway(), "active_run": active_run["session_id"]}
