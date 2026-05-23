"""Visual schedule inspector - operator CLI.

Renders a ``SchedulerInput`` + ``SchedulerOutput`` as a self-contained
HTML/SVG diagnostic so the user can eyeball whether placements respect
allowed hours, deep-work windows, daily caps, and free/busy blocks, and
see *why* tasks were rejected when they were.

Phase 1 read-only - does not call calendar APIs, does not modify any
artefact. Mirrors the operator-CLI pattern used by ``export_schemas``.

Determinism: ``render_schedule_html`` is a pure function. Same inputs
produce a byte-identical HTML string (no clock, no filesystem, no
randomness).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from html import escape as _esc
from pathlib import Path
from typing import Any

from agentic_calendar.contracts.common_types import Day, FocusLevel
from agentic_calendar.contracts.scheduler_output import (
    ScheduledTask,
    SchedulerOutput,
)
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.scheduler import schedule
from agentic_calendar.scheduler.inputs import FreeBusyInterval, SchedulerInput
from agentic_calendar.scheduler.policy import (
    DeepWorkWindowPolicy,
    SchedulingPolicy,
)

# ---------------------------------------------------------------------------
# Built-in scenarios
# ---------------------------------------------------------------------------
#
# Each scenario constructs a ``SchedulerInput`` inline. We deliberately do not
# import from ``tests/fixtures`` because ``src/`` must not depend on ``tests/``.


@dataclass(frozen=True, slots=True)
class Scenario:
    """One named, self-contained example for the visualizer."""

    name: str
    description: str
    build: Callable[[], SchedulerInput]


_MONDAY_UTC = datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)
"""A pinned Monday so deep-work-window day-of-week math is reproducible."""


def _scenario_success() -> SchedulerInput:
    plan = TaskPlan.model_validate(
        {
            "plan_version": "plan_success",
            "tasks": [
                {
                    "task_id": "dp_001",
                    "module_id": "dp",
                    "title": "Deep work: DP review",
                    "dependencies": [],
                    "estimated_duration_min": 60,
                    "cognitive_load": 4,
                    "category": "concept_review",
                    "required_focus_level": "deep",
                    "splittable": False,
                },
                {
                    "task_id": "review_001",
                    "module_id": "dp",
                    "title": "Light review",
                    "dependencies": [],
                    "estimated_duration_min": 45,
                    "cognitive_load": 2,
                    "category": "review",
                    "required_focus_level": "light",
                    "splittable": False,
                },
            ],
        }
    )
    policy = SchedulingPolicy(
        no_events_before="08:00",
        no_events_after="22:30",
        allow_weekends=True,
        min_break_between_deep_blocks_min=30,
        max_daily_study_min=240,
        respect_deep_work_windows=True,
        deep_work_windows=[
            DeepWorkWindowPolicy(day=Day.MON, start="18:00", end="21:00"),
            DeepWorkWindowPolicy(day=Day.TUE, start="18:00", end="21:00"),
        ],
        max_session_length_min=120,
    )
    return SchedulerInput(
        run_id="run_success",
        plan_version="plan_success",
        plan=plan,
        policy=policy,
        calendar_free_busy=[],
        completed_task_ids=[],
        horizon_start=_MONDAY_UTC,
        horizon_end=_MONDAY_UTC + timedelta(days=3),
    )


def _scenario_fragmented() -> SchedulerInput:
    """90-min task vs two 60-min windows -> ``NO_VALID_CONTIGUOUS_BLOCK``."""
    plan = TaskPlan.model_validate(
        {
            "plan_version": "plan_fragmented",
            "tasks": [
                {
                    "task_id": "api_001",
                    "module_id": "api_design",
                    "title": "API design practice",
                    "dependencies": [],
                    "estimated_duration_min": 90,
                    "cognitive_load": 4,
                    "category": "practice",
                    "required_focus_level": "medium",
                    "splittable": True,
                }
            ],
        }
    )
    policy = SchedulingPolicy(
        no_events_before="20:00",
        no_events_after="21:00",
        allow_weekends=True,
        min_break_between_deep_blocks_min=30,
        max_daily_study_min=240,
        respect_deep_work_windows=False,
        deep_work_windows=[],
        max_session_length_min=120,
    )
    return SchedulerInput(
        run_id="run_fragmented",
        plan_version="plan_fragmented",
        plan=plan,
        policy=policy,
        calendar_free_busy=[],
        completed_task_ids=[],
        horizon_start=_MONDAY_UTC,
        horizon_end=_MONDAY_UTC + timedelta(days=2),
    )


def _scenario_over_capacity() -> SchedulerInput:
    """Total required minutes far exceed availability -> capacity promotion."""
    plan = TaskPlan.model_validate(
        {
            "plan_version": "plan_over_capacity",
            "tasks": [
                {
                    "task_id": f"t_{i}",
                    "module_id": "dp",
                    "title": f"Practice block {i}",
                    "dependencies": [],
                    "estimated_duration_min": 120,
                    "cognitive_load": 3,
                    "category": "practice",
                    "required_focus_level": "medium",
                    "splittable": True,
                }
                for i in range(4)
            ],
        }
    )
    policy = SchedulingPolicy(
        no_events_before="20:00",
        no_events_after="21:00",
        allow_weekends=True,
        min_break_between_deep_blocks_min=30,
        max_daily_study_min=240,
        respect_deep_work_windows=False,
        deep_work_windows=[],
        max_session_length_min=120,
    )
    return SchedulerInput(
        run_id="run_over_capacity",
        plan_version="plan_over_capacity",
        plan=plan,
        policy=policy,
        calendar_free_busy=[],
        completed_task_ids=[],
        horizon_start=_MONDAY_UTC,
        horizon_end=_MONDAY_UTC + timedelta(days=3),
    )


def _scenario_task_too_long() -> SchedulerInput:
    """One unsplittable task longer than ``max_session_length_min``."""
    plan = TaskPlan.model_validate(
        {
            "plan_version": "plan_too_long",
            "tasks": [
                {
                    "task_id": "huge",
                    "module_id": "dp",
                    "title": "Marathon study session",
                    "dependencies": [],
                    "estimated_duration_min": 200,
                    "cognitive_load": 5,
                    "category": "practice",
                    "required_focus_level": "deep",
                    "splittable": False,
                }
            ],
        }
    )
    policy = SchedulingPolicy(
        no_events_before="08:00",
        no_events_after="22:30",
        allow_weekends=True,
        min_break_between_deep_blocks_min=30,
        max_daily_study_min=240,
        respect_deep_work_windows=False,
        deep_work_windows=[],
        max_session_length_min=120,
    )
    return SchedulerInput(
        run_id="run_too_long",
        plan_version="plan_too_long",
        plan=plan,
        policy=policy,
        calendar_free_busy=[],
        completed_task_ids=[],
        horizon_start=_MONDAY_UTC,
        horizon_end=_MONDAY_UTC + timedelta(days=2),
    )


def _scenario_deep_work_blocked() -> SchedulerInput:
    """Deep task with no configured deep-work windows."""
    plan = TaskPlan.model_validate(
        {
            "plan_version": "plan_deep_blocked",
            "tasks": [
                {
                    "task_id": "deep_001",
                    "module_id": "dp",
                    "title": "Needs deep focus",
                    "dependencies": [],
                    "estimated_duration_min": 60,
                    "cognitive_load": 5,
                    "category": "concept_review",
                    "required_focus_level": "deep",
                    "splittable": False,
                }
            ],
        }
    )
    policy = SchedulingPolicy(
        no_events_before="08:00",
        no_events_after="22:30",
        allow_weekends=True,
        min_break_between_deep_blocks_min=30,
        max_daily_study_min=240,
        respect_deep_work_windows=True,
        deep_work_windows=[],
        max_session_length_min=120,
    )
    return SchedulerInput(
        run_id="run_deep_blocked",
        plan_version="plan_deep_blocked",
        plan=plan,
        policy=policy,
        calendar_free_busy=[],
        completed_task_ids=[],
        horizon_start=_MONDAY_UTC,
        horizon_end=_MONDAY_UTC + timedelta(days=2),
    )


def _scenario_partial_failure() -> SchedulerInput:
    """One placeable + one unsplittable monster, plus a real busy block."""
    plan = TaskPlan.model_validate(
        {
            "plan_version": "plan_partial",
            "tasks": [
                {
                    "task_id": "ok",
                    "module_id": "dp",
                    "title": "Normal task",
                    "dependencies": [],
                    "estimated_duration_min": 60,
                    "cognitive_load": 3,
                    "category": "practice",
                    "required_focus_level": "medium",
                    "splittable": False,
                },
                {
                    "task_id": "huge",
                    "module_id": "dp",
                    "title": "Too big to split",
                    "dependencies": [],
                    "estimated_duration_min": 200,
                    "cognitive_load": 5,
                    "category": "practice",
                    "required_focus_level": "medium",
                    "splittable": False,
                },
            ],
        }
    )
    policy = SchedulingPolicy(
        no_events_before="08:00",
        no_events_after="22:30",
        allow_weekends=True,
        min_break_between_deep_blocks_min=30,
        max_daily_study_min=240,
        respect_deep_work_windows=False,
        deep_work_windows=[],
        max_session_length_min=120,
    )
    return SchedulerInput(
        run_id="run_partial",
        plan_version="plan_partial",
        plan=plan,
        policy=policy,
        calendar_free_busy=[
            FreeBusyInterval(
                start=_MONDAY_UTC + timedelta(hours=10),
                end=_MONDAY_UTC + timedelta(hours=12),
            )
        ],
        completed_task_ids=[],
        horizon_start=_MONDAY_UTC,
        horizon_end=_MONDAY_UTC + timedelta(days=2),
    )


SCENARIOS: dict[str, Scenario] = {
    "success": Scenario(
        name="success",
        description=(
            "Clean weekday schedule; the deep task lands inside the Monday "
            "18:00-21:00 deep-work window."
        ),
        build=_scenario_success,
    ),
    "fragmented": Scenario(
        name="fragmented",
        description=(
            "A 90-minute task against two 60-minute free windows -> "
            "NO_VALID_CONTIGUOUS_BLOCK with the split_task repair hint."
        ),
        build=_scenario_fragmented,
    ),
    "over_capacity": Scenario(
        name="over_capacity",
        description=(
            "Total required minutes exceed available capacity -> the "
            "capacity-promotion path emits INSUFFICIENT_WEEKLY_CAPACITY."
        ),
        build=_scenario_over_capacity,
    ),
    "task_too_long": Scenario(
        name="task_too_long",
        description=(
            "Unsplittable task longer than max_session_length_min -> "
            "TASK_TOO_LONG_UNSPLITTABLE with ask_user repair."
        ),
        build=_scenario_task_too_long,
    ),
    "deep_work_blocked": Scenario(
        name="deep_work_blocked",
        description=(
            "Deep-focus task with no configured deep-work windows -> "
            "DEEP_WORK_REQUIRED_UNAVAILABLE."
        ),
        build=_scenario_deep_work_blocked,
    ),
    "partial_failure": Scenario(
        name="partial_failure",
        description=(
            "One placeable task plus one unsplittable monster and a real "
            "busy block -> partial_failure with repair options."
        ),
        build=_scenario_partial_failure,
    ),
}


# ---------------------------------------------------------------------------
# HTML / SVG rendering
# ---------------------------------------------------------------------------

_PX_PER_MINUTE = 1.2
_DAY_COLUMN_WIDTH = 200
_DAY_COLUMN_GAP = 12
_GRID_PADDING_LEFT = 64
_GRID_PADDING_TOP = 32

_WEEKDAY_TO_DAY: dict[int, Day] = {
    0: Day.MON,
    1: Day.TUE,
    2: Day.WED,
    3: Day.THU,
    4: Day.FRI,
    5: Day.SAT,
    6: Day.SUN,
}

_FOCUS_FILL: dict[FocusLevel, str] = {
    FocusLevel.DEEP: "#2563eb",
    FocusLevel.MEDIUM: "#0d9488",
    FocusLevel.LIGHT: "#65a30d",
}


def render_schedule_html(
    *,
    scheduler_input: SchedulerInput,
    scheduler_output: SchedulerOutput,
    title: str = "",
) -> str:
    """Render input + output as a self-contained HTML document.

    Pure function - no clock, no filesystem, no randomness. Identical
    inputs always produce a byte-identical string.
    """
    inp = scheduler_input
    out = scheduler_output
    by_id: dict[str, Task] = {t.task_id: t for t in inp.plan.tasks}

    days = _day_columns(inp.horizon_start, inp.horizon_end)
    grid_height = _grid_pixel_height(inp.policy)
    grid_width = _GRID_PADDING_LEFT + len(days) * (
        _DAY_COLUMN_WIDTH + _DAY_COLUMN_GAP
    )

    page_title = title or f"Schedule preview - {inp.run_id}"

    body_parts = [
        _render_header(inp, page_title),
        _render_legend(),
        _render_svg_grid(inp, out, days, by_id, grid_width, grid_height),
        _render_unscheduled_table(out, by_id),
        _render_footer(out),
    ]
    body = "\n".join(body_parts)

    return _DOCUMENT_SHELL.format(
        title=_esc(page_title),
        styles=_STYLES,
        body=body,
    )


def _render_header(inp: SchedulerInput, page_title: str) -> str:
    p = inp.policy
    deep_windows_summary = _deep_windows_summary(p.deep_work_windows)
    return f"""\
