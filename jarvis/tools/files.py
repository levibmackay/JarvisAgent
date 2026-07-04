"""File tools, confined to permitted roots via resolve_within."""

from pathlib import Path
from typing import Any

from jarvis.security.paths import resolve_within
from jarvis.tools.base import RiskLevel, Tool, ToolError


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a text file from the user's Mac."
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "File path."}},
        "required": ["path"],
    }
    risk = RiskLevel.READ_ONLY

    def __init__(self, roots: list[Path], max_chars: int = 50_000) -> None:
        self._roots = roots
        self._max_chars = max_chars

    def execute(self, params: dict[str, Any]) -> str:
        path = resolve_within(params["path"], self._roots)
        if not path.is_file():
            raise ToolError(f"Not a file: {params['path']}")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ToolError(f"Cannot read {params['path']}: {exc}") from None
        if len(text) > self._max_chars:
            text = text[: self._max_chars] + "\n…[truncated]"
        return text


class WriteFileTool(Tool):
    name = "write_file"
    description = "Create or overwrite a text file. Parent directories are created."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path."},
            "content": {"type": "string", "description": "Full file content."},
        },
        "required": ["path", "content"],
    }
    risk = RiskLevel.REVERSIBLE

    def __init__(self, roots: list[Path]) -> None:
        self._roots = roots

    def classify(self, params: dict[str, Any]) -> RiskLevel:
        try:
            path = resolve_within(params.get("path", ""), self._roots)
        except ToolError:
            return self.risk  # confinement error surfaces at execute()
        return RiskLevel.DESTRUCTIVE if path.exists() else RiskLevel.REVERSIBLE

    def execute(self, params: dict[str, Any]) -> str:
        path = resolve_within(params["path"], self._roots)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(params["content"], encoding="utf-8")
        return f"Wrote {len(params['content'])} chars to {path}"


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "Replace an exact string in a text file. old_str must occur exactly once; "
        "include surrounding lines to disambiguate."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path."},
            "old_str": {"type": "string", "description": "Exact text to replace."},
            "new_str": {"type": "string", "description": "Replacement text."},
        },
        "required": ["path", "old_str", "new_str"],
    }
    risk = RiskLevel.REVERSIBLE

    def __init__(self, roots: list[Path]) -> None:
        self._roots = roots

    def execute(self, params: dict[str, Any]) -> str:
        path = resolve_within(params["path"], self._roots)
        if not path.is_file():
            raise ToolError(f"Not a file: {params['path']}")
        text = path.read_text(encoding="utf-8")
        count = text.count(params["old_str"])
        if count == 0:
            raise ToolError("old_str not found in file")
        if count > 1:
            raise ToolError(f"old_str occurs {count} times; provide more context")
        path.write_text(text.replace(params["old_str"], params["new_str"]), encoding="utf-8")
        return f"Edited {path}"
