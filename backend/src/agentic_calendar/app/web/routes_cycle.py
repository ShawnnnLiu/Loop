"""JSON API mirroring the operator ``run_cycle`` workflow over ``CycleService``.

One endpoint per cycle command. The mapping to HTTP status is deliberate and
preserves the axiom "every failure produces a typed ``reason_code``":

* A *workflow* failure (validation rejected a plan, a write could not verify)
  is a normal result with ``reason_code`` set and HTTP 200 — the typed code
  travels in the body, exactly as the CLI prints it.
* A *command-precondition* failure (``approve`` before ``propose``, unknown
  user) raises :class:`CycleError` and is translated to HTTP 409 by the
  handler in :mod:`agentic_calendar.app.web.app`.

The acting ``user_id`` always comes from :func:`require_user`, never from the
request body — ``onboard`` overwrites any client-supplied ``user_profile.
user_id`` with it. In Increment 1 that id is a single configured value; the
override is written now so the trust boundary is identical once the id becomes
session-derived (Increment 3).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from agentic_calendar.app.cycle import DEFAULT_TARGET_CALENDAR_ID, CycleService
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.common_types import EvidenceKind, MasteryTier
from agentic_calendar.contracts.recommitment import RecommitmentChoice
from agentic_calendar.scheduler.adjustment import DraftAdjustment

from .calendar_service import best_effort_free_busy, build_user_calendar_service
from .deps import get_cycle_service, require_user

router = APIRouter(prefix="/api", tags=["cycle"])

# FastAPI's Annotated dependency style keeps these out of argument defaults
# (lint-clean: no function calls in defaults).
Service = Annotated[CycleService, Depends(get_cycle_service)]
ActingUser = Annotated[str, Depends(require_user)]


class ProposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    free_busy: list[dict[str, Any]] = []
    horizon_days: int | None = None
    recovery_mode: RecoveryAction | None = None


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    reject: bool = False


class WriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    target_calendar_id: str = DEFAULT_TARGET_CALENDAR_ID
    dry_run: bool = False


class RollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    target_calendar_id: str = DEFAULT_TARGET_CALENDAR_ID
    dry_run: bool = False


class RetryWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    target_calendar_id: str = DEFAULT_TARGET_CALENDAR_ID


class AdjustRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjustments: list[DraftAdjustment]
    run_id: str | None = None


class DropRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_ids: list[str]
    run_id: str | None = None


class CheckinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    outcome: Literal["complete", "missed"]


class MarkEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    organization: str | None = None
    summary: str | None = None
    kind: EvidenceKind = EvidenceKind.WORK
    theme_tags: list[str] = []


class SelectPathwayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pathway_id: str
    # Slot-override editing has no NP-E UI yet; the field is accepted (and
    # registry-validated by the service) so the shape is forward-compatible.
    slot_overrides: list[dict[str, Any]] = []


class SetMasteryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    target_tier: MasteryTier


class UpsertNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    text: str


class CalendarSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class RecommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice: RecommitmentChoice
    recommitment_request_id: str | None = None


class WeeklyCheckinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blockers: str | None = None
    recovery_action: RecoveryAction | None = None


def _json(result: BaseModel) -> JSONResponse:
    """Serialize exactly as the CLI does (``model_dump_json``) — no FastAPI
    response-model coercion, so the body is byte-identical to the operator
    surface."""
    return JSONResponse(content=result.model_dump(mode="json"))


@router.post("/onboard")
def onboard(
    service: Service,
    user_id: ActingUser,
    payload: Annotated[dict[str, Any], Body()],
) -> JSONResponse:
    profile = payload.get("user_profile")
    if isinstance(profile, dict):
        # Trust boundary: the acting user owns the record, not whatever id the
        # client put in the body (identical override to Increment 3's session id).
        payload = {**payload, "user_profile": {**profile, "user_id": user_id}}
    return _json(service.onboard(payload))


@router.post("/onboard/extract")
def onboard_extract(
    service: Service,
    user_id: ActingUser,
    payload: Annotated[dict[str, Any], Body()],
) -> JSONResponse:
    """Persistence-free résumé extraction for the wizard's Résumé step.

    Body: ``{resume_text, draft_context?}``. The acting user is session-derived;
    a client-supplied ``user_id`` is ignored (the onboard trust boundary). LLM
    failures return HTTP 200 with the typed ``reason_code``; contract-invalid
    payloads (résumé too short/long, bad draft context) are the standard 422.
    Nothing persists — the only profile write path stays ``POST /api/onboard``.
    Rate limiting beyond auth is deliberately deferred for the MVP: extraction
    sits behind an explicit button on per-press-priced Haiku calls.
    """
    return _json(service.extract_resume(user_id, payload))


@router.post("/propose")
def propose(
    request: Request,
    service: Service,
    user_id: ActingUser,
    body: ProposeRequest | None = None,
) -> JSONResponse:
    body = body or ProposeRequest()
    # Hosted: schedule around the user's real calendar, fetched server-side (the
    # SPA cannot supply free/busy — it needs the per-user token cipher — and a
    # client list is never trusted anyway). Dev: honor the body's free_busy so
    # the operator/test surface keeps full control.
    free_busy = (
        _server_free_busy(request, user_id)
        if request.app.state.auth_enabled
        else body.free_busy
    )
    return _json(
        service.propose(
            user_id,
            free_busy=free_busy,
            horizon_days=body.horizon_days,
            recovery_mode=body.recovery_mode,
        )
    )


@router.post("/approve")
def approve(
    service: Service,
    user_id: ActingUser,
    body: ApproveRequest | None = None,
) -> JSONResponse:
    body = body or ApproveRequest()
    return _json(service.approve(user_id, run_id=body.run_id, reject=body.reject))


def _server_free_busy(request: Request, user_id: str) -> list[dict[str, str]]:
    """The user's real busy windows, fetched server-side so scheduling and
    adjust re-validation never trust a client-supplied list. Dev mode has no
    per-user token, so it falls back to no calendar awareness (best-effort)."""
    if not request.app.state.auth_enabled:
        return []
    return best_effort_free_busy(
        request.app.state.env,
        user_id=user_id,
        token_cipher=request.app.state.token_cipher,
    )


@router.post("/adjust")
def adjust(
    request: Request,
    service: Service,
    user_id: ActingUser,
    body: AdjustRequest,
) -> JSONResponse:
    return _json(
        service.adjust(
            user_id,
            body.adjustments,
            run_id=body.run_id,
            free_busy=_server_free_busy(request, user_id),
        )
    )


@router.post("/drop")
def drop(
    service: Service,
    user_id: ActingUser,
    body: DropRequest,
) -> JSONResponse:
    """Drop unfinished tasks: a deterministic plan edit producing a
    survivors-only draft awaiting approval (then a delete-only write)."""
    return _json(service.drop_tasks(user_id, body.task_ids, run_id=body.run_id))


@router.post("/write")
def write(
    request: Request,
    service: Service,
    user_id: ActingUser,
    body: WriteRequest | None = None,
) -> JSONResponse:
    body = body or WriteRequest()
    if request.app.state.auth_enabled:
        # Hosted mode: write to THIS user's dedicated calendar via a per-user
        # adapter. The target id comes from their stored credential, never the
        # request body — a client cannot redirect the write to another calendar.
        user_service, calendar_id = build_user_calendar_service(
            request.app.state.env,
            user_id=user_id,
            token_cipher=request.app.state.token_cipher,
        )
        return _json(
            user_service.write(
                user_id,
                run_id=body.run_id,
                target_calendar_id=calendar_id,
                dry_run=body.dry_run,
            )
        )
    # Dev mode: shared in-memory adapter, target from the request.
    return _json(
        service.write(
            user_id,
            run_id=body.run_id,
            target_calendar_id=body.target_calendar_id,
            dry_run=body.dry_run,
        )
    )


@router.post("/rollback")
def rollback(
    request: Request,
    service: Service,
    user_id: ActingUser,
    body: RollbackRequest | None = None,
) -> JSONResponse:
    """Roll back a failed calendar write: delete the events it created.

    ``dry_run`` returns the would-delete count for the SPA's confirmation
    dialog without touching the calendar. Only valid while the run sits in
    the write-failure state; a completed rollback exits the run to
    ``ERROR_REQUIRES_USER``. Hosted mode targets *this* user's dedicated
    calendar via a per-user adapter — the same trust boundary as ``write``.
    """
    body = body or RollbackRequest()
    if request.app.state.auth_enabled:
        user_service, calendar_id = build_user_calendar_service(
            request.app.state.env,
            user_id=user_id,
            token_cipher=request.app.state.token_cipher,
        )
        return _json(
            user_service.rollback(
                user_id,
                run_id=body.run_id,
                target_calendar_id=calendar_id,
                dry_run=body.dry_run,
            )
        )
    return _json(
        service.rollback(
            user_id,
            run_id=body.run_id,
            target_calendar_id=body.target_calendar_id,
            dry_run=body.dry_run,
        )
    )


@router.post("/retry-write")
def retry_write(
    request: Request,
    service: Service,
    user_id: ActingUser,
    body: RetryWriteRequest | None = None,
) -> JSONResponse:
    """Retry a failed calendar write, creating only confirmed-missing events
    (the manager's crash-reconcile path; the approved_payload_hash recheck
    runs again, so the approval gate holds). Only valid from the
    write-failure state."""
    body = body or RetryWriteRequest()
    if request.app.state.auth_enabled:
        user_service, calendar_id = build_user_calendar_service(
            request.app.state.env,
            user_id=user_id,
            token_cipher=request.app.state.token_cipher,
        )
        return _json(
            user_service.retry_write(
                user_id, run_id=body.run_id, target_calendar_id=calendar_id
            )
        )
    return _json(
        service.retry_write(
            user_id,
            run_id=body.run_id,
            target_calendar_id=body.target_calendar_id,
        )
    )


@router.post("/calendar-sync")
def calendar_sync(
    service: Service,
    user_id: ActingUser,
    body: CalendarSyncRequest,
) -> JSONResponse:
    """Toggle the user's opt-in to inbound calendar reconciliation. Returns the
    refreshed ``me`` projection so the client reflects the new setting."""
    service.set_inbound_calendar_sync(user_id, enabled=body.enabled)
    return _json(service.me(user_id))


@router.post("/reconcile")
def reconcile(request: Request, service: Service, user_id: ActingUser) -> JSONResponse:
    """On-demand inbound reconciliation pull (the SPA triggers this on Today/Week
    when a plan is active). Read-only against the calendar; a no-op result when
    the user hasn't opted in. The hosted path targets *this* user's dedicated
    calendar via a per-user adapter — the same trust boundary as ``write``; dev
    mode uses the shared adapter and the default calendar."""
    enabled = service.inbound_calendar_sync_enabled(user_id)
    free_busy = _server_free_busy(request, user_id)
    if request.app.state.auth_enabled:
        user_service, calendar_id = build_user_calendar_service(
            request.app.state.env,
            user_id=user_id,
            token_cipher=request.app.state.token_cipher,
        )
        return _json(
            user_service.reconcile(
                user_id,
                target_calendar_id=calendar_id,
                free_busy=free_busy,
                enabled=enabled,
            )
        )
    return _json(
        service.reconcile(
            user_id,
            target_calendar_id=DEFAULT_TARGET_CALENDAR_ID,
            free_busy=free_busy,
            enabled=enabled,
        )
    )


@router.post("/recommit")
def recommit(
    service: Service,
    user_id: ActingUser,
    body: RecommitRequest,
) -> JSONResponse:
    """Answer the open recommitment ask with a typed choice. A revise_* choice
    deterministically parks (or resolves) a recovery replan; the resulting
    draft still flows through review + approval."""
    return _json(
        service.recommit(
            user_id,
            body.choice,
            recommitment_request_id=body.recommitment_request_id,
        )
    )


@router.post("/weekly-checkin")
def weekly_checkin(
    service: Service,
    user_id: ActingUser,
    body: WeeklyCheckinRequest | None = None,
) -> JSONResponse:
    """Submit the weekly check-in. Counts are computed server-side; the client
    contributes only optional blockers prose and a recovery preference."""
    body = body or WeeklyCheckinRequest()
    return _json(
        service.weekly_checkin(
            user_id,
            blockers=body.blockers,
            recovery_action=body.recovery_action,
        )
    )


@router.post("/ingest")
def ingest(
    service: Service,
    user_id: ActingUser,
    payload: Annotated[list[dict[str, Any]] | dict[str, Any], Body()],
) -> JSONResponse:
    payloads = payload if isinstance(payload, list) else [payload]
    return _json(service.ingest(user_id, payloads))


@router.get("/status")
def status(service: Service, user_id: ActingUser) -> JSONResponse:
    return _json(service.status(user_id))


# --------------------------------------------------------------------------- #
# Read projections (F-A): JSON the SPA renders from. Each is a thin wrapper over
# a side-effect-free ``CycleService`` projection; the acting user is always
# session-derived. ``/checkin`` is the one mutation — its guard lives in the
# service, so the SPA cannot double-count or report a non-due / foreign task.
# --------------------------------------------------------------------------- #


@router.get("/draft")
def draft(request: Request, service: Service, user_id: ActingUser) -> JSONResponse:
    # Free/busy is fetched server-side so the grid's "fixed" events are the real
    # calendar, never a client-supplied list (same helper /api/adjust uses).
    return _json(service.draft_view(user_id, free_busy=_server_free_busy(request, user_id)))


@router.get("/today")
def today(service: Service, user_id: ActingUser) -> JSONResponse:
    return _json(service.today(user_id))


@router.get("/accountability")
def accountability(service: Service, user_id: ActingUser) -> JSONResponse:
    return _json(service.accountability_view(user_id))


@router.get("/thresholds")
def thresholds(service: Service, user_id: ActingUser) -> JSONResponse:
    return _json(service.thresholds_view())


@router.post("/evidence")
def mark_evidence(
    service: Service, user_id: ActingUser, body: MarkEvidenceRequest
) -> JSONResponse:
    """Append one confirmed evidence item to the profile (NP-D) — a plain profile
    edit (no LLM, no plan invalidation); returns the refreshed ``me`` projection.
    An off-vocabulary ``theme_tag`` is a command-precondition failure (HTTP 409);
    exceeding the evidence cap is the standard contract 422 on rebuild."""
    return _json(
        service.mark_evidence(
            user_id,
            title=body.title,
            organization=body.organization,
            summary=body.summary,
            kind=body.kind,
            theme_tags=body.theme_tags,
        )
    )


@router.get("/pathways")
def pathways(
    service: Service, user_id: ActingUser, track: str | None = None
) -> JSONResponse:
    """Narrative pathway cards for a track plus this user's deterministic slot
    coverage (NP-D). Read-only, kernel-computed, no LLM; ``track`` is an optional
    filter that falls back to the profile's resolved track."""
    return _json(service.pathways_view(user_id, track=track))


