"""Builds the five agents and runs the agent loop.

Connectivity: every agent has a `delegate(to, task)` tool that can hand work
to any other agent, so the team is fully connected (Boss -> specialist,
specialist -> specialist, specialist -> Boss). Three limits keep that from
running away:
  * no agent can delegate to itself or to anyone already in the current
    chain (blocks A -> B -> A loops),
  * the chain can be at most MAX_DELEGATION_DEPTH agents long,
  * the whole session has MAX_DELEGATIONS delegate calls and one shared
    UsageLimits budget (delegated runs reuse the caller's usage counter).

Every step of every agent loop is appended to output/audit_trail.json.
"""
import uuid
from dataclasses import replace
from functools import cache
from typing import Any

from pydantic_ai import Agent, RunContext, UsageLimitExceeded
from pydantic_ai.usage import RunUsage

from . import audit
from .agents import ROLES
from .config import (
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS,
    MODEL_NAME,
    llm_gateway,
    MODEL_SETTINGS,
    PROMPTS_DIR,
    USAGE_LIMITS,
    get_model,
)
from .mcp_tools import toolset_for
from .models import AgentName, DelegationResult, TeamDeps

TEAM_ROSTER = "\n".join(f"- `{r.name}` ({r.title}): {r.description}" for r in ROLES.values())


@cache
def get_agent(name: str) -> Agent[TeamDeps, Any]:
    role = ROLES[name]
    agent: Agent[TeamDeps, Any] = Agent(
        get_model(),
        name=role.name,
        instructions=(PROMPTS_DIR / role.prompt_file).read_text(encoding="utf-8"),
        deps_type=TeamDeps,
        output_type=role.output_type,
        toolsets=[toolset_for(role.tools)],
        model_settings=MODEL_SETTINGS,
        retries=2,
    )

    @agent.instructions
    def team_context(ctx: RunContext[TeamDeps]) -> str:
        left = MAX_DELEGATIONS - ctx.deps.counters["delegations"]
        return (
            f"You are `{role.name}`. Delegation chain so far: {' -> '.join(ctx.deps.chain)}. "
            f"Team delegations left this session: {left}. Max chain length: {MAX_DELEGATION_DEPTH}.\n"
            f"Teammates you can delegate to:\n{TEAM_ROSTER}"
        )

    @agent.tool
    async def delegate(ctx: RunContext[TeamDeps], to: AgentName, task: str) -> DelegationResult:
        """Hand a task to a teammate and wait for their report.

        Args:
            to: The teammate: boss, inventory, accounting, facilities, or customer_service.
            task: A self-contained task. Include the ticket id and any facts they need;
                they have not seen your conversation.
        """
        return await delegate_task(ctx, to, task)

    return agent


async def delegate_task(ctx: RunContext[TeamDeps], to: str, task: str) -> DelegationResult:
    deps = ctx.deps
    caller = deps.chain[-1]
    problem = None
    if to == caller:
        problem = "You can't delegate to yourself."
    elif to in deps.chain:
        problem = f"{to} is already working on this chain ({' -> '.join(deps.chain)}); answer them instead."
    elif len(deps.chain) >= MAX_DELEGATION_DEPTH:
        problem = f"Delegation chain is at the limit of {MAX_DELEGATION_DEPTH}; finish with what you have."
    elif deps.counters["delegations"] >= MAX_DELEGATIONS:
        problem = f"The session's {MAX_DELEGATIONS}-delegation budget is used up; finish with what you have."

    await audit.append(
        {
            "session_id": deps.session_id,
            "agent": caller,
            "chain": deps.chain,
            "step": "delegate",
            "to": to,
            "task": task,
            "allowed": problem is None,
            "blocked_reason": problem,
        }
    )
    if problem:
        return DelegationResult(to=to, ok=False, error=problem)

    deps.counters["delegations"] += 1
    child = replace(deps, chain=[*deps.chain, to])
    try:
        report = await run_agent(to, task, child, usage=ctx.usage)
    except UsageLimitExceeded as exc:
        return DelegationResult(to=to, ok=False, error=f"Token/request budget exhausted: {exc}")
    return DelegationResult(to=to, ok=True, report=report)


async def run_agent(name: str, prompt: str, deps: TeamDeps, *, usage: RunUsage | None = None) -> Any:
    """One agent loop: prompt -> (model -> tools)* -> typed output, audited step by step."""
    agent = get_agent(name)
    base = {"session_id": deps.session_id, "agent": name, "chain": deps.chain}
    try:
        async with agent.iter(prompt, deps=deps, usage=usage, usage_limits=USAGE_LIMITS) as run:
            async for node in run:
                deps.counters["steps"] += 1
                await audit.append(
                    {
                        **base,
                        "run_id": run.run_id,
                        "step_no": deps.counters["steps"],
                        **audit.describe_node(node),
                        "session_usage": audit.usage_dict(run.usage),
                    }
                )
            return run.result.output
    except Exception as exc:
        await audit.append({**base, "step": "error", "error": f"{type(exc).__name__}: {exc}"})
        raise


DEFAULT_TASK = (
    "Work every open ticket on the board. Route each to the right specialists, check how the "
    "tickets affect each other (cash and vendors), set each ticket's status, and return the plan "
    "with the approval queue a human should review."
)


def ticket_task(ticket_id: int) -> str:
    return (
        f"Work ticket {ticket_id} only. Route it to the specialists it actually needs, check how it "
        "interacts with other tickets' pending payments and cash, set its status, and return the plan "
        "with any approvals a human should review. Leave other tickets alone."
    )


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


async def run_team(
    task: str = DEFAULT_TASK, *, session_id: str | None = None, ticket_id: int | None = None
) -> Any:
    """Start a session with the Boss. Returns the Boss's BossReport.

    `ticket_id` is recorded on the session's start/end entries so the
    dashboard can tell which ticket a run was for and whether it finished.
    """
    deps = TeamDeps(session_id=session_id or new_session_id(), chain=["boss"])
    await audit.append(
        {
            "session_id": deps.session_id,
            "agent": "system",
            "step": "session_start",
            "model": MODEL_NAME,
            "gateway": llm_gateway(),
            "ticket_id": ticket_id,
            "task": task,
        }
    )
    ok = False
    try:
        report = await run_agent("boss", task, deps)
        ok = True
    finally:
        await audit.append(
            {
                "session_id": deps.session_id,
                "agent": "system",
                "step": "session_end",
                "ticket_id": ticket_id,
                "ok": ok,
                "delegations": deps.counters["delegations"],
                "steps": deps.counters["steps"],
            }
        )
    return report