<header class="header">
  <h1>{_esc(page_title)}</h1>
  <dl class="meta">
    <dt>run_id</dt><dd>{_esc(inp.run_id)}</dd>
    <dt>plan_version</dt><dd>{_esc(inp.plan_version)}</dd>
    <dt>horizon</dt><dd>{_esc(inp.horizon_start.isoformat())} to {_esc(inp.horizon_end.isoformat())}</dd>
    <dt>allowed hours</dt><dd>{_esc(p.no_events_before)} to {_esc(p.no_events_after)}</dd>
    <dt>weekends</dt><dd>{"allowed" if p.allow_weekends else "blocked"}</dd>
    <dt>max daily study</dt><dd>{p.max_daily_study_min} min</dd>
    <dt>max session</dt><dd>{p.max_session_length_min} min</dd>
    <dt>min deep-break</dt><dd>{p.min_break_between_deep_blocks_min} min</dd>
    <dt>deep-work windows</dt><dd>{_esc(deep_windows_summary)}</dd>
  </dl>
</header>"""


def _render_legend() -> str:
    return """\
<section class="legend">
  <span class="chip chip-deep">scheduled - deep</span>
  <span class="chip chip-medium">scheduled - medium</span>
  <span class="chip chip-light">scheduled - light</span>
  <span class="chip chip-deep-band">deep-work window</span>
  <span class="chip chip-busy">free/busy block</span>