@router.post("/onboard/pathways")
def onboard_pathways(
    service: Service,
    user_id: ActingUser,
    payload: Annotated[dict[str, Any], Body()],
) -> JSONResponse:
    """Persistence-free pathway cards + coverage over a *draft* profile (NP-E).

    Powers the onboarding wizard's "Your story" step, which needs live slot
    coverage before anything is saved. Body: ``{user_profile, track?}``; the
    acting user is session-derived (the onboard trust boundary). Nothing persists
    - the only profile write path stays ``POST /api/onboard``. A contract-invalid
    draft profile is the standard 422."""
    return _json(service.preview_pathways(user_id, payload))


@router.get("/evidence-vocabulary")
def evidence_vocabulary(
    service: Service, user_id: ActingUser, role: str | None = None
) -> JSONResponse:
    """The closed evidence-tagging vocabularies for the UI dropdowns (NP-E).

    Returns the fixed ``EvidenceKind`` enum plus the registry's per-track theme
    slice, resolved from ``role`` (the wizard's not-yet-saved ``target_role``) or,
    absent that, the stored profile. Onboarding is not required; registry/enum
    literals only, no LLM."""
    return _json(service.evidence_vocabulary_view(user_id, role=role))


@router.post("/pathways/select")
def select_pathway(
    service: Service, user_id: ActingUser, body: SelectPathwayRequest
) -> JSONResponse:
    """Set or change the profile's pathway selection (NP-E) - a targeted mutation
    preserving every other profile field (the accountability contract included).
    A ``pathway_id`` change invalidates the syllabus/tasks/schedule like ``onboard``;
    an unknown pathway or override slot is a command-precondition failure (409).
    Returns the refreshed ``me`` projection."""
    return _json(
        service.select_pathway(
            user_id, pathway_id=body.pathway_id, slot_overrides=body.slot_overrides
        )
    )


