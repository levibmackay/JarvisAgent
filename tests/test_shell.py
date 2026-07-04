from pathlib import Path

import pytest

from jarvis.tools.base import RiskLevel, ToolError
from jarvis.tools.shell import ShellTool


@pytest.fixture
def shell(tmp_path: Path) -> ShellTool:
    return ShellTool(roots=[tmp_path], timeout=5, max_output=200)


@pytest.mark.parametrize("cmd", ["ls -la", "pwd", "date", "df -h", "wc -l notes.txt"])
def test_benign_commands_are_read_only(shell: ShellTool, cmd: str) -> None:
    assert shell.classify({"command": cmd}) is RiskLevel.READ_ONLY


@pytest.mark.parametrize(
    "cmd",
    [
        "rm -rf /tmp/x",            # mutating binary
        "cat secrets.txt",          # reads file contents — not auto-allowed
        "ls | grep foo",            # pipe
        "date; rm x",               # command chaining
        "echo $(whoami)",           # substitution
        'ls "unclosed',             # unparseable
    ],
)
def test_risky_commands_require_consent(shell: ShellTool, cmd: str) -> None:
    assert shell.classify({"command": cmd}) is RiskLevel.DESTRUCTIVE


def test_execute_captures_output(shell: ShellTool, tmp_path: Path) -> None:
    out = shell.execute({"command": "pwd", "working_dir": str(tmp_path)})
    assert str(tmp_path) in out


def test_execute_nonzero_exit_raises(shell: ShellTool, tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="Exit code"):
        shell.execute({"command": "false", "working_dir": str(tmp_path)})


def test_execute_truncates_long_output(shell: ShellTool, tmp_path: Path) -> None:
    out = shell.execute({"command": "yes | head -500", "working_dir": str(tmp_path)})
    assert "[output truncated]" in out


def test_working_dir_confined(shell: ShellTool) -> None:
    with pytest.raises(ToolError, match="outside permitted roots"):
        shell.execute({"command": "pwd", "working_dir": "/etc"})
