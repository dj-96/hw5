from ..models import BossReport
from .base import RoleSpec

BOSS = RoleSpec(
    name="boss",
    title="Boss",
    prompt_file="boss.md",
    description="Shop manager. Routes tickets, weighs them against each other, and hands a human the approval plan.",
    tools=frozenset({"list_tickets", "get_ticket", "get_cash_position", "list_payment_requests", "update_ticket"}),
    output_type=BossReport,
)