@router.get("/knowledge-map")
def knowledge_map(service: Service, user_id: ActingUser) -> JSONResponse:
    """The account's knowledge map with deterministic per-node mastery tiers (KT-C).

    Read-only: structure from the pathway registry + the append-only overlay, tiers
    from the ``map_state`` kernel fold - no LLM, reproducible on stored data. Empty
    (``has_selection=false``) until a pathway is selected. Personal custom content
    renders as a separate layer and counts toward nothing."""
    return _json(service.knowledge_map_view(user_id))


@router.post("/knowledge-map/setpoint")
def knowledge_map_setpoint(
    service: Service, user_id: ActingUser, body: SetMasteryRequest
) -> JSONResponse:
    """Set a per-node mastery set-point - the only control that lowers a tier (KT-C).

    ``proven`` is evidence-gated, not settable (409); an unknown node is a 409.
    Returns the refreshed map."""
    return _json(
        service.set_mastery(user_id, node_id=body.node_id, target_tier=body.target_tier)
    )


@router.post("/knowledge-map/note")
def knowledge_map_note(
    service: Service, user_id: ActingUser, body: UpsertNoteRequest
) -> JSONResponse:
    """Upsert the single private note on a node (KT-C).

    Display-only personal content - never enters a prompt, coverage metric, or
    sponsor report. An unknown node is a 409; the length cap is contract-enforced.
    Returns the refreshed map."""
    return _json(
        service.upsert_note(user_id, node_id=body.node_id, text=body.text)
    )


