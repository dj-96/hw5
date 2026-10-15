"""Campus Customs MCP server.

Exposes shop-database tools to the agent team. Every tool reads only
from the working copy `data/campus_customs_new.db`, never the original, and
returns only what is in the database (nothing is invented). Lookups that
find nothing return `found: False` instead of guessing.

Money rule: agents can only *request* a payment (`request_payment`). Only a
human can approve it (`approve_payment` / `deny_payment`), and the backend
hides those two tools from every agent. Approving a payment is the only
thing that moves cash.

Run (stdio transport):  python mcp_server/server.py
"""
import calendar
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastmcp import FastMCP

PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "data" / "campus_customs_new.db"

# Shop policy. Kept here so every agent sees the same numbers.
MIN_MARGIN = 0.40  # a discounted sale must keep at least a 40% gross margin
CASH_ACCOUNT = "checking"
TICKET_STATUSES = (
    "open", "in_progress", "waiting_on_approval", "waiting_on_vendor", "resolved", "declined",
)
PAYMENT_KINDS = ("invoice", "rent", "purchase_order")
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service", "customer service"}

mcp = FastMCP(
    name="campus-customs",
    instructions=(
        "Tools for the Campus Customs shop database. 'Today' is desk.date_today, "
        "not the real-world date. Only report values these tools return."
    ),
)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    # mode=rw: fail loudly if the working copy is missing instead of
    # silently creating an empty database.
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    ensure_work_tables(conn)
    try:
        yield conn
    finally:
        conn.close()


def ensure_work_tables(conn: sqlite3.Connection) -> None:
    """Add the tables the agent team writes to. The original tables are untouched."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS payment_requests (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,
            ref_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            ticket_id INTEGER,
            reason TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            decided_by TEXT,
            decided_at TEXT,
            decision_note TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY,
            vendor_id INTEGER NOT NULL REFERENCES vendors(id),
            sku TEXT NOT NULL,
            size TEXT NOT NULL,
            qty INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            total REAL NOT NULL,
            ticket_id INTEGER,
            status TEXT NOT NULL DEFAULT 'draft',
            eta TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS message_drafts (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER NOT NULL REFERENCES tickets(id),
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


def now_stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1]))


def shop_today(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None:
        raise ValueError("desk.date_today is missing from the database")
    return date.fromisoformat(row["date_today"])


def cash_balance(conn: sqlite3.Connection) -> float:
    row = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)).fetchone()
    if row is None:
        raise ValueError(f"Cash account '{CASH_ACCOUNT}' is missing")
    return row["balance"]


def open_invoice_count(conn: sqlite3.Connection, vendor_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM invoices WHERE vendor_id = ? AND status = 'open'", (vendor_id,)
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# Stock, vendors, leases (Problem 3)
# ---------------------------------------------------------------------------

@mcp.tool
def check_stock(sku: str, size: str, qty_needed: int | None = None) -> dict:
    """Check units on hand for one SKU and size in the inventory table.

    Pass qty_needed (the ticket's qty) to get the shortfall, i.e. how many
    units must be restocked before the request can be filled.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku.strip(), size.strip()),
        ).fetchone()
        if row is None:
            sizes = [
                r["size"]
                for r in conn.execute("SELECT size FROM inventory WHERE sku = ?", (sku.strip(),))
            ]
            return {
                "found": False,
                "sku": sku,
                "size": size,
                "sizes_on_file_for_sku": sizes,
                "message": "No inventory row for this SKU and size.",
            }

    result = {
        "found": True,
        "sku": row["sku"],
        "name": row["name"],
        "size": row["size"],
        "qty_on_hand": row["qty"],
        "location": row["location"],
    }
    if qty_needed is not None:
        shortfall = max(qty_needed - row["qty"], 0)
        result.update(
            qty_needed=qty_needed,
            shortfall=shortfall,
            can_fill_from_stock=shortfall == 0,
        )
    return result


