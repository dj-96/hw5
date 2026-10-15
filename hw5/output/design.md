# The Desk: Dashboard Design

The Campus Customs dashboard (`frontend/`, React + Vite + TypeScript) is designed as **a real desk at a small shop after hours**, lit like a stage. It's black lacquer and hot pink, in the Blackpink-inspired style we use for this class. The goal: someone could sit here for a whole shift, see at a glance what the agents are doing, and feel in control of the money.

## Run it

```
# terminal 1 (from backend/)
uvicorn main:app --reload --port 8000

# terminal 2 (from frontend/)
npm install      # first time only
npm run dev      # opens http://localhost:5173
```

The page calls the backend at `http://localhost:8000` (set in `frontend/src/api.ts`, overridable with `VITE_API_URL` in `frontend/.env.local`). uvicorn serves plain **http**, not https, unless you give it a certificate, so the page uses http. The backend's CORS settings allow the Vite origin (`http(s)://localhost:5173`, plus any other localhost port Vite picks if 5173 is taken).

## Layout: three zones, like a real counter

| Zone | Where | What it's for |
|---|---|---|
| **The spike** | Left rail | Tickets as paper stubs on a spike, the way a diner or print shop keeps orders. |
| **The floor** | Center | A stage where the five agents stand. The ticket you picked sits above it, and the debrief and live feed below. |
| **The till** | Right column | The cash register and the signature tray. Money lives on its own side of the desk, separate from the agents. |

Why: a manager's eye goes left to right through the job: **what's asked → who's working on it → what it costs**. Putting money in its own column means you never confuse "an agent suggested paying" with "money moved."

