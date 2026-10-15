"""Model, paths, and the limits that keep a team run cheap and bounded."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import ModelSettings, UsageLimits
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
MCP_SERVER = PROJECT_DIR / "mcp_server" / "server.py"
AUDIT_PATH = PROJECT_DIR / "output" / "audit_trail.json"

# Every agent uses this one model.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# --- Token and loop limits -------------------------------------------------
# One budget for the whole session: delegated agents share the Boss's usage
# counter, so these caps cover all five agents together.
USAGE_LIMITS = UsageLimits(
    request_limit=60,  # model calls across every agent
    tool_calls_limit=120,  # MCP + delegate calls across every agent
    total_tokens_limit=300_000,
)
MODEL_SETTINGS = ModelSettings(max_tokens=4_000, timeout=90)
MAX_DELEGATION_DEPTH = 3  # boss -> specialist -> specialist, no deeper
MAX_DELEGATIONS = 12  # total delegate calls per session
AUDIT_TEXT_LIMIT = 4_000  # chars kept per tool result / message in the audit trail

# Load every .env from the project folder up: Homework 5/.env holds local
# switches (LLM_GATEWAY), the class folder's .env holds the API keys. The
# nearest file wins if both set the same name.
for folder in (PROJECT_DIR, *PROJECT_DIR.parents):
    if (folder / ".env").is_file():
        load_dotenv(folder / ".env")


def llm_gateway() -> str:
    """'portkey' (class default) or 'openai' (direct, e.g. when the Portkey key is out of budget).

    Set LLM_GATEWAY=openai to use OPENAI_API_KEY. Same model either way.
    """
    gateway = os.getenv("LLM_GATEWAY", "portkey").strip().lower()
    if gateway not in ("portkey", "openai"):
        raise RuntimeError("LLM_GATEWAY must be 'portkey' or 'openai'.")
    return gateway


@lru_cache(maxsize=1)
def get_model() -> OpenAIResponsesModel:
    if llm_gateway() == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set (expected in the class folder's .env).")
        client = AsyncOpenAI(api_key=api_key, max_retries=1)
    else:
        api_key = os.getenv("PORTKEY_API_KEY")
        if not api_key:
            raise RuntimeError("PORTKEY_API_KEY is not set (expected in the class folder's .env).")
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=PORTKEY_BASE_URL,
            default_headers={"x-portkey-api-key": api_key},
            max_retries=1,
        )
    # Responses API: gpt-6-luna only supports function tools on /v1/responses.
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