@mcp.tool
def check_vendor_status(vendor_id: int | None = None) -> dict:
    """Show each vendor's specialty, lead time, and open unpaid invoices.

    A vendor will not ship new product while it has any open invoice, so
    `can_ship` is False until those invoices are paid. Omit vendor_id to
    see every vendor. Overdue days are measured from desk.date_today.
    """
    with connect() as conn:
        today = shop_today(conn)
        query = "SELECT id, name, specialty, lead_days FROM vendors"
        params: tuple = ()
        if vendor_id is not None:
            query += " WHERE id = ?"
            params = (vendor_id,)
        vendors = conn.execute(query + " ORDER BY id", params).fetchall()
        if not vendors:
            return {"found": False, "vendor_id": vendor_id, "message": "No vendor with this id."}

        results = []
        for v in vendors:
            open_invoices = []
            for inv in conn.execute(
                "SELECT id, amount, due_date, description FROM invoices "
                "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
                (v["id"],),
            ):
                days_past_due = (today - date.fromisoformat(inv["due_date"])).days
                open_invoices.append(
                    {
                        "invoice_id": inv["id"],
                        "amount": inv["amount"],
                        "due_date": inv["due_date"],
                        "days_overdue": max(days_past_due, 0),
                        "is_overdue": days_past_due > 0,
                        "description": inv["description"],
                    }
                )
            can_ship = not open_invoices
            results.append(
                {
                    "vendor_id": v["id"],
                    "name": v["name"],
                    "specialty": v["specialty"],
                    "lead_days": v["lead_days"],
                    "open_invoices": open_invoices,
                    "open_balance": round(sum(i["amount"] for i in open_invoices), 2),
                    "can_ship": can_ship,
                    # Only meaningful once the vendor is unblocked and an order is placed today.
                    "arrival_if_ordered_today": (
                        (today + timedelta(days=v["lead_days"])).isoformat() if can_ship else None
                    ),
                }
            )

    return {"found": True, "shop_today": today.isoformat(), "vendors": results}


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Look up a lease: landlord, monthly rent, and when the next rent is due.

    `days_until_due` is counted from desk.date_today; a negative value means
    the rent is overdue.
    """
    with connect() as conn:
        today = shop_today(conn)
        row = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
    if row is None:
        return {"found": False, "lease_id": lease_id, "message": "No lease with this id."}

    days_until_due = (date.fromisoformat(row["next_due"]) - today).days
    return {
        "found": True,
        "lease_id": row["id"],
        "space_name": row["space_name"],
        "landlord": row["landlord"],
        "monthly_rent": row["monthly_rent"],
        "next_due": row["next_due"],
        "shop_today": today.isoformat(),
        "days_until_due": days_until_due,
        "is_overdue": days_until_due < 0,
        "notes": row["notes"],
    }


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

@mcp.tool
def list_tickets(status: str | None = "open") -> dict:
    """List tickets on the board, oldest first. Pass status=None for every ticket."""
    with connect() as conn:
        query = "SELECT id, type, requester, subject, status, created_at FROM tickets"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        rows = [dict(r) for r in conn.execute(query + " ORDER BY created_at", params)]
        return {"shop_today": shop_today(conn).isoformat(), "count": len(rows), "tickets": rows}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Full ticket plus the records it links to (stock row, invoice, lease)
    and any payment requests, purchase orders, or drafts already made for it."""
    with connect() as conn:
        t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"found": False, "ticket_id": ticket_id, "message": "No ticket with this id."}
        linked: dict = {}
        if t["sku"]:
            row = conn.execute(
                "SELECT qty, location FROM inventory WHERE sku = ? AND size = ?", (t["sku"], t["size"])
            ).fetchone()
            linked["inventory"] = dict(row) if row else None
        if t["invoice_id"]:
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (t["invoice_id"],)).fetchone()
            linked["invoice"] = dict(row) if row else None
        if t["lease_id"]:
            row = conn.execute("SELECT * FROM leases WHERE id = ?", (t["lease_id"],)).fetchone()
            linked["lease"] = dict(row) if row else None
        work = {
            table: [dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE ticket_id = ?", (ticket_id,))]
            for table in ("payment_requests", "purchase_orders", "message_drafts")
        }
        return {
            "found": True,
            "shop_today": shop_today(conn).isoformat(),
            "ticket": dict(t),
            "linked": linked,
            "work_so_far": work,
        }


@mcp.tool
def update_ticket(ticket_id: int, status: str, note: str, agent: str) -> dict:
    """Set a ticket's status and append a signed note to it.

    status must be one of: open, in_progress, waiting_on_approval,
    waiting_on_vendor, resolved, declined.
    """
    if status not in TICKET_STATUSES:
        return {"ok": False, "message": f"status must be one of {list(TICKET_STATUSES)}"}
    with connect() as conn:
        t = conn.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"ok": False, "message": f"No ticket {ticket_id}."}
        stamp = shop_today(conn).isoformat()
        notes = (t["notes"] or "") + f"\n[{stamp} {agent}] {note.strip()}"
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
        conn.commit()
    return {"ok": True, "ticket_id": ticket_id, "status": status}


