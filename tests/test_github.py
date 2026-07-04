import subprocess
from pathlib import Path

import pytest

from jarvis.tools.base import RiskLevel, ToolError
from jarvis.tools.github import GitHubTool


@pytest.fixture
def gh(tmp_path: Path) -> GitHubTool:
    return GitHubTool(roots=[tmp_path], timeout=5)


@pytest.mark.parametrize(
    "args",
    ["pr list", "pr view 42", "issue list --repo o/r", "repo view", "run list",
     "search repos jarvis", "status", "auth status"],
)
def test_read_only_commands(gh: GitHubTool, args: str) -> None:
    assert gh.classify({"args": args}) is RiskLevel.READ_ONLY


@pytest.mark.parametrize(
    "args",
    ["pr create --title x", "pr merge 42", "issue close 7", "repo delete o/r",
     "api -X POST /repos", "release create v1", "", 'pr "unclosed'],
)
def test_mutating_commands_require_consent(gh: GitHubTool, args: str) -> None:
    assert gh.classify({"args": args}) is RiskLevel.DESTRUCTIVE


def test_execute_success(gh: GitHubTool, tmp_path: Path, monkeypatch) -> None:
    def fake_run(argv, **kwargs):
        assert argv == ["gh", "pr", "list"]
        return subprocess.CompletedProcess(argv, 0, stdout="#1 Fix bug", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = gh.execute({"args": "pr list", "working_dir": str(tmp_path)})
    assert out == "#1 Fix bug"


def test_execute_failure_raises(gh: GitHubTool, tmp_path: Path, monkeypatch) -> None:
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="not authenticated")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ToolError, match="not authenticated"):
        gh.execute({"args": "pr list", "working_dir": str(tmp_path)})


def test_missing_gh_binary(gh: GitHubTool, tmp_path: Path, monkeypatch) -> None:
    def fake_run(argv, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ToolError, match="brew install gh"):
        gh.execute({"args": "pr list", "working_dir": str(tmp_path)})


def test_working_dir_confined(gh: GitHubTool) -> None:
    with pytest.raises(ToolError, match="outside permitted roots"):
        gh.execute({"args": "pr list", "working_dir": "/etc"})
