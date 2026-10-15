# Campus Customs Multi-Agent Operations — Harness

This file is the working spec for the Campus Customs agent team: what data it works on, which tools it can use, who the agents are, how the backend and dashboard expose them, and the safety rules around real customers and real money.

**Contents:** 1. Database (tables) · 2. MCP server tools · 3. The five agents · 4. Backend API routes · 5. Dashboard · 6. Safety rules · 7. Full run (Problem 9)

**Run everything:**

```
# terminal 1, from Homework 5/backend   (API + agents + MCP server)
..\.venv\Scripts\uvicorn main:app --reload --port 8000

# terminal 2, from Homework 5/frontend  (React desk at http://localhost:5173)
npm run dev
```

All agents use `gpt-6-luna`. Keys come from the class folder's `.env`, and `Homework 5/.env` sets `LLM_GATEWAY` (`portkey` by default, `openai` while the Portkey key is out of budget).

## 1. Database

- **Original (never modified):** `data/campus_customs.db`
- **Working copy (agents, MCP server and backend point here):** `data/campus_customs_new.db`
- To reset, copy the original over the working copy before each full run.

### Tables

#### `desk`
| Field | Type | Notes |
|---|---|---|
| `date_today` | TEXT | The shop's "today" (`2026-08-31`) |
| `notes` | TEXT | Free-form desk notes (currently empty) |

**Why it matters:** This is the shop clock. Every agent uses `date_today`, not the real date, to decide what is overdue or due soon and to compute vendor arrival dates.

#### `tickets`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Ticket number |
| `type` | TEXT | `customer_order`, `rent_notice`, `price_override`, ... |
| `requester` | TEXT | Who raised it (customer, landlord, student org) |
| `subject` | TEXT | Short title |
| `sku`, `size`, `qty` | TEXT / TEXT / INTEGER | Product being asked about (if any) |
| `lease_id` | INTEGER FK → `leases.id` | Linked lease (rent tickets) |
| `invoice_id` | INTEGER FK → `invoices.id` | Linked vendor invoice |
| `status` | TEXT | `open` → updated as agents resolve it |
| `notes` | TEXT | Request details |
| `created_at` | TEXT | ISO timestamp |

**Why it matters:** This is the board. The Boss reads each open ticket and routes it, and the foreign keys tell the specialists exactly which stock row, lease, or invoice to look at.

#### `inventory`
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT (PK part) | Product code |
| `name` | TEXT | Product name |
| `size` | TEXT (PK part) | `S`/`M`/`L`/`XL`, or `OS` (one size) |
| `qty` | INTEGER | Units on hand |
| `location` | TEXT | Aisle |

**Why it matters:** Inventory checks stock by SKU + size here to spot shortfalls before anyone promises a customer an order.

#### `pricing`
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT PK | Product code |
| `unit_cost` | REAL | What the shop pays the vendor |
| `list_price` | REAL | What the customer pays |

**Why it matters:** Accounting uses cost vs. price to check margins on discount requests and to cost out restock purchase orders.

#### `vendors`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Vendor id |
| `name` | TEXT | Vendor name |
| `specialty` | TEXT | What they supply |
| `lead_days` | INTEGER | Days from order to delivery |

**Why it matters:** Inventory picks the right vendor for a restock by specialty and uses `lead_days` to give a realistic arrival date.

#### `leases`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Lease id |
| `space_name` | TEXT | The shop space |
| `landlord` | TEXT | Who gets paid |
| `monthly_rent` | REAL | Rent amount |
| `next_due` | TEXT | Next rent due date |
| `notes` | TEXT | Lease notes |

**Why it matters:** Facilities owns this table. It tells the team how much rent is due and when, and `next_due` should advance one month after rent is paid.

#### `cash_accounts`
| Field | Type | Notes |
|---|---|---|
| `name` | TEXT PK | Account name (`checking`) |
| `balance` | REAL | Current cash |
| `date` | TEXT | As-of date |

**Why it matters:** This is the only source of cash, and money only goes out in this homework. The pay tool must check `balance` and refuse any payment that would make it negative.

