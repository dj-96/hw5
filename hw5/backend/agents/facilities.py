from ..models import SpecialistReport
from .base import RoleSpec

FACILITIES = RoleSpec(
    name="facilities",
    title="Facilities",
    prompt_file="facilities.md",
    description="The shop lease and landlord: verifies rent amounts and due dates against the lease on file.",
    tools=frozenset({"get_ticket", "get_lease", "get_cash_position", "update_ticket"}),
    output_type=SpecialistReport,
)
