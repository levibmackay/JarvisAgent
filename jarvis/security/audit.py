"""Append-only JSONL audit log of every tool execution attempt."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jarvis.tools.base import RiskLevel

_PARAMS_LIMIT = 500


class AuditLog:
    def __init__(self, path: Path) -> None:
        self._path = path.expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        tool: str,
        params: dict[str, Any],
        risk: RiskLevel,
        decision: str,   # "auto" | "user" | "denied"
        outcome: str,    # "ok" | "error" | "denied"
        detail: str = "",
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "risk": str(risk),
            "decision": decision,
            "outcome": outcome,
            "params": json.dumps(params, ensure_ascii=False)[:_PARAMS_LIMIT],
            "detail": detail[:_PARAMS_LIMIT],
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
