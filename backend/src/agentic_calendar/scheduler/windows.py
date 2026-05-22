"""Free-window enumeration over the planning horizon.

Given a horizon, the user's allowed hours, and existing free/busy intervals,
produce a list of contiguous "free windows" the Scheduler may consider for
placement. Windows are split by day so daily-load checks remain trivial.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from agentic_calendar.contracts.common_types import Day

from .inputs import FreeBusyInterval
from .policy import SchedulingPolicy

WEEKDAY_TO_DAY: dict[int, Day] = {
    0: Day.MON,
    1: Day.TUE,
    2: Day.WED,
    3: Day.THU,
    4: Day.FRI,
    5: Day.SAT,
    6: Day.SUN,
}
WEEKEND = {Day.SAT, Day.SUN}


@dataclass(frozen=True, slots=True)
class FreeWindow:
    """A contiguous time range the Scheduler may consider for placement."""

    start: datetime
    end: datetime
    is_deep_work: bool

    @property
    def duration_min(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


def enumerate_free_windows(
    *,
    horizon_start: datetime,
    horizon_end: datetime,
    free_busy: list[FreeBusyInterval],
    policy: SchedulingPolicy,
) -> list[FreeWindow]:
    """Return all free windows within the horizon, day-by-day, sorted ascending.

    Each day-level free window is further sliced at deep-work-window
    boundaries so the placement loop sees explicit deep / non-deep windows
    rather than a single oversized one.
    """
    if horizon_start.tzinfo is None or horizon_end.tzinfo is None:
        raise ValueError("horizon must be timezone-aware")

    sorted_busy = sorted(
        (i for i in free_busy if i.end > horizon_start and i.start < horizon_end),
        key=lambda i: i.start,
    )

    windows: list[FreeWindow] = []
    cursor = horizon_start
    while cursor < horizon_end:
        if not _day_allowed(cursor, policy):
            cursor = _next_day(cursor)
            continue
        day_start, day_end = _day_allowed_range(cursor, policy)
        day_end = min(day_end, horizon_end)
        if day_end > day_start:
            for win_start, win_end in _free_in_range(
                day_start, day_end, sorted_busy
            ):
                windows.extend(_split_by_deep_work(win_start, win_end, policy))
        cursor = _next_day(cursor)
    windows.sort(key=lambda w: w.start)
    return windows


def _next_day(dt: datetime) -> datetime:
    return (dt + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _split_by_deep_work(
    win_start: datetime, win_end: datetime, policy: SchedulingPolicy
) -> list[FreeWindow]:
    """Slice a free interval at deep-work boundaries.

    Output is a list of contiguous non-overlapping ``FreeWindow`` records
    covering ``[win_start, win_end)`` exactly, with ``is_deep_work=True`` for
    sub-ranges that fall inside a configured deep-work window.
    """
    if not policy.respect_deep_work_windows or not policy.deep_work_windows:
        return [FreeWindow(start=win_start, end=win_end, is_deep_work=False)]

    day = WEEKDAY_TO_DAY[win_start.weekday()]
    relevant = [w for w in policy.deep_work_windows if w.day is day]
    if not relevant:
        return [FreeWindow(start=win_start, end=win_end, is_deep_work=False)]

    deep_intervals: list[tuple[datetime, datetime]] = []
    for w in relevant:
        ws = datetime.combine(
            win_start.date(), _hhmm_to_time(w.start), tzinfo=win_start.tzinfo
        )
        we = datetime.combine(
            win_start.date(), _hhmm_to_time(w.end), tzinfo=win_start.tzinfo
        )
        i_start = max(ws, win_start)
        i_end = min(we, win_end)
        if i_end > i_start:
            deep_intervals.append((i_start, i_end))

    if not deep_intervals:
        return [FreeWindow(start=win_start, end=win_end, is_deep_work=False)]

    deep_intervals.sort()
    out: list[FreeWindow] = []
    cursor = win_start
    for d_start, d_end in deep_intervals:
        if d_start > cursor:
            out.append(FreeWindow(start=cursor, end=d_start, is_deep_work=False))
        out.append(FreeWindow(start=d_start, end=d_end, is_deep_work=True))
        cursor = d_end
    if cursor < win_end:
        out.append(FreeWindow(start=cursor, end=win_end, is_deep_work=False))
    return out


def _day_allowed(dt: datetime, policy: SchedulingPolicy) -> bool:
    day = WEEKDAY_TO_DAY[dt.weekday()]
    return not (day in WEEKEND and not policy.allow_weekends)


def _day_allowed_range(
    dt: datetime, policy: SchedulingPolicy
) -> tuple[datetime, datetime]:
    """Return the user-allowed start/end on the calendar day containing ``dt``."""
    day_start = datetime.combine(
        dt.date(),
        _hhmm_to_time(policy.no_events_before),
        tzinfo=dt.tzinfo,
    )
    day_end = datetime.combine(
        dt.date(),
        _hhmm_to_time(policy.no_events_after),
        tzinfo=dt.tzinfo,
    )
    return day_start, day_end


def _free_in_range(
    range_start: datetime,
    range_end: datetime,
    sorted_busy: list[FreeBusyInterval],
) -> list[tuple[datetime, datetime]]:
    """Return free intervals inside ``[range_start, range_end)``."""
    free: list[tuple[datetime, datetime]] = []
    cursor = range_start
    for busy in sorted_busy:
        if busy.end <= range_start or busy.start >= range_end:
            continue
        b_start = max(busy.start, range_start)
        b_end = min(busy.end, range_end)
        if b_start > cursor:
            free.append((cursor, b_start))
        cursor = max(cursor, b_end)
    if cursor < range_end:
        free.append((cursor, range_end))
    return [interval for interval in free if interval[1] > interval[0]]


def _hhmm_to_time(hhmm: str) -> time:
    hh, mm = hhmm.split(":")
    return time(int(hh), int(mm))
