"""Tool protocol and registry — the plugin backbone of Jarvis.

Every capability (shell, files, calendar, ...) implements Tool. The risk
level is declared here so the consent layer (Milestone 2) can gate execution
per tier without knowing anything about individual tools.
"""

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    DESTRUCTIVE = "destructive"


class ToolError(Exception):
    """Raised by tools on execution failure; reported back to the model."""


class Tool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]
    risk: RiskLevel

    @abstractmethod
    def execute(self, params: dict[str, Any]) -> str:
        """Run the tool and return a result string for the model."""

    def classify(self, params: dict[str, Any]) -> RiskLevel:
        """Risk of this specific call. Override when risk depends on params
        (e.g. shell: `ls` vs `rm`)."""
        return self.risk


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise ToolError(f"Unknown tool: {name}") from None

    def execute(self, name: str, params: dict[str, Any]) -> str:
        return self.get(name).execute(params)

    def schemas(self) -> list[dict[str, Any]]:
        """API-shaped tool definitions, sorted by name for cache stability."""
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in sorted(self._tools.values(), key=lambda t: t.name)
        ]

    def __len__(self) -> int:
        return len(self._tools)
