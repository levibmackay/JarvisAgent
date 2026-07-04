"""Mail.app integration via AppleScript."""

from typing import Any

from jarvis.tools.applescript import applescript_quote, run_applescript
from jarvis.tools.base import RiskLevel, Tool


class ListEmailsTool(Tool):
    name = "list_emails"
    description = "List the most recent messages in the Mail inbox (date, sender, subject)."
    input_schema = {
        "type": "object",
        "properties": {
            "count": {"type": "integer", "description": "How many (default 10, max 25)."}
        },
        "required": [],
    }
    risk = RiskLevel.READ_ONLY

    def execute(self, params: dict[str, Any]) -> str:
        count = min(int(params.get("count", 10)), 25)
        script = f"""
        set out to ""
        tell application "Mail"
            set n to count of messages of inbox
            if n > {count} then set n to {count}
            repeat with i from 1 to n
                set m to message i of inbox
                set out to out & i & ". " & (date received of m as string) & " | " & (sender of m) & " | " & (subject of m) & linefeed
            end repeat
        end tell
        return out
        """
        result = run_applescript(script, timeout=120)
        return result or "Inbox is empty."


class ReadEmailTool(Tool):
    name = "read_email"
    description = "Read the body of an inbox message by its list_emails index (1 = newest)."
    input_schema = {
        "type": "object",
        "properties": {
            "index": {"type": "integer", "description": "Message index from list_emails."}
        },
        "required": ["index"],
    }
    risk = RiskLevel.READ_ONLY

    def execute(self, params: dict[str, Any]) -> str:
        index = int(params["index"])
        script = f"""
        tell application "Mail"
            set m to message {index} of inbox
            return (subject of m) & linefeed & "From: " & (sender of m) & linefeed & linefeed & (content of m)
        end tell
        """
        body = run_applescript(script, timeout=120)
        return body[:20_000] + ("\n…[truncated]" if len(body) > 20_000 else "")


class SendEmailTool(Tool):
    name = "send_email"
    description = "Send an email from the user's Mail account. Always confirm content first."
    input_schema = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address."},
            "subject": {"type": "string", "description": "Subject line."},
            "body": {"type": "string", "description": "Plain-text body."},
        },
        "required": ["to", "subject", "body"],
    }
    risk = RiskLevel.DESTRUCTIVE  # outward-facing: always prompts

    def execute(self, params: dict[str, Any]) -> str:
        script = f"""
        tell application "Mail"
            set msg to make new outgoing message with properties {{subject:{applescript_quote(params["subject"])}, content:{applescript_quote(params["body"])}, visible:false}}
            tell msg to make new to recipient at end of to recipients with properties {{address:{applescript_quote(params["to"])}}}
            send msg
        end tell
        return "sent"
        """
        run_applescript(script)
        return f"Sent to {params['to']}"
