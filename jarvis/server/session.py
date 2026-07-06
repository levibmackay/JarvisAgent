"""Server sessions: one Agent per session, one turn at a time.

A turn runs Agent.run_turn (synchronous) on a worker thread, pushing
events into a Queue that the SSE response drains. A None sentinel marks
end-of-turn.
"""

import queue
import threading
import uuid
from typing import Any, Callable

from jarvis.core.agent import Agent
from jarvis.server.consent import HttpConsent

AgentFactory = Callable[[HttpConsent], Agent]


class SessionBusyError(Exception):
    """A turn is already in progress for this session."""


class Session:
    def __init__(self, agent_factory: AgentFactory, consent_timeout: float) -> None:
        self.id = uuid.uuid4().hex
        self.consent = HttpConsent(self._emit, consent_timeout)
        self.agent = agent_factory(self.consent)
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._turn_lock = threading.Lock()

    def _emit(self, event: dict[str, Any]) -> None:
        self._queue.put(event)

    def start_turn(self, text: str) -> "queue.Queue[dict[str, Any] | None]":
        if not self._turn_lock.acquire(blocking=False):
            raise SessionBusyError
        self._queue = queue.Queue()  # drop events from any abandoned prior turn
        threading.Thread(target=self._run_turn, args=(text,), daemon=True).start()
        return self._queue

    def _run_turn(self, text: str) -> None:
        q = self._queue
        try:
            reply = self.agent.run_turn(
                text,
                on_text=lambda t: q.put({"type": "text", "text": t}),
                on_tool_use=lambda name, params: q.put(
                    {"type": "tool_use", "tool": name, "params": params}
                ),
            )
            q.put({"type": "done", "reply": reply})
        except Exception as exc:  # surfaced to the client, never crashes the server
            q.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            q.put(None)
            self._turn_lock.release()


class SessionManager:
    def __init__(self, agent_factory: AgentFactory, consent_timeout: float) -> None:
        self._agent_factory = agent_factory
        self._consent_timeout = consent_timeout
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        session = Session(self._agent_factory, self._consent_timeout)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None
