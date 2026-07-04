"""Consent manager: the human gate in front of non-read-only tool calls."""

import json
from abc import ABC, abstractmethod
from typing import Any

from jarvis.tools.base import RiskLevel


class ConsentManager(ABC):
    @abstractmethod
    def request(self, tool_name: str, params: dict[str, Any], risk: RiskLevel) -> bool:
        """Return True if the user allows this specific call."""


class CliConsent(ConsentManager):
    """Interactive y/N/a prompt; 'a' allows the tool for the rest of the session."""

    def __init__(self) -> None:
        self._session_allowed: set[str] = set()

    def request(self, tool_name: str, params: dict[str, Any], risk: RiskLevel) -> bool:
        if tool_name in self._session_allowed:
            return True
        detail = json.dumps(params, ensure_ascii=False)
        if len(detail) > 300:
            detail = detail[:300] + "…"
        print(f"\n[consent] {tool_name} ({risk}): {detail}")
        answer = input("Allow? [y/N/a=always this session] ").strip().lower()
        if answer == "a":
            self._session_allowed.add(tool_name)
            return True
        return answer == "y"


class StaticConsent(ConsentManager):
    """Fixed-answer consent for tests and non-interactive runs."""

    def __init__(self, allow: bool) -> None:
        self.allow = allow
        self.requests: list[str] = []

    def request(self, tool_name: str, params: dict[str, Any], risk: RiskLevel) -> bool:
        self.requests.append(tool_name)
        return self.allow