# ---------------------------------------------------------------------------
# Pricing and cash
# ---------------------------------------------------------------------------

@mcp.tool
def quote_discount(sku: str, qty: int, discount_pct: float = 0.0) -> dict:
    """Price a (possibly discounted) order from the pricing table and check it
    against the shop's 40% minimum gross margin.

    discount_pct is percent off list price, e.g. 15 for 15% off. Also returns
    the largest discount that still meets the margin floor.
    """
    with connect() as conn:
        p = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku.strip(),)).fetchone()
    if p is None:
        return {"found": False, "sku": sku, "message": "No pricing row for this SKU."}
    if not 0 <= discount_pct < 100:
        return {"found": True, "ok": False, "message": "discount_pct must be at least 0 and below 100."}
    unit_price = round(p["list_price"] * (1 - discount_pct / 100), 2)
    margin = (unit_price - p["unit_cost"]) / unit_price
    # Highest discount d where (price*(1-d) - cost) / (price*(1-d)) >= MIN_MARGIN
    max_discount = (1 - p["unit_cost"] / ((1 - MIN_MARGIN) * p["list_price"])) * 100
    return {
        "found": True,
        "ok": True,
        "sku": p["sku"],
        "qty": qty,
        "unit_cost": p["unit_cost"],
        "list_price": p["list_price"],
        "discount_pct": discount_pct,
        "unit_price": unit_price,
        "order_revenue": round(unit_price * qty, 2),
        "order_cost": round(p["unit_cost"] * qty, 2),
        "gross_margin_pct": round(margin * 100, 1),
        "min_margin_pct": MIN_MARGIN * 100,
        "meets_margin_floor": margin >= MIN_MARGIN,
        "max_discount_pct_at_floor": round(max_discount, 1),
    }


@mcp.tool
def get_cash_position() -> dict:
    """Cash on hand, money already waiting on approval, and what would be left.

    No revenue is modeled: cash only goes down, so every payment competes for
    the same balance.
    """
    with connect() as conn:
        today = shop_today(conn)
        balance = cash_balance(conn)
        pending = [
            dict(r)
            for r in conn.execute(
                "SELECT id, kind, ref_id, amount, ticket_id FROM payment_requests WHERE status = 'pending'"
            )
        ]
        open_invoices = [
            dict(r) for r in conn.execute("SELECT id, vendor_id, amount, due_date FROM invoices WHERE status = 'open'")
        ]
        rent_due = [
            dict(r)
            for r in conn.execute(
                "SELECT id, landlord, monthly_rent, next_due FROM leases WHERE next_due <= ?",
                ((today + timedelta(days=30)).isoformat(),),
            )
        ]
    pending_total = round(sum(r["amount"] for r in pending), 2)
    return {
        "shop_today": today.isoformat(),
        "account": CASH_ACCOUNT,
        "balance": balance,
        "pending_requests": pending,
        "pending_total": pending_total,
        "balance_after_pending": round(balance - pending_total, 2),
        "open_invoices": open_invoices,
        "rent_due_next_30_days": rent_due,
    }


# ---------------------------------------------------------------------------
# Purchase orders and outgoing messages (drafts only)
# ---------------------------------------------------------------------------

