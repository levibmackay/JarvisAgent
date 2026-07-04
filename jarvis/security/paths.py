"""Path confinement shared by all filesystem-touching tools."""

from pathlib import Path

from jarvis.tools.base import ToolError


def resolve_within(path_str: str, roots: list[Path]) -> Path:
    """Resolve a model-supplied path and verify it stays inside a permitted root.

    Resolution is canonical (symlinks and `..` collapsed) so traversal
    attempts are caught regardless of how the path is spelled.
    """
    path = Path(path_str).expanduser().resolve()
    for root in roots:
        if path.is_relative_to(root.expanduser().resolve()):
            return path
    raise ToolError(f"Path outside permitted roots: {path_str}")
