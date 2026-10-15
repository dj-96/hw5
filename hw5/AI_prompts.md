# AI Prompts Log

## Problem 1: Vibe Coder Prompts

### Prompt I typed

"Problem 1: vibe coder prompts. Create 'AI_prompts.md' at the start of the assignment and keep it updated as you work. This file is the log of what I typed to my vibe coder. Describe each problem to the vibe coder in my own words. Put one section for each problem. Each section must include the problem number and title, at least one prompt I typed (in my own words as much as possible), and one follow-up prompt if I needed it, plus one sentence on what was lacking after the first."

### Follow-up prompt

No follow-up prompt was needed. The instructions were specific enough to create the log right away.

### What was lacking after the first prompt

Nothing was lacking; the first prompt clearly described the file name, the per-problem structure, and the required fields.

## Problem 2: Study the Campus Customs Database

### Prompt I typed

"Problem 2: study the Campus Customs database. Open 'data/campus_customs.db' and look through every table and its fields. Copy the original file to 'data/campus_customs_new.db' — later problems update that working copy. Study the three open tickets so you see how they link to other tables. Start 'output/harness.md'. For each table, list the fields and one short line on why that table matters for the agents. You will keep growing this harness file in later problems."

### Follow-up prompt

No follow-up prompt was needed. The prompt named the file to copy, the output file, and what each table entry should contain.

### What was lacking after the first prompt

Nothing essential was lacking; the only gap was that the unzipped data landed in a nested 'data/data/' folder, so the vibe coder copied the database up into 'data/' to match the paths in the instructions.

## Problem 3: Build the MCP Server

### Prompt I typed

"Problem 3: build the MCP server. Write an MCP server in 'mcp_server/' using FastMCP that talks to 'data/campus_customs_new.db'. You don't need to connect or run it yet. Every agent will use the tools in this server, and we'll add more later — for now write three tools you know we'll need for the tickets in the database, with clear names. Never invent data; only use what's in the database. In 'output/harness.md', list each tool with the table it reads, which ticket it unlocks (101, 102, or 103), and one sentence on why it's the right tool for that ticket — tie the tool to the ticket, not vague lines like 'reads inventory'. Also add a short 'mcp_server/README.md' explaining what the server is for, which database it uses, and its three tools."

### Follow-up prompt

No follow-up prompt was needed. The prompt specified the folder, framework, database, number of tools, and exactly what to document for each tool.

### What was lacking after the first prompt

The prompt didn't say which FastMCP package to use; the newest official MCP SDK (v2) renamed its built-in FastMCP, so the vibe coder used the standalone 'fastmcp' package, which is also what the agent library connects with later.

## Problem 4: Add the MCP Server to the Vibe Coder and Test Each Tool

### Prompt I typed

"Problem 4: add the MCP server to the vibe coder and test each tool. Add my MCP server to this project so you can call the tools, and save the connection JSON in '.mcp.json' at the project root. Once you're connected, test each of the three MCP tools and save the evidence in 'output/mcp_smoke.json'. For every tool include the prompt I asked you, the tool name, and the tool output — the output must match the values in 'data/campus_customs_new.db'."

### Follow-up prompt

"You need to build the file named something like smoke.json?"

### What was lacking after the first prompt

The vibe coder saved '.mcp.json' but the server only connected after a restart, so the tool tests and 'output/mcp_smoke.json' weren't written until I followed up.

## Problem 5: Build the Agent Team and Grow the MCP Tools

### Prompt I typed

"Problem 5: build the agent team and grow the MCP tools. Build the agentic team for Campus Customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity. Put the agent prompts in 'backend/prompts/', one file per agent. Put data types in 'backend/models.py', and the agent files under 'backend/'. Use my PORTKEY_API_KEY and only 'gpt-6-luna' for every agent. Write each prompt with the shop rules that agent needs; detailed prompts that cover the agent's whole scope are better than short generic ones. Add any tools the agents need to the MCP server so they can work the open tickets. Shop facts come from the MCP server over 'data/campus_customs_new.db'; don't build a second tools layer that bypasses MCP. Wire the agents so they append to 'output/audit_trail.json' as they run, one record per agent-loop step with enough to audit later, and never wipe it. In 'output/harness.md', list each agent and each MCP tool with the table it uses, and add a short safety section on guardrails for real customers and real money, plus limits that keep token use in check. Update 'mcp_server/README.md' so the tool list matches."

