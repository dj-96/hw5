"""Data types shared by the Campus Customs agent team.

Every agent returns a typed report instead of free text, so the Boss (and a
human reading the audit trail) can see exactly which facts came from which
MCP tool, what was changed in the database, and what still needs a person.
"""
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal[
    "open", "in_progress", "waiting_on_approval", "waiting_on_vendor", "resolved", "declined"
]


class Fact(BaseModel):
    """One fact, tied to the MCP tool that returned it."""

    tool: str = Field(description="MCP tool that returned this fact, e.g. 'check_stock'.")
    detail: str = Field(description="The fact in plain words, with the exact numbers the tool returned.")


class SpecialistReport(BaseModel):
    """What Inventory, Accounting, Facilities, or Customer Service hands back."""

    agent: AgentName
    ticket_ids: list[int] = Field(description="Tickets this report is about.")
    summary: str = Field(description="Two or three sentences: what you found and what you did.")
    facts: list[Fact] = Field(default_factory=list, description="Only facts returned by tools in this run.")
    actions_taken: list[str] = Field(
        default_factory=list,
        description="Database changes you made, with ids (e.g. 'payment request 1 for invoice 501').",
    )
    payment_request_ids: list[int] = Field(default_factory=list)
    purchase_order_ids: list[int] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list)
    needs_human: list[str] = Field(
        default_factory=list, description="Decisions or approvals only a person can make."
    )
    recommended_status: TicketStatus | None = None


class TicketDecision(BaseModel):
    """The Boss's call on one ticket."""

    ticket_id: int
    decision: str = Field(description="What the shop will do, in one or two sentences.")
    status: TicketStatus
    handled_by: list[AgentName] = Field(description="Agents that worked on this ticket.")
    rationale: str = Field(description="Why, citing the numbers the specialists reported.")
    human_actions: list[str] = Field(
        default_factory=list, description="What a person must approve, send, or decide next."
    )


class ApprovalItem(BaseModel):
    """A payment request waiting on a human."""

    request_id: int
    kind: Literal["invoice", "rent", "purchase_order"]
    amount: float
    why: str
    priority: int = Field(description="1 = approve first.")


class BossReport(BaseModel):
    """The Boss's final plan for the whole board."""

    tickets: list[TicketDecision]
    approval_queue: list[ApprovalItem] = Field(
        default_factory=list, description="Pending payment requests, in the order a human should review them."
    )
    cash_note: str = Field(description="Cash now, cash if the queue is approved, and any conflict between tickets.")
    open_risks: list[str] = Field(default_factory=list)


class DelegationResult(BaseModel):
    """What the `delegate` tool returns to the agent that asked."""

    to: AgentName
    ok: bool
    report: SpecialistReport | BossReport | None = None
    error: str | None = None


@dataclass
class TeamDeps:
    """Run-wide state passed to every agent (and every delegated agent).

    `chain` is the current delegation path, e.g. ['boss', 'inventory'], so the
    team can't loop (A -> B -> A) and can't nest deeper than the limit. Each
    delegated agent gets its own copy of `chain`, but `counters` is shared by
    the whole session so the delegation budget covers every agent.
    """

    session_id: str
    chain: list[str] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: {"delegations": 0, "steps": 0})
