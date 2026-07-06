"""HTTP consent broker: bridges SafeExecutor's blocking consent check to
an async client. The turn's worker thread blocks here while the client
sees a `consent_request` SSE event and answers via POST; no answer within
the timeout means deny.
"""

import threading
import uuid
from typing import Any, Callable

from jarvis.security.consent import ConsentManager
from jarvis.tools.base import RiskLevel

EmitEvent = Callable[[dict[str, Any]], None]


class _Pending:
    __slots__ = ("event", "allow")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.allow = False


class HttpConsent(ConsentManager):
    def __init__(self, emit: EmitEvent, timeout: float) -> None:
        self._emit = emit
        self._timeout = timeout
        self._pending: dict[str, _Pending] = {}
        self._lock = threading.Lock()

    def request(self, tool_name: str, params: dict[str, Any], risk: RiskLevel) -> bool:
        consent_id = uuid.uuid4().hex
        pending = _Pending()
        with self._lock:
            self._pending[consent_id] = pending
        try:
            self._emit(
                {
                    "type": "consent_request",
                    "consent_id": consent_id,
                    "tool": tool_name,
                    "params": params,
                    "risk": str(risk),
                    "timeout_seconds": self._timeout,
                }
            )
            answered = pending.event.wait(self._timeout)
            return answered and pending.allow
        finally:
            with self._lock:
                self._pending.pop(consent_id, None)

    def resolve(self, consent_id: str, allow: bool) -> bool:
        """Answer a pending request. Returns False if unknown or already resolved."""
        with self._lock:
            pending = self._pending.get(consent_id)
            if pending is None or pending.event.is_set():
                return False
            pending.allow = allow
            pending.event.set()
            return True
