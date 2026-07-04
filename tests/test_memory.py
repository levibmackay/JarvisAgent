from pathlib import Path

import pytest

from jarvis.core.agent import Agent
from jarvis.core.llm.base import TurnResult
from jarvis.memory.store import MemoryStore
from jarvis.memory.tools import RecallTool, RememberTool
from jarvis.tools.base import ToolRegistry
from tests.test_agent import FakeProvider


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    s = MemoryStore(tmp_path / "test.db")
    yield s
    s.close()


def test_message_roundtrip(store: MemoryStore) -> None:
    conv = store.create_conversation()
    store.add_message(conv, "user", "hello")
    store.add_message(conv, "assistant", [{"type": "text", "text": "hi"}])
    msgs = store.get_messages(conv)
    assert msgs == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": [{"type": "text", "text": "hi"}]},
    ]


def test_conversations_isolated(store: MemoryStore) -> None:
    a, b = store.create_conversation(), store.create_conversation()
    store.add_message(a, "user", "in a")
    assert store.get_messages(b) == []


def test_sdk_block_serialization(store: MemoryStore) -> None:
    class FakeBlock:
        def model_dump(self):
            return {"type": "text", "text": "from sdk"}

    conv = store.create_conversation()
    store.add_message(conv, "assistant", [FakeBlock()])
    assert store.get_messages(conv)[0]["content"] == [{"type": "text", "text": "from sdk"}]


def test_fact_search(store: MemoryStore) -> None:
    store.add_fact("The user's dog is named Biscuit")
    store.add_fact("The user prefers dark mode")
    assert store.search_facts("dog name") == ["The user's dog is named Biscuit"]
    assert store.search_facts("zebra quantum") == []


def test_fact_search_survives_odd_query(store: MemoryStore) -> None:
    store.add_fact("plain fact")
    # FTS5 syntax characters must not raise
    assert store.search_facts('AND OR "NOT( fact') == ["plain fact"]


def test_recent_facts_newest_first(store: MemoryStore) -> None:
    store.add_fact("first")
    store.add_fact("second")
    assert store.recent_facts(1) == ["second"]


def test_remember_recall_tools(store: MemoryStore) -> None:
    RememberTool(store).execute({"fact": "User's favorite editor is Zed"})
    out = RecallTool(store).execute({"query": "favorite editor"})
    assert "Zed" in out
    assert RecallTool(store).execute({"query": "nonexistent topic"}) == "No matching memories."


def test_agent_on_message_persists_history(store: MemoryStore) -> None:
    conv = store.create_conversation()
    provider = FakeProvider(
        [TurnResult(text="Hello!", stop_reason="end_turn", raw_content=[{"type": "text", "text": "Hello!"}])]
    )
    registry = ToolRegistry()
    agent = Agent(
        provider, registry, "system",
        on_message=lambda m: store.add_message(conv, m["role"], m["content"]),
    )
    agent.run_turn("hi", on_text=lambda _: None)
    msgs = store.get_messages(conv)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["content"] == [{"type": "text", "text": "Hello!"}]