#### `payments`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Payment id |
| `kind` | TEXT | e.g. `invoice`, `rent`, `purchase_order` |
| `ref_id` | INTEGER | id of the invoice, lease, or PO being paid |
| `amount` | REAL | Amount paid |
| `account` | TEXT | Cash account debited |
| `paid_at` | TEXT | Shop date of payment |
| `approved_by` | TEXT | The human who approved it |

**Why it matters:** This is the audit trail. Every payment must have a row here naming the human approver, which proves no agent paid anything on its own. It starts empty.

#### `invoices`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Invoice id |
| `vendor_id` | INTEGER FK → `vendors.id` | Who billed us |
| `amount` | REAL | Amount owed |
| `due_date` | TEXT | Due date |
| `status` | TEXT | `open` or `paid` |
| `description` | TEXT | What it was for |

**Why it matters:** These are unpaid bills. A vendor will not ship new product while it has an `open` invoice, so Accounting must clear it before Inventory can restock from that vendor.

### Tables the agent team adds

The MCP server creates these in the working copy on first use. The original nine tables keep their schema.

#### `payment_requests`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Request id |
| `kind` | TEXT | `invoice`, `rent`, or `purchase_order` |
| `ref_id` | INTEGER | Invoice id, lease id, or PO id |
| `amount` | REAL | Copied from that record, never typed by an agent |
| `ticket_id` | INTEGER | Ticket it serves |
| `reason` | TEXT | Why it's needed now |
| `requested_by` | TEXT | Agent (or `human:<name>` from the dashboard) |
| `status` | TEXT | `pending` → `approved` / `denied` |
| `decided_by`, `decided_at`, `decision_note` | TEXT | The human's decision |
| `created_at` | TEXT | Timestamp |

**Why it matters:** This is the line between agents and money. Agents can only add `pending` rows here. Only a named human's approval turns one into a `payments` row.

#### `purchase_orders`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | PO id |
| `vendor_id` | INTEGER FK → `vendors.id` | Who ships it |
| `sku`, `size`, `qty` | TEXT / TEXT / INTEGER | What to restock |
| `unit_cost`, `total` | REAL | From `pricing.unit_cost` × qty |
| `ticket_id` | INTEGER | Ticket it serves |
| `status` | TEXT | `draft` → `ordered` (after approval) |
| `eta` | TEXT | Shop date + vendor `lead_days`, set when ordered |
| `created_by`, `created_at` | TEXT | Inventory, timestamp |

**Why it matters:** Restocks are drafted at no cost and only become orders (and spend money) once a human approves them.

#### `message_drafts`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Draft id |
| `ticket_id` | INTEGER FK → `tickets.id` | Ticket it answers |
| `recipient`, `subject`, `body` | TEXT | The message |
| `status` | TEXT | Always `draft`; agents never send |
| `created_by`, `created_at` | TEXT | Customer Service, timestamp |

**Why it matters:** Every word that reaches a customer is reviewed by a person first.

### Starting snapshot (shop date 2026-08-31)

| Item | Value |
|---|---|
| Cash (checking) | $3,400.00 |
| Invoice 501 (Bulldog Print Co) | $840.00, due 2026-08-28, **open, 3 days overdue** |
| Rent (Chapel Street shop) | $2,400.00, due 2026-09-02 (in 2 days) |
| Payments made so far | none |

| SKU | Name | Stock by size | Unit cost | List price | Margin |
|---|---|---|---|---|---|
| CC-HOOD-NAVY | Basic Hoodie Big Yale | S 4, M 8, L 14, XL 6 | $22.00 | $58.00 | 62.1% |
| CC-TEE-WHITE | Classic Bulldog Tee | **S 0**, M 5, L 3, XL 2 | $8.00 | $28.00 | 71.4% |
| CC-HAT-BLUE | Yale Cap | OS 40 | $6.00 | $22.00 | 72.7% |
| CC-MUG-CREST | Crest Mug | **OS 0** | $3.50 | $14.00 | 75.0% |

| Vendor | Specialty | Lead days | Can ship now? |
|---|---|---|---|
| 1 Bulldog Print Co | apparel reprint | 5 | **No**, invoice 501 is open |
| 2 Elm City Gifts | mugs and small goods | 3 | Yes |
| 3 QuickShip CT | local courier | 1 | Yes |

### The three open tickets and how they link

