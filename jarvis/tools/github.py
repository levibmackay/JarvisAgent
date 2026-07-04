"""GitHub integration via the `gh` CLI.

Runs without a shell (argv exec), so no metacharacter risk. Read-only
subcommands are auto-allowed; anything that can mutate GitHub state
(pr create, issue close, api, ...) prompts for consent.
"""

import shlex
import subprocess
from pathlib import Path
from typing import Any

from jarvis.security.paths import resolve_within
from jarvis.tools.base import RiskLevel, Tool, ToolError

_READ_ONLY = frozenset(
    {
        ("pr", "list"), ("pr", "view"), ("pr", "status"), ("pr", "diff"), ("pr", "checks"),
        ("issue", "list"), ("issue", "view"), ("issue", "status"),
        ("repo", "view"), ("repo", "list"),
        ("run", "list"), ("run", "view"),
        ("release", "list"), ("release", "view"),
        ("gist", "list"), ("gist", "view"),
        ("search", None), ("status", None), ("auth", "status"),
    }
)


class GitHubTool(Tool):
    name = "github"
    description = (
        "Run a GitHub CLI (gh) command for PRs, issues, repos, and CI runs. "
        "Pass arguments only, without the leading 'gh' — e.g. 'pr list' or "
        "'issue view 42 --repo owner/name'."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "args": {"type": "string", "description": "gh arguments, e.g. 'pr list'."},
            "working_dir": {
                "type": "string",
                "description": "Repo directory for repo-context commands. Defaults to home.",
            },
        },
        "required": ["args"],
    }
    risk = RiskLevel.DESTRUCTIVE

    def __init__(self, roots: list[Path], timeout: int = 60, max_output: int = 20_000) -> None:
        self._roots = roots
        self._timeout = timeout
        self._max_output = max_output

    def classify(self, params: dict[str, Any]) -> RiskLevel:
        try:
            argv = shlex.split(params.get("args", ""))
        except ValueError:
            return RiskLevel.DESTRUCTIVE
        if not argv:
            return RiskLevel.DESTRUCTIVE
        cmd = argv[0]
        sub = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else None
        if (cmd, sub) in _READ_ONLY or (cmd, None) in _READ_ONLY:
            return RiskLevel.READ_ONLY
        return RiskLevel.DESTRUCTIVE

    def execute(self, params: dict[str, Any]) -> str:
        try:
            argv = shlex.split(params["args"])
        except ValueError as exc:
            raise ToolError(f"Cannot parse args: {exc}") from None
        if not argv:
            raise ToolError("Empty gh command")
        cwd = resolve_within(params.get("working_dir", "~"), self._roots)
        try:
            proc = subprocess.run(
                ["gh", *argv],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=cwd,
            )
        except FileNotFoundError:
            raise ToolError("GitHub CLI not installed. Install with: brew install gh") from None
        except subprocess.TimeoutExpired:
            raise ToolError(f"gh timed out after {self._timeout}s") from None

        output = proc.stdout + (f"\n[stderr]\n{proc.stderr}" if proc.stderr else "")
        if len(output) > self._max_output:
            output = output[: self._max_output] + "\n…[output truncated]"
        if proc.returncode != 0:
            raise ToolError(f"Exit code {proc.returncode}\n{output}")
        return output or "(no output)"
