"""SafeExecutor: consent + audit wrapper around the tool registry.

Duck-type compatible with ToolRegistry (schemas/execute), so the Agent
doesn't know it exists.
"""

from typing import Any

from jarvis.security.audit import AuditLog
from jarvis.security.consent import ConsentManager
from jarvis.tools.base import RiskLevel, ToolError, ToolRegistry


class SafeExecutor:
    def __init__(self, registry: ToolRegistry, consent: ConsentManager, audit: AuditLog) -> None:
        self._registry = registry
        self._consent = consent
        self._audit = audit

    def schemas(self) -> list[dict[str, Any]]:
        return self._registry.schemas()

    def execute(self, name: str, params: dict[str, Any]) -> str:
        tool = self._registry.get(name)
        risk = tool.classify(params)

        if risk is RiskLevel.READ_ONLY:
            decision = "auto"
        elif self._consent.request(name, params, risk):
            decision = "user"
        else:
            self._audit.record(
                tool=name, params=params, risk=risk, decision="denied", outcome="denied"
            )
            raise ToolError("User denied permission for this action.")

        try:
            output = tool.execute(params)
        except ToolError as exc:
            self._audit.record(
                tool=name, params=params, risk=risk, decision=decision,
                outcome="error", detail=str(exc),
            )
            raise
        self._audit.record(
            tool=name, params=params, risk=risk, decision=decision,
            outcome="ok", detail=f"{len(output)} chars",
        )
        return output
