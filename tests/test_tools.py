import pytest

from jarvis.tools.base import RiskLevel, ToolError, ToolRegistry
from jarvis.tools.builtin.time import GetTimeTool


@pytest.fixture
def registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(GetTimeTool())
    return r


def test_get_time_local(registry: ToolRegistry) -> None:
    out = registry.execute("get_time", {})
    assert any(day in out for day in ("Monday", "Tuesday", "Wednesday", "Thursday",
                                      "Friday", "Saturday", "Sunday"))


def test_get_time_with_timezone(registry: ToolRegistry) -> None:
    out = registry.execute("get_time", {"timezone": "UTC"})
    assert "UTC" in out


def test_get_time_bad_timezone(registry: ToolRegistry) -> None:
    with pytest.raises(ToolError, match="Unknown timezone"):
        registry.execute("get_time", {"timezone": "Not/AZone"})


def test_unknown_tool(registry: ToolRegistry) -> None:
    with pytest.raises(ToolError, match="Unknown tool"):
        registry.execute("nope", {})


def test_duplicate_registration(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError, match="already registered"):
        registry.register(GetTimeTool())


def test_schemas_shape(registry: ToolRegistry) -> None:
    (schema,) = registry.schemas()
    assert schema["name"] == "get_time"
    assert schema["input_schema"]["type"] == "object"


def test_risk_level_declared() -> None:
    assert GetTimeTool().risk is RiskLevel.READ_ONLY