**Ticket 101: `customer_order` from Tauhid Zaman, 1× CC-TEE-WHITE size S**
- `inventory`: CC-TEE-WHITE / S has **0** on hand, so the order can't be filled today.
- `invoice_id = 501`: the open $840 invoice from Bulldog Print Co for a *"Rush reprint CC-TEE-WHITE S"*. That reprint is the stock this customer is waiting on.
- `vendors`: Bulldog Print Co (apparel, 5 lead days) won't ship while 501 is unpaid.
- Path: Accounting asks a human to approve paying invoice 501 → the vendor can ship → Inventory sets the ETA at shop date + 5 days → Customer Service drafts an update for the customer.

**Ticket 102: `rent_notice` from Elm City Properties**
- `lease_id = 1`: Chapel Street shop, $2,400, due 2026-09-02 (not overdue yet, but due in 2 days).
- `cash_accounts`: $3,400 covers it.
- Path: Facilities confirms the lease and amount → Accounting asks a human to approve the payment → after payment, `leases.next_due` moves to 2026-10-02.

**Ticket 103: `price_override` from Yale AI Club, 20× CC-HOOD-NAVY size M with a bulk discount**
- `inventory`: only **8** size M on hand, so the shop is **12 short**.
- `pricing`: cost $22 and list price $58. At full price, 20 hoodies = $1,160 revenue on $440 cost. Accounting must keep any discount above a margin floor.
- `vendors`: a restock needs Bulldog Print Co (apparel), which is also blocked by invoice 501. 12 × $22 = **$264** purchase order, arriving 5 days after it's placed.
- Path: Inventory reports the shortfall and vendor → Accounting checks the margin on the discount and the cash for the PO → Boss decides → Customer Service drafts the reply.

### Cross-ticket constraints the Boss must weigh
- **Cash is tight:** invoice 501 ($840) + rent ($2,400) = $3,240, which leaves **$160**. That is not enough for the $264 hoodie restock PO.
- **One blocker affects two tickets:** invoice 501 blocks Bulldog Print Co, which both ticket 101 (tee) and ticket 103 (hoodies) depend on.
- **No revenue is modeled:** a discount sale doesn't add cash, so cash is only spent, and every spend needs human approval.

## 2. MCP Server Tools

Server: `mcp_server/server.py` (FastMCP), working on `data/campus_customs_new.db`. Every tool uses `desk.date_today` as "today" and returns `found: false` (or `ok: false`) instead of inventing data when a lookup misses. The three Problem 3 tools below are read-only. The full list, including the tools added in Problem 5, is in the table after them.

### `check_stock(sku, size, qty_needed=None)`
- **Reads:** `inventory` (one row matched on `sku` + `size`)
- **Unlocks:** **Ticket 103** (Yale AI Club, 20× CC-HOOD-NAVY size M); also used for ticket 101
- **Why it's the right tool:** Ticket 103 asks for 20 size-M hoodies, and calling `check_stock("CC-HOOD-NAVY", "M", 20)` returns 8 on hand and a `shortfall` of 12. That exact number tells Inventory how big the restock order must be and tells the Boss the discount can't be approved for all 20 units today. (For ticket 101, the same call on `CC-TEE-WHITE` / `S` returns 0 on hand, which confirms the customer's tee is out of stock.)

### `check_vendor_status(vendor_id=None)`
- **Reads:** `vendors`, `invoices`, `desk`
- **Unlocks:** **Ticket 101** (Tauhid Zaman, 1× CC-TEE-WHITE size S, linked to `invoice_id` 501)
- **Why it's the right tool:** The tee is at 0, so the only path is a reprint from Bulldog Print Co. This tool shows that vendor still has invoice 501 ($840, 3 days overdue as of 2026-08-31) open, so `can_ship` is false. That makes paying invoice 501 the step that unlocks ticket 101, and once it's paid the 5 `lead_days` give the customer an arrival date. (The same blocker also stops the ticket 103 hoodie restock.)

### `get_lease(lease_id)`
- **Reads:** `leases`, `desk`
- **Unlocks:** **Ticket 102** (Elm City Properties rent notice, `lease_id` 1)
- **Why it's the right tool:** Ticket 102 is only an email saying "rent due in 2 days". This tool checks that claim against the lease on file ($2,400 to Elm City Properties for the Chapel Street shop, due 2026-09-02, `days_until_due` = 2, not overdue). That gives Facilities and Accounting the verified amount and deadline before anyone requests payment approval.

### Full tool list (after Problem 5)

Tools marked **write** change the working database. The backend signs every write with the calling agent's name (the model can't choose it), so an agent can't sign as someone else.

