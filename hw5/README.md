# Campus Customs: Multi-Agent Shop Desk (MGT 409 · Homework 5)

A five-agent team (Boss, Inventory, Accounting, Facilities, Customer Service) built with **PydanticAI** works the tickets at Campus Customs, a small Yale apparel shop. All shop data goes through one **FastMCP** server over a SQLite database. A **FastAPI** backend runs the agents and is the only place a human can approve a payment. A **React + Vite + TypeScript** dashboard ("The Desk") lets you pick a ticket, watch the agents work, and sign payments.

Agents can only *prepare* money moves (payment requests, draft purchase orders, draft messages). Cash changes only when a named human clicks **Approve** on the dashboard.

---

## 1. Setup (once)

Requires **Python 3.12+** and **Node 20+**.

```bash
# from the repo root
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
cd ..
```

Create your `.env` from the example and add a key (the real `.env` is git-ignored):

```bash
cp .env.example .env
# PORTKEY_API_KEY=...            class default (LLM_GATEWAY=portkey)
# or OPENAI_API_KEY=... and LLM_GATEWAY=openai
```

Every agent uses the `gpt-6-luna` model through the OpenAI Responses API.

## 2. The databases

| File | What it is |
|---|---|
| `data/campus_customs.db` | **Original.** Never modified. |
| `data/campus_customs_new.db` | **Working copy.** The MCP server, agents, and backend read and write only this file. As committed, it holds the end state of the graded full run (checking = $152.00). |

**For a clean run, copy the original over the working copy:**

```bash
# macOS/Linux/Git Bash
cp data/campus_customs.db data/campus_customs_new.db
# Windows PowerShell
Copy-Item data\campus_customs.db data\campus_customs_new.db -Force
```

With the backend running, `POST http://localhost:8000/api/reset` or the **↺ New shift** button on the dashboard does the same copy. The audit trail is never wiped, only appended to.

## 3. Start the MCP server

```bash
python mcp_server/server.py
```

This runs the `campus-customs` server on stdio, which you need for MCP clients like Claude Code (configured in `.mcp.json`, which expects the venv to be active). **The backend starts its own copy automatically**, so you don't need a separate terminal for it when using the dashboard. Its tools are listed in `mcp_server/README.md`.

## 4. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API runs at **http://localhost:8000**, with interactive docs at http://localhost:8000/docs. The routes are listed in `output/harness.md` §4.

## 5. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

This opens **http://localhost:5173**. The board calls the backend at `http://localhost:8000` (change it with `VITE_API_URL` in `frontend/.env.local`). The backend's CORS settings allow the Vite origin.

## 6. Full three-ticket run

1. **Reset the database first:** copy the original over the working copy (section 2), or click **↺ New shift**. Checking should read **$3,400.00**.
2. Type your name in **Signing as** (top right). Approve buttons stay disabled without it.
3. Pick **#101** on the left and click **Send in the team**. Watch the floor and the live feed. When the run finishes, the ticket gets a RESOLVED stamp and a debrief appears.
4. Sign the slips in **Needs your signature**, in the Boss's order ("Boss says #1"). The till drops with each payment.
5. Repeat for **#102** and **#103**.

The graded run's results: `output/desk_tickets.html` (plan vs. actual, cash ledger, reflection), `output/resolved_tickets.json`, `output/resolved_board.html` (board screenshots), and `output/audit_trail.json`. The run went $3,400.00 → $152.00: invoice 501 −$840, tee PO −$8, rent −$2,400; the hoodie PO was left unsigned.

**Without the dashboard:**

```bash
python -m backend.run_team                         # Boss works every open ticket
python -m backend.approve list                     # pending payment requests
python -m backend.approve approve 1 --by "Your Name"
```

## Layout

```
AI_prompts.md          prompts I gave the vibe coder, per problem
requirements.txt       Python dependencies
.env.example           copy to .env and add your key
.mcp.json              MCP server config for Claude Code
data/                  original + working-copy SQLite databases
mcp_server/            FastMCP server (server.py) + tool list (README.md)
backend/               FastAPI app (main.py), agents, data types (models.py), prompts/
  agents/              one file per role: boss, inventory, accounting, facilities, customer_service
  prompts/             one prompt per agent
frontend/              React + Vite + TypeScript dashboard
output/                harness, smoke test, plan/actual page, design notes, results, audit trail
```

## Safety, in short

- Agents never see `approve_payment` or `deny_payment`. Those tools are filtered out of every agent's tool list and blocked again at call time.
- Payment amounts always come from the database record (invoice, lease, or PO), never from the model.
- A payment that would overdraw checking, or a PO for a vendor with an open invoice, is refused.
- Customer messages are saved as drafts only. A person sends them.
- Each session has caps of 60 model requests, 120 tool calls, 300k tokens, and 12 delegations, with a maximum delegation chain of 3.

See `output/harness.md` for the full spec and `output/design.md` for the dashboard design.
