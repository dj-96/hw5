from ..models import SpecialistReport
from .base import RoleSpec

ACCOUNTING = RoleSpec(
    name="accounting",
    title="Accounting",
    prompt_file="accounting.md",
    description="Cash, unpaid invoices, discount margins, and payment requests for human approval.",
    tools=frozenset(
        {
            "get_ticket",
            "get_cash_position",
            "check_vendor_status",
            "quote_discount",
            "request_payment",
            "list_payment_requests",
            "update_ticket",
        }
    ),
    output_type=SpecialistReport,
)
