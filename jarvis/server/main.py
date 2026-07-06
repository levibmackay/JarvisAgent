"""Server entry point: loopback-only uvicorn with a persistent bearer token."""

import secrets
import sys
from pathlib import Path

from jarvis.core.config import Settings
from jarvis.interfaces.cli import build_agent
from jarvis.memory.store import MemoryStore
from jarvis.server.app import create_app
from jarvis.workflows.notify import MacNotifier
from jarvis.workflows.runner import WorkflowRunner
from jarvis.workflows.scheduler import WorkflowScheduler
from jarvis.workflows.store import WorkflowStore


def load_or_create_token(path: Path) -> str:
    path = path.expanduser()
    if path.exists():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    path.touch(mode=0o600)
    path.write_text(token)
    return token


def main() -> int:
    try:
        import uvicorn
    except ImportError:
        print("Server extras not installed: pip install 'jarvis[server]'", file=sys.stderr)
        return 1

    settings = Settings()
    if settings.server_host != "127.0.0.1":
        print(f"Warning: binding {settings.server_host} exposes tool execution "
              "beyond this machine.", file=sys.stderr)

    token = load_or_create_token(settings.server_token_path)
    store = MemoryStore(settings.db_path)
    agent_factory = lambda consent: build_agent(settings, store, consent=consent)  # noqa: E731

    workflow_store = WorkflowStore(settings.db_path)
    scheduler = WorkflowScheduler(
        settings.workflows_dir,
        WorkflowRunner(agent_factory, workflow_store, MacNotifier()),
        workflow_store,
        poll_interval=settings.workflow_poll_interval,
    )
    scheduler.start()

    app = create_app(
        agent_factory=agent_factory,
        token=token,
        consent_timeout=settings.consent_timeout,
        workflows=scheduler,
    )
    print(f"Jarvis server on http://{settings.server_host}:{settings.server_port} "
          f"(token: {settings.server_token_path})")
    uvicorn.run(app, host=settings.server_host, port=settings.server_port, log_level="warning")
    scheduler.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