| Tool | Tables | Type | Used by | What it's for |
|---|---|---|---|---|
| `check_stock` | `inventory` | read | Inventory, Customer Service | Units on hand and shortfall for one SKU + size |
| `check_vendor_status` | `vendors`, `invoices`, `desk` | read | Inventory, Accounting, Customer Service | Lead days, open invoices, `can_ship` |
| `get_lease` | `leases`, `desk` | read | Facilities | Rent, landlord, due date, days until due |
| `list_tickets` | `tickets`, `desk` | read | Boss | The open board |
| `get_ticket` | `tickets`, `inventory`, `invoices`, `leases`, `payment_requests`, `purchase_orders`, `message_drafts` | read | all five | One ticket, its linked records, and work already done on it (prevents duplicates) |
| `quote_discount` | `pricing` | read | Accounting, Customer Service | Discounted price, margin %, and the largest discount that keeps the 40% floor (ticket 103) |
| `get_cash_position` | `cash_accounts`, `payment_requests`, `invoices`, `leases`, `desk` | read | Boss, Accounting, Facilities | Balance, pending approvals, balance after pending, bills due in 30 days |
| `list_payment_requests` | `payment_requests`, `cash_accounts` | read | Boss, Accounting, Customer Service | What's waiting on a human, and what was approved or denied |
| `list_purchase_orders` | `purchase_orders`, `vendors`, `payment_requests` | read | no agent (backend API, Problem 7) | Draft and ordered POs with vendor name and any payment request, for the dashboard's Approve button |
| `update_ticket` | `tickets`, `desk` | **write** | all five | Set status and append a signed, dated note |
| `create_purchase_order` | `purchase_orders`, `vendors`, `inventory`, `pricing`, `invoices` | **write** (draft) | Inventory | Draft a restock PO at unit cost (ticket 103: 12 × $22 = $264). Spends nothing. |
| `draft_customer_message` | `message_drafts`, `tickets` | **write** (draft) | Customer Service | Save a reply for a human to send. Nothing is sent. |
| `request_payment` | `payment_requests`, `invoices`, `leases`, `purchase_orders`, `cash_accounts` | **write** (request only) | Accounting | Ask a human to approve paying an invoice, rent, or a PO. The amount comes from the database, never from the agent. |
| `approve_payment` | `payment_requests`, `payments`, `cash_accounts`, `invoices`, `leases`, `purchase_orders`, `vendors`, `desk` | **write, HUMAN ONLY** | no agent (`python -m backend.approve`) | The only tool that moves money: writes `payments` with the approver's name, lowers cash, then marks the invoice paid, moves `next_due` forward a month, or orders the PO with an ETA. Refuses if cash would go negative or the vendor is still blocked. |
| `deny_payment` | `payment_requests` | **write, HUMAN ONLY** | no agent | Deny a request with a note. No money moves. |

**Tables the server adds** (created on first use, in the working copy only; the original DB is untouched):
- `payment_requests`: an agent asks, a human decides (`pending` → `approved` or `denied`, with `decided_by`)
- `purchase_orders`: restock drafts (`draft` → `ordered` with an `eta` after approval)
- `message_drafts`: outgoing messages waiting for a human to send

## 3. Agent Team (PydanticAI)

All five agents use **`gpt-6-luna`** through Portkey (`PORTKEY_API_KEY` from the class `.env`). Code lives in `backend/`.

- **Responses API:** the model is `OpenAIResponsesModel`, because `gpt-6-luna` only allows function tools on `/v1/responses` (Chat Completions returns a 400).
- **Fallback key:** set `LLM_GATEWAY=openai` to call OpenAI directly with `OPENAI_API_KEY` when the Portkey key is out of budget. The model, prompts, tools, and limits are identical, and each `session_start` entry in the audit trail records which gateway was used. The live run on 2026-10-14 used `openai` because the Portkey key had hit its usage limit.

