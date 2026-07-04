"""Memory exposed to the model as tools.

Both are READ_ONLY tier: they touch only Jarvis's own memory database,
never the user's files or system.
"""

from typing import Any

from jarvis.memory.store import MemoryStore
from jarvis.tools.base import RiskLevel, Tool


class RememberTool(Tool):
    name = "remember"
    description = (
        "Save a durable fact about the user, their preferences, or their projects "
        "for future sessions. Use whenever the user shares lasting information "
        "(name, preferences, recurring context) — not transient task details."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "fact": {"type": "string", "description": "One self-contained fact."}
        },
        "required": ["fact"],
    }
    risk = RiskLevel.READ_ONLY

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def execute(self, params: dict[str, Any]) -> str:
        self._store.add_fact(params["fact"])
        return "Remembered."


class RecallTool(Tool):
    name = "recall"
    description = (
        "Search long-term memory for facts from previous sessions. Use when the "
        "user references something you might have been told before."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keywords to search for."}
        },
        "required": ["query"],
    }
    risk = RiskLevel.READ_ONLY

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def execute(self, params: dict[str, Any]) -> str:
        facts = self._store.search_facts(params["query"])
        if not facts:
            return "No matching memories."
        return "\n".join(f"- {f}" for f in facts)
