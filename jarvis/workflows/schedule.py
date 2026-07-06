"""Tiny schedule grammar — three forms, no cron dependency:

    every 15m | every 2h        interval
    daily 08:00                 once a day at local time
    weekly mon 09:00            once a week

All datetimes are naive local time (this runs on the user's Mac).
"""

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta

_WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_INTERVAL = re.compile(r"^every (\d+)([mh])$")
_DAILY = re.compile(r"^daily (\d{2}):(\d{2})$")
_WEEKLY = re.compile(rf"^weekly ({'|'.join(_WEEKDAYS)}) (\d{{2}}):(\d{{2}})$")


class ScheduleError(ValueError):
    """Unparseable or out-of-range schedule text."""


@dataclass(frozen=True)
class Schedule:
    text: str
    interval: timedelta | None = None
    at: time | None = None
    weekday: int | None = None  # 0 = Monday

    @classmethod
    def parse(cls, text: str) -> "Schedule":
        text = text.strip().lower()
        if m := _INTERVAL.match(text):
            amount, unit = int(m.group(1)), m.group(2)
            if amount == 0:
                raise ScheduleError(f"Zero interval: {text!r}")
            return cls(text, interval=timedelta(minutes=amount) if unit == "m"
                       else timedelta(hours=amount))
        if m := _DAILY.match(text):
            return cls(text, at=_time(m.group(1), m.group(2), text))
        if m := _WEEKLY.match(text):
            return cls(text, at=_time(m.group(2), m.group(3), text),
                       weekday=_WEEKDAYS.index(m.group(1)))
        raise ScheduleError(
            f"Bad schedule {text!r} — use 'every 15m', 'daily 08:00', or 'weekly mon 09:00'"
        )

    def next_run(self, after: datetime) -> datetime:
        if self.interval is not None:
            return after + self.interval
        assert self.at is not None
        candidate = datetime.combine(after.date(), self.at)
        step = timedelta(days=1)
        while candidate <= after or (
            self.weekday is not None and candidate.weekday() != self.weekday
        ):
            candidate += step
        return candidate


def _time(hh: str, mm: str, text: str) -> time:
    try:
        return time(int(hh), int(mm))
    except ValueError:
        raise ScheduleError(f"Bad time in schedule {text!r}") from None
