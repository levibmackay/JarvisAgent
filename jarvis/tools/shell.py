"""Shell execution tool — consent-gated unless provably benign.

Classification: a command is READ_ONLY (auto-allowed) only if it parses
cleanly, contains no shell metacharacters, and its binary is on a small
benign allowlist. Everything else is DESTRUCTIVE and prompts the user,
who sees the exact command before it runs.
"""

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from jarvis.security.paths import resolve_within
from jarvis.tools.base import RiskLevel, Tool, ToolError

# Binaries that neither mutate state nor read file contents.
_READ_ONLY_BINARIES = frozenset(
    {"ls", "pwd", "date", "whoami", "uname", "df", "du", "stat", "file", "which", "wc", "ps"}
)
_SHELL_META = re.compile(r"[|;&<>`$\n]")


class ShellTool(Tool):
    name = "run_shell"
    description = (
        "Run a shell command on the user's Mac (zsh). Use for system tasks the "
        "dedicated file tools don't cover. Output is truncated if long."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to run."},
            "working_dir": {
                "type": "string",
                "description": "Directory to run in. Defaults to the user's home.",
            },
        },
        "required": ["command"],
    }
    risk = RiskLevel.DESTRUCTIVE

    def __init__(self, roots: list[Path], timeout: int = 30, max_output: int = 10_000) -> None:
        self._roots = roots
        self._timeout = timeout
        self._max_output = max_output

    def classify(self, params: dict[str, Any]) -> RiskLevel:
        command = params.get("command", "")
        if _SHELL_META.search(command):
            return RiskLevel.DESTRUCTIVE
        try:
            argv = shlex.split(command)
        except ValueError:
            return RiskLevel.DESTRUCTIVE
        if argv and Path(argv[0]).name in _READ_ONLY_BINARIES:
            return RiskLevel.READ_ONLY
        return RiskLevel.DESTRUCTIVE

    def execute(self, params: dict[str, Any]) -> str:
        command = params["command"]
        cwd = resolve_within(params.get("working_dir", "~"), self._roots)
        try:
            proc = subprocess.run(
                ["/bin/zsh", "-c", command],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            raise ToolError(f"Command timed out after {self._timeout}s") from None

        output = proc.stdout + (f"\n[stderr]\n{proc.stderr}" if proc.stderr else "")
        if len(output) > self._max_output:
            output = output[: self._max_output] + "\n…[output truncated]"
        if proc.returncode != 0:
            raise ToolError(f"Exit code {proc.returncode}\n{output}")
        return output or "(no output)"
