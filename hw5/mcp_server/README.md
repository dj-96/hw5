# Campus Customs MCP Server

## What it is for

This is the single tool layer for the Campus Customs agent team. The Boss, Inventory, Accounting, Facilities, and Customer Service agents never touch the database directly. They call the tools in this MCP server instead. That keeps every agent working from the same real shop data, and the tools only return what is in the database (lookups that find nothing return `found: false` rather than a guess).

Built with **FastMCP** (`fastmcp` package) in `server.py`.

## Which database it uses

`data/campus_customs_new.db`, the **working copy**.

The original `data/campus_customs.db` is never opened by this server. To start over, copy the original over the working copy.

"Today" for every tool is `desk.date_today` in the database (2026-08-31), not the real-world date.

## Tools

### Read tools

| Tool | Tables | What it returns |
|---|---|---|
| `check_stock(sku, size, qty_needed=None)` | `inventory` | Units on hand and location for one SKU + size. With `qty_needed`, it also returns the `shortfall` and whether stock can fill the request. |
| `check_vendor_status(vendor_id=None)` | `vendors`, `invoices`, `desk` | Each vendor's specialty, lead days, and open unpaid invoices (with days overdue), plus `can_ship`, which is false while any invoice is open, and the arrival date if ordered today. Omit `vendor_id` to list every vendor. |
| `get_lease(lease_id)` | `leases`, `desk` | Landlord, monthly rent, next due date, and `days_until_due` counted from the shop's today (negative means overdue). |
| `list_tickets(status="open")` | `tickets`, `desk` | Tickets on the board, oldest first. `status=None` lists all. |
| `get_ticket(ticket_id)` | `tickets`, `inventory`, `invoices`, `leases`, `payment_requests`, `purchase_orders`, `message_drafts` | One ticket, its linked stock row, invoice, and lease, plus any requests, POs, or drafts already made for it. |
| `quote_discount(sku, qty, discount_pct=0)` | `pricing` | Discounted unit price, order revenue and cost, gross margin %, whether it meets the 40% floor, and the largest discount that does. |
| `get_cash_position()` | `cash_accounts`, `payment_requests`, `invoices`, `leases`, `desk` | Balance, pending payment requests, balance after pending, open invoices, and rent due in the next 30 days. |
| `list_payment_requests(status="pending")` | `payment_requests`, `cash_accounts` | Payment requests and the human decision on each. |
| `list_purchase_orders(status=None)` | `purchase_orders`, `vendors`, `payment_requests` | Purchase orders with vendor name and any payment request. Used by the backend API's approve-purchase route; not given to agents. |

### Write tools (agents)

| Tool | Tables | What it does |
|---|---|---|
| `update_ticket(ticket_id, status, note, agent)` | `tickets`, `desk` | Sets the status (`open`, `in_progress`, `waiting_on_approval`, `waiting_on_vendor`, `resolved`, `declined`) and appends a signed, dated note. |
| `create_purchase_order(vendor_id, sku, size, qty, agent, ticket_id=None)` | `purchase_orders`, `vendors`, `inventory`, `pricing`, `invoices` | Drafts a restock PO at the unit cost on file. Spends nothing. Reports whether the vendor is blocked by an open invoice. |
| `draft_customer_message(ticket_id, recipient, subject, body, agent)` | `message_drafts`, `tickets` | Saves an outgoing message as a draft. Nothing is sent. |
| `request_payment(kind, ref_id, reason, agent, ticket_id=None)` | `payment_requests`, `invoices`, `leases`, `purchase_orders`, `cash_accounts` | Asks a human to approve paying an `invoice`, `rent`, or a `purchase_order`. The amount is read from the database. Duplicate pending requests are refused. **Does not pay.** |

### Human-only tools

The agent backend hides these from every agent and blocks them at call time. Only the human approval desk (`python -m backend.approve`) calls them.

| Tool | Tables | What it does |
|---|---|---|
| `approve_payment(request_id, approved_by)` | `payment_requests`, `payments`, `cash_accounts`, `invoices`, `leases`, `purchase_orders`, `vendors`, `desk` | Pays a pending request: writes a `payments` row with the approver's name and lowers cash. It also marks the invoice paid, moves the lease's `next_due` forward a month, or orders the PO with an ETA. Refuses if cash would go negative, the vendor is still blocked, or the approver is an agent name. |
| `deny_payment(request_id, denied_by, note="")` | `payment_requests` | Denies a pending request. No money moves. |

### Tables the server adds

On first use the server creates `payment_requests`, `purchase_orders`, and `message_drafts` in the working copy. The original tables are not altered.

## Running it

From the `Homework 5` folder:

```
.venv\Scripts\python.exe mcp_server\server.py
```

This starts the server on the stdio transport, which the agent backend connects to.
