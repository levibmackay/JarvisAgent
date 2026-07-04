"""Trivial first tool proving the dispatch loop end to end."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jarvis.tools.base import RiskLevel, Tool, ToolError


class GetTimeTool(Tool):
    name = "get_time"
    description = "Get the current date and time, optionally in a specific IANA timezone."
    input_schema = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone, e.g. 'America/Denver'. Defaults to local time.",
            }
        },
        "required": [],
    }
    risk = RiskLevel.READ_ONLY

    def execute(self, params: dict[str, Any]) -> str:
        tz_name = params.get("timezone")
        if tz_name:
            try:
                now = datetime.now(ZoneInfo(tz_name))
            except ZoneInfoNotFoundError:
                raise ToolError(f"Unknown timezone: {tz_name}") from None
        else:
            now = datetime.now().astimezone()
        return now.strftime("%A, %B %d %Y, %H:%M:%S %Z")