| Agent | Role file | Prompt | Output type | MCP tools | Owns |
|---|---|---|---|---|---|
| **Boss** | `backend/agents/boss.py` | `backend/prompts/boss.md` | `BossReport` | `list_tickets`, `get_ticket`, `get_cash_position`, `list_payment_requests`, `update_ticket` | Routing, cross-ticket trade-offs, the approval queue for the human |
| **Inventory** | `backend/agents/inventory.py` | `backend/prompts/inventory.md` | `SpecialistReport` | `get_ticket`, `check_stock`, `check_vendor_status`, `create_purchase_order`, `update_ticket` | Stock, shortfalls, vendor choice, lead times, PO drafts |
| **Accounting** | `backend/agents/accounting.py` | `backend/prompts/accounting.md` | `SpecialistReport` | `get_ticket`, `get_cash_position`, `check_vendor_status`, `quote_discount`, `request_payment`, `list_payment_requests`, `update_ticket` | Cash, margins, payment requests |
| **Facilities** | `backend/agents/facilities.py` | `backend/prompts/facilities.md` | `SpecialistReport` | `get_ticket`, `get_lease`, `get_cash_position`, `update_ticket` | Verifying rent and lease claims |
| **Customer Service** | `backend/agents/customer_service.py` | `backend/prompts/customer_service.md` | `SpecialistReport` | `get_ticket`, `check_stock`, `check_vendor_status`, `quote_discount`, `list_payment_requests`, `draft_customer_message`, `update_ticket` | Drafting replies (never sends) |

Other backend files:
- `backend/models.py`: `SpecialistReport`, `BossReport`, `TicketDecision`, `ApprovalItem`, `Fact`, `DelegationResult`, `TeamDeps`
- `backend/team.py`: builds the agents, the `delegate` tool, and the audited agent loop
- `backend/mcp_tools.py`: one shared stdio connection to the MCP server, filtered per role
- `backend/audit.py`: the append-only `output/audit_trail.json`
- `backend/config.py`: model, Portkey client, token and loop limits
- `backend/run_team.py`: `python -m backend.run_team` starts a session with the Boss
- `backend/approve.py`: the human approval desk (`list`, `approve`, `deny`)

### Connectivity (delegation)

Every agent has a `delegate(to, task)` tool that can call **any** other agent, so the team is fully connected: Boss → specialist, specialist → specialist (for example Facilities → Accounting once the lease checks out), and specialist → Boss. A delegated agent starts fresh with only the task text, so the task must carry the facts it needs. `delegate` returns the teammate's typed report.

Loop guards, enforced in code and not just in the prompts:
- No delegating to yourself, or to any agent already in the current chain (blocks A → B → A).
- Chain length of at most 3 (for example boss → inventory → accounting).
- At most 12 delegations per session.

### Agent loop and audit trail

Each agent runs PydanticAI's loop with `agent.iter()`: prompt → model response with tool calls → tool results → … → typed output. `backend/team.py` appends one entry to `output/audit_trail.json` for **every step**:

| Field | Meaning |
|---|---|
| `ts`, `session_id`, `run_id`, `step_no` | When, which team session, which agent run, and the order |
| `agent`, `chain` | Who acted and how they were reached (e.g. `boss/inventory`) |
| `step` | `user_prompt`, `model_response`, `model_request`, `end`, `delegate`, `error`, `session_start`/`session_end`, and the human's `payment_approve`/`payment_deny` |
| `tool_calls` | Tool name and arguments the model chose |
| `tool_results` | What each tool returned (clipped to 4,000 chars), plus any retries or errors |
| `text`, `output` | Model text and the final typed report |
| `response_tokens`, `session_usage` | Tokens for this response, plus running requests, tool calls, and tokens for the session |
| `allowed`, `blocked_reason` | For delegations, whether the guard let it through |

The file is a JSON array. Each step reads it, appends, and atomically replaces it. It is never cleared between runs, and an unreadable file is renamed aside rather than overwritten.

## 4. Backend API Routes (FastAPI)

`backend/main.py`. Start it from `backend/` with `uvicorn main:app --reload --port 8000` → `http://localhost:8000` (interactive docs at `/docs`). Every route reads and writes shop data through the MCP server.

