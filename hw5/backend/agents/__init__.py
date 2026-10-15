"""The five Campus Customs roles. Each file defines one role's prompt, tools, and output."""
from .accounting import ACCOUNTING
from .base import RoleSpec
from .boss import BOSS
from .customer_service import CUSTOMER_SERVICE
from .facilities import FACILITIES
from .inventory import INVENTORY

ROLES: dict[str, RoleSpec] = {r.name: r for r in (BOSS, INVENTORY, ACCOUNTING, FACILITIES, CUSTOMER_SERVICE)}