The **top bar** holds the shop date (the database's "today", not the real date), a live/offline light, the model in use, a **"Signing as"** name field, and **"New shift"** (reset).

## Tickets: stubs on a spike

- Each ticket is a dark paper stub with a **perforated left edge**, a huge display-font number (`#101`), an emoji for its type (👕 order, 🏠 rent, 🏷️ price override), the subject, and who it's from.
- The selected stub slides right and glows pink. The ticket being worked **pulses** with a "Team working" pill.
- **Resolved tickets get a rubber stamp.** When a run finishes, a pink **RESOLVED** stamp slams onto the stub (it scales down from 2.4× with a little bounce, like a hand stamp), and the stub dims slightly, like paperwork that's done. Its pill then says either **"Resolved · 2 to sign"** or **"Resolved · signed off"**, so you know whether the human part is finished too.
- Why: "resolved" should feel like a physical, satisfying moment, and the stamp metaphor fits a shop counter. The "to sign" count keeps a resolved ticket from hiding money that's still waiting on you.

## Agents: five people on a stage, each with a different voice

The floor is a stage: pink spotlight from above, a perspective grid floor, the **Boss up front** (bigger avatar, crown) and the four specialists in a row below. When someone delegates, a **glowing wire** draws between their stations, colored by whoever is receiving the work, with dashes flowing in the direction of the hand-off. Specialist-to-specialist hand-offs arc above the row so you can see the team talking to *itself*, not just to the Boss. Blocked hand-offs show as a red dotted wire.

Each agent reads differently in **four ways**, so you can tell them apart even when they're tiny or scrolling past:

| Agent | Color | Glyph | Voice in bubbles and feed |
|---|---|---|---|
| Boss | hot pink | ♛ | **UPPERCASE, bold**: it gives the orders |
| Inventory | lilac | ▦ | plain and factual |
| Accounting | champagne gold | $ | `monospace`, like a ledger |
| Facilities | cyan | ⌂ | plain and factual |
| Customer Service | coral | ✉ | *italic*, softer, like handwriting |

**What each station shows while the ticket runs:**
- A **speech bubble** with what the agent is doing right now, in plain English rather than function names ("Counting CC-HOOD-NAVY · M (needs 20)", "Asking a human to sign for invoice #501", "Waiting on Accounting").
- The **avatar's ring** shows state at a glance: grey and asleep when **idle**, slowly breathing when **thinking**, a spinning ring when **working** (calling tools), a slow dotted ring when **waiting** on a teammate, and a check badge when **done**.
- A count of tool calls and chips naming the MCP tools that agent has used.

Under the floor, the **Live wire** is a running transcript (it shows "● REC" while live): a timestamp from the start of the run, who acted, a tag (*does / hands off / reports / blocked*), what they did, and the exact tool names. It scrolls itself during a run without moving the page.

Why: the brief was "show each agent and what they are saying / doing." A list of log lines would technically do that, but a stage lets you *watch the shape* of the work: who the Boss went to first, whether Inventory looped in Accounting, who never got called. That's exactly what you compare against the plan in `desk_tickets.html`.

## Debrief: what each agent did

When a run ends, a **Debrief** panel rises in under the floor with one card per agent that worked the ticket, built from each agent's final typed report:
- **Boss** (full width): the decision, the reasoning, and the cash note.
- **Each specialist**: their summary and the concrete actions they took (requests, POs, drafts, ticket notes).
- A pink **"Needs a human"** box on any card that left something for you.

Agents that weren't called don't get a card. A short debrief means the team was efficient.

## Money: a till and a signature tray

**The till** looks like a cash register's LED display: pink glowing digits, faint scanlines, tabular numbers. Under it:
- **"Waiting on signatures"**, the total of pending requests.
- **"Left if all signed"**, which turns gold when it gets low and red if it would go negative. On ticket 103, that's how you see the $264 hoodie restock doesn't fit.
- **A paper receipt** (light paper with a torn zigzag edge) that prints a line for every payment: what it was, the amount, and **who signed it**.

When a payment is approved, **the till visibly drops**: the digits roll down to the new balance, the display flashes, and the amount that left (e.g. **−$840.00**) floats up and fades. You can *feel* money leaving, which is the right reaction for a real business.

**The signature tray** ("Needs your signature") holds one slip per pending payment request and per drafted purchase order:
- the kind (vendor invoice / rent / purchase order), a big amount, the ticket tag, and the agent's reason
- who prepared it, in that agent's color
- a **"Boss says #1"** badge when the Boss ranked it in its approval queue, and the slips are sorted in the Boss's order (pay the vendor blocker first, then rent)
- **Approve & pay** / **Approve purchase**, and **Deny**

Approving **slams a PAID / ORDERED stamp** onto the slip, prints a receipt line, and drops the till. Buttons stay disabled until you type your name in **"Signing as"**, because every payment in this shop is signed by a named person, and that name is what's written into the `payments` table. If the backend refuses (not enough cash, vendor still blocked), the reason appears as a toast instead of failing silently.

Why: in this homework agents can only *prepare* money moves. The tray makes that boundary visible. The agents fill it, and only your signature empties it.

## Small touches that make it feel special

- **Stage lighting and film grain** on a near-black background, so it reads as an evening shift at a lit counter rather than a spreadsheet.
- **"Send in the team"** is a big glossy pink pill with a moving shine. While a run is going it becomes "Team on it" with a running clock, and afterwards it says how long the last run took.
- **The till shows the exact balance the moment the page loads** and only rolls when money actually moves, so a screenshot never catches an in-between number.
- **Toasts** in plain language: "The team is on ticket #101", "$840 invoice approved by Jun Kim. Checking is now $2,560."
- **"New shift"** instead of "reset database": resetting is framed as clocking in to a fresh day. It still asks for confirmation.
- **Your name is remembered** (browser local storage), so the desk knows who's sitting at it.
- **It stays usable everywhere.** On narrow screens the stage turns into a grid of agent cards and the spike scrolls sideways. Keyboard focus rings are pink and visible, and everything calms down if your system asks for reduced motion.

## How "resolved" is decided

A ticket shows **Resolved** when the agent team **finished a run on it** since the last reset (the backend reads this from the audit trail, so it survives page reloads and server restarts), or when its database status is `resolved` or `declined`. The database status the agents left (for example `waiting_on_approval`) is still shown through the "to sign / signed off" pill.

## Files

- `src/App.tsx`: state, polling (every 4 s; every 1.2 s while a run is live), dispatch, approvals, reset
- `src/floor.ts`: turns audit events into station states, wires, the feed, and the debrief
- `src/agents.ts`: each agent's color, glyph, and voice, plus plain-English verbs for every MCP tool
- `src/components/`: `TicketRail`, `TicketHero`, `AgentFloor`, `LiveWire`, `DebriefPanel`, `Till`, `SignatureTray`, `Header`, `Toasts`
- `src/styles.css`: the whole look (fonts: Anton for display, Space Grotesk for UI, JetBrains Mono for numbers)
