"""Run history for workflows — same SQLite file as MemoryStore, own table."""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    id INTEGER PRIMARY KEY,
    workflow TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,   -- running | ok | error
    detail TEXT             -- final reply or error message
);
CREATE INDEX IF NOT EXISTS workflow_runs_by_name
    ON workflow_runs (workflow, started_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowStore:
    def __init__(self, path: Path) -> None:
        path = path.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def start_run(self, workflow: str) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO workflow_runs (workflow, started_at, status) "
                "VALUES (?, ?, 'running')",
                (workflow, _now()),
            )
            self._db.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def finish_run(self, run_id: int, status: str, detail: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE workflow_runs SET finished_at = ?, status = ?, detail = ? "
                "WHERE id = ?",
                (_now(), status, detail, run_id),
            )
            self._db.commit()

    def last_started_at(self, workflow: str) -> datetime | None:
        with self._lock:
            row = self._db.execute(
                "SELECT MAX(started_at) FROM workflow_runs WHERE workflow = ?",
                (workflow,),
            ).fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

    def runs(self, workflow: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, started_at, finished_at, status, detail "
                "FROM workflow_runs WHERE workflow = ? ORDER BY id DESC LIMIT ?",
                (workflow, limit),
            ).fetchall()
        return [
            {"id": r[0], "started_at": r[1], "finished_at": r[2],
             "status": r[3], "detail": r[4]}
            for r in rows
        ]

    def close(self) -> None:
        self._db.close()
