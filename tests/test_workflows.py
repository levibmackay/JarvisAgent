"""Workflow tests: schedule grammar, definitions, policy consent, runner,
due-ness, and the server endpoints."""

import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from jarvis.core.agent import Agent
from jarvis.security.audit import AuditLog
from jarvis.security.executor import SafeExecutor
from jarvis.server.app import create_app
from jarvis.tools.base import RiskLevel, ToolRegistry
from jarvis.workflows.consent import PolicyConsent
from jarvis.workflows.model import Workflow, WorkflowError, load_workflows
from jarvis.workflows.notify import NullNotifier
from jarvis.workflows.runner import WorkflowRunner
from jarvis.workflows.schedule import Schedule, ScheduleError
from jarvis.workflows.scheduler import WorkflowScheduler, due_workflows
from jarvis.workflows.store import WorkflowStore
from tests.test_agent import FakeProvider
from tests.test_server import TOKEN, AUTH, TouchTool, end_turn, tool_use_turn

# -- schedule ---------------------------------------------------------------


def test_interval_schedule() -> None:
    s = Schedule.parse("every 15m")
    after = datetime(2026, 7, 5, 12, 0)
    assert s.next_run(after) == after + timedelta(minutes=15)
    assert Schedule.parse("every 2h").next_run(after) == after + timedelta(hours=2)


def test_daily_schedule_wraps_midnight() -> None:
    s = Schedule.parse("daily 08:00")
    assert s.next_run(datetime(2026, 7, 5, 7, 0)) == datetime(2026, 7, 5, 8, 0)
    assert s.next_run(datetime(2026, 7, 5, 9, 0)) == datetime(2026, 7, 6, 8, 0)
    assert s.next_run(datetime(2026, 7, 5, 8, 0)) == datetime(2026, 7, 6, 8, 0)


def test_weekly_schedule() -> None:
    s = Schedule.parse("weekly mon 09:00")
    # 2026-07-05 is a Sunday; next Monday is the 6th.
    assert s.next_run(datetime(2026, 7, 5, 12, 0)) == datetime(2026, 7, 6, 9, 0)
    assert s.next_run(datetime(2026, 7, 6, 9, 0)) == datetime(2026, 7, 13, 9, 0)


@pytest.mark.parametrize("bad", ["every 0m", "hourly", "daily 25:00", "weekly funday 09:00", ""])
def test_bad_schedules_rejected(bad: str) -> None:
    with pytest.raises(ScheduleError):
        Schedule.parse(bad)


# -- definitions --------------------------------------------------------------


def write_workflow(directory, name="brief", **overrides) -> None:
    definition = {"name": name, "schedule": "every 15m", "prompt": "do the thing"}
    definition.update(overrides)
    directory.mkdir(exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(definition))


def test_load_workflows(tmp_path) -> None:
    write_workflow(tmp_path / "wf", notify=False, allow_tools=["touch"])
    (loaded,) = load_workflows(tmp_path / "wf")
    assert loaded.name == "brief" and loaded.allow_tools == ["touch"]
    assert load_workflows(tmp_path / "missing-dir") == []


def test_bad_definitions_are_loud(tmp_path) -> None:
    directory = tmp_path / "wf"
    write_workflow(directory, schedule="sometimes")
    with pytest.raises(WorkflowError):
        load_workflows(directory)
    write_workflow(directory, schedule="every 5m", name="bad name!")
    with pytest.raises(WorkflowError):
        load_workflows(directory)


def test_duplicate_names_rejected(tmp_path) -> None:
    directory = tmp_path / "wf"
    directory.mkdir()
    (directory / "a.json").write_text(json.dumps(
        {"name": "same", "schedule": "every 5m", "prompt": "x"}))
    (directory / "b.json").write_text(json.dumps(
        {"name": "same", "schedule": "every 5m", "prompt": "y"}))
    with pytest.raises(WorkflowError):
        load_workflows(directory)


# -- consent policy -----------------------------------------------------------


def test_policy_consent() -> None:
    policy = PolicyConsent(["touch"])
    assert policy.request("touch", {}, RiskLevel.REVERSIBLE)
    assert not policy.request("shell", {}, RiskLevel.REVERSIBLE)
    assert not policy.request("touch", {}, RiskLevel.DESTRUCTIVE)  # never


# -- runner --------------------------------------------------------------------


def make_runner(script, registry, tmp_path):
    def factory(consent):
        executor = SafeExecutor(registry, consent, AuditLog(tmp_path / "audit.jsonl"))
        return Agent(FakeProvider(list(script)), executor, "system")

    store = WorkflowStore(tmp_path / "wf.db")
    notifier = NullNotifier()
    return WorkflowRunner(factory, store, notifier), store, notifier


