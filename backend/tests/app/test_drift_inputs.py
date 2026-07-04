"""ingest feeds the drift classifier its full input (UX pass B4).

Before this increment ingest constructed ``DriftInput(plan=plan,
events=events)`` only, so four of the nine deterministic rules
(capacity_mismatch, calendar_fragmentation, accountability_mismatch,
sponsor_pressure_mismatch) could never fire in production, and an external
calendar deletion fed only read projections — never the classifier. These
tests pin the deterministic derivations (``_drift_input`` /
``_fragmentation_signal`` are pure functions over stored facts) and the
flagship end-to-end route: external delete → EXTERNAL_CONFLICT drift.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from agentic_calendar.contracts.draft_schedule import DraftSchedule
from agentic_calendar.contracts.drift_event import DriftType
from agentic_calendar.contracts.motivation_profile import NudgeChannel, SponsorVisibility
from agentic_calendar.contracts.notification_log import NotificationLog, NotificationStatus
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.recommitment import RecommitmentRequest
from agentic_calendar.contracts.sponsor import Sponsor, SponsorRelationship, SponsorStatus
from agentic_calendar.contracts.task_disposition import (
    DispositionSource,
    TaskDispositionRecord,
    TaskDispositionType,
)
from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent
from agentic_calendar.supervisor.state import SupervisorState as S
from tests.app.test_cycle import (
    USER_ID,
    _activate_plan,
    _advance_past_draft,
    _missed_event,
    make_service,
)


def _context(service, env):  # type: ignore[no-untyped-def]
    onboarding = env.state.get_onboarding(USER_ID)
    run = env.state.latest_run_for_user(USER_ID)
    active = env.plan_store.get_active(USER_ID)
    assert onboarding is not None and run is not None and active is not None
    return onboarding, run, active


def _completed_telemetry(task_id: str, *, actual: int, at: datetime) -> TelemetryEvent:
    return TelemetryEvent(
        telemetry_event_id=f"t_{task_id}_{int(at.timestamp())}",
        task_id=task_id,
        scheduled_duration_min=60,
        actual_duration_min=actual,
        completed=True,
        completion_timestamp=at,
        user_reschedule_count=0,
        data_quality=DataQuality.COMPLETE,
    )


# --------------------------------------------------------------------------- #
# flagship end-to-end: external delete reaches the classifier
# --------------------------------------------------------------------------- #


def test_external_deletion_routes_into_external_conflict_drift() -> None:
    """A user deleting Loop's events on their real calendar is the loudest
    feedback they can give. Before B4 the EVENT_DELETED disposition fed only
    read projections; now it reaches the classifier and — with the miss
    pattern the rule requires — produces EXTERNAL_CONFLICT and a replan
    proposal instead of dead-ending in a banner."""
    service, env, clock = make_service()
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)

    # Durable memory of the external deletion (what reconcile records).
    env.disposition_store.append(
        TaskDispositionRecord(
            disposition_id="disp_del_1",
            user_id=USER_ID,
            plan_version=proposed.plan_version,
            task_id="dp_001",
            disposition=TaskDispositionType.EVENT_DELETED,
            source=DispositionSource.SYSTEM,
            reason_code=ReasonCode.EXTERNAL_EVENT_DELETED,
            created_at=clock.now(),
        )
    )

    # The rule needs >= 3 misses with >= 50% associated to the conflict:
    # dp_001 missed twice (rescheduled attempts) + dp_002 missed once.
    result = service.ingest(
        USER_ID,
        [
            _missed_event("evt_m1", "dp_001"),
            _missed_event("evt_m2", "dp_001"),
            _missed_event("evt_m3", "dp_002"),
        ],
    )

    drift_types = {e.drift_type for e in result.drift_events}
    assert DriftType.EXTERNAL_CONFLICT in drift_types
    assert result.replan_required is True
    assert result.state is S.REPLAN_REQUIRED


# --------------------------------------------------------------------------- #
# derivation pins for the assembler
# --------------------------------------------------------------------------- #


def test_weekly_cycles_bucket_fully_elapsed_local_weeks() -> None:
    service, env, _clock = make_service()
    _activate_plan(service)
    onboarding, run, active = _context(service, env)
    now = env.clock.now()
    durations = {t.task_id: t.estimated_duration_min for t in active.plan.tasks}

    # Fabricate a draft: dp_001 ended three weeks ago, dp_002 two weeks ago,
    # plus an entry in the CURRENT (not yet elapsed) week that must be skipped.
    def entry(task_id: str, end: datetime) -> dict:  # type: ignore[type-arg]
        return {
            "task_id": task_id,
            "start": (end - timedelta(minutes=60)).isoformat(),
            "end": end.isoformat(),
        }

    fabricated = DraftSchedule.model_validate(
        {
            "draft_schedule_id": "draft_fab",
            "plan_version": active.plan_version,
            "created_at": now.isoformat(),
            "entries": [
                entry("dp_001", now - timedelta(days=21)),
                entry("dp_002", now - timedelta(days=14)),
                # Current week (not yet elapsed): must not produce a cycle.
                # A non-plan id keeps the draft's unique-task rule satisfied.
                entry("dp_999", now),
            ],
        }
    )
    env.state.save_draft(USER_ID, fabricated)
    # House rule: rebuild through full validation, never model_copy.
    fab_run = run.model_validate(run.model_dump() | {"draft_schedule_id": "draft_fab"})

    events = [
        _completed_telemetry("dp_001", actual=45, at=now - timedelta(days=21)),
    ]
    di = service._drift_input(onboarding, fab_run, active, events)

    assert len(di.weekly_cycles) == 2  # the current week is excluded
    assert [c.scheduled_min for c in di.weekly_cycles] == [
        durations["dp_001"],
        durations["dp_002"],
    ]
    assert [c.completed_min for c in di.weekly_cycles] == [45, 0]


def test_fragmentation_window_shrinks_when_entries_occupy_it() -> None:
    service, env, _clock = make_service()
    _activate_plan(service)
    onboarding, _run, _active = _context(service, env)
    now_local = env.clock.now().astimezone(onboarding.tzinfo())

    empty = service._fragmentation_signal(onboarding, (), now_local)
    assert empty.total_free_min > 0
    assert empty.largest_free_block_min <= empty.total_free_min

    # Fill tomorrow's entire scheduling window (08:00-22:30 in the canonical
    # profile): total free time drops by exactly that window.
    tomorrow = (now_local + timedelta(days=1)).date()
    tz = onboarding.tzinfo()
    blocker = DraftSchedule.model_validate(
        {
            "draft_schedule_id": "draft_block",
            "plan_version": "plan_x",
            "created_at": env.clock.now().isoformat(),
            "entries": [
                {
                    "task_id": "dp_001",
                    "start": datetime.combine(tomorrow, datetime.min.time(), tz).isoformat(),
                    "end": (
                        datetime.combine(tomorrow, datetime.min.time(), tz)
                        + timedelta(hours=23)
                    ).isoformat(),
                }
            ],
        }
    )
    carved = service._fragmentation_signal(onboarding, tuple(blocker.entries), now_local)
    window_minutes = (22 * 60 + 30) - 8 * 60  # canonical 08:00-22:30
    assert empty.total_free_min - carved.total_free_min == window_minutes


def test_declined_interventions_and_sponsor_pressure_derivation() -> None:
    service, env, _clock = make_service()
    _activate_plan(service)
    onboarding, run, active = _context(service, env)
    now = env.clock.now()

    # A stale unanswered ask counts; a fresh one does not.
    for request_id, age_days in (("req_stale", 8), ("req_fresh", 1)):
        env.recommitment_store.append_request(
            RecommitmentRequest(
                recommitment_request_id=request_id,
                user_id=USER_ID,
                plan_version=active.plan_version,
                decision_id="intv_x",
                reason_code=ReasonCode.USER_RECOMMITMENT_REQUIRED,
                requested_at=now - timedelta(days=age_days),
            )
        )
    # A recently revoked sponsor counts as a decline AND flags the disable.
    sponsor = Sponsor(
        sponsor_id="spn_1",
        user_id=USER_ID,
        relationship=SponsorRelationship.PEER,
        contact_channel=NudgeChannel.EMAIL,
        status=SponsorStatus.PENDING,
        invited_at=now - timedelta(days=30),
        created_at=now - timedelta(days=30),
        updated_at=now - timedelta(days=30),
    )
    env.sponsor_store.invite(sponsor)
    env.sponsor_store.accept("spn_1")
    env.sponsor_store.revoke("spn_1")
    # Two sent reports inside the window; a dry-run must not count.
    for log_id, status, dry in (
        ("nlog_1", NotificationStatus.SENT, False),
        ("nlog_2", NotificationStatus.SENT, False),
        ("nlog_3", NotificationStatus.DRY_RUN, True),
    ):
        env.notification_log_store.append(
            NotificationLog(
                notification_log_id=log_id,
                report_id="rep_1",
                sponsor_id="spn_1",
                user_id=USER_ID,
                visibility_level=SponsorVisibility.SUMMARY_ONLY,
                channel=NudgeChannel.EMAIL,
                status=status,
                dry_run=dry,
                created_at=now - timedelta(days=2),
            )
        )

    di = service._drift_input(onboarding, run, active, [])

    assert di.declined_interventions == 2  # stale ask + revoked sponsor
    assert di.sponsor_reporting_disabled is True
    assert di.sponsor_reports_sent_recent == 2
    assert di.external_conflict_task_ids == frozenset()
