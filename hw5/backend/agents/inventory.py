from ..models import SpecialistReport
from .base import RoleSpec

INVENTORY = RoleSpec(
    name="inventory",
    title="Inventory",
    prompt_file="inventory.md",
    description="Stock on hand, shortfalls, which vendor restocks what, lead times, and draft purchase orders.",
    tools=frozenset({"get_ticket", "check_stock", "check_vendor_status", "create_purchase_order", "update_ticket"}),
    output_type=SpecialistReport,
)
