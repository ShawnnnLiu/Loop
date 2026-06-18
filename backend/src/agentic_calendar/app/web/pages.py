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
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.datastructures import FormData
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from agentic_calendar.app.cycle import HASH_CANONICALIZATION_VERSION
from agentic_calendar.app.state import OnboardingRecord
from agentic_calendar.contracts.common_types import Day, ExperienceLevel
from agentic_calendar.contracts.hashing import canonical_payload_hash

from .calendar_service import build_user_calendar_service
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


@router.post("/ui/propose")
def ui_propose(request: Request, csrf_token: CsrfField) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    get_cycle_service(request).propose(_require_user(request))
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
