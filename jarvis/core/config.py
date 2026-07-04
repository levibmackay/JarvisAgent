"""Typed application settings.

Secrets are never stored here: the Anthropic SDK resolves credentials from
ANTHROPIC_API_KEY or an `ant auth login` profile on its own.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JARVIS_", env_file=".env", extra="ignore")

    model: str = "claude-opus-4-8"
    max_tokens: int = 64_000
    permitted_roots: list[Path] = Field(default_factory=lambda: [Path.home()])
    shell_timeout: int = 30
    audit_log_path: Path = Path("~/.jarvis/audit.jsonl")
    db_path: Path = Path("~/.jarvis/jarvis.db")
    seed_facts: int = 10  # recent facts injected into the system prompt at startup
    system_prompt: str = (
        "You are Jarvis, a personal assistant running on the user's Mac. "
        "Be concise and direct. Use tools when they help answer the request."
    )