- `GET /api/tickets` — all three tickets with their status, `state` (`resolved` once the team finished a run on it since the last reset, else `open`), and `last_run`.
- `GET /api/tickets/{id}` — one ticket with its linked stock/invoice/lease and the work agents have done on it.
- `POST /api/tickets/{id}/run` — starts the agent team on that ticket in the background; returns a `session_id` at once (409 if a run is already going).
- `GET /api/runs/{session_id}` — whether that run is `running`, `done`, or `failed`, plus the Boss's report when done.
- `GET /api/events?limit=50&session_id=…&agent=…` — recent agent events from the audit trail: who acted, what they said, which tools they called, and delegations.
- `GET /api/payments?status=pending` — payment requests the agents prepared, waiting on a human.
- `POST /api/payments/{request_id}/approve` `{"approved_by": "Jun Kim"}` — human approves: writes `payments`, lowers checking, marks the bill paid (refused if cash would go negative).
- `POST /api/payments/{request_id}/deny` `{"denied_by": "…", "note": "…"}` — human denies; no money moves.
- `GET /api/purchase-orders` — purchase orders the agents drafted, with vendor and any payment request.
- `POST /api/purchase-orders/{po_id}/approve` `{"approved_by": "Jun Kim"}` — human approves a purchase: pays it and places the order with an ETA (refused while the vendor has an open invoice).
- `GET /api/cash` — current checking balance from `cash_accounts`, plus pending total and balance after pending.
- `POST /api/reset` — copies `data/campus_customs.db` over the working copy for a fresh run (the audit trail is kept).
- `GET /api/health` — server is up, which model and gateway it uses, and any run in progress.

Only the four approve/deny routes can move money, and only with a human's name. Agents never call them.

CORS allows the Vite dashboard origin (`http(s)://localhost:5173`, plus other localhost ports). The React desk is in `frontend/` (start it with `npm run dev`), and its design is described in `output/design.md`.

## 5. Dashboard (React + Vite + TypeScript)

`frontend/`, started with `npm run dev` → `http://localhost:5173`. It calls the API at `http://localhost:8000` (`VITE_API_URL` overrides). The full design rationale is in `output/design.md`.

