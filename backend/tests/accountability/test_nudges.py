"""Tests for nudge delivery: channel preference, quiet hours, audit.

Phase 7 acceptance: private nudges respect ``nudge_channel_preference`` and
``quiet_hours`` with zero violations in tests.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from agentic_calendar.accountability.nudge_store import InMemoryNudgeStore
from agentic_calendar.accountability.nudges import (
    NudgeDeliveryService,
    resolve_deliver_at,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.accountability_intervention import (
    AccountabilityAction,
    InterventionDecision,
    PolicyRuleEvaluation,
)
from agentic_calendar.contracts.motivation_profile import NudgeChannel, QuietHours
from agentic_calendar.contracts.nudge import NudgeStatus
from agentic_calendar.contracts.reason_codes import ReasonCode

from ._builders import build_contract

LA = ZoneInfo("America/Los_Angeles")
NOON = datetime(2026, 5, 10, 12, 0, tzinfo=LA)


def _evaluations(matched_policy: str | None = None) -> list[PolicyRuleEvaluation]:
    rows = []
    for name in (
        "missed_task_warning",
        "recovery_plan",
        "weekly_checkin_required",
        "scope_reduction",
        "sponsor_summary",
    ):
        rows.append(
            PolicyRuleEvaluation(
                policy_name=name,
                matched=name == matched_policy,
                observed_value=0.0,
                threshold_value=1.0,
            )
        )
    return rows


def _decision(
    action: AccountabilityAction | None = AccountabilityAction.SEND_USER_NUDGE,
    reason: ReasonCode | None = ReasonCode.MISSED_TASK_THRESHOLD_REACHED,
    policy: str | None = "missed_task_warning",
) -> InterventionDecision:
    return InterventionDecision(
        decision_id="intv_1",
        user_id="user_123",
        plan_id="plan_004",
        contract_id="acct_1",
        action=action,
        reason_code=reason,
        policy_name=policy,
        sponsor_action=None,
        sponsor_reason_code=None,
        evaluations=_evaluations(policy),
        decided_at=NOON,
    )


def _service(now: datetime) -> tuple[NudgeDeliveryService, InMemoryNudgeStore]:
    store = InMemoryNudgeStore()
    service = NudgeDeliveryService(
        clock=FrozenClock(now),
        id_generator=DeterministicIdGenerator(),
        store=store,
    )
    return service, store


def test_sent_outside_quiet_hours_on_preferred_channel() -> None:
    service, store = _service(NOON)
    record = service.maybe_deliver(
        decision=_decision(),
        contract=build_contract(nudge_channel_preference=NudgeChannel.PUSH),
        tz=LA,
    )
    assert record is not None
    assert record.status is NudgeStatus.SENT
    assert record.channel is NudgeChannel.PUSH
    assert record.deliver_at == NOON
    assert store.all() == [record]


def test_quiet_hours_defer_to_end_boundary() -> None:
    late = datetime(2026, 5, 10, 23, 15, tzinfo=LA)
    service, _ = _service(late)
    record = service.maybe_deliver(decision=_decision(), contract=build_contract(), tz=LA)
    assert record is not None
    assert record.status is NudgeStatus.DEFERRED_QUIET_HOURS
    assert record.deliver_at == datetime(2026, 5, 11, 8, 0, tzinfo=LA)


def test_early_morning_defers_to_same_day_end() -> None:
    dawn = datetime(2026, 5, 10, 6, 30, tzinfo=LA)
    service, _ = _service(dawn)
    record = service.maybe_deliver(decision=_decision(), contract=build_contract(), tz=LA)
    assert record is not None
    assert record.deliver_at == datetime(2026, 5, 10, 8, 0, tzinfo=LA)


def test_zero_quiet_hours_violations_across_full_day() -> None:
    """Sweep every half hour of a day: no sent nudge ever lands in the window,
    and every deferral lands exactly on the end boundary."""
    quiet = QuietHours(start="22:00", end="08:00")
    start, end = time(22, 0), time(8, 0)
    for half_hours in range(48):
        now = datetime(2026, 5, 10, 0, 0, tzinfo=LA) + timedelta(minutes=30 * half_hours)
        deliver_at, deferred = resolve_deliver_at(now, quiet, LA)
        local = deliver_at.astimezone(LA)
        in_window = local.time() >= start or local.time() < end
        if deferred:
            assert local.time() == end
            assert deliver_at > now
        else:
            assert deliver_at == now
            assert not in_window


def test_same_day_quiet_window() -> None:
    quiet = QuietHours(start="12:00", end="14:00")
    inside = datetime(2026, 5, 10, 13, 0, tzinfo=LA)
    deliver_at, deferred = resolve_deliver_at(inside, quiet, LA)
    assert deferred and deliver_at == datetime(2026, 5, 10, 14, 0, tzinfo=LA)
    outside = datetime(2026, 5, 10, 14, 0, tzinfo=LA)
    deliver_at, deferred = resolve_deliver_at(outside, quiet, LA)
    assert not deferred and deliver_at == outside


def test_zero_length_window_disables_quiet_hours() -> None:
    quiet = QuietHours(start="08:00", end="08:00")
    now = datetime(2026, 5, 10, 8, 0, tzinfo=LA)
    deliver_at, deferred = resolve_deliver_at(now, quiet, LA)
    assert not deferred and deliver_at == now


def test_dry_run_sends_nothing_but_logs() -> None:
    service, store = _service(NOON)
    record = service.maybe_deliver(
        decision=_decision(), contract=build_contract(), tz=LA, dry_run=True
    )
    assert record is not None
    assert record.status is NudgeStatus.DRY_RUN
    assert store.all() == [record]


def test_inactive_contract_produces_no_nudge() -> None:
    """Scenario 24: disabling the contract stops nudges."""
    service, store = _service(NOON)
    inactive_decision = InterventionDecision(
        decision_id="intv_1",
        user_id="user_123",
        plan_id="plan_004",
        contract_id="acct_1",
        action=None,
        reason_code=ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE,
        policy_name=None,
        sponsor_action=None,
        sponsor_reason_code=ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE,
        evaluations=[],
        decided_at=NOON,
    )
    record = service.maybe_deliver(
        decision=inactive_decision,
        contract=build_contract(active=False),
        tz=LA,
    )
    assert record is None
    assert store.all() == []


def test_recovery_action_speaks_through_approval_not_nudge() -> None:
    service, store = _service(NOON)
    record = service.maybe_deliver(
        decision=_decision(
            action=AccountabilityAction.GENERATE_RECOVERY_PLAN_DRAFT,
            reason=ReasonCode.BEHIND_SCHEDULE_THRESHOLD_REACHED,
            policy="recovery_plan",
        ),
        contract=build_contract(),
        tz=LA,
    )
    assert record is None
    assert store.all() == []


def test_direct_nudge_requests_recommitment() -> None:
    service, _ = _service(NOON)
    record = service.maybe_deliver(decision=_decision(), contract=build_contract(), tz=LA)
    assert record is not None
    assert record.recommitment_requested is True


def test_checkin_prompt_does_not_request_recommitment() -> None:
    service, _ = _service(NOON)
    record = service.maybe_deliver(
        decision=_decision(
            action=AccountabilityAction.CREATE_WEEKLY_CHECKIN_PROMPT,
            reason=ReasonCode.CHECKIN_DUE,
            policy="weekly_checkin_required",
        ),
        contract=build_contract(),
        tz=LA,
    )
    assert record is not None
    assert record.recommitment_requested is False
    assert record.reason_code is ReasonCode.CHECKIN_DUE