### Follow-up prompt

"Maybe I'm using the other one. That one ran out of tokens, so I'm using this OPENAI_API_KEY instead. Why don't you run with this? Will the result be different?"

### What was lacking after the first prompt

The prompt didn't say how payments get approved, so the vibe coder had to design that: agents can only request a payment, and a separate human-only approval desk is the only thing that moves cash. Also, the Portkey key had run out ("Usage Limit Exceeded"), so the first live run failed. After the follow-up, the vibe coder added a switch to use OPENAI_API_KEY with the same gpt-6-luna model. It then had to fix two things before the team ran end to end: gpt-6-luna needs the Responses API for tool calls, and OneDrive briefly locked the audit file mid-run.

## Problem 6: Plan the Three Tickets

### Prompt I typed

"Problem 6: plan the three tickets. Before you wire the backend, write down what you expect the team to do on each open ticket. Build 'output/desk_tickets.html', a page I can double-click with one tab per ticket (101, 102, and 103), plus empty Cash and Reflection tabs for later problems with a short 'coming later' note. On each ticket tab, fill in an Expected section only and leave room for an Actual section to fill after running the agents. For each ticket's Expected section, write who the Boss should call first and why, all the agent delegations I expect (not 'Boss calls everyone'), and which MCP tools I expect the run to use. Plans that send every specialist on every ticket score low; I'll compare this plan to what actually happens."

### Follow-up prompt

No follow-up prompt was needed. The prompt named the file, the tabs, and the three things each Expected section must cover.

### What was lacking after the first prompt

The prompt didn't say how to handle invoice 501, which blocks both ticket 101 and ticket 103. The plan assumes Accounting requests it once on ticket 101 and reuses that request on ticket 103, which is something to check against the Actual run.

## Problem 7: Backend Routes

### Prompt I typed

"Problem 7: backend routes. My React frontend dashboard (the next problem) needs a backend it can call. In 'backend/main.py', use FastAPI and add routes that return the three tickets and whether each is open or resolved; take a ticket id and run the agent team on that ticket; return recent agent events (what each agent said and which tools they used) so the board can refresh; approve a payment or purchase after a human clicks approve (agents only prepare the payment, this route is what actually changes cash); return the current checking balance from 'cash_accounts'; and reset the database to the original values for a fresh run. Start it from 'backend/' with 'uvicorn main:app --reload --port 8000'. In 'output/harness.md', list each route in one line (URL and what it does)."

### Follow-up prompt

No follow-up prompt was needed. The prompt listed every route the dashboard needs and how to start the server.

### What was lacking after the first prompt

The prompt didn't say whether running the agents should block the request. A run takes about a minute, so the vibe coder made the run route return a session id at once and added a status route the dashboard can poll. It also noted that the server address is http://localhost:8000, not https.

## Problem 8: Agent Dashboard

### Prompt I typed

"Problem 8: agent dashboard. Build the frontend dashboard in 'frontend/' with React + Vite + TypeScript. The page should call the routes from Problem 7. At minimum the board should list all three tickets, let me pick one and start the agent team on it, show each agent and what they're saying or doing while the ticket runs, mark a ticket resolved when the run finishes, show a short summary of what each agent did on that ticket, let a human approve a payment or purchase when asked, and show the checking balance (it should drop after an approved payment). Make it look good and be creative with the layout and feel; this is a real desk people would want to sit at. Point the frontend at the backend on localhost:8000, allow the Vite page origin (localhost:5173) on the backend, and start the board with npm run dev. Write 'output/design.md' with what I chose for the look (layout, how agents read differently, how resolved tickets and cash show up) and why, including the creative choices that make it feel special."

