"""Unattended consent policy for workflow runs.

No human is watching, so: read-only runs (SafeExecutor auto-allows it),
reversible tools run only if explicitly listed in the workflow's
allow_tools, and destructive calls are always denied — v1 draws that line
absolutely rather than making it configurable.
"""

from typing import Any

from jarvis.security.consent import ConsentManager
from jarvis.tools.base import RiskLevel


class PolicyConsent(ConsentManager):
    def __init__(self, allowed_tools: list[str]) -> None:
        self._allowed = set(allowed_tools)

    def request(self, tool_name: str, params: dict[str, Any], risk: RiskLevel) -> bool:
        if risk is RiskLevel.DESTRUCTIVE:
            return False
        return tool_name in self._allowed
