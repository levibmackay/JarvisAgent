"""Background scheduler: polls definitions, runs whatever is due.

Due = the workflow's next_run after its last recorded start (or after
scheduler startup, if it has never run) is in the past. Anchoring to
startup means a `daily 08:00` workflow doesn't fire immediately when the
server boots at noon. Definitions are re-read every poll, so editing a
JSON file takes effect without a restart.
"""

import threading
from datetime import datetime
from pathlib import Path

from jarvis.workflows.model import Workflow, WorkflowError, load_workflows
from jarvis.workflows.runner import WorkflowRunner
from jarvis.workflows.store import WorkflowStore


def _to_local_naive(moment: datetime) -> datetime:
    """Schedules use naive local time; run history is stored UTC-aware."""
    if moment.tzinfo is None:
        return moment
    return moment.astimezone().replace(tzinfo=None)


def due_workflows(workflows: list[Workflow], store: WorkflowStore,
                  anchor: datetime, now: datetime) -> list[Workflow]:
    """Pure due-ness check, unit-testable without threads."""
    due = []
    for workflow in workflows:
        if not workflow.enabled:
            continue
        last = store.last_started_at(workflow.name)
        last = _to_local_naive(last) if last else anchor
        if workflow.parsed_schedule().next_run(last) <= now:
            due.append(workflow)
    return due


class WorkflowScheduler:
    def __init__(self, directory: Path, runner: WorkflowRunner, store: WorkflowStore,
                 poll_interval: float = 30.0) -> None:
        self.directory = directory.expanduser()
        self.store = store
        self._runner = runner
        self._poll_interval = poll_interval
        self._anchor = datetime.now()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_load_error: str | None = None

    # -- used by the API ---------------------------------------------------

    def workflows(self) -> list[Workflow]:
        try:
            loaded = load_workflows(self.directory)
            self.last_load_error = None
            return loaded
        except WorkflowError as exc:
            self.last_load_error = str(exc)
            return []

    def trigger(self, name: str) -> bool:
        """Manually run a workflow on a background thread (even if disabled —
        an explicit request outranks the schedule flag). Returns False if
        the name is unknown; the run lands in history like any other."""
        workflow = next((w for w in self.workflows() if w.name == name), None)
        if workflow is None:
            return False
        threading.Thread(target=self._runner.run, args=(workflow,), daemon=True).start()
        return True

    # -- loop ----------------------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.wait(self._poll_interval):
            now = datetime.now()
            for workflow in due_workflows(self.workflows(), self.store,
                                          self._anchor, now):
                self._runner.run(workflow)