@mcp.tool
def create_purchase_order(
    vendor_id: int, sku: str, size: str, qty: int, agent: str, ticket_id: int | None = None
) -> dict:
    """Draft a restock purchase order at the pricing table's unit cost.

    This does not spend money or contact the vendor. The draft only becomes an
    order after Accounting requests payment for it and a human approves.
    """
    if qty <= 0:
        return {"ok": False, "message": "qty must be positive."}
    with connect() as conn:
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"ok": False, "message": f"No vendor {vendor_id}."}
        if conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone() is None:
            return {"ok": False, "message": f"{sku} / {size} is not a product the shop stocks."}
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return {"ok": False, "message": f"No unit cost on file for {sku}."}
        total = round(price["unit_cost"] * qty, 2)
        cur = conn.execute(
            "INSERT INTO purchase_orders (vendor_id, sku, size, qty, unit_cost, total, ticket_id, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (vendor_id, sku, size, qty, price["unit_cost"], total, ticket_id, agent, now_stamp()),
        )
        conn.commit()
        blocked = open_invoice_count(conn, vendor_id) > 0
    return {
        "ok": True,
        "po_id": cur.lastrowid,
        "status": "draft",
        "vendor": vendor["name"],
        "sku": sku,
        "size": size,
        "qty": qty,
        "unit_cost": price["unit_cost"],
        "total": total,
        "vendor_blocked_by_open_invoice": blocked,
        "next_step": "Accounting must request_payment(kind='purchase_order', ref_id=po_id) for human approval.",
    }


@mcp.tool
def list_purchase_orders(status: str | None = None) -> dict:
    """List purchase orders (draft or ordered) with vendor name and any payment request on them."""
    with connect() as conn:
        query = (
            "SELECT po.*, v.name AS vendor_name, "
            "(SELECT pr.id FROM payment_requests pr WHERE pr.kind = 'purchase_order' AND pr.ref_id = po.id "
            " ORDER BY pr.id DESC LIMIT 1) AS payment_request_id "
            "FROM purchase_orders po JOIN vendors v ON v.id = po.vendor_id"
        )
        params: tuple = ()
        if status:
            query, params = query + " WHERE po.status = ?", (status,)
        rows = [dict(r) for r in conn.execute(query + " ORDER BY po.id", params)]
    return {"count": len(rows), "purchase_orders": rows}


@mcp.tool
def draft_customer_message(ticket_id: int, recipient: str, subject: str, body: str, agent: str) -> dict:
    """Save a message to a customer or partner as a DRAFT. Nothing is sent;
    a human reviews and sends every outgoing message."""
    with connect() as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"ok": False, "message": f"No ticket {ticket_id}."}
        cur = conn.execute(
            "INSERT INTO message_drafts (ticket_id, recipient, subject, body, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, recipient, subject, body, agent, now_stamp()),
        )
        conn.commit()
    return {"ok": True, "draft_id": cur.lastrowid, "status": "draft", "sent": False}


# ---------------------------------------------------------------------------
# Payments: agents request, humans approve
# ---------------------------------------------------------------------------

def _payment_target(conn: sqlite3.Connection, kind: str, ref_id: int) -> tuple[float | None, str]:
    """Return (amount on file, problem) for the record being paid."""
    if kind == "invoice":
        row = conn.execute("SELECT amount, status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
        if row is None:
            return None, f"No invoice {ref_id}."
        if row["status"] != "open":
            return None, f"Invoice {ref_id} is already {row['status']}."
        return row["amount"], ""
    if kind == "rent":
        row = conn.execute("SELECT monthly_rent FROM leases WHERE id = ?", (ref_id,)).fetchone()
        return (row["monthly_rent"], "") if row else (None, f"No lease {ref_id}.")
    if kind == "purchase_order":
        row = conn.execute("SELECT total, status FROM purchase_orders WHERE id = ?", (ref_id,)).fetchone()
        if row is None:
            return None, f"No purchase order {ref_id}."
        if row["status"] != "draft":
            return None, f"Purchase order {ref_id} is already {row['status']}."
        return row["total"], ""
    return None, f"kind must be one of {list(PAYMENT_KINDS)}"


@mcp.tool
def request_payment(kind: str, ref_id: int, reason: str, agent: str, ticket_id: int | None = None) -> dict:
    """Ask a human to approve a payment. This does NOT pay anything.

    kind is 'invoice' (ref_id = invoice id), 'rent' (ref_id = lease id), or
    'purchase_order' (ref_id = PO id). The amount always comes from the
    database record, never from the agent.
    """
    with connect() as conn:
        amount, problem = _payment_target(conn, kind, ref_id)
        if problem:
            return {"ok": False, "message": problem}
        dup = conn.execute(
            "SELECT id FROM payment_requests WHERE kind = ? AND ref_id = ? AND status = 'pending'", (kind, ref_id)
        ).fetchone()
        if dup:
            return {"ok": False, "message": f"Already waiting on approval as request {dup['id']}.", "request_id": dup["id"]}
        balance = cash_balance(conn)
        pending_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payment_requests WHERE status = 'pending'"
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO payment_requests (kind, ref_id, amount, ticket_id, reason, requested_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kind, ref_id, amount, ticket_id, reason, agent, now_stamp()),
        )
        conn.commit()
    after = round(balance - pending_total - amount, 2)
    return {
        "ok": True,
        "request_id": cur.lastrowid,
        "status": "pending",
        "kind": kind,
        "ref_id": ref_id,
        "amount": amount,
        "balance": balance,
        "balance_if_all_pending_approved": after,
        "warning": "Not enough cash if every pending request is approved." if after < 0 else None,
    }