</section>"""


def _render_svg_grid(
    inp: SchedulerInput,
    out: SchedulerOutput,
    days: list[date],
    by_id: dict[str, Task],
    grid_width: int,
    grid_height: int,
) -> str:
    p = inp.policy
    total_h = grid_height + _GRID_PADDING_TOP + 24
    chunks: list[str] = [
        '<section class="grid">',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{grid_width}" height="{total_h}" '
            f'viewBox="0 0 {grid_width} {total_h}" '
            f'aria-label="Schedule grid">'
        ),
        _render_time_axis(p, grid_height),
    ]

    for column_idx, day in enumerate(days):
        x = _GRID_PADDING_LEFT + column_idx * (_DAY_COLUMN_WIDTH + _DAY_COLUMN_GAP)
        chunks.append(_render_day_column(day, x, grid_height, p))
        chunks.append(_render_deep_work_bands(day, x, p))
        chunks.append(_render_busy_blocks(day, x, inp, p))
        chunks.append(_render_scheduled_tasks(day, x, out.scheduled_tasks, by_id, p))

    chunks.append("</svg>")
    chunks.append("</section>")
    return "\n".join(chunks)


def _render_time_axis(p: SchedulingPolicy, grid_height: int) -> str:
    """Hourly tick labels down the left margin."""
    start_min = _hhmm_to_minutes(p.no_events_before)
    end_min = _hhmm_to_minutes(p.no_events_after)
    parts: list[str] = []
    hour = (start_min // 60) + (1 if start_min % 60 else 0)
    while hour * 60 <= end_min:
        y = _GRID_PADDING_TOP + (hour * 60 - start_min) * _PX_PER_MINUTE
        parts.append(
            f'<text x="{_GRID_PADDING_LEFT - 8}" y="{y + 4}" '
            f'class="axis-label" text-anchor="end">{hour:02d}:00</text>'
        )
        parts.append(
            f'<line x1="{_GRID_PADDING_LEFT - 4}" y1="{y}" '
            f'x2="{_GRID_PADDING_LEFT}" y2="{y}" class="axis-tick" />'
        )
        hour += 1
    return "\n".join(parts)


def _render_day_column(
    day: date, x: int, grid_height: int, p: SchedulingPolicy
) -> str:
    weekday_name = day.strftime("%a")
    iso = day.isoformat()
    label = f"{weekday_name} {iso}"
    weekend = _WEEKDAY_TO_DAY[day.weekday()] in {Day.SAT, Day.SUN}
    blocked = weekend and not p.allow_weekends
    bg_class = "column-bg-blocked" if blocked else "column-bg"
    return (
        f'<text x="{x + _DAY_COLUMN_WIDTH / 2}" y="{_GRID_PADDING_TOP - 10}" '
        f'class="day-label" text-anchor="middle">{_esc(label)}</text>'
        f'<rect x="{x}" y="{_GRID_PADDING_TOP}" width="{_DAY_COLUMN_WIDTH}" '
        f'height="{grid_height}" class="{bg_class}" />'
    )


def _render_deep_work_bands(day: date, x: int, p: SchedulingPolicy) -> str:
    if not p.respect_deep_work_windows or not p.deep_work_windows:
        return ""
    day_enum = _WEEKDAY_TO_DAY[day.weekday()]
    matching = [w for w in p.deep_work_windows if w.day is day_enum]
    parts: list[str] = []
    for window in matching:
        y, h = _band_geometry(window.start, window.end, p)
        if h <= 0:
            continue
        parts.append(
            f'<rect class="deep-work-band" x="{x}" y="{y}" '
            f'width="{_DAY_COLUMN_WIDTH}" height="{h}">'
            f'<title>deep-work window {window.day.value} '
            f'{window.start} to {window.end}</title>'
            f"</rect>"
        )
    return "\n".join(parts)


def _render_busy_blocks(
    day: date, x: int, inp: SchedulerInput, p: SchedulingPolicy
) -> str:
    parts: list[str] = []
    for interval in inp.calendar_free_busy:
        clipped = _clip_to_day(interval.start, interval.end, day)
        if clipped is None:
            continue
        start_dt, end_dt = clipped
        start_hhmm = start_dt.strftime("%H:%M")
        end_hhmm = end_dt.strftime("%H:%M")
        y, h = _band_geometry(start_hhmm, end_hhmm, p)
        if h <= 0:
            continue
        parts.append(
            f'<rect class="busy-block" x="{x}" y="{y}" '
            f'width="{_DAY_COLUMN_WIDTH}" height="{h}">'
            f'<title>busy {start_hhmm} to {end_hhmm}</title>'
            f"</rect>"
        )
    return "\n".join(parts)


def _render_scheduled_tasks(
    day: date,
    x: int,
    scheduled: list[ScheduledTask],
    by_id: dict[str, Task],
    p: SchedulingPolicy,
) -> str:
    parts: list[str] = []
    for st in scheduled:
        if st.start.date() != day:
            continue
        task = by_id.get(st.task_id)
        focus = task.required_focus_level if task else FocusLevel.MEDIUM
        fill = _FOCUS_FILL[focus]
        start_hhmm = st.start.strftime("%H:%M")
        end_hhmm = st.end.strftime("%H:%M")
        y, h = _band_geometry(start_hhmm, end_hhmm, p)
        if h <= 0:
            continue
        title_text = task.title if task else st.task_id
        tooltip = f"{st.task_id} - {title_text} - {start_hhmm} to {end_hhmm}"
        if task is not None:
            tooltip += (
                f" - {task.estimated_duration_min}min - "
                f"load={task.cognitive_load} - {task.category.value}"
            )
        parts.append(
            f'<g class="scheduled-task" data-task-id="{_esc(st.task_id)}">'
            f'<rect x="{x + 4}" y="{y}" '
            f'width="{_DAY_COLUMN_WIDTH - 8}" height="{h}" '
            f'fill="{fill}" rx="4" ry="4">'
            f"<title>{_esc(tooltip)}</title>"
            f"</rect>"
            f'<text x="{x + 12}" y="{y + 16}" class="task-label">{_esc(st.task_id)}</text>'
            f"</g>"
        )
    return "\n".join(parts)


def _render_unscheduled_table(
    out: SchedulerOutput, by_id: dict[str, Task]
) -> str:
    if not out.unscheduled_tasks:
        return (
            '<section class="unscheduled empty">'
            "<h2>Unscheduled</h2>"
            "<p>None - every validated task was placed.</p>"
            "</section>"
        )
    rows: list[str] = []
    for u in out.unscheduled_tasks:
        debug_summary = _debug_summary(u.debug)
        task = by_id.get(u.task_id)
        title = task.title if task else u.task_id
        rows.append(
            f'<tr class="unscheduled-row" data-reason-code="{_esc(u.reason_code.value)}">'
            f'<td class="task-id">{_esc(u.task_id)}</td>'
            f'<td class="task-title">{_esc(title)}</td>'
            f'<td class="reason-code">{_esc(u.reason_code.value)}</td>'
            f'<td class="debug-summary">{_esc(debug_summary)}</td>'
            f"</tr>"
        )
    return f"""\
