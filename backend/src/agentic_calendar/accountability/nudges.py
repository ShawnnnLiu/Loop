"""Private nudge delivery (Phase 7).

Spec: ``docs/specs/nudge.schema.md``; axiom 21 intervention table. Golden
scenario 16 ("a private in-app nudge only").

Delivery is deterministic end to end: the channel is always the contract's
``nudge_channel_preference``, and a nudge requested inside the contract's
quiet hours is **deferred to the next quiet-hours end boundary, never
dropped** and never sent inside the window (Phase 7 acceptance: zero
quiet-hours violations). Wording is rendered elsewhere (LLM-touchable); this
service handles only when/where/whether, and writes an audit record for every
attempt.

The MVP records delivery intent and outcome only; the concrete channel
transport — including dispatch of deferred records at their ``deliver_at`` —
is wired in a later phase (same split as the sponsor delivery service).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, tzinfo

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.accountability_contract import AccountabilityContract
from agentic_calendar.contracts.accountability_intervention import (
    AccountabilityAction,
    InterventionDecision,
)
from agentic_calendar.contracts.motivation_profile import QuietHours
from agentic_calendar.contracts.nudge import NudgeRecord, NudgeStatus

from .nudge_store import NudgeStore

#: Private-lane actions that reach the user as a nudge. ``send_user_nudge`` is
#: the direct/escalation nudge and therefore asks for recommitment (axiom 21
#: intervention table); recovery drafts speak through the approval flow, not a
#: nudge, and the sponsor lane never produces one.
_NUDGE_ACTIONS: dict[AccountabilityAction, bool] = {
    AccountabilityAction.SEND_USER_NUDGE: True,
    AccountabilityAction.CREATE_WEEKLY_CHECKIN_PROMPT: False,
    AccountabilityAction.SUGGEST_SCOPE_REDUCTION: False,
}


def _parse_hhmm(value: str) -> time:
    hour, minute = (int(p) for p in value.split(":"))
    return time(hour, minute)


def _in_quiet_window(t: time, start: time, end: time) -> bool:
    """Overnight-aware membership; the ``end`` instant itself is outside.

    A zero-length window (``start == end``) disables quiet hours rather than
    swallowing the whole day.
    """
    if start == end:
        return False
    if start < end:
        return start <= t < end
    return t >= start or t < end


def resolve_deliver_at(now: datetime, quiet_hours: QuietHours, tz: tzinfo) -> tuple[datetime, bool]:
    """Return ``(deliver_at, deferred)`` for a nudge requested at ``now``.

    Inside quiet hours the delivery instant is the next ``end`` boundary in
    the user's timezone; outside, it is ``now`` unchanged.
    """
    local = now.astimezone(tz)
    start = _parse_hhmm(quiet_hours.start)
    end = _parse_hhmm(quiet_hours.end)
    if not _in_quiet_window(local.time(), start, end):
        return now, False
    boundary = local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if boundary <= local:
        boundary += timedelta(days=1)
    return boundary, True


class NudgeDeliveryService:
    """Deliver (or defer) the private nudge a decision calls for."""

    def __init__(self, *, clock: Clock, id_generator: IdGenerator, store: NudgeStore) -> None:
        self._clock = clock
        self._ids = id_generator
        self._store = store

    def maybe_deliver(
        self,
        *,
        decision: InterventionDecision,
        contract: AccountabilityContract,
        tz: tzinfo,
        dry_run: bool = False,
    ) -> NudgeRecord | None:
        """Deliver the nudge for ``decision``, or return None when it has none.

        None means the decision carries no private nudge: no action chosen,
        the contract is inactive (scenario 24: no further nudges), or the
        action speaks through another surface (recovery approval flow).
        Every actual attempt — sent, deferred, dry-run — is appended to the
        audit store.
        """
        if not contract.active:
            return None
        if decision.action is None or decision.action not in _NUDGE_ACTIONS:
            return None
        if decision.reason_code is None:
            # The decision validator pairs every action with a reason code.
            raise ValueError("decision carries an action without its reason_code")

        now = self._clock.now()
        deliver_at, deferred = resolve_deliver_at(now, contract.quiet_hours, tz)
        if dry_run:
            status = NudgeStatus.DRY_RUN
            deliver_at = now
        elif deferred:
            status = NudgeStatus.DEFERRED_QUIET_HOURS
        else:
            status = NudgeStatus.SENT

        record = NudgeRecord(
            nudge_id=self._ids.new_id("nudge"),
            user_id=decision.user_id,
            plan_id=decision.plan_id,
            decision_id=decision.decision_id,
            reason_code=decision.reason_code,
            channel=contract.nudge_channel_preference,
            status=status,
            recommitment_requested=_NUDGE_ACTIONS[decision.action],
            created_at=now,
            deliver_at=deliver_at,
        )
        self._store.append(record)
        return record