@mcp.tool
def list_payment_requests(status: str | None = "pending") -> dict:
    """List payment requests and their human decisions. Pass status=None for all."""
    with connect() as conn:
        query, params = "SELECT * FROM payment_requests", ()
        if status:
            query, params = query + " WHERE status = ?", (status,)
        rows = [dict(r) for r in conn.execute(query + " ORDER BY id", params)]
        return {"balance": cash_balance(conn), "count": len(rows), "requests": rows}


@mcp.tool
def approve_payment(request_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Approve a pending request and make the payment.

    Refuses if cash would go negative or the vendor is blocked. On success it
    writes a `payments` row naming the approver, lowers the cash balance, and
    updates the paid record (invoice -> paid, lease next_due + 1 month,
    purchase order -> ordered with an ETA).
    """
    if not approved_by.strip() or approved_by.strip().lower() in AGENT_NAMES:
        return {"ok": False, "message": "approved_by must be a named human, not an agent."}
    with connect() as conn:
        req = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"ok": False, "message": f"No payment request {request_id}."}
        if req["status"] != "pending":
            return {"ok": False, "message": f"Request {request_id} is already {req['status']}."}
        amount, problem = _payment_target(conn, req["kind"], req["ref_id"])
        if problem:
            return {"ok": False, "message": problem}
        balance = cash_balance(conn)
        if amount > balance:
            return {"ok": False, "message": f"Refused: ${amount:,.2f} is more than the ${balance:,.2f} in {CASH_ACCOUNT}."}
        today = shop_today(conn)
        result: dict = {}
        if req["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
        elif req["kind"] == "rent":
            due = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()["next_due"]
            new_due = add_month(date.fromisoformat(due)).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, req["ref_id"]))
            result["lease_next_due"] = new_due
        else:
            po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (req["ref_id"],)).fetchone()
            if open_invoice_count(conn, po["vendor_id"]) > 0:
                return {"ok": False, "message": "Refused: this vendor still has an open invoice and will not ship."}
            lead = conn.execute("SELECT lead_days FROM vendors WHERE id = ?", (po["vendor_id"],)).fetchone()["lead_days"]
            eta = (today + timedelta(days=lead)).isoformat()
            conn.execute("UPDATE purchase_orders SET status = 'ordered', eta = ? WHERE id = ?", (eta, po["id"]))
            result["po_eta"] = eta
        new_balance = round(balance - amount, 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today.isoformat(), CASH_ACCOUNT),
        )
        pay = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (req["kind"], req["ref_id"], amount, CASH_ACCOUNT, today.isoformat(), approved_by.strip()),
        )
        conn.execute(
            "UPDATE payment_requests SET status = 'approved', decided_by = ?, decided_at = ? WHERE id = ?",
            (approved_by.strip(), now_stamp(), request_id),
        )
        conn.commit()
    return {"ok": True, "payment_id": pay.lastrowid, "amount": amount, "new_balance": new_balance, **result}


@mcp.tool
def deny_payment(request_id: int, denied_by: str, note: str = "") -> dict:
    """HUMAN ONLY. Deny a pending payment request. No money moves."""
    with connect() as conn:
        cur = conn.execute(
            "UPDATE payment_requests SET status = 'denied', decided_by = ?, decided_at = ?, decision_note = ? "
            "WHERE id = ? AND status = 'pending'",
            (denied_by.strip(), now_stamp(), note, request_id),
        )
        conn.commit()
    if cur.rowcount == 0:
        return {"ok": False, "message": f"No pending request {request_id}."}
    return {"ok": True, "request_id": request_id, "status": "denied"}


if __name__ == "__main__":
    mcp.run(show_banner=False)
