"""Agent loop tests using a scripted fake provider (no network)."""

from typing import Any

import pytest

from jarvis.core.agent import Agent
from jarvis.core.llm.base import LLMProvider, OnText, ToolCall, TurnResult
from jarvis.tools.base import ToolRegistry
from jarvis.tools.builtin.time import GetTimeTool


class FakeProvider(LLMProvider):
    def __init__(self, script: list[TurnResult]) -> None:
        self.script = script
        self.calls: list[list[dict[str, Any]]] = []

    def stream_turn(self, *, system, messages, tools, on_text: OnText) -> TurnResult:
        self.calls.append([dict(m) for m in messages])
        result = self.script.pop(0)
        on_text(result.text)
        return result


@pytest.fixture
def registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(GetTimeTool())
    return r


def make_agent(script: list[TurnResult], registry: ToolRegistry) -> tuple[Agent, FakeProvider]:
    provider = FakeProvider(script)
    return Agent(provider, registry, "system"), provider


def test_plain_text_turn(registry: ToolRegistry) -> None:
    agent, _ = make_agent([TurnResult(text="Hello!", stop_reason="end_turn",
                                      raw_content="Hello!")], registry)
    chunks: list[str] = []
    reply = agent.run_turn("hi", on_text=chunks.append)
    assert reply == "Hello!"
    assert "".join(chunks) == "Hello!"


def test_tool_dispatch_loop(registry: ToolRegistry) -> None:
    script = [
        TurnResult(
            text="",
            stop_reason="tool_use",
            tool_calls=[ToolCall(id="t1", name="get_time", input={"timezone": "UTC"})],
            raw_content=[{"type": "tool_use", "id": "t1", "name": "get_time",
                          "input": {"timezone": "UTC"}}],
        ),
        TurnResult(text="It is now.", stop_reason="end_turn", raw_content="It is now."),
    ]
    agent, provider = make_agent(script, registry)
    seen_tools: list[str] = []
    reply = agent.run_turn("what time?", on_text=lambda _: None,
                           on_tool_use=lambda name, _: seen_tools.append(name))

    assert reply == "It is now."
    assert seen_tools == ["get_time"]
    # Second call must include: user msg, assistant tool_use, user tool_result
    second_call = provider.calls[1]
    assert [m["role"] for m in second_call] == ["user", "assistant", "user"]
    tool_result = second_call[2]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "t1"
    assert "UTC" in tool_result["content"]


def test_tool_error_reported_not_raised(registry: ToolRegistry) -> None:
    script = [
        TurnResult(
            text="",
            stop_reason="tool_use",
            tool_calls=[ToolCall(id="t1", name="get_time", input={"timezone": "Bad/Zone"})],
            raw_content=[],
        ),
        TurnResult(text="Sorry, bad timezone.", stop_reason="end_turn", raw_content="x"),
    ]
    agent, provider = make_agent(script, registry)
    reply = agent.run_turn("time in Bad/Zone?", on_text=lambda _: None)

    assert reply == "Sorry, bad timezone."
    tool_result = provider.calls[1][2]["content"][0]
    assert tool_result["is_error"] is True
    assert "Unknown timezone" in tool_result["content"]


def test_runaway_loop_guard(registry: ToolRegistry) -> None:
    endless = TurnResult(
        text="",
        stop_reason="tool_use",
        tool_calls=[ToolCall(id="t", name="get_time", input={})],
        raw_content=[],
    )
    agent, _ = make_agent([endless] * 3, registry)
    agent._max_tool_rounds = 3
    with pytest.raises(RuntimeError, match="tool rounds"):
        agent.run_turn("loop forever", on_text=lambda _: None)


def test_reset_clears_history(registry: ToolRegistry) -> None:
    agent, provider = make_agent(
        [TurnResult(text="a", stop_reason="end_turn", raw_content="a"),
         TurnResult(text="b", stop_reason="end_turn", raw_content="b")],
        registry,
    )
    agent.run_turn("one", on_text=lambda _: None)
    agent.reset()
    agent.run_turn("two", on_text=lambda _: None)
    assert len(provider.calls[1]) == 1  # history starts fresh after reset
