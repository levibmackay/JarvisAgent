"""macOS user notifications via osascript."""

import subprocess
from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def notify(self, title: str, body: str) -> None: ...


class MacNotifier(Notifier):
    def notify(self, title: str, body: str) -> None:
        # Arguments go through argv (never string-interpolated into the
        # script), so notification text can't inject AppleScript.
        script = 'on run argv\ndisplay notification (item 2 of argv) ' \
                 "with title (item 1 of argv)\nend run"
        subprocess.run(
            ["osascript", "-e", script, title, body[:400]],
            capture_output=True, timeout=10, check=False,
        )


class NullNotifier(Notifier):
    """For tests and notify=false."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def notify(self, title: str, body: str) -> None:
        self.sent.append((title, body))
