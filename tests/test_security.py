import json
from pathlib import Path

import pytest

from jarvis.security.audit import AuditLog
from jarvis.security.consent import StaticConsent
from jarvis.security.executor import SafeExecutor
from jarvis.security.paths import resolve_within
from jarvis.tools.base import RiskLevel, Tool, ToolError, ToolRegistry


class DummyTool(Tool):
    name = "dummy"
    description = "test tool"
    input_schema = {"type": "object", "properties": {}, "required": []}

    def __init__(self, risk: RiskLevel, fail: bool = False) -> None:
        self.risk = risk
        self._fail = fail

    def execute(self, params):
        if self._fail:
            raise ToolError("boom")
        return "ok"


def make_executor(tool: Tool, allow: bool, tmp_path: Path):
    registry = ToolRegistry()
    registry.register(tool)
    consent = StaticConsent(allow)
    audit_path = tmp_path / "audit.jsonl"
    return SafeExecutor(registry, consent, AuditLog(audit_path)), consent, audit_path


def read_audit(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_read_only_skips_consent(tmp_path: Path) -> None:
    executor, consent, audit = make_executor(DummyTool(RiskLevel.READ_ONLY), False, tmp_path)
    assert executor.execute("dummy", {}) == "ok"
    assert consent.requests == []  # never consulted
    assert read_audit(audit)[0]["decision"] == "auto"


def test_destructive_denied(tmp_path: Path) -> None:
    executor, consent, audit = make_executor(DummyTool(RiskLevel.DESTRUCTIVE), False, tmp_path)
    with pytest.raises(ToolError, match="denied"):
        executor.execute("dummy", {})
    assert consent.requests == ["dummy"]
    entry = read_audit(audit)[0]
    assert entry["decision"] == "denied" and entry["outcome"] == "denied"


def test_destructive_allowed(tmp_path: Path) -> None:
    executor, _, audit = make_executor(DummyTool(RiskLevel.DESTRUCTIVE), True, tmp_path)
    assert executor.execute("dummy", {}) == "ok"
    entry = read_audit(audit)[0]
    assert entry["decision"] == "user" and entry["outcome"] == "ok"


def test_tool_failure_audited(tmp_path: Path) -> None:
    executor, _, audit = make_executor(DummyTool(RiskLevel.READ_ONLY, fail=True), True, tmp_path)
    with pytest.raises(ToolError, match="boom"):
        executor.execute("dummy", {})
    entry = read_audit(audit)[0]
    assert entry["outcome"] == "error" and "boom" in entry["detail"]


def test_resolve_within_allows_inside(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b.txt"
    assert resolve_within(str(target), [tmp_path]) == target.resolve()


def test_resolve_within_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="outside permitted roots"):
        resolve_within(str(tmp_path / ".." / "escape.txt"), [tmp_path])
