"""API server tests: auth, sessions, SSE turn streaming, consent flow."""

import json
import threading
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from jarvis.core.agent import Agent
from jarvis.core.llm.base import ToolCall, TurnResult
from jarvis.security.audit import AuditLog
from jarvis.security.executor import SafeExecutor
from jarvis.server.app import create_app
from jarvis.server.consent import HttpConsent
from jarvis.server.session import Session, SessionBusyError
from jarvis.tools.base import RiskLevel, Tool, ToolRegistry
from jarvis.tools.builtin.time import GetTimeTool
from tests.test_agent import FakeProvider

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class TouchTool(Tool):
    name = "touch"
    description = "reversible test tool"
    input_schema = {"type": "object", "properties": {}}
    risk = RiskLevel.REVERSIBLE

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, params: dict[str, Any]) -> str:
        self.calls += 1
        return "touched"


def tool_use_turn(name: str, tool_id: str = "t1") -> TurnResult:
    return TurnResult(
        text="",
        stop_reason="tool_use",
        tool_calls=[ToolCall(id=tool_id, name=name, input={})],
        raw_content=[{"type": "tool_use", "id": tool_id, "name": name, "input": {}}],
    )


def end_turn(text: str) -> TurnResult:
    return TurnResult(text=text, stop_reason="end_turn", raw_content=text)


def make_factory(script: list[TurnResult], registry: ToolRegistry, tmp_path: Path):
    def factory(consent: HttpConsent) -> Agent:
        executor = SafeExecutor(registry, consent, AuditLog(tmp_path / "audit.jsonl"))
        return Agent(FakeProvider(script), executor, "system")

    return factory


def make_client(script: list[TurnResult], registry: ToolRegistry, tmp_path: Path,
                consent_timeout: float = 0.2) -> TestClient:
    app = create_app(make_factory(script, registry, tmp_path), TOKEN, consent_timeout)
    return TestClient(app)


def sse_events(client: TestClient, session_id: str, text: str) -> list[dict[str, Any]]:
    with client.stream(
        "POST", f"/v1/sessions/{session_id}/messages", json={"text": text}, headers=AUTH
    ) as response:
        assert response.status_code == 200
        return [
            json.loads(line[len("data: "):])
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]


@pytest.fixture
def registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(GetTimeTool())
    r.register(TouchTool())
    return r


def test_health_needs_no_auth(registry, tmp_path) -> None:
    client = make_client([], registry, tmp_path)
    assert client.get("/v1/health").status_code == 200


def test_rejects_missing_or_wrong_token(registry, tmp_path) -> None:
    client = make_client([], registry, tmp_path)
    assert client.post("/v1/sessions").status_code == 401
    assert client.post(
        "/v1/sessions", headers={"Authorization": "Bearer wrong"}
    ).status_code == 401


def test_session_lifecycle(registry, tmp_path) -> None:
    client = make_client([], registry, tmp_path)
    sid = client.post("/v1/sessions", headers=AUTH).json()["session_id"]
    assert client.delete(f"/v1/sessions/{sid}", headers=AUTH).status_code == 204
    assert client.delete(f"/v1/sessions/{sid}", headers=AUTH).status_code == 404


def test_message_to_unknown_session_404(registry, tmp_path) -> None:
    client = make_client([], registry, tmp_path)
    response = client.post(
        "/v1/sessions/nope/messages", json={"text": "hi"}, headers=AUTH
    )
    assert response.status_code == 404


def test_text_turn_streams_text_and_done(registry, tmp_path) -> None:
    client = make_client([end_turn("Hello!")], registry, tmp_path)
    sid = client.post("/v1/sessions", headers=AUTH).json()["session_id"]
    events = sse_events(client, sid, "hi")
    assert [e["type"] for e in events] == ["text", "done"]
    assert events[1]["reply"] == "Hello!"


def test_read_only_tool_runs_without_consent(registry, tmp_path) -> None:
    script = [tool_use_turn("get_time"), end_turn("It is now.")]
    client = make_client(script, registry, tmp_path)
    sid = client.post("/v1/sessions", headers=AUTH).json()["session_id"]
    events = sse_events(client, sid, "time?")
    types = [e["type"] for e in events]
    assert "tool_use" in types and "consent_request" not in types
    assert events[-1] == {"type": "done", "reply": "It is now."}


def test_consent_timeout_denies_tool(registry, tmp_path) -> None:
    touch = registry.get("touch")
    script = [tool_use_turn("touch"), end_turn("Denied, then.")]
    client = make_client(script, registry, tmp_path, consent_timeout=0.1)
    sid = client.post("/v1/sessions", headers=AUTH).json()["session_id"]
    events = sse_events(client, sid, "touch it")
    assert "consent_request" in [e["type"] for e in events]
    assert touch.calls == 0  # denied by timeout; tool never ran
    assert events[-1]["type"] == "done"


def test_resolve_unknown_consent_404(registry, tmp_path) -> None:
    client = make_client([], registry, tmp_path)
    sid = client.post("/v1/sessions", headers=AUTH).json()["session_id"]
    response = client.post(
        f"/v1/sessions/{sid}/consent/nope", json={"allow": True}, headers=AUTH
    )
    assert response.status_code == 404


def drain(q) -> Iterator[dict[str, Any]]:
    while (event := q.get(timeout=5)) is not None:
        yield event


def test_consent_granted_runs_tool(registry, tmp_path) -> None:
    touch = registry.get("touch")
    script = [tool_use_turn("touch"), end_turn("Touched!")]
    session = Session(make_factory(script, registry, tmp_path), consent_timeout=5)

    events = []
    for event in drain(session.start_turn("touch it")):
        events.append(event)
        if event["type"] == "consent_request":
            assert session.consent.resolve(event["consent_id"], allow=True)

    assert touch.calls == 1
    assert events[-1] == {"type": "done", "reply": "Touched!"}


def test_second_turn_while_busy_raises(registry, tmp_path) -> None:
    release = threading.Event()

    class BlockingProvider(FakeProvider):
        def stream_turn(self, **kwargs) -> TurnResult:
            release.wait(timeout=5)
            return super().stream_turn(**kwargs)

    def factory(consent: HttpConsent) -> Agent:
        executor = SafeExecutor(registry, consent, AuditLog(tmp_path / "audit.jsonl"))
        return Agent(BlockingProvider([end_turn("ok")]), executor, "system")

    session = Session(factory, consent_timeout=5)
    q = session.start_turn("first")
    with pytest.raises(SessionBusyError):
        session.start_turn("second")
    release.set()
    assert list(drain(q))[-1]["type"] == "done"
