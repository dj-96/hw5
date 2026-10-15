"""What every role definition has in common."""
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class RoleSpec:
    name: str  # also the delegate target name
    title: str
    prompt_file: str  # file in backend/prompts/
    description: str  # one line the other agents see when choosing who to delegate to
    tools: frozenset[str]  # MCP tools this role may call
    output_type: type[BaseModel]