@router.post("/pathways/fit-notes")
def pathway_fit_notes(
    service: Service,
    user_id: ActingUser,
    payload: Annotated[dict[str, Any], Body()],
) -> JSONResponse:
    """Batched LLM fit notes for the top pathway cards (NP-F) — display-only prose
    that decorates the deterministic ``pathways`` ranking (it participates in no
    card ordering or slot state). Body mirrors ``/onboard/pathways``:
    ``{user_profile?, track?}`` — a draft profile for the wizard's Your-story
    step, or none to use the stored profile. An LLM failure is a 200 with
    ``status: "failed"`` + typed ``reason_code`` (inspected, not caught); the
    cards are never blocked on this call. Nothing persists."""
    return _json(service.pathway_fit_notes(user_id, payload))


@router.post("/story-summary")
def story_summary(service: Service, user_id: ActingUser) -> JSONResponse:
    """User-initiated "where your package stands" summary over the selected
    pathway (NP-F) — display-only prose. Requires a live selection (409
    otherwise); an LLM failure is a 200 with ``status: "failed"`` + typed
    ``reason_code``. Nothing persists — the client holds it for the session."""
    return _json(service.story_summary(user_id))


@router.get("/me")
def me(service: Service, user_id: ActingUser) -> JSONResponse:
    return _json(service.me(user_id))


@router.post("/checkin")
def checkin(service: Service, user_id: ActingUser, body: CheckinRequest) -> JSONResponse:
    return _json(service.checkin(user_id, body.task_id, completed=body.outcome == "complete"))