### Follow-up prompt

No follow-up prompt was needed. The prompt listed every feature the board needs and where the design write-up goes.

### What was lacking after the first prompt

The prompt asked for https://localhost:8000, but uvicorn serves plain http, so the dashboard uses http://localhost:8000 (changeable with VITE_API_URL). It also didn't define "resolved". The agents leave tickets at 'waiting_on_approval', so the vibe coder treated a finished agent run as resolved and added a "to sign / signed off" label so pending money isn't hidden.

## Problem 9: Resolve the Tickets

### Prompt I typed

"Problem 9: resolve the tickets. Before a full run over the three tickets, reset the working database 'data/campus_customs_new.db' so you start clean, and note the starting checking balance. Then run all three tickets on the board (101, 102, 103) until each is resolved. In 'output/desk_tickets.html' from Problem 6, fill each ticket's Actual section from this run (which agents worked, what they delegated, which tools they used) and keep the Expected section to compare. On the Cash tab, itemize the money: the starting balance after the reset, how cash changed when each ticket resolved and why (which payment or purchase, dollar amount), and the ending balance, which must match 'cash_accounts' in the working database. Also save 'output/resolved_tickets.json' (for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals) and 'output/resolved_board.html' (a page I can double-click with a screenshot of my React board for each resolved ticket). Append real runs to 'output/audit_trail.json', and finish 'output/harness.md' so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules."

### Follow-up prompt

No follow-up prompt was needed. The prompt listed every file to produce and what the cash itemization must include.

### What was lacking after the first prompt

The prompt didn't say which payments the human should approve, so the vibe coder followed the Boss's approval queue: invoice 501 and the $8 tee PO on 101, then rent on 102. It left the $264 hoodie PO on 103 unsigned because only $152 was left. The first board screenshot also caught the till mid-animation ($2,548.99 instead of $2,552.00), so the till was changed to show the exact balance on load before the final screenshots were taken.

## Problem 10: Reflection

### Prompt I typed

"Problem 10: reflection. Open 'output/desk_tickets.html' and fill the Reflection tab, in my own voice and in detail: how I'd evaluate the agents' performance on each ticket and why; how Actual compared to my Expected plan for each ticket; what would have been simpler as one agent with tools, and why; three new problems Campus Customs might face that this team could solve with the tools I built; and three it couldn't, with the tools and agents I'd need. Tie every answer to this app and the three tickets I ran, using the ticket tabs and the Cash tab as evidence. Generic AI essays without Campus Customs details score low."

### Follow-up prompt

No follow-up prompt was needed. The prompt listed the five questions and said the answers must cite this run.

### What was lacking after the first prompt

The prompt didn't give a grading scale, so the vibe coder graded on correctness, safety, judgment, and cost, and pulled extra evidence from the audit trail that the earlier tabs didn't show: repeated get_ticket and get_cash_position reads, and agents overwriting each other's ticket status. It also noticed the page's in-page links didn't switch tabs, and fixed that.

## Problem 11: Submit to GitHub

### Prompt I typed

"Problem 11: submit to GitHub. Push my code to a public GitHub repository so graders can clone it, and put the repo URL in 'output/github_url.txt'. Don't push my real '.env'. Do include both database files under 'data/' (the original and the working copy) so graders can run the app easily. Follow the expected layout (AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/, mcp_server/, frontend/, backend/, output/). The README should explain copying the original DB to the working copy for a clean run, starting the MCP server, starting the FastAPI backend, starting the React board, and resetting the DB before a full three-ticket run."

### Follow-up prompt

"Just put those files in a single folder so that I can upload them to GitHub myself."

### What was lacking after the first prompt

The GitHub CLI wasn't installed and the Windows admin prompt for installing it was declined, so the vibe coder couldn't create the repo. Instead it built a clean 'hw5/' folder that follows .gitignore (no .env, .venv, node_modules, build output, or caches), checked that a copy runs on its own (MCP server, backend, and a fresh npm ci + build), and left 'output/github_url.txt' as a placeholder to fill in after I create the repo.
