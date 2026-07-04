"""Calendar/email tool tests — AppleScript runner is stubbed (real osascript
would trigger macOS permission dialogs)."""

import subprocess

import pytest

import jarvis.tools.calendar as calendar_mod
import jarvis.tools.email as email_mod
from jarvis.tools.applescript import applescript_quote, run_applescript
from jarvis.tools.base import RiskLevel, ToolError
from jarvis.tools.calendar import CreateEventTool, ListEventsTool
from jarvis.tools.email import ListEmailsTool, ReadEmailTool, SendEmailTool


def test_quote_escapes_injection() -> None:
    hostile = 'x" & (do shell script "rm -rf ~") & "'
    quoted = applescript_quote(hostile)
    assert quoted.startswith('"') and quoted.endswith('"')
    assert '\\"' in quoted and '" &' not in quoted[1:-1].replace('\\"', "")


def test_quote_escapes_backslashes() -> None:
    assert applescript_quote('a\\"b') == '"a\\\\\\"b"'


def test_run_applescript_permission_denied(monkeypatch) -> None:
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="error -1743")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(ToolError, match="Privacy & Security"):
        run_applescript("tell application \"Calendar\" to count calendars")


def test_risk_tiers() -> None:
    assert ListEventsTool().risk is RiskLevel.READ_ONLY
    assert CreateEventTool().risk is RiskLevel.REVERSIBLE
    assert ListEmailsTool().risk is RiskLevel.READ_ONLY
    assert ReadEmailTool().risk is RiskLevel.READ_ONLY
    assert SendEmailTool().risk is RiskLevel.DESTRUCTIVE


def test_create_event_script(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        calendar_mod, "run_applescript",
        lambda script, timeout=60: captured.setdefault("script", script) or "created",
    )
    out = CreateEventTool().execute(
        {"calendar": "Home", "title": 'Demo "day"', "start": "2026-07-10 14:00",
         "end": "2026-07-10 15:00"}
    )
    assert "Created" in out
    script = captured["script"]
    assert "set year of d1 to 2026" in script
    assert "set hours of d2 to 15" in script
    assert '\\"day\\"' in script  # title quoted safely


def test_create_event_rejects_bad_date() -> None:
    with pytest.raises(ToolError, match="Bad datetime"):
        CreateEventTool().execute(
            {"calendar": "Home", "title": "x", "start": "tomorrow", "end": "2026-01-01 10:00"}
        )


def test_list_events_caps_window(monkeypatch) -> None:
    captured: dict = {}

    def fake_run(script, timeout=60):
        captured["script"] = script
        return ""

    monkeypatch.setattr(calendar_mod, "run_applescript", fake_run)
    assert "No events" in ListEventsTool().execute({"days_ahead": 500})
    assert "(60 * days)" in captured["script"]


def test_list_emails_caps_count(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        email_mod, "run_applescript",
        lambda script, timeout=60: captured.setdefault("script", script) or "1. mail",
    )
    ListEmailsTool().execute({"count": 999})
    assert "if n > 25 then set n to 25" in captured["script"]


def test_send_email_script(monkeypatch) -> None:
    captured: dict = {}
    monkeypatch.setattr(
        email_mod, "run_applescript",
        lambda script, timeout=60: captured.setdefault("script", script) or "sent",
    )
    out = SendEmailTool().execute(
        {"to": "a@b.com", "subject": "Hi", "body": "line1\nline2"}
    )
    assert out == "Sent to a@b.com"
    assert 'address:"a@b.com"' in captured["script"]
    assert "send msg" in captured["script"]