<section class="unscheduled">
  <h2>Unscheduled ({len(out.unscheduled_tasks)})</h2>
  <table>
    <thead>
      <tr><th>task_id</th><th>title</th><th>reason_code</th><th>debug</th></tr>
    </thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
  </table>
</section>"""


def _render_footer(out: SchedulerOutput) -> str:
    repair_chips = (
        "".join(
            f'<span class="chip chip-repair">{_esc(r.value)}</span>'
            for r in out.repair_options
        )
        or '<span class="dim">none</span>'
    )
    return f"""\
<footer class="footer">
  <dl class="capacity">
    <dt>schedule status</dt><dd>{_esc(out.schedule_status.value)}</dd>
    <dt>scheduled</dt><dd>{len(out.scheduled_tasks)} task(s)</dd>
    <dt>unscheduled</dt><dd>{len(out.unscheduled_tasks)} task(s)</dd>
    <dt>available capacity</dt><dd>{out.available_capacity_min} min</dd>
    <dt>largest block</dt><dd>{out.largest_available_block_min} min</dd>
  </dl>
  <div class="repair-options">
    <span class="dim">repair options:</span> {repair_chips}
  </div>
</footer>"""


# ---------------------------------------------------------------------------
# Geometry / time helpers
# ---------------------------------------------------------------------------


def _hhmm_to_minutes(hhmm: str) -> int:
    hh, mm = hhmm.split(":")
    return int(hh) * 60 + int(mm)


def _band_geometry(
    start_hhmm: str, end_hhmm: str, p: SchedulingPolicy
) -> tuple[float, float]:
    """Return (y, height) px for a [start, end] within the allowed-hours band."""
    start_min = _hhmm_to_minutes(start_hhmm)
    end_min = _hhmm_to_minutes(end_hhmm)
    band_start = _hhmm_to_minutes(p.no_events_before)
    band_end = _hhmm_to_minutes(p.no_events_after)
    clipped_start = max(start_min, band_start)
    clipped_end = min(end_min, band_end)
    if clipped_end <= clipped_start:
        return (0.0, 0.0)
    y = _GRID_PADDING_TOP + (clipped_start - band_start) * _PX_PER_MINUTE
    h = (clipped_end - clipped_start) * _PX_PER_MINUTE
    return (y, h)


def _grid_pixel_height(p: SchedulingPolicy) -> int:
    band = _hhmm_to_minutes(p.no_events_after) - _hhmm_to_minutes(p.no_events_before)
    return int(band * _PX_PER_MINUTE)


def _day_columns(horizon_start: datetime, horizon_end: datetime) -> list[date]:
    out: list[date] = []
    cur = horizon_start.date()
    end = horizon_end.date()
    while cur < end:
        out.append(cur)
        cur = cur + timedelta(days=1)
    return out


def _clip_to_day(
    start: datetime, end: datetime, day: date
) -> tuple[datetime, datetime] | None:
    """Return ``(start, end)`` clipped to the calendar day, or None if no overlap."""
    day_start = datetime.combine(day, time(0, 0), tzinfo=start.tzinfo)
    day_end = day_start + timedelta(days=1)
    if end <= day_start or start >= day_end:
        return None
    return (max(start, day_start), min(end, day_end))


def _deep_windows_summary(windows: list[DeepWorkWindowPolicy]) -> str:
    if not windows:
        return "none"
    return ", ".join(f"{w.day.value} {w.start} to {w.end}" for w in windows)


def _debug_summary(debug: dict[str, Any]) -> str:
    """Compact, deterministic one-line summary of a debug payload."""
    keys_of_interest = (
        "required_duration_min",
        "largest_available_block_min",
        "total_required_min",
        "available_capacity_min",
        "shortfall_min",
        "max_session_length_min",
        "duration_min",
        "blocked_by",
        "deep_work_windows_seen",
        "suggested_repair",
    )
    parts: list[str] = []
    for key in keys_of_interest:
        if key in debug:
            parts.append(f"{key}={debug[key]}")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# HTML document shell + inline styles
# ---------------------------------------------------------------------------

_STYLES = """\
:root {
  color-scheme: light dark;
  --fg: #111827;
  --fg-dim: #6b7280;
  --bg: #ffffff;
  --bg-soft: #f9fafb;
  --border: #e5e7eb;
  --accent: #2563eb;
  --deep-band: rgba(37, 99, 235, 0.16);
  --busy: rgba(75, 85, 99, 0.55);
  --column-bg: #f3f4f6;
}
body {
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
  color: var(--fg); background: var(--bg);
  margin: 24px; max-width: 1400px;
}
h1 { margin: 0 0 12px; font-size: 22px; }
h2 { margin: 24px 0 8px; font-size: 16px; }
.header { border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 16px; }
.meta {
  display: grid; grid-template-columns: max-content 1fr max-content 1fr;
  gap: 4px 16px; margin: 0; font-size: 13px;
}
.meta dt { color: var(--fg-dim); }
.meta dd { margin: 0; font-variant-numeric: tabular-nums; }
.legend { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.chip {
  display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: 12px; border: 1px solid var(--border); background: var(--bg-soft);
}
.chip-deep { background: #2563eb; color: white; border-color: #1d4ed8; }
.chip-medium { background: #0d9488; color: white; border-color: #0f766e; }
.chip-light { background: #65a30d; color: white; border-color: #4d7c0f; }
.chip-deep-band { background: var(--deep-band); }
.chip-busy { background: var(--busy); color: white; }
.chip-repair { background: #fef3c7; border-color: #fcd34d; }
.grid { overflow-x: auto; margin: 12px 0 24px; }
.column-bg { fill: var(--column-bg); }
.column-bg-blocked { fill: var(--column-bg); opacity: 0.35; }
.deep-work-band { fill: var(--deep-band); }
.busy-block { fill: var(--busy); }
.scheduled-task rect { stroke: rgba(0,0,0,0.15); stroke-width: 1; }
.scheduled-task .task-label { fill: white; font: 600 12px system-ui; pointer-events: none; }
.day-label { font: 600 12px system-ui; fill: var(--fg); }
.axis-label { font: 11px system-ui; fill: var(--fg-dim); }
.axis-tick { stroke: var(--fg-dim); stroke-width: 1; }
.unscheduled { margin: 24px 0; }
.unscheduled.empty p { color: var(--fg-dim); }
.unscheduled table { border-collapse: collapse; width: 100%; font-size: 13px; }
.unscheduled th, .unscheduled td {
  text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border);
  font-variant-numeric: tabular-nums;
}
.unscheduled th { color: var(--fg-dim); font-weight: 500; }
.unscheduled .reason-code { font-family: ui-monospace, SFMono-Regular, monospace; }
.unscheduled .debug-summary { color: var(--fg-dim); }
.footer { border-top: 1px solid var(--border); padding-top: 12px; margin-top: 16px; }
.capacity {
  display: grid; grid-template-columns: max-content 1fr max-content 1fr max-content 1fr;
  gap: 4px 16px; margin: 0 0 8px; font-size: 13px;
}
.capacity dt { color: var(--fg-dim); }
.capacity dd { margin: 0; font-variant-numeric: tabular-nums; }
.dim { color: var(--fg-dim); }
.repair-options { font-size: 13px; }
"""

_DOCUMENT_SHELL = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{title}</title>
<style>{styles}</style>
</head>
<body>
{body}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _render_scenario(name: str) -> str:
    """Build the scenario, run the scheduler, return the rendered HTML."""
    scenario = SCENARIOS[name]
    scheduler_input = scenario.build()
    scheduler_output = schedule(scheduler_input)
    return render_schedule_html(
        scheduler_input=scheduler_input,
        scheduler_output=scheduler_output,
        title=f"Schedule preview - scenario={name}",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render a Phase 1 scheduler scenario as a self-contained HTML/SVG "
            "diagnostic. Useful for visually verifying that placements respect "
            "allowed hours, deep-work windows, and free/busy constraints."
        )
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default="success",
        help="Built-in scenario to render (default: success).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("./schedule.html"),
        help="Output HTML file (default: ./schedule.html).",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List built-in scenarios and exit.",
    )
    args = parser.parse_args(argv)

    if args.list_scenarios:
        for name in sorted(SCENARIOS):
            print(f"{name}: {SCENARIOS[name].description}")
        return 0

    html = _render_scenario(args.scenario)
    out_path: Path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
