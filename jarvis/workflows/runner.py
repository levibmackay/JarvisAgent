"""Execute one workflow: fresh agent, policy consent, recorded outcome."""

from typing import Callable

from jarvis.core.agent import Agent
from jarvis.security.consent import ConsentManager
from jarvis.workflows.consent import PolicyConsent
from jarvis.workflows.model import Workflow
from jarvis.workflows.notify import Notifier
from jarvis.workflows.store import WorkflowStore

AgentFactory = Callable[[ConsentManager], Agent]


class WorkflowRunner:
    def __init__(self, agent_factory: AgentFactory, store: WorkflowStore,
                 notifier: Notifier) -> None:
        self._agent_factory = agent_factory
        self._store = store
        self._notifier = notifier

    def run(self, workflow: Workflow) -> int:
        """Run to completion (blocking); returns the history run id."""
        run_id = self._store.start_run(workflow.name)
        try:
            agent = self._agent_factory(PolicyConsent(workflow.allow_tools))
            reply = agent.run_turn(workflow.prompt, on_text=lambda _: None)
            self._store.finish_run(run_id, "ok", reply)
            if workflow.notify:
                self._notifier.notify(f"Jarvis · {workflow.name}", reply)
        except Exception as exc:  # recorded, never crashes the scheduler
            detail = f"{type(exc).__name__}: {exc}"
            self._store.finish_run(run_id, "error", detail)
            if workflow.notify:
                self._notifier.notify(f"Jarvis · {workflow.name} failed", detail)
        return run_id