def test_runner_records_ok_and_notifies(tmp_path) -> None:
    registry = ToolRegistry()
    touch = TouchTool()
    registry.register(touch)
    script = [tool_use_turn("touch"), end_turn("All done.")]
    runner, store, notifier = make_runner(
        script, registry, tmp_path)
    workflow = Workflow(name="brief", schedule="every 15m", prompt="go",
                        allow_tools=["touch"])
    runner.run(workflow)
    (run,) = store.runs("brief")
    assert run["status"] == "ok" and run["detail"] == "All done."
    assert touch.calls == 1
    assert notifier.sent == [("Jarvis · brief", "All done.")]


def test_runner_denies_unlisted_tool_but_finishes(tmp_path) -> None:
    registry = ToolRegistry()
    touch = TouchTool()
    registry.register(touch)
    script = [tool_use_turn("touch"), end_turn("Could not.")]
    runner, store, _ = make_runner(script, registry, tmp_path)
    runner.run(Workflow(name="brief", schedule="every 15m", prompt="go"))
    assert touch.calls == 0  # consent denied, agent continued
    assert store.runs("brief")[0]["status"] == "ok"


def test_runner_records_error(tmp_path) -> None:
    def exploding_factory(consent):
        raise RuntimeError("no provider")

    store = WorkflowStore(tmp_path / "wf.db")
    notifier = NullNotifier()
    runner = WorkflowRunner(exploding_factory, store, notifier)
    runner.run(Workflow(name="brief", schedule="every 15m", prompt="go"))
    (run,) = store.runs("brief")
    assert run["status"] == "error" and "no provider" in run["detail"]
    assert "failed" in notifier.sent[0][0]


# -- due-ness --------------------------------------------------------------------


def test_due_workflows(tmp_path) -> None:
    store = WorkflowStore(tmp_path / "wf.db")
    workflow = Workflow(name="brief", schedule="every 15m", prompt="go")
    disabled = Workflow(name="off", schedule="every 15m", prompt="go", enabled=False)
    anchor = datetime(2026, 7, 5, 12, 0)

    # Never run: due only once the interval has elapsed since anchor.
    assert due_workflows([workflow, disabled], store, anchor,
                         datetime(2026, 7, 5, 12, 10)) == []
    assert due_workflows([workflow, disabled], store, anchor,
                         datetime(2026, 7, 5, 12, 15)) == [workflow]

    # After a recorded run (stored UTC-aware), not due again immediately.
    store.start_run("brief")
    assert due_workflows([workflow], store, anchor, datetime.now()) == []
    assert due_workflows([workflow], store, anchor,
                         datetime.now() + timedelta(minutes=16)) == [workflow]


# -- server endpoints -------------------------------------------------------------


def make_workflow_client(tmp_path, script, registry) -> tuple[TestClient, WorkflowStore]:
    runner, store, _ = make_runner(script, registry, tmp_path)
    scheduler = WorkflowScheduler(tmp_path / "wf", runner, store)
    app = create_app(lambda consent: None, TOKEN, workflows=scheduler)  # type: ignore[arg-type]
    return TestClient(app), store


def test_workflow_endpoints(tmp_path) -> None:
    registry = ToolRegistry()
    write_workflow(tmp_path / "wf")
    client, store = make_workflow_client(tmp_path, [end_turn("Done.")], registry)

    listed = client.get("/v1/workflows", headers=AUTH).json()
    assert [w["name"] for w in listed["workflows"]] == ["brief"]
    assert listed["load_error"] is None

    assert client.post("/v1/workflows/nope/run", headers=AUTH).status_code == 404
    assert client.post("/v1/workflows/brief/run", headers=AUTH).status_code == 202

    deadline = datetime.now() + timedelta(seconds=5)
    while datetime.now() < deadline:
        runs = client.get("/v1/workflows/brief/runs", headers=AUTH).json()["runs"]
        if runs and runs[0]["status"] != "running":
            break
    assert runs[0]["status"] == "ok" and runs[0]["detail"] == "Done."


def test_workflow_endpoints_surface_load_errors(tmp_path) -> None:
    registry = ToolRegistry()
    write_workflow(tmp_path / "wf", schedule="sometimes")
    client, _ = make_workflow_client(tmp_path, [], registry)
    listed = client.get("/v1/workflows", headers=AUTH).json()
    assert listed["workflows"] == [] and "sometimes" in listed["load_error"]
