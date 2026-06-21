"""Server-rendered HTML pages (F0b) — the basic hosted UI.

The core journey: connect Google (login), see your plan (home), review the
draft schedule with its canonical payload hash, approve, and write to your
calendar. Minimal CSS, no JS framework. Registered only in hosted mode, since
every page needs the session for both auth and CSRF.

State-changing POSTs carry a per-session CSRF token (a hidden form field
validated against the session). Combined with the SameSite=lax session cookie,
that closes the gap the JSON API left open. Onboarding is still done via the
JSON API for now — a profile form is a follow-up.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.datastructures import FormData
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from agentic_calendar.app.cycle import HASH_CANONICALIZATION_VERSION
from agentic_calendar.app.environment import AppEnvironment
from agentic_calendar.app.state import OnboardingRecord
from agentic_calendar.app.tuning import TUNABLE_SECTIONS, EffectiveTuning, scalar_fields
from agentic_calendar.contracts.common_types import Day, ExperienceLevel
from agentic_calendar.contracts.draft_schedule import DraftSchedule, DraftScheduleEntry
from agentic_calendar.contracts.hashing import canonical_payload_hash

from .calendar_service import best_effort_free_busy, build_user_calendar_service
from .deps import get_cycle_service

router = APIRouter(tags=["pages"])
_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_USER_KEY = "user_id"
_CSRF_KEY = "csrf_token"

CsrfField = Annotated[str, Form()]


def _user(request: Request) -> str | None:
    return request.session.get(_USER_KEY)


def _require_user(request: Request) -> str:
    user_id = request.session.get(_USER_KEY)
    if not user_id:
        raise HTTPException(status_code=401, detail="not authenticated")
    return str(user_id)


def _csrf(request: Request) -> str:
    """Get-or-create this session's CSRF token (rendered into every form)."""
    token = request.session.get(_CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[_CSRF_KEY] = token
    return str(token)


def _check_csrf(request: Request, token: str) -> None:
    expected = request.session.get(_CSRF_KEY)
    if not expected or token != expected:
        raise HTTPException(status_code=403, detail="invalid CSRF token")


def _page(request: Request, name: str, *, status_code: int = 200, **context: object) -> Response:
    return _templates.TemplateResponse(
        request=request,
        name=name,
        context={"email": request.session.get("email"), "csrf_token": _csrf(request), **context},
        status_code=status_code,
    )


# ---------------------------------------------------------------------------- #
# Onboarding profile form (#1): the HTML mirror of POST /api/onboard.
#
# The form collects a full ``UserProfile`` plus the IANA ``timezone`` (which
# lives on the OnboardingRecord, not the profile). Submitted strings are handed
# straight to the contract for validation/coercion — the form does no parsing of
# its own beyond CSV splitting and checkbox presence, so the typed model stays
# the single validation oracle. The motivation profile is deliberately out of
# scope here; it drives check-in cadence and belongs with the check-in work.
# ---------------------------------------------------------------------------- #

_DAYS: tuple[str, ...] = tuple(day.value for day in Day)
_LEVELS: tuple[str, ...] = tuple(level.value for level in ExperienceLevel)
_CHECKBOXES: tuple[str, ...] = (
    "allow_weekends",
    "prefer_evening_sessions",
    "prefer_weekend_long_blocks",
    "avoid_back_to_back_deep_work",
)
_SCALAR_FIELDS: tuple[str, ...] = (
    "goal",
    "target_role",
    "target_companies",
    "target_level",
    "timeline_weeks",
    "weekly_hours",
    "experience_level",
    "known_strengths",
    "known_weaknesses",
    "preferred_session_length_min",
    "max_session_length_min",
    "dww_start",
    "dww_end",
    "no_events_before",
    "no_events_after",
    "max_daily_study_min",
    "min_break_between_deep_blocks_min",
    "timezone",
)

# Pre-filled, valid-by-default values so a freshly connected user can submit
# immediately and tweak, rather than face an empty form. Mirrors the heuristics
# in ``dogfood_profile.json``.
_DEFAULT_ONBOARD_VALUES: dict[str, Any] = {
    "goal": "",
    "target_role": "",
    "target_companies": "",
    "target_level": "",
    "timeline_weeks": "10",
    "weekly_hours": "8",
    "experience_level": ExperienceLevel.INTERMEDIATE.value,
    "known_strengths": "",
    "known_weaknesses": "",
    "preferred_session_length_min": "60",
    "max_session_length_min": "120",
    "dww_start": "18:00",
    "dww_end": "21:00",
    "no_events_before": "08:00",
    "no_events_after": "22:30",
    "max_daily_study_min": "180",
    "min_break_between_deep_blocks_min": "30",
    "timezone": "UTC",
    "selected_days": [],
    "checkboxes": {name: name == "allow_weekends" for name in _CHECKBOXES},
}


def _csv(raw: str) -> list[str]:
    """Split a comma-separated text input into a clean list (drops blanks)."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def _build_profile(form: FormData, user_id: str, now: datetime) -> dict[str, Any]:
    """Assemble the ``user_profile`` dict from raw form values.

    Numbers and times stay as strings — the ``UserProfile`` contract coerces and
    validates them. The acting ``user_id`` always comes from the session, never
    the form, matching ``routes_cycle.onboard``'s trust boundary.
    """
    start = str(form.get("dww_start", "")).strip()
    end = str(form.get("dww_end", "")).strip()
    windows = (
        [{"day": day, "start": start, "end": end} for day in form.getlist("dww_day")]
        if start and end
        else []
    )
    return {
        "user_id": user_id,
        "profile_version": "profile_001",
        "goal": str(form.get("goal", "")).strip(),
        "target_role": str(form.get("target_role", "")).strip(),
        "target_companies": _csv(str(form.get("target_companies", ""))),
        "target_level": str(form.get("target_level", "")).strip() or None,
        "timeline_weeks": form.get("timeline_weeks", ""),
        "weekly_hours": form.get("weekly_hours", ""),
        "experience_level": form.get("experience_level", ""),
        "known_strengths": _csv(str(form.get("known_strengths", ""))),
        "known_weaknesses": _csv(str(form.get("known_weaknesses", ""))),
        "preferred_session_length_min": form.get("preferred_session_length_min", ""),
        "max_session_length_min": form.get("max_session_length_min", ""),
        "deep_work_windows": windows,
        "hard_constraints": {
            "no_events_before": form.get("no_events_before", ""),
            "no_events_after": form.get("no_events_after", ""),
            "allow_weekends": form.get("allow_weekends") is not None,
            "max_daily_study_min": form.get("max_daily_study_min", ""),
            "min_break_between_deep_blocks_min": form.get("min_break_between_deep_blocks_min", ""),
        },
        "preferences": {
            "prefer_evening_sessions": form.get("prefer_evening_sessions") is not None,
            "prefer_weekend_long_blocks": form.get("prefer_weekend_long_blocks") is not None,
            "avoid_back_to_back_deep_work": form.get("avoid_back_to_back_deep_work") is not None,
        },
        "created_at": now,
        "updated_at": now,
    }


def _submitted_values(form: FormData) -> dict[str, Any]:
    """Echo the user's input back into the template so a rejected submit keeps it."""
    values: dict[str, Any] = {key: str(form.get(key, "")) for key in _SCALAR_FIELDS}
    values["selected_days"] = form.getlist("dww_day")
    values["checkboxes"] = {name: form.get(name) is not None for name in _CHECKBOXES}
    return values


def _validation_errors(exc: ValidationError) -> list[str]:
    """Flatten a contract ``ValidationError`` into per-field form messages."""
    messages: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"] if part != "user_profile")
        messages.append(f"{loc or 'profile'}: {err['msg']}")
    return messages


def _values_from_record(record: OnboardingRecord) -> dict[str, Any]:
    """Pre-fill the form from a saved record (the inverse of ``_build_profile``).

    Deep-work windows are collapsed back onto the simplified widget: every
    window's day becomes a checked weekday, and the first window's times fill the
    single start/end pair. That is lossy only if the saved windows have differing
    times — the trade for keeping the widget simple.
    """
    profile = record.user_profile
    hard = profile.hard_constraints
    prefs = profile.preferences
    windows = profile.deep_work_windows
    return {
        "goal": profile.goal,
        "target_role": profile.target_role,
        "target_companies": ", ".join(profile.target_companies),
        "target_level": profile.target_level or "",
        "timeline_weeks": str(profile.timeline_weeks),
        "weekly_hours": f"{profile.weekly_hours:g}",
        "experience_level": profile.experience_level.value,
        "known_strengths": ", ".join(profile.known_strengths),
        "known_weaknesses": ", ".join(profile.known_weaknesses),
        "preferred_session_length_min": str(profile.preferred_session_length_min),
        "max_session_length_min": str(profile.max_session_length_min),
        "dww_start": windows[0].start if windows else "",
        "dww_end": windows[0].end if windows else "",
        "no_events_before": hard.no_events_before,
        "no_events_after": hard.no_events_after,
        "max_daily_study_min": str(hard.max_daily_study_min),
        "min_break_between_deep_blocks_min": str(hard.min_break_between_deep_blocks_min),
        "timezone": record.timezone,
        "selected_days": [window.day.value for window in windows],
        "checkboxes": {
            "allow_weekends": hard.allow_weekends,
            "prefer_evening_sessions": prefs.prefer_evening_sessions,
            "prefer_weekend_long_blocks": prefs.prefer_weekend_long_blocks,
            "avoid_back_to_back_deep_work": prefs.avoid_back_to_back_deep_work,
        },
    }


# ---------------------------------------------------------------------------- #
# Today / check-in (#2): the telemetry feedback loop.
#
# Renders the active plan's scheduled tasks. A task becomes "due" once its draft
# entry has ended; a due task offers Complete / Missed, which POST a single
# telemetry event through the same CycleService.ingest the JSON API uses. A task
# that already has a telemetry event is shown as reported and a re-submit is
# refused server-side, so a double click can never double-count.
# ---------------------------------------------------------------------------- #


def _active_draft(env: AppEnvironment, user_id: str) -> DraftSchedule | None:
    """The draft backing the user's *active* (written) plan, or ``None``.

    Guards that the latest run's draft actually matches the active plan version,
    so a replan-in-flight draft is never shown as today's schedule.
    """
    run = env.state.latest_run_for_user(user_id)
    active = env.plan_store.get_active(user_id)
    if active is None or run is None or run.draft_schedule_id is None:
        return None
    draft = env.state.get_draft(run.draft_schedule_id)
    if draft is None or draft.plan_version != active.plan_version:
        return None
    return draft


def _entry_for_task(
    env: AppEnvironment, user_id: str, task_id: str
) -> DraftScheduleEntry | None:
    draft = _active_draft(env, user_id)
    if draft is None:
        return None
    return next((entry for entry in draft.entries if entry.task_id == task_id), None)


def _today_rows(env: AppEnvironment, user_id: str) -> list[dict[str, Any]]:
    """One render row per scheduled task, localized to the user's timezone."""
    draft = _active_draft(env, user_id)
    active = env.plan_store.get_active(user_id)
    if draft is None or active is None:
        return []
    onboarding = env.state.get_onboarding(user_id)
    tz = onboarding.tzinfo() if onboarding is not None else UTC
    now = env.clock.now()
    tasks = {task.task_id: task for task in active.plan.tasks}
    rows: list[dict[str, Any]] = []
    for entry in draft.entries:
        task = tasks.get(entry.task_id)
        if task is None:
            continue
        rows.append(
            {
                "task_id": entry.task_id,
                "title": task.title,
                "category": task.category.value,
                "focus": task.required_focus_level.value,
                "when": entry.start.astimezone(tz).strftime("%a %b %d, %H:%M"),
                "end_hm": entry.end.astimezone(tz).strftime("%H:%M"),
                "due": entry.end <= now,
                "reported": bool(env.telemetry_store.list_for_task(entry.task_id)),
            }
        )
    return rows


def _checkin_payload(
    env: AppEnvironment, task_id: str, scheduled_min: int, *, completed: bool
) -> dict[str, Any]:
    """Build one telemetry event for a user-reported, online outcome.

    Mirrors the ``_completed_event`` / ``_missed_event`` shapes the cycle tests
    use: a completion carries actuals + timestamp so ``data_quality`` stays
    ``complete``; a miss carries neither.
    """
    payload: dict[str, Any] = {
        "telemetry_event_id": env.id_generator.new_id("telemetry"),
        "task_id": task_id,
        "scheduled_duration_min": scheduled_min,
        "actual_duration_min": scheduled_min if completed else None,
        "completed": completed,
        "user_reschedule_count": 0,
        "data_quality": "complete",
    }
    if completed:
        payload["completion_timestamp"] = env.clock.now()
    return payload


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> Response:
    if _user(request):
        return RedirectResponse("/home", status_code=303)
    return _page(request, "login.html")


@router.get("/home", response_class=HTMLResponse)
def home(request: Request) -> Response:
    if not _user(request):
        return RedirectResponse("/", status_code=303)
    status = get_cycle_service(request).status(_require_user(request))
    return _page(request, "home.html", status=status)


@router.get("/onboard", response_class=HTMLResponse)
def onboard_page(request: Request) -> Response:
    if not _user(request):
        return RedirectResponse("/", status_code=303)
    record = request.app.state.env.state.get_onboarding(_require_user(request))
    values = _values_from_record(record) if record is not None else _DEFAULT_ONBOARD_VALUES
    return _page(request, "onboard.html", days=_DAYS, levels=_LEVELS, values=values, errors=None)


@router.post("/ui/onboard")
async def ui_onboard(request: Request) -> Response:
    form = await request.form()
    _check_csrf(request, str(form.get("csrf_token", "")))
    user_id = _require_user(request)
    profile = _build_profile(form, user_id, request.app.state.env.clock.now())
    timezone = str(form.get("timezone", "")).strip()
    try:
        get_cycle_service(request).onboard({"user_profile": profile, "timezone": timezone})
    except ValidationError as exc:
        return _page(
            request, "onboard.html", status_code=400, days=_DAYS, levels=_LEVELS,
            values=_submitted_values(form), errors=_validation_errors(exc),
        )
    return RedirectResponse("/home", status_code=303)


@router.get("/today", response_class=HTMLResponse)
def today_page(request: Request) -> Response:
    if not _user(request):
        return RedirectResponse("/", status_code=303)
    rows = _today_rows(request.app.state.env, _require_user(request))
    return _page(request, "today.html", rows=rows)


@router.post("/ui/checkin")
async def ui_checkin(request: Request) -> Response:
    form = await request.form()
    _check_csrf(request, str(form.get("csrf_token", "")))
    user_id = _require_user(request)
    env = request.app.state.env
    task_id = str(form.get("task_id", ""))
    completed = str(form.get("outcome", "")) == "complete"
    entry = _entry_for_task(env, user_id, task_id)
    # Only a task in the active plan, already ended, and not yet reported can
    # produce an event — this enforces membership, the "due" rule, and
    # idempotency (a double-submit cannot double-count).
    if (
        entry is not None
        and entry.end <= env.clock.now()
        and not env.telemetry_store.list_for_task(task_id)
    ):
        scheduled_min = int((entry.end - entry.start).total_seconds() // 60)
        get_cycle_service(request).ingest(
            user_id, [_checkin_payload(env, task_id, scheduled_min, completed=completed)]
        )
    return RedirectResponse("/today", status_code=303)


# ---------------------------------------------------------------------------- #
# Accountability dashboard (#3): the read-only projection of completion
# telemetry + check-ins against the user's accountability contract.
#
# Sources every field from ``CycleService.accountability_snapshot`` — the pure
# half of the cycle's accountability pass, with no nudge delivery, recommitment
# request, or run-state transition — so the GET is genuinely side-effect-free
# (and needs no CSRF). It mirrors what the ``show_accountability`` operator CLI
# renders, off the same projection.
#
# DECISION (2026-06-18): ship the empty state first. Accountability is opt-in —
# the snapshot is ``None`` until the user has a motivation profile (axiom 21) —
# and the onboarding form (#1) deliberately omits that profile, so a current
# dogfooding user sees the "not set up" state. The page distinguishes that from
# "no active plan yet" so the guidance is accurate.
#
# DEFERRED: a motivation-profile capture surface (so the dashboard lights up
# with live data for a real account). Tracked in phase-frontend-mvp.md.
# ---------------------------------------------------------------------------- #


@router.get("/accountability", response_class=HTMLResponse)
def accountability_page(request: Request) -> Response:
    if not _user(request):
        return RedirectResponse("/", status_code=303)
    user_id = _require_user(request)
    onboarding = request.app.state.env.state.get_onboarding(user_id)
    has_motivation_profile = (
        onboarding is not None and onboarding.motivation_profile is not None
    )
    snapshot = get_cycle_service(request).accountability_snapshot(user_id)
    return _page(
        request,
        "accountability.html",
        snapshot=snapshot,
        has_motivation_profile=has_motivation_profile,
    )


# ---------------------------------------------------------------------------- #
# Thresholds page (#4): the read-only mirror of the effective deterministic
# tuning + its change history.
#
# Display-only by design (axiom 07 "Threshold Change Log"): tuning values change
# ONLY via ``tuning.toml`` → ``apply_tuning``, which journals every effective
# change to the threshold log. The UI never edits — it reads ``env.tuning`` (the
# already-applied ``EffectiveTuning`` the composition root serves from) and
# ``env.threshold_log_store`` (the append-only journal). It mirrors what the
# ``show_thresholds`` operator CLI prints, off the same surfaces.
# ---------------------------------------------------------------------------- #


def _threshold_sections(tuning: EffectiveTuning) -> list[dict[str, Any]]:
    """Per-section effective scalar values, each tagged default/overridden.

    Iterates the tuning registry (``TUNABLE_SECTIONS`` then ``scalar_fields``)
    and reads the effective value straight off ``tuning`` — the values the system
    actually serves — so ``status`` compares serving truth against the code
    default, the same honest comparison the ``show_thresholds`` CLI makes.
    """
    sections: list[dict[str, Any]] = []
    for name, (config_type, default) in TUNABLE_SECTIONS.items():
        effective = getattr(tuning, name)
        fields: list[dict[str, Any]] = []
        for field_name in scalar_fields(config_type):
            value = getattr(effective, field_name)
            default_value = getattr(default, field_name)
            fields.append(
                {
                    "name": field_name,
                    "value": value,
                    "status": "default" if value == default_value else "overridden",
                }
            )
        sections.append({"name": name, "fields": fields})
    return sections


@router.get("/thresholds", response_class=HTMLResponse)
def thresholds_page(request: Request) -> Response:
    if not _user(request):
        return RedirectResponse("/", status_code=303)
    env = request.app.state.env
    return _page(
        request,
        "thresholds.html",
        sections=_threshold_sections(env.tuning),
        history=env.threshold_log_store.list_all(),
    )


@router.get("/draft", response_class=HTMLResponse)
def draft_page(request: Request) -> Response:
    if not _user(request):
        return RedirectResponse("/", status_code=303)
    user_id = _require_user(request)
    status = get_cycle_service(request).status(user_id)
    draft = None
    payload_hash = None
    if status.draft_schedule_id:
        draft = request.app.state.env.state.get_draft(status.draft_schedule_id)
        if draft is not None:
            payload_hash = canonical_payload_hash(draft, HASH_CANONICALIZATION_VERSION)
    return _page(request, "draft.html", status=status, draft=draft, payload_hash=payload_hash)


def _user_free_busy(request: Request, user_id: str) -> list[dict[str, str]]:
    """The user's real-calendar busy ranges over the plan horizon, so the
    scheduler avoids their existing commitments (best-effort; ``[]`` if the
    calendar can't be read — see :func:`best_effort_free_busy`)."""
    return best_effort_free_busy(
        request.app.state.env,
        user_id=user_id,
        token_cipher=request.app.state.token_cipher,
    )


@router.post("/ui/propose")
def ui_propose(request: Request, csrf_token: CsrfField) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    user_id = _require_user(request)
    get_cycle_service(request).propose(user_id, free_busy=_user_free_busy(request, user_id))
    return RedirectResponse("/draft", status_code=303)


@router.post("/ui/approve")
def ui_approve(
    request: Request,
    csrf_token: CsrfField,
    action: Annotated[str, Form()] = "approve",
) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    get_cycle_service(request).approve(_require_user(request), reject=action == "reject")
    return RedirectResponse("/draft", status_code=303)


@router.post("/ui/write")
def ui_write(request: Request, csrf_token: CsrfField) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    user_id = _require_user(request)
    user_service, calendar_id = build_user_calendar_service(
        request.app.state.env, user_id=user_id, token_cipher=request.app.state.token_cipher
    )
    user_service.write(user_id, target_calendar_id=calendar_id)
    return RedirectResponse("/home", status_code=303)


@router.post("/ui/logout")
def ui_logout(request: Request, csrf_token: CsrfField) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/", status_code=303)
