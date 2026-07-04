"""Shared AppleScript execution for macOS app integration (Calendar, Mail).

First use of each app triggers a one-time macOS automation permission dialog.
"""

import subprocess

from jarvis.tools.base import ToolError


def applescript_quote(text: str) -> str:
    """Quote untrusted text for embedding in an AppleScript string literal."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def run_applescript(script: str, timeout: int = 60) -> str:
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ToolError(f"AppleScript timed out after {timeout}s") from None
    if proc.returncode != 0:
        err = proc.stderr.strip()
        if "-1743" in err:
            raise ToolError(
                "macOS denied automation access. Grant it in System Settings → "
                "Privacy & Security → Automation."
            )
        raise ToolError(f"AppleScript failed: {err[:300]}")
    return proc.stdout.strip()
