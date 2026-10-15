from ..models import SpecialistReport
from .base import RoleSpec

CUSTOMER_SERVICE = RoleSpec(
    name="customer_service",
    title="Customer Service",
    prompt_file="customer_service.md",
    description="Writes replies to customers and partners as drafts for a human to review and send.",
    tools=frozenset(
        {
            "get_ticket",
            "check_stock",
            "check_vendor_status",
            "quote_discount",
            "list_payment_requests",
            "draft_customer_message",
            "update_ticket",
        }
    ),
    output_type=SpecialistReport,
)
