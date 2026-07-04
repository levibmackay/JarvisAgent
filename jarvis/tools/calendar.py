"""Calendar.app integration via AppleScript."""

from datetime import datetime
from typing import Any

from jarvis.tools.applescript import applescript_quote, run_applescript
from jarvis.tools.base import RiskLevel, Tool, ToolError


class ListEventsTool(Tool):
    name = "list_events"
    description = "List calendar events from today through the next N days."
    input_schema = {
        "type": "object",
        "properties": {
            "days_ahead": {
                "type": "integer",
                "description": "How many days ahead to include (default 7, max 60).",
            }
        },
        "required": [],
    }
    risk = RiskLevel.READ_ONLY

    def execute(self, params: dict[str, Any]) -> str:
        days = min(int(params.get("days_ahead", 7)), 60)
        script = f"""
        set windowStart to (current date) - (time of (current date))
        set windowEnd to windowStart + ({days} * days) + 1 * days
        set out to ""
        tell application "Calendar"
            repeat with cal in calendars
                repeat with ev in (every event of cal whose start date is greater than or equal to windowStart and start date is less than windowEnd)
                    set out to out & (start date of ev as string) & " | " & (summary of ev) & linefeed
                end repeat
            end repeat
        end tell
        return out
        """
        result = run_applescript(script, timeout=120)
        return result or "No events in that window."


class CreateEventTool(Tool):
    name = "create_event"
    description = "Create a calendar event. Times are local, format 'YYYY-MM-DD HH:MM'."
    input_schema = {
        "type": "object",
        "properties": {
            "calendar": {"type": "string", "description": "Calendar name, e.g. 'Home'."},
            "title": {"type": "string", "description": "Event title."},
            "start": {"type": "string", "description": "Start, 'YYYY-MM-DD HH:MM'."},
            "end": {"type": "string", "description": "End, 'YYYY-MM-DD HH:MM'."},
        },
        "required": ["calendar", "title", "start", "end"],
    }
    risk = RiskLevel.REVERSIBLE

    @staticmethod
    def _as_applescript_date(var: str, value: str) -> str:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError:
            raise ToolError(f"Bad datetime '{value}', expected 'YYYY-MM-DD HH:MM'") from None
        return (
            f"set {var} to current date\n"
            f"set year of {var} to {dt.year}\n"
            f"set month of {var} to {dt.month}\n"
            f"set day of {var} to {dt.day}\n"
            f"set hours of {var} to {dt.hour}\n"
            f"set minutes of {var} to {dt.minute}\n"
            f"set seconds of {var} to 0\n"
        )

    def execute(self, params: dict[str, Any]) -> str:
        script = (
            self._as_applescript_date("d1", params["start"])
            + self._as_applescript_date("d2", params["end"])
            + f"""
        tell application "Calendar"
            tell calendar {applescript_quote(params["calendar"])}
                make new event with properties {{summary:{applescript_quote(params["title"])}, start date:d1, end date:d2}}
            end tell
        end tell
        return "created"
        """
        )
        run_applescript(script)
        return f"Created '{params['title']}' on {params['start']}"