| Zone | What it shows | Routes it uses |
|---|---|---|
| **The spike** (left) | The three tickets as paper stubs. A pink RESOLVED stamp appears when the team finishes a run, with "N to sign" or "signed off" underneath. | `GET /api/tickets` |
| **Ticket hero** (top center) | The selected ticket and a **Send in the team** button with a live run clock. `#101` in the URL opens that ticket. | `GET /api/tickets/{id}`, `POST /api/tickets/{id}/run`, `GET /api/runs/{id}` |
| **The floor** (center) | Five agent stations, each with its own color, glyph, and voice. Live speech bubbles in plain English, rings for idle / thinking / working / waiting / done, the MCP tools used, and glowing wires along each delegation. | `GET /api/events?session_id=…` (every 1.2 s while live) |
| **Debrief** | One card per agent that worked the ticket, from its final typed report: what it did, plus a "Needs a human" box. | `GET /api/events` (the `end` steps) |
| **Live wire** | A timestamped feed of every move: tool calls, hand-offs, blocked hand-offs, reports. | `GET /api/events` |
| **The till** (right) | An LED checking balance that rolls down and flashes when money leaves, the pending total, cash left if everything is signed, and a paper receipt of every payment with who signed it. | `GET /api/cash`, `GET /api/payments?status=approved` |
| **Signature tray** | One slip per pending payment request (sorted by the Boss's priority) and per draft PO, with **Approve & pay**, **Approve purchase**, and **Deny**. Buttons stay disabled until "Signing as" has a name. | `GET /api/payments`, `GET /api/purchase-orders`, the approve/deny routes |
| **Top bar** | Shop date, backend status, model, the "Signing as" name, and **New shift** (reset, with confirmation). | `GET /api/health`, `POST /api/reset` |

## 6. Safety Rules

### Guardrails for real customers and real money

1. **A human approves every dollar.** Agents can only `request_payment`. `approve_payment` and `deny_payment` are hidden from every agent's tool list *and* blocked again at call time. Only `backend/approve.py`, run by a person, can call them. Each payment row records the human's name, and agent names are rejected as approvers.
2. **Amounts come from the books, not the model.** `request_payment` reads the amount from the invoice, lease, or PO, so an agent can't type a different number. A second pending request for the same bill is refused.
3. **Cash can't go negative.** Approval refuses any payment larger than the balance, and a request warns when all pending requests together would overdraw.
4. **No paying a blocked vendor's PO.** A purchase order can't be approved while that vendor still has an open invoice.
5. **Nothing reaches a customer automatically.** Customer Service only saves drafts, and a person reviews and sends them. The prompts forbid sharing internal details (unpaid bills, cash, costs, margins).
6. **Verify outside claims.** Rent notices and other outside messages are checked against the lease on file before anyone asks for payment. A mismatch goes to a human, since it could be a billing error or a scam.
7. **Least privilege.** Each agent sees only the MCP tools its role needs. All shop data goes through the MCP server, and agents have no direct database access.
8. **Signed changes and a full trail.** The backend signs every write with the real agent name, and every step goes into the append-only audit trail.
9. **Margin floor.** `quote_discount` flags any discount below a 40% gross margin, and the prompts say it must not be offered.
10. **No invented facts.** The prompts require every number to come from a tool result, and tools return `found: false` instead of guessing.
11. **Work on a copy.** Agents only touch `data/campus_customs_new.db`, and the original is the reset point.

### Rules the API and dashboard add

12. **A named person signs every payment.** The approve routes require `approved_by`, and the dashboard keeps its Approve buttons disabled until "Signing as" has a name. That name is written into `payments.approved_by` and the audit trail.
13. **Approve in the Boss's order.** The tray sorts slips by the Boss's priority. Testing showed why it matters: approving a $264 PO before rent left too little for rent, and the API refused the rent rather than overdraw. Refusals show up as toasts.
14. **One agent run at a time.** A second run while one is going gets a 409, so two teams can't spend the same cash at once. Reset is also blocked mid-run and asks for confirmation.
15. **Only local pages can call the API.** CORS allows the Vite origin (`localhost:5173`) and other localhost ports, nothing on the internet.
16. **The audit trail is never wiped.** Reset only copies the database. It logs a `database_reset` entry, and the board uses that marker to know which runs belong to the current shift.

### Limits that keep token use in check

| Limit | Value | Where |
|---|---|---|
| Model requests per session (all agents combined) | 60 | `UsageLimits.request_limit` |
| Tool calls per session | 120 | `UsageLimits.tool_calls_limit` |
| Total tokens per session | 300,000 | `UsageLimits.total_tokens_limit` |
| Max output tokens per model call | 4,000 | `ModelSettings.max_tokens` |
| Model call timeout | 90 s, 1 retry | `ModelSettings.timeout`, OpenAI client |
| Delegations per session | 12 | `MAX_DELEGATIONS` |
| Delegation chain length | 3 | `MAX_DELEGATION_DEPTH` |
| Output-validation retries per agent | 2 | `Agent(retries=2)` |

The budget is shared: delegated agents reuse the Boss's usage counter, so the caps cover the whole team, not each agent separately. Delegated agents also start with a short, fresh context (just the task), so long histories aren't re-sent. Every agent uses only `gpt-6-luna`.

## 7. Full Run (Problem 9)

The database was reset through `POST /api/reset`, then tickets 101 → 102 → 103 were run from the dashboard. A human (Jun Kim) signed approvals after each ticket's run, following the Boss's approval queue. Every step was appended to `output/audit_trail.json`.

| Ticket | Session | Delegations | Human approvals | Cash after |
|---|---|---|---|---|
| start | | | | **$3,400.00** |
| 101 Bulldog tee | `f6037c171044` | boss → inventory, inventory → accounting, boss → customer_service | invoice 501 −$840.00; PO #1 (1 tee) −$8.00 | $2,552.00 |
| 102 Rent due | `49503de97534` | boss → facilities, boss → accounting | rent, lease 1, −$2,400.00 (next_due → 2026-10-02) | $152.00 |
| 103 Bulk hoodies | `1700e3c34fd6` | boss → inventory, boss → accounting, boss → customer_service | none: PO #2 ($264) left unsigned, $112 short | **$152.00** |

Ending balance $152.00 = `cash_accounts.balance` in `data/campus_customs_new.db` ($3,400 − $840 − $8 − $2,400). Results: `output/resolved_tickets.json`, `output/resolved_board.html` (board screenshots), and the Actual and Cash tabs of `output/desk_tickets.html`.
