"""FastAPI app factory.

Auth: static bearer token on every /v1 route except /v1/health. The
server binds loopback only (see main.py); the token guards against other
local processes driving the agent.
"""

import asyncio
import json
import secrets
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from jarvis.server.session import AgentFactory, SessionBusyError, SessionManager
from jarvis.workflows.scheduler import WorkflowScheduler


class MessageIn(BaseModel):
    text: str


class ConsentIn(BaseModel):
    allow: bool


def _sse(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


def create_app(agent_factory: AgentFactory, token: str, consent_timeout: float = 300.0,
               workflows: WorkflowScheduler | None = None) -> FastAPI:
    app = FastAPI(title="Jarvis", docs_url=None, redoc_url=None, openapi_url=None)
    sessions = SessionManager(agent_factory, consent_timeout)

    def require_auth(request: Request) -> None:
        header = request.headers.get("authorization", "")
        scheme, _, presented = header.partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(presented, token):
            raise HTTPException(status_code=401, detail="Invalid or missing bearer token")

    auth = Depends(require_auth)

    @app.get("/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/sessions", dependencies=[auth], status_code=201)
    def create_session() -> dict[str, str]:
        return {"session_id": sessions.create().id}

    @app.delete("/v1/sessions/{session_id}", dependencies=[auth], status_code=204)
    def delete_session(session_id: str) -> None:
        if not sessions.delete(session_id):
            raise HTTPException(status_code=404, detail="Unknown session")

    @app.post("/v1/sessions/{session_id}/messages", dependencies=[auth])
    def post_message(session_id: str, message: MessageIn) -> StreamingResponse:
        session = sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        try:
            q = session.start_turn(message.text)
        except SessionBusyError:
            raise HTTPException(status_code=409, detail="A turn is already in progress") from None

        async def stream() -> AsyncIterator[str]:
            while True:
                event = await asyncio.to_thread(q.get)
                if event is None:
                    return
                yield _sse(event)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.post("/v1/sessions/{session_id}/consent/{consent_id}", dependencies=[auth],
              status_code=204)
    def post_consent(session_id: str, consent_id: str, decision: ConsentIn) -> None:
        session = sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        if not session.consent.resolve(consent_id, decision.allow):
            raise HTTPException(status_code=404, detail="Unknown or expired consent request")

    if workflows is not None:

        @app.get("/v1/workflows", dependencies=[auth])
        def list_workflows() -> dict[str, Any]:
            return {
                "workflows": [w.model_dump() for w in workflows.workflows()],
                "load_error": workflows.last_load_error,
            }

        @app.post("/v1/workflows/{name}/run", dependencies=[auth], status_code=202)
        def run_workflow(name: str) -> dict[str, str]:
            if not workflows.trigger(name):
                raise HTTPException(status_code=404, detail="Unknown workflow")
            return {"status": "started"}

        @app.get("/v1/workflows/{name}/runs", dependencies=[auth])
        def workflow_runs(name: str) -> dict[str, Any]:
            return {"runs": workflows.store.runs(name)}

    return app
