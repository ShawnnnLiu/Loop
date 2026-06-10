"""Explicit user recommitment flow (Phase 7).

Spec: ``docs/specs/recommitment-event.schema.md``; axiom 21 intervention table
("Direct nudge" notifies and asks for recommitment; "Accountability reset"
asks the user to revise goal, timeline, or intensity).

Recommitment never mutates anything by itself. ``keep_plan`` records explicit
re-approval of the active plan version; the ``revise_*`` choices map
deterministically onto the recovery/replan and profile-update paths (spec
"Choice Semantics"). A request is answered at most once — a changed mind is a
new request, so the audit trail stays append-only.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.accountability_intervention import (
    AccountabilityAction,
    InterventionDecision,
)
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.recommitment import (
    RecommitmentChoice,
    RecommitmentEvent,
    RecommitmentRequest,
)

#: Deterministic next action per ``revise_*`` choice (spec "Choice Semantics").
#: ``keep_plan`` records re-approval (no recovery mode); ``revise_goal`` routes
#: to the profile-update path (``PROFILE_MAJOR_CHANGE`` invalidation), so
#: neither appears here.
RECOMMITMENT_CHOICE_TO_RECOVERY_MODE: Mapping[RecommitmentChoice, RecoveryAction] = (
    MappingProxyType(
        {
            RecommitmentChoice.REVISE_TIMELINE: RecoveryAction.EXTEND_TIMELINE,
            RecommitmentChoice.REVISE_INTENSITY: RecoveryAction.SCOPE_REDUCTION,
        }
    )
)


class RecommitmentStoreError(AgenticCalendarError):
    """Base for recommitment-store errors."""


class RecommitmentRequestAlreadyExistsError(RecommitmentStoreError):
    """Attempted to append a ``recommitment_request_id`` that already exists."""


class RecommitmentRequestNotFoundError(RecommitmentStoreError):
    """An event referenced a request the store has never seen."""


class RecommitmentAlreadyAnsweredError(RecommitmentStoreError):
    """A request may be answered at most once; the first answer stands."""


@runtime_checkable
class RecommitmentStore(Protocol):
    """Append/read surface for recommitment requests and answers."""

    def append_request(self, request: RecommitmentRequest) -> None: ...

    def append_event(self, event: RecommitmentEvent) -> None: ...

    def get_request(self, recommitment_request_id: str) -> RecommitmentRequest | None: ...

    def event_for_request(self, recommitment_request_id: str) -> RecommitmentEvent | None: ...

    def all_requests(self) -> list[RecommitmentRequest]: ...

    def all_events(self) -> list[RecommitmentEvent]: ...


class InMemoryRecommitmentStore:
    """Default Phase 7 store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._requests: dict[str, RecommitmentRequest] = {}
        self._request_order: list[str] = []
        self._events_by_request: dict[str, RecommitmentEvent] = {}
        self._event_order: list[str] = []
        self._lock = threading.RLock()

    def append_request(self, request: RecommitmentRequest) -> None:
        with self._lock:
            if request.recommitment_request_id in self._requests:
                raise RecommitmentRequestAlreadyExistsError(request.recommitment_request_id)
            self._requests[request.recommitment_request_id] = request
            self._request_order.append(request.recommitment_request_id)

    def append_event(self, event: RecommitmentEvent) -> None:
        with self._lock:
            if event.recommitment_request_id not in self._requests:
                raise RecommitmentRequestNotFoundError(event.recommitment_request_id)
            if event.recommitment_request_id in self._events_by_request:
                raise RecommitmentAlreadyAnsweredError(event.recommitment_request_id)
            self._events_by_request[event.recommitment_request_id] = event
            self._event_order.append(event.recommitment_request_id)

    def get_request(self, recommitment_request_id: str) -> RecommitmentRequest | None:
        with self._lock:
            return self._requests.get(recommitment_request_id)

    def event_for_request(self, recommitment_request_id: str) -> RecommitmentEvent | None:
        with self._lock:
            return self._events_by_request.get(recommitment_request_id)

    def all_requests(self) -> list[RecommitmentRequest]:
        with self._lock:
            return [self._requests[i] for i in self._request_order]

    def all_events(self) -> list[RecommitmentEvent]:
        with self._lock:
            return [self._events_by_request[i] for i in self._event_order]


def request_recommitment(
    decision: InterventionDecision,
    *,
    plan_version: str,
    store: RecommitmentStore,
    clock: Clock,
    id_generator: IdGenerator,
) -> RecommitmentRequest:
    """Emit (and persist) the explicit recommitment ask for ``decision``.

    Only the direct/escalation nudge asks for recommitment, so the decision
    must carry ``send_user_nudge`` — anything else is a caller bug, not a
    policy outcome.
    """
    if decision.action is not AccountabilityAction.SEND_USER_NUDGE:
        raise ValueError(
            "recommitment is requested only by the direct (send_user_nudge) "
            f"escalation, not {decision.action!r}"
        )
    request = RecommitmentRequest(
        recommitment_request_id=id_generator.new_id("recommit_req"),
        user_id=decision.user_id,
        plan_version=plan_version,
        decision_id=decision.decision_id,
        reason_code=ReasonCode.USER_RECOMMITMENT_REQUIRED,
        requested_at=clock.now(),
    )
    store.append_request(request)
    return request


def record_recommitment(
    request: RecommitmentRequest,
    choice: RecommitmentChoice,
    *,
    store: RecommitmentStore,
    clock: Clock,
    id_generator: IdGenerator,
) -> RecommitmentEvent:
    """Persist the user's explicit answer (append-only, answer-once)."""
    event = RecommitmentEvent(
        recommitment_event_id=id_generator.new_id("recommit_evt"),
        recommitment_request_id=request.recommitment_request_id,
        user_id=request.user_id,
        plan_version=request.plan_version,
        choice=choice,
        created_at=clock.now(),
    )
    store.append_event(event)
    return event
