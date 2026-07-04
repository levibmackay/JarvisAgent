from pathlib import Path

import pytest

from jarvis.tools.base import RiskLevel, ToolError
from jarvis.tools.files import EditFileTool, ReadFileTool, WriteFileTool


@pytest.fixture
def roots(tmp_path: Path) -> list[Path]:
    return [tmp_path]


def test_write_read_roundtrip(roots: list[Path], tmp_path: Path) -> None:
    write, read = WriteFileTool(roots), ReadFileTool(roots)
    write.execute({"path": str(tmp_path / "sub" / "a.txt"), "content": "hello"})
    assert read.execute({"path": str(tmp_path / "sub" / "a.txt")}) == "hello"


def test_write_classify_new_vs_overwrite(roots: list[Path], tmp_path: Path) -> None:
    write = WriteFileTool(roots)
    target = str(tmp_path / "a.txt")
    assert write.classify({"path": target}) is RiskLevel.REVERSIBLE
    write.execute({"path": target, "content": "x"})
    assert write.classify({"path": target}) is RiskLevel.DESTRUCTIVE


def test_edit_exact_once(roots: list[Path], tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("one two three")
    EditFileTool(roots).execute(
        {"path": str(target), "old_str": "two", "new_str": "2"}
    )
    assert target.read_text() == "one 2 three"


def test_edit_rejects_ambiguous(roots: list[Path], tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("dup dup")
    with pytest.raises(ToolError, match="2 times"):
        EditFileTool(roots).execute({"path": str(target), "old_str": "dup", "new_str": "x"})


def test_edit_rejects_missing(roots: list[Path], tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_text("abc")
    with pytest.raises(ToolError, match="not found"):
        EditFileTool(roots).execute({"path": str(target), "old_str": "zzz", "new_str": "x"})


def test_read_outside_roots_rejected(roots: list[Path]) -> None:
    with pytest.raises(ToolError, match="outside permitted roots"):
        ReadFileTool(roots).execute({"path": "/etc/hosts"})


def test_read_missing_file(roots: list[Path], tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="Not a file"):
        ReadFileTool(roots).execute({"path": str(tmp_path / "nope.txt")})
