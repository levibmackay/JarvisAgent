"""SQLite persistence: conversations, messages, and long-term facts.

Fact recall uses FTS5 keyword search for now; swap in vector search here
later without touching callers.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    content, content=facts, content_rowid=id
);
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(content: Any) -> Any:
    """Message content may be a string, dicts, or SDK content blocks."""
    if isinstance(content, str):
        return content
    return [b if isinstance(b, dict) else b.model_dump() for b in content]


class MemoryStore:
    def __init__(self, path: Path) -> None:
        path = path.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(_SCHEMA)
        self._db.commit()

    # -- conversations ------------------------------------------------

    def create_conversation(self) -> int:
        cur = self._db.execute("INSERT INTO conversations (created_at) VALUES (?)", (_now(),))
        self._db.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def add_message(self, conversation_id: int, role: str, content: Any) -> None:
        self._db.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (conversation_id, role, json.dumps(_jsonable(content)), _now()),
        )
        self._db.commit()

    def get_messages(self, conversation_id: int) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        return [{"role": role, "content": json.loads(content)} for role, content in rows]

    # -- facts ---------------------------------------------------------

    def add_fact(self, content: str) -> int:
        cur = self._db.execute(
            "INSERT INTO facts (content, created_at) VALUES (?, ?)", (content, _now())
        )
        self._db.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def search_facts(self, query: str, limit: int = 5) -> list[str]:
        # Quote each term so user text can't break FTS5 query syntax.
        terms = " OR ".join(f'"{t}"' for t in query.replace('"', "").split() if t)
        if not terms:
            return []
        rows = self._db.execute(
            "SELECT f.content FROM facts_fts JOIN facts f ON f.id = facts_fts.rowid "
            "WHERE facts_fts MATCH ? ORDER BY rank LIMIT ?",
            (terms, limit),
        ).fetchall()
        return [content for (content,) in rows]

    def recent_facts(self, limit: int = 10) -> list[str]:
        rows = self._db.execute(
            "SELECT content FROM facts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [content for (content,) in rows]

    def close(self) -> None:
        self._db.close()
