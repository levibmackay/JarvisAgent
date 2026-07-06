"""Workflow definitions: one JSON file per workflow in ~/.jarvis/workflows."""

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError, field_validator

from jarvis.workflows.schedule import Schedule, ScheduleError


class WorkflowError(ValueError):
    """Invalid workflow definition."""


class Workflow(BaseModel):
    name: str
    schedule: str
    prompt: str
    allow_tools: list[str] = []  # non-read-only tools granted without prompting
    notify: bool = True  # post the result as a macOS notification
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _name_is_slug(cls, v: str) -> str:
        if not v or not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(f"Workflow name must be alphanumeric/-/_: {v!r}")
        return v

    @field_validator("schedule")
    @classmethod
    def _schedule_parses(cls, v: str) -> str:
        Schedule.parse(v)  # raises ScheduleError on bad input
        return v

    def parsed_schedule(self) -> Schedule:
        return Schedule.parse(self.schedule)


def load_workflows(directory: Path) -> list[Workflow]:
    """Load every *.json definition; raises WorkflowError on the first bad file
    (a broken definition should be loud, not silently skipped)."""
    directory = directory.expanduser()
    workflows: list[Workflow] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            workflow = Workflow.model_validate(json.loads(path.read_text()))
        except (json.JSONDecodeError, ValidationError, ScheduleError) as exc:
            raise WorkflowError(f"{path.name}: {exc}") from exc
        if workflow.name in seen:
            raise WorkflowError(f"{path.name}: duplicate workflow name {workflow.name!r}")
        seen.add(workflow.name)
        workflows.append(workflow)
    return workflows
