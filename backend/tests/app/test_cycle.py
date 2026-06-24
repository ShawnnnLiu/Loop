"""End-to-end tests for :class:`agentic_calendar.app.cycle.CycleService`.

Every test drives the real supervisor routing table over a fully wired
:func:`build_environment` with fixture LLM nodes, a ``FrozenClock`` anchored to
the golden-test Monday (2026-05-04), and a ``DeterministicIdGenerator`` — so
every assertion below pins deterministic states, typed reason codes, and store
contents, never prompt text.

Fixture facts these tests rely on (verified against ``tests/fixtures/valid``):

* ``user_profile`` → ``user_123``, target_role ``"Backend SWE"``,
  max_session_length_min 120, deep-work windows Mon 18-21 / Wed 19-21:30.
* ``syllabus_units`` → ``syl_003`` with modules ``dp`` (claims ``claim_012``,
  ``claim_018``) and ``api_design`` (claim ``claim_024``).
* ``task_plan`` → ``plan_004`` with tasks ``dp_001`` (concept_review, 60 min)
  and ``dp_002`` (practice, 90 min, depends on ``dp_001``); validates against
  ``syl_003`` + ``user_123``.
* ``motivation_profile`` (first fixture) → ``mot_001`` for ``user_123`` with
  ``recovery_mode_preference="reschedule"``,
  ``missed_task_escalation_threshold=2``, and
  ``behind_schedule_intervention_threshold_pct=20``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from agentic_calendar.app.cycle import (
    HASH_CANONICALIZATION_VERSION,
    CycleError,
    CycleService,
)
from agentic_calendar.app.environment import (
    AppEnvironment,
    LlmNodeBundle,
    NodeDependencies,
    PlannerNode,
    build_environment,
)
from agentic_calendar.app.state import ReplanKind, RunRecord
from agentic_calendar.calendar_writer.adapter import (
    ExternalCalendarAdapter,
    ExternalEventHandle,
    ExternalEventRecord,
)
from agentic_calendar.calendar_writer.google_adapter import GoogleCalendarApiError
from agentic_calendar.calendar_writer.in_memory_adapter import (
    FailureModes,
    InMemoryCalendarAdapter,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.data_access_audit import (
    DataAccessOutcome,
    DataAccessPurpose,
)
from agentic_calendar.contracts.draft_schedule import DraftSchedule, DraftScheduleEntry
from agentic_calendar.contracts.drift_event import DriftType
from agentic_calendar.contracts.hashing import canonical_payload_hash
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import ValidationResult
from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.llm_nodes.planner import FixturePlanner
from agentic_calendar.llm_nodes.reflection_summary import DeterministicReflectionSummary
from agentic_calendar.llm_nodes.strategist import FixtureStrategist
from agentic_calendar.llm_nodes.user_facing_explanation import (
    DeterministicUserFacingExplanation,
)
from agentic_calendar.planning.plan_version import LifecycleState
from agentic_calendar.supervisor.state import SupervisorState as S
from tests._fixture_loader import iter_valid

USER_ID = "user_123"

#: Monday noon UTC, matching the golden-suite HORIZON_START anchor (Mon
#: 2026-05-04) so deep-work day-of-week math is deterministic.
HAPPY_NOW = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)

#: Claims referenced by the canonical syllabus ``syl_003``.
SYLLABUS_CLAIM_IDS = ("claim_012", "claim_018", "claim_024")

PLAN_TASK_IDS = ("dp_001", "dp_002")


# --------------------------------------------------------------------------- #
# harness
# --------------------------------------------------------------------------- #


def _canonical_profile() -> UserProfile:
    return UserProfile.model_validate(next(iter_valid("user_profile")).payload)


def _canonical_syllabus() -> SyllabusUnits:
    return SyllabusUnits.model_validate(next(iter_valid("syllabus_units")).payload)


def _canonical_plan() -> TaskPlan:
    return TaskPlan.model_validate(next(iter_valid("task_plan")).payload)


def _motivation_profile_payload() -> dict[str, Any]:
    """First motivation-profile fixture: ``mot_001`` for ``user_123``."""
    payload = dict(next(iter_valid("motivation_profile")).payload)
    assert payload["user_id"] == USER_ID
    return payload


def _seed_claims(env: AppEnvironment) -> None:
    """Append the three claims ``syl_003`` references to the claim store.

    ``claim_024`` exists as a fixture; ``claim_012``/``claim_018`` are built
    from the long-lived ``claim_topic_dp`` fixture payload with the id
    overridden (full re-validation through the ``SourceClaim`` contract).
    """
    payloads = {
        str(fixture.payload["claim_id"]): fixture.payload
        for fixture in iter_valid("source_claim")
    }
    base = payloads["claim_topic_dp"]
    for claim_id in ("claim_012", "claim_018"):
        env.claim_store.append(SourceClaim.model_validate({**base, "claim_id": claim_id}))
    env.claim_store.append(SourceClaim.model_validate(payloads["claim_024"]))


class CountingPlanner:
    """Delegating planner that counts ``run`` invocations (loop-bound proof)."""

    def __init__(self, inner: FixturePlanner) -> None:
        self._inner = inner
        self.calls = 0

    def run(
        self,
        *,
        run_id: str,
        syllabus: SyllabusUnits,
        user_profile: UserProfile | None = None,
        repair: ValidationResult | None = None,
    ) -> TaskPlan:
        self.calls += 1
        return self._inner.run(
            run_id=run_id, syllabus=syllabus, user_profile=user_profile, repair=repair
        )


class RecordingPlanner:
    """Constant planner that records the repair context of every pass."""

    def __init__(self, plan: TaskPlan) -> None:
        self._plan = plan
        self.repairs: list[ValidationResult | None] = []

    def run(
        self,
        *,
        run_id: str,
        syllabus: SyllabusUnits,
        user_profile: UserProfile | None = None,
        repair: ValidationResult | None = None,
    ) -> TaskPlan:
        del run_id, syllabus, user_profile
        self.repairs.append(repair)
        return self._plan


def make_service(
    *,
    motivation_profile: Mapping[str, Any] | None = None,
    calendar_adapter: ExternalCalendarAdapter | None = None,
    db_path: Path | None = None,
    strategist_fixtures: Mapping[str, SyllabusUnits] | None = None,
    planner_fixtures: Mapping[str, TaskPlan] | None = None,
    planner: PlannerNode | None = None,
    seed_claims: bool = True,
    onboard: bool = True,
    now: datetime = HAPPY_NOW,
    tuning_path: Path | None = None,
) -> tuple[CycleService, AppEnvironment, FrozenClock]:
    """Build a fully wired service over fixture nodes.

    ``onboard=False`` + ``seed_claims=False`` rebuilds over an existing SQLite
    file without re-writing persisted state (restart-survival tests).
    """
    clock = FrozenClock(now)
    ids = DeterministicIdGenerator()
    profile = _canonical_profile()
    syllabus = _canonical_syllabus()
    plan = _canonical_plan()

    def factory(deps: NodeDependencies) -> LlmNodeBundle:
        del deps
        return LlmNodeBundle(
            strategist=FixtureStrategist(
                strategist_fixtures or {profile.target_role: syllabus}
            ),
            planner=planner
            or FixturePlanner(planner_fixtures or {syllabus.syllabus_version: plan}),
            reflection=DeterministicReflectionSummary(),
            explanation=DeterministicUserFacingExplanation(),
        )

    env = build_environment(
        nodes_factory=factory,
        clock=clock,
        id_generator=ids,
        calendar_adapter=calendar_adapter,
        db_path=db_path,
        tuning_path=tuning_path,
    )
    if seed_claims:
        _seed_claims(env)
    service = CycleService(env)
    if onboard:
        service.onboard(
            {
                "user_profile": profile.model_dump(mode="json"),
                "timezone": "UTC",
                "motivation_profile": motivation_profile,
            }
        )
    return service, env, clock


def _activate_plan(service: CycleService) -> Any:
    """Drive propose → approve → write to ACTIVE_PLAN; return the ProposeResult."""
    proposed = service.propose(USER_ID)
    assert proposed.state is S.AWAITING_USER_APPROVAL
    service.approve(USER_ID)
    written = service.write(USER_ID)
    assert written.state is S.ACTIVE_PLAN
    return proposed


def _advance_past_draft(
    env: AppEnvironment, clock: FrozenClock, draft_schedule_id: str
) -> DraftSchedule:
    """Advance the frozen clock 1h past the last draft entry's end.

    The cycle's accountability/projection logic only counts a task as "due"
    once its draft entry has ended, and the drafts are scheduled in the
    future at propose time.
    """
    draft = env.state.get_draft(draft_schedule_id)
    assert draft is not None
    latest_end = max(entry.end for entry in draft.entries)
    delta_seconds = int((latest_end - clock.now()).total_seconds()) + 3600
    assert delta_seconds > 0
    clock.advance(seconds=delta_seconds)
    return draft


def _completed_event(
    event_id: str,
    task_id: str,
    *,
    completed_at: datetime,
    scheduled: int = 60,
    actual: int | None = None,
) -> dict[str, Any]:
    """A fully user-reported completion (data_quality stays ``complete``)."""
    return {
        "telemetry_event_id": event_id,
        "task_id": task_id,
        "scheduled_duration_min": scheduled,
        "actual_duration_min": actual if actual is not None else scheduled,
        "completed": True,
        "completion_timestamp": completed_at,
        "user_reschedule_count": 0,
        "data_quality": "complete",
    }


def _missed_event(event_id: str, task_id: str, *, scheduled: int = 60) -> dict[str, Any]:
    """An incomplete event: no actuals, no completion timestamp (contract-legal)."""
    return {
        "telemetry_event_id": event_id,
        "task_id": task_id,
        "scheduled_duration_min": scheduled,
        "actual_duration_min": None,
        "completed": False,
        "user_reschedule_count": 0,
        "data_quality": "complete",
    }


# --------------------------------------------------------------------------- #
# A. propose happy path
# --------------------------------------------------------------------------- #


def test_propose_happy_path_parks_run_awaiting_approval() -> None:
    """Propose ends in AWAITING_USER_APPROVAL with a DRAFT plan version, a
    stored hashable draft, a persisted run record, and the validated syllabus
    saved for later replans."""
    service, env, _clock = make_service()

    result = service.propose(USER_ID)

    assert result.state is S.AWAITING_USER_APPROVAL
    assert result.reason_code is None
    assert result.scheduled_task_count == len(PLAN_TASK_IDS)
    assert result.unscheduled_tasks == []

    plan_version = env.plan_store.get(USER_ID, result.plan_version)
    assert plan_version.state is LifecycleState.DRAFT
    assert plan_version.generation_history

    draft = env.state.get_draft(result.draft_schedule_id)
    assert draft is not None
    assert result.draft_payload_hash == canonical_payload_hash(
        draft, HASH_CANONICALIZATION_VERSION
    )

    run = env.state.get_run(result.run_id)
    assert run is not None
    assert run.state is S.AWAITING_USER_APPROVAL
    assert run.plan_version == result.plan_version
    assert run.draft_schedule_id == result.draft_schedule_id

    syllabus = env.state.get_syllabus(USER_ID)
    assert syllabus is not None
    assert syllabus.syllabus_version == "syl_003"


# --------------------------------------------------------------------------- #
# B. propose without onboarding
# --------------------------------------------------------------------------- #


def test_propose_without_onboarding_raises_cycle_error() -> None:
    """Propose for a user who never onboarded is a command-precondition error,
    not a workflow failure."""
    service, _env, _clock = make_service()

    with pytest.raises(CycleError):
        service.propose("user_never_onboarded")


# --------------------------------------------------------------------------- #
# C. strategist failure
# --------------------------------------------------------------------------- #


def test_strategist_failure_routes_to_error_with_llm_call_failed() -> None:
    """An LLMNodeError from the strategist becomes the typed panic edge:
    ERROR_REQUIRES_USER with reason_code LLM_CALL_FAILED, persisted on the run."""
    service, env, _clock = make_service(
        strategist_fixtures={"Other Role": _canonical_syllabus()}
    )

    result = service.propose(USER_ID)

    assert result.state is S.ERROR_REQUIRES_USER
    assert result.reason_code is ReasonCode.LLM_CALL_FAILED

    run = env.state.get_run(result.run_id)
    assert run is not None
    assert run.state is S.ERROR_REQUIRES_USER
    assert run.reason_code is ReasonCode.LLM_CALL_FAILED


# --------------------------------------------------------------------------- #
# D. syllabus validation repair exhaustion
# --------------------------------------------------------------------------- #


def test_orphan_claims_exhaust_strategist_repairs_with_typed_reason() -> None:
    """With an empty claim store the syllabus's claim refs are orphans; after
    two strategist repair attempts the run lands in ERROR_REQUIRES_USER with
    SOURCE_CLAIM_VALIDATION_FAILED and a user-facing explanation attached."""
    service, env, _clock = make_service(seed_claims=False)

    result = service.propose(USER_ID)

    assert result.state is S.ERROR_REQUIRES_USER
    assert result.reason_code is ReasonCode.SOURCE_CLAIM_VALIDATION_FAILED
    assert result.explanation is not None

    run = env.state.get_run(result.run_id)
    assert run is not None
    assert run.state is S.ERROR_REQUIRES_USER
    assert run.reason_code is ReasonCode.SOURCE_CLAIM_VALIDATION_FAILED


# --------------------------------------------------------------------------- #
# E. planner validation repair exhaustion
# --------------------------------------------------------------------------- #


def test_invalid_plan_exhausts_planner_repairs_with_typed_reason() -> None:
    """A plan referencing a module absent from the syllabus fails validation on
    every pass; the bounded planner repair loop (2 attempts) exhausts into
    ERROR_REQUIRES_USER with a typed reason and an explanation attached."""
    bad_plan = TaskPlan.model_validate(
        {
            "plan_version": "plan_bad",
            "tasks": [
                {
                    "task_id": "ghost_001",
                    "module_id": "nonexistent",
                    "title": "task in a module the syllabus does not define",
                    "dependencies": [],
                    "estimated_duration_min": 60,
                    "cognitive_load": 3,
                    "category": "practice",
                    "required_focus_level": "medium",
                    "splittable": False,
                }
            ],
        }
    )
    service, env, _clock = make_service(planner_fixtures={"syl_003": bad_plan})

    result = service.propose(USER_ID)

    assert result.state is S.ERROR_REQUIRES_USER
    assert result.reason_code is not None
    assert isinstance(result.reason_code, ReasonCode)
    assert result.explanation is not None

    run = env.state.get_run(result.run_id)
    assert run is not None
    assert run.state is S.ERROR_REQUIRES_USER
    assert run.reason_code is result.reason_code


def test_planner_repair_retries_receive_failed_validation_result() -> None:
    """The repair loop hands each retry the previous failed ValidationResult:
    pass 1 gets None, passes 2-3 get the typed user-fit violations (150-min
    non-splittable task vs max_session_length_min=120). The stub keeps
    returning the same plan, so the bounded loop (axiom 04: 2 repair
    re-prompts) still exhausts into ERROR_REQUIRES_USER."""
    bad = _canonical_plan().model_dump()
    bad["tasks"][0]["estimated_duration_min"] = 150  # > fixture max session 120
    bad["tasks"][0]["splittable"] = False
    recording = RecordingPlanner(TaskPlan.model_validate(bad))
    service, env, _clock = make_service(planner=recording)

    result = service.propose(USER_ID)

    assert result.state is S.ERROR_REQUIRES_USER
    assert result.reason_code is ReasonCode.USER_FIT_VIOLATED
    assert len(recording.repairs) == 3  # 1 initial pass + 2 bounded repairs
    assert recording.repairs[0] is None
    for repair in recording.repairs[1:]:
        assert repair is not None
        assert repair.valid is False
        assert repair.violations
        assert repair.reason_code is ReasonCode.USER_FIT_VIOLATED

    # The terminal ProposeResult carries the typed, structured violations from
    # the failed validation so clients can surface the specific reason (the
    # 150-min non-splittable task vs the fixture's 120-min max session) instead
    # of a generic message.
    assert result.violations
    assert any(
        v.type is ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION
        and v.details["duration_min"] == 150
        and v.details["max_session_length_min"] == 120
        for v in result.violations
    )

    run = env.state.get_run(result.run_id)
    assert run is not None
    assert run.state is S.ERROR_REQUIRES_USER
    assert run.reason_code is ReasonCode.USER_FIT_VIOLATED


# --------------------------------------------------------------------------- #
# F. scheduler exhaustion
# --------------------------------------------------------------------------- #


def test_blocked_horizon_exhausts_scheduler_planner_iterations() -> None:
    """A fully busy horizon makes every scheduler pass fail; the loop is bounded
    at two scheduler→planner iterations and exhaustion preserves the typed
    per-task reasons, debug payloads, and repair options."""
    counting = CountingPlanner(FixturePlanner({"syl_003": _canonical_plan()}))
    service, env, clock = make_service(planner=counting)
    busy = [{"start": clock.now(), "end": clock.now() + timedelta(days=14)}]

    # The horizon is pinned to the busy interval: this test exercises the
    # bounded-iteration exhaustion, not the timeline-derived default.
    result = service.propose(USER_ID, free_busy=busy, horizon_days=14)

    assert result.state is S.ERROR_REQUIRES_USER
    assert counting.calls == 2  # axiom 05 bound: at most two planner passes
    assert result.reason_code is not None
    assert result.unscheduled_tasks
    for unscheduled in result.unscheduled_tasks:
        assert isinstance(unscheduled.reason_code, ReasonCode)
        assert unscheduled.debug
    assert result.repair_options

    run = env.state.get_run(result.run_id)
    assert run is not None
    assert run.state is S.ERROR_REQUIRES_USER
    assert run.reason_code is result.unscheduled_tasks[0].reason_code


def test_propose_places_blocks_in_user_local_timezone() -> None:
    """Time-of-day constraints are read in the user's timezone, not UTC. A
    Pacific user's blocks land within their LOCAL allowed hours — the previous
    UTC anchoring placed them ~7-8h off (08:00 local read as 08:00 UTC, i.e.
    ~01:00 Pacific)."""
    service, env, _clock = make_service()
    # Re-onboard the same profile in a western timezone (make_service uses UTC).
    service.onboard(
        {
            "user_profile": _canonical_profile().model_dump(mode="json"),
            "timezone": "America/Los_Angeles",
        }
    )

    result = service.propose(USER_ID)

    assert result.state is S.AWAITING_USER_APPROVAL
    draft = env.state.get_draft(result.draft_schedule_id)
    assert draft is not None and draft.entries

    tz = ZoneInfo("America/Los_Angeles")
    hard = _canonical_profile().hard_constraints
    for entry in draft.entries:
        local_start = entry.start.astimezone(tz)
        local_end = entry.end.astimezone(tz)
        assert f"{local_start.hour:02d}:{local_start.minute:02d}" >= hard.no_events_before
        assert f"{local_end.hour:02d}:{local_end.minute:02d}" <= hard.no_events_after


def test_default_horizon_covers_the_profile_timeline() -> None:
    """The default scheduling horizon is the profile's full timeline
    (timeline_weeks * 7), not a fixed fortnight: user-fit validation sizes
    plans to weekly_hours * timeline_weeks, and the Phase 1 scheduler places
    the whole plan inside the horizon — a 14-day default made any plan that
    needs week 3+ structurally unschedulable (capacity failures cascading
    into DEPENDENCY_BLOCKED). A 15-day busy block must therefore no longer
    fail a propose for the canonical 10-week profile; placement lands after
    the block, beyond the old default."""
    service, env, clock = make_service()
    busy = [{"start": clock.now(), "end": clock.now() + timedelta(days=15)}]

    result = service.propose(USER_ID, free_busy=busy)

    assert result.state is S.AWAITING_USER_APPROVAL
    assert result.draft_schedule_id is not None
    draft = env.state.get_draft(result.draft_schedule_id)
    assert draft is not None
    assert all(e.start >= clock.now() + timedelta(days=15) for e in draft.entries)


# --------------------------------------------------------------------------- #
# G. approve
# --------------------------------------------------------------------------- #


def test_approve_records_hash_locked_approval_and_promotes_plan() -> None:
    """Approve stores an ApprovalEvent whose approved_payload_hash equals the
    canonical hash of the stored draft, and the plan version moves to APPROVED."""
    service, env, _clock = make_service()
    proposed = service.propose(USER_ID)

    approved = service.approve(USER_ID)

    assert approved.state is S.CALENDAR_WRITE_APPROVED
    assert approved.rejected is False
    assert approved.approval_event_id is not None

    approval = env.approval_store.get(approved.approval_event_id)
    draft = env.state.get_draft(proposed.draft_schedule_id)
    assert draft is not None
    expected_hash = canonical_payload_hash(draft, HASH_CANONICALIZATION_VERSION)
    assert approval.approved_payload_hash == expected_hash
    assert approved.approved_payload_hash == expected_hash

    plan_version = env.plan_store.get(USER_ID, proposed.plan_version)
    assert plan_version.state is LifecycleState.APPROVED


def test_reject_discards_run_and_plan() -> None:
    """approve(reject=True) terminates the run in TERMINAL_DISCARDED and
    discards the draft plan version."""
    service, env, _clock = make_service()
    proposed = service.propose(USER_ID)

    rejected = service.approve(USER_ID, reject=True)

    assert rejected.state is S.TERMINAL_DISCARDED
    assert rejected.rejected is True
    plan_version = env.plan_store.get(USER_ID, proposed.plan_version)
    assert plan_version.state is LifecycleState.DISCARDED


# --------------------------------------------------------------------------- #
# H. command guards
# --------------------------------------------------------------------------- #


def test_approve_before_propose_raises() -> None:
    """Approve without any run is a command-precondition error."""
    service, _env, _clock = make_service()
    with pytest.raises(CycleError):
        service.approve(USER_ID)


def test_write_before_approve_raises() -> None:
    """Write while the run still awaits approval is rejected (approval gate)."""
    service, _env, _clock = make_service()
    service.propose(USER_ID)
    with pytest.raises(CycleError):
        service.write(USER_ID)


def test_double_approve_raises() -> None:
    """A second approve fails: the run already left AWAITING_USER_APPROVAL."""
    service, _env, _clock = make_service()
    service.propose(USER_ID)
    service.approve(USER_ID)
    with pytest.raises(CycleError):
        service.approve(USER_ID)


# --------------------------------------------------------------------------- #
# I. write
# --------------------------------------------------------------------------- #


def test_dry_run_previews_without_side_effects_then_write_activates() -> None:
    """dry-run leaves the state machine untouched and creates no mappings;
    the real write verifies every event and activates the plan."""
    service, env, _clock = make_service()
    proposed = service.propose(USER_ID)
    service.approve(USER_ID)
    draft = env.state.get_draft(proposed.draft_schedule_id)
    assert draft is not None

    dry = service.write(USER_ID, dry_run=True)

    assert dry.dry_run is True
    assert dry.state is S.CALENDAR_WRITE_APPROVED
    assert dry.planned_event_count == len(draft.entries)
    for task_id in PLAN_TASK_IDS:
        assert env.mapping_store.list_for_task(task_id) == []
    run = env.state.get_run(proposed.run_id)
    assert run is not None
    assert run.state is S.CALENDAR_WRITE_APPROVED

    written = service.write(USER_ID)

    assert written.dry_run is False
    assert written.state is S.ACTIVE_PLAN
    assert written.write_status == "success"
    assert set(written.mapping_status_by_task) == set(PLAN_TASK_IDS)
    assert all(v == "verified" for v in written.mapping_status_by_task.values())

    active = env.plan_store.get_active(USER_ID)
    assert active is not None
    assert active.plan_version == proposed.plan_version
    assert active.state is LifecycleState.ACTIVE


# --------------------------------------------------------------------------- #
# I-b. full-horizon / plan-level write (D-7, D-8): the whole horizon is approved
# and written as ONE unit; no per-week slicing creeps in.
# --------------------------------------------------------------------------- #


def _multi_week_profile() -> UserProfile:
    """Canonical profile, but the only deep-work window is Monday evening and the
    daily cap fits just one of the two deep tasks per day. ``dp_002`` depends on
    ``dp_001``; with a single deep day per week and a 120-min cap, the greedy
    scheduler must push ``dp_002`` to the *following* Monday — so the draft spans
    more than one calendar week."""
    data = _canonical_profile().model_dump(mode="json")
    data["deep_work_windows"] = [{"day": "Mon", "start": "18:00", "end": "21:00"}]
    data["hard_constraints"]["max_daily_study_min"] = 120
    return UserProfile.model_validate(data)


def test_multi_week_plan_writes_full_horizon_in_single_approval() -> None:
    """A multi-week draft is proposed, then a SINGLE approve → write writes every
    entry across the full horizon (plan-level, D-7; entire horizon, D-8). Guards
    against a future regression toward per-week approval / per-week writes."""
    service, env, _clock = make_service()
    # Re-onboard with a profile that forces a genuine multi-week draft (onboard
    # upserts; profile edits during dogfooding are expected).
    service.onboard(
        {"user_profile": _multi_week_profile().model_dump(mode="json"), "timezone": "UTC"}
    )

    proposed = service.propose(USER_ID)
    assert proposed.state is S.AWAITING_USER_APPROVAL
    assert proposed.scheduled_task_count == len(PLAN_TASK_IDS)

    draft = env.state.get_draft(proposed.draft_schedule_id)
    assert draft is not None
    # Guard the test itself: the draft must genuinely span >1 ISO week, otherwise
    # it would not exercise the no-per-week-slicing guarantee at all.
    iso_weeks = {entry.start.isocalendar()[:2] for entry in draft.entries}
    assert len(iso_weeks) >= 2
    assert {entry.task_id for entry in draft.entries} == set(PLAN_TASK_IDS)

    # One approval, one write — covering every entry across the whole horizon.
    service.approve(USER_ID)
    written = service.write(USER_ID)

    assert written.state is S.ACTIVE_PLAN
    assert written.write_status == "success"
    assert set(written.mapping_status_by_task) == set(PLAN_TASK_IDS)
    assert all(status == "verified" for status in written.mapping_status_by_task.values())


# --------------------------------------------------------------------------- #
# J. write failure
# --------------------------------------------------------------------------- #


def test_adapter_create_failure_preserves_reason_and_blocks_activation() -> None:
    """An injected create_event failure lands the run in
    CALENDAR_WRITE_FAILED_STATE with reason_code CALENDAR_WRITE_FAILED and the
    plan never becomes active."""
    adapter = InMemoryCalendarAdapter(
        id_generator=DeterministicIdGenerator(),
        failure_modes=FailureModes(fail_create_for_task_ids=frozenset({"dp_001"})),
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    proposed = service.propose(USER_ID)
    service.approve(USER_ID)

    written = service.write(USER_ID)

    assert written.state is S.CALENDAR_WRITE_FAILED_STATE
    assert written.reason_code is ReasonCode.CALENDAR_WRITE_FAILED
    # The manager's failure text reaches the operator surface, not just the
    # bare reason_code (typed prose only, never raw content/secrets).
    assert written.error is not None
    assert "create_event" in written.error
    assert env.plan_store.get_active(USER_ID) is None
    assert env.plan_store.get(USER_ID, proposed.plan_version).state is (
        LifecycleState.APPROVED
    )

    run = env.state.get_run(proposed.run_id)
    assert run is not None
    assert run.state is S.CALENDAR_WRITE_FAILED_STATE
    assert run.reason_code is ReasonCode.CALENDAR_WRITE_FAILED


def test_discard_releases_a_failed_write_run_for_a_fresh_start() -> None:
    """From CALENDAR_WRITE_FAILED the user can abandon the dead run: discard
    moves it to TERMINAL_DISCARDED and discards its plan version (no calendar
    touch), and a fresh propose then starts a clean run awaiting approval."""
    adapter = InMemoryCalendarAdapter(
        id_generator=DeterministicIdGenerator(),
        failure_modes=FailureModes(fail_create_for_task_ids=frozenset({"dp_001"})),
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    proposed = service.propose(USER_ID)
    service.approve(USER_ID)
    assert service.write(USER_ID).state is S.CALENDAR_WRITE_FAILED_STATE

    result = service.discard(USER_ID)

    assert result.rejected is True
    assert result.state is S.TERMINAL_DISCARDED
    assert result.plan_version == proposed.plan_version
    run = env.state.get_run(proposed.run_id)
    assert run is not None
    assert run.state is S.TERMINAL_DISCARDED
    assert env.plan_store.get(USER_ID, proposed.plan_version).state is (
        LifecycleState.DISCARDED
    )

    # The user can now start over: a fresh propose makes a new run.
    again = service.propose(USER_ID)
    assert again.run_id != proposed.run_id
    assert again.state is S.AWAITING_USER_APPROVAL


def test_discard_requires_a_failed_write_run() -> None:
    """Discard is only valid out of CALENDAR_WRITE_FAILED — it must not be a
    back door to abandon a run that is merely awaiting approval or approved."""
    service, _env, _clock = make_service()
    service.propose(USER_ID)
    service.approve(USER_ID)  # run is now CALENDAR_WRITE_APPROVED, not failed
    with pytest.raises(CycleError, match="calendar_write_failed"):
        service.discard(USER_ID)


class _QueryRaisingAdapter:
    """:class:`ExternalCalendarAdapter` stub whose duplicate-guard query
    raises — the live dogfood failure mode (Google ``events.list`` failing
    inside ``approve_and_write`` step 4)."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def create_event(
        self,
        *,
        target_calendar_id: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        metadata: Mapping[str, str],
    ) -> ExternalEventHandle:
        raise AssertionError("create_event must not be reached")

    def read_event(
        self, *, target_calendar_id: str, calendar_event_id: str
    ) -> ExternalEventRecord | None:
        return None

    def delete_event(
        self, *, target_calendar_id: str, calendar_event_id: str
    ) -> None:
        return None

    def query_events_by_metadata(
        self, *, target_calendar_id: str, run_id: str
    ) -> list[ExternalEventRecord]:
        raise self._exc


def test_adapter_query_failure_returns_typed_result_instead_of_raising() -> None:
    """The live dogfood regression: a Google API failure during the manager's
    duplicate guard must surface as a RETURNED WriteCycleResult — typed state
    + reason_code, run record matching — never escape ``service.write`` as a
    raw exception that strands the run in CALENDAR_WRITE_IN_PROGRESS."""
    adapter = _QueryRaisingAdapter(
        GoogleCalendarApiError(
            "events.list failed for calendar 'dogfood': HTTP 403: "
            "insufficient permissions",
            status=403,
        )
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    proposed = service.propose(USER_ID)
    service.approve(USER_ID)

    written = service.write(USER_ID)

    assert written.dry_run is False
    assert written.state is S.CALENDAR_WRITE_FAILED_STATE
    assert written.reason_code is ReasonCode.CALENDAR_WRITE_FAILED
    # The Google adapter's enriched provider detail must survive the
    # manager's WriteResult translation all the way to the operator result.
    assert written.error is not None
    assert "events.list failed" in written.error
    assert written.written_task_ids == []
    assert env.plan_store.get_active(USER_ID) is None

    run = env.state.get_run(proposed.run_id)
    assert run is not None
    assert run.state is S.CALENDAR_WRITE_FAILED_STATE
    assert run.reason_code is ReasonCode.CALENDAR_WRITE_FAILED


def test_write_guard_catches_untranslated_domain_error() -> None:
    """Defense in depth (axiom 16): even an AgenticCalendarError that is NOT
    a CalendarWriterError — i.e. one the manager's boundary translation does
    not catch — must land the run in CALENDAR_WRITE_FAILED_STATE with the
    typed fallback reason_code instead of escaping the operator surface."""
    adapter = _QueryRaisingAdapter(AgenticCalendarError("untranslated defect"))
    service, env, _clock = make_service(calendar_adapter=adapter)
    proposed = service.propose(USER_ID)
    service.approve(USER_ID)

    written = service.write(USER_ID)

    assert written.state is S.CALENDAR_WRITE_FAILED_STATE
    assert written.reason_code is ReasonCode.CALENDAR_WRITE_FAILED
    assert written.write_status == "failed"
    # The defense-in-depth path also carries the failure text for the
    # operator (domain-error messages are typed prose, never secrets).
    assert written.error is not None
    assert "untranslated defect" in written.error
    assert written.written_task_ids == []

    run = env.state.get_run(proposed.run_id)
    assert run is not None
    assert run.state is S.CALENDAR_WRITE_FAILED_STATE
    assert run.reason_code is ReasonCode.CALENDAR_WRITE_FAILED


# --------------------------------------------------------------------------- #
# K. hash recheck at the cycle level
# --------------------------------------------------------------------------- #


def test_hash_recheck_blocks_write_when_run_points_at_different_draft() -> None:
    """If the run record is doctored to reference a draft other than the one
    approved, the manager's mandatory hash recheck aborts pre-write: typed
    failure state, no mappings, no external events."""
    service, env, clock = make_service()
    proposed = service.propose(USER_ID)
    service.approve(USER_ID)

    now = clock.now()
    doctored = DraftSchedule(
        draft_schedule_id="draft_doctored",
        plan_version=proposed.plan_version,
        entries=(
            DraftScheduleEntry(
                task_id="dp_001",
                start=now + timedelta(days=1),
                end=now + timedelta(days=1, hours=1),
            ),
        ),
        created_at=now,
    )
    env.state.save_draft(USER_ID, doctored)
    run = env.state.get_run(proposed.run_id)
    assert run is not None
    env.state.save_run(
        RunRecord.model_validate(
            run.model_dump() | {"draft_schedule_id": doctored.draft_schedule_id}
        )
    )

    written = service.write(USER_ID)

    assert written.state is S.CALENDAR_WRITE_FAILED_STATE
    assert written.reason_code is not None
    assert written.reason_code is ReasonCode.APPROVAL_HASH_MISMATCH
    assert written.written_task_ids == []
    assert written.mapping_status_by_task == {}
    for task_id in PLAN_TASK_IDS:
        assert env.mapping_store.list_for_task(task_id) == []
    assert isinstance(env.calendar_adapter, InMemoryCalendarAdapter)
    assert env.calendar_adapter.all_events() == []


# --------------------------------------------------------------------------- #
# L. ingest before any active plan
# --------------------------------------------------------------------------- #


def test_ingest_before_active_plan_stores_telemetry_without_assessment() -> None:
    """Telemetry ingested with no active plan is stored but never assessed."""
    service, env, clock = make_service()

    result = service.ingest(
        USER_ID, [_completed_event("evt_001", "dp_001", completed_at=clock.now())]
    )

    assert result.ingested_count == 1
    assert result.assessed is False
    assert result.run_id is None
    assert result.state is None
    assert len(env.telemetry_store.all()) == 1


# --------------------------------------------------------------------------- #
# M. plan completion
# --------------------------------------------------------------------------- #


def test_completing_every_task_reaches_terminal_success() -> None:
    """Completed events covering every plan task end the journey in
    TERMINAL_SUCCESS with plan_completed=True."""
    service, env, clock = make_service()
    proposed = _activate_plan(service)

    result = service.ingest(
        USER_ID,
        [
            _completed_event("evt_001", "dp_001", completed_at=clock.now()),
            _completed_event(
                "evt_002", "dp_002", scheduled=90, completed_at=clock.now()
            ),
        ],
    )

    assert result.assessed is True
    assert result.plan_completed is True
    assert result.state is S.TERMINAL_SUCCESS
    run = env.state.get_run(proposed.run_id)
    assert run is not None
    assert run.state is S.TERMINAL_SUCCESS


# --------------------------------------------------------------------------- #
# N. NO_DRIFT self-loop
# --------------------------------------------------------------------------- #


def test_partial_completion_without_drift_self_loops_active_plan() -> None:
    """One completed task out of two fires no drift rule: the run takes the
    NO_DRIFT self-loop and stays in ACTIVE_PLAN."""
    service, _env, clock = make_service()
    _activate_plan(service)

    result = service.ingest(
        USER_ID, [_completed_event("evt_001", "dp_001", completed_at=clock.now())]
    )

    assert result.assessed is True
    assert result.plan_completed is False
    assert result.drift_events == []
    assert result.replan_required is False
    assert result.state is S.ACTIVE_PLAN


# --------------------------------------------------------------------------- #
# O. duration drift → recalibration replan → continuation
# --------------------------------------------------------------------------- #


def test_duration_drift_requires_recalibration_replan_then_continuation() -> None:
    """Five completed dp_001 events at 2x the scheduled duration (ratio 2.0 >=
    the 1.3 underestimate threshold, sample 5 >= duration_min_sample, and 5.0
    weighted calibration evidence) classify DURATION_UNDERESTIMATE and require
    a recalibration replan. The pooled-serving consent gate is consulted (and
    denied — no consent record exists) with an audit entry either way. The
    continuation propose produces a child plan version whose concept_review
    duration is recalibrated to 120 minutes."""
    service, env, clock = make_service()
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)

    events = [
        _completed_event(
            f"evt_{i:03d}",
            "dp_001",
            scheduled=60,
            actual=120,
            completed_at=clock.now(),
        )
        for i in range(1, 6)
    ]
    result = service.ingest(USER_ID, events)

    assert result.ingested_count == 5
    assert result.assessed is True
    drift_types = {event.drift_type for event in result.drift_events}
    assert DriftType.DURATION_UNDERESTIMATE in drift_types
    underestimate = next(
        event
        for event in result.drift_events
        if event.drift_type is DriftType.DURATION_UNDERESTIMATE
    )
    assert underestimate.reason_code is ReasonCode.DRIFT_DURATION_UNDERESTIMATE
    assert result.replan_required is True
    assert result.replan_kind is ReplanKind.RECALIBRATION
    assert result.recovery_mode_pending_user_choice is False
    assert result.state is S.REPLAN_REQUIRED

    pooled_checks = [
        entry
        for entry in env.audit_store.list_for_user(USER_ID)
        if entry.purpose is DataAccessPurpose.POOLED_SERVING
    ]
    assert pooled_checks
    assert all(entry.outcome is DataAccessOutcome.DENIED for entry in pooled_checks)

    continuation = service.propose(USER_ID)

    assert continuation.state is S.AWAITING_USER_APPROVAL
    assert continuation.parent_plan_version == proposed.plan_version
    assert continuation.plan_version != proposed.plan_version
    assert continuation.replan_kind is ReplanKind.RECALIBRATION

    parent = env.plan_store.get(USER_ID, proposed.plan_version)
    child = env.plan_store.get(USER_ID, continuation.plan_version)
    parent_durations = {t.task_id: t.estimated_duration_min for t in parent.plan.tasks}
    child_durations = {t.task_id: t.estimated_duration_min for t in child.plan.tasks}
    assert child_durations != parent_durations
    assert child_durations["dp_001"] == 120  # 60 min x observed 2.0 ratio
    assert child_durations["dp_002"] == parent_durations["dp_002"]  # uncalibrated


# --------------------------------------------------------------------------- #
# P. accountability recovery replan
# --------------------------------------------------------------------------- #


def test_behind_schedule_accountability_drives_recovery_replan() -> None:
    """Pinned deterministic behavior with the canonical motivation profile
    (mot_001: missed-task threshold 2, behind-schedule threshold 20%,
    recovery preference "reschedule"):

    With both draft entries due and exactly ONE missed event (dp_001),
    ``missed_tasks_7d`` is 1 < 2, so the first private-lane rule does not fire,
    and ``behind_schedule_percent`` is 100% >= 20%, so the second rule selects
    GENERATE_RECOVERY_PLAN_DRAFT. Drift fires deterministically alongside it
    via DEPENDENCY_BLOCKED (dp_002 depends on the missed dp_001), which makes
    the ACTIVE_PLAN → DRIFT_DETECTED → REPLAN_REQUIRED route reachable. The
    accountability decision wins replan precedence; the profile's preference
    maps directly to RECOVERY/reschedule with no pending user choice, and the
    continuation reschedules identical plan content under a new version."""
    service, env, clock = make_service(motivation_profile=_motivation_profile_payload())
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)

    result = service.ingest(USER_ID, [_missed_event("evt_001", "dp_001")])

    assert result.assessed is True
    assert result.accountability_action == "generate_recovery_plan_draft"
    assert result.accountability_reason_code is (
        ReasonCode.BEHIND_SCHEDULE_THRESHOLD_REACHED
    )
    assert result.nudge_id is None  # recovery drafts speak via approval, not nudges
    assert result.recommitment_request_id is None
    drift_types = {event.drift_type for event in result.drift_events}
    assert DriftType.DEPENDENCY_BLOCKED in drift_types
    assert result.replan_required is True
    assert result.replan_kind is ReplanKind.RECOVERY
    assert result.recovery_mode is RecoveryAction.RESCHEDULE
    assert result.recovery_mode_pending_user_choice is False
    assert result.state is S.REPLAN_REQUIRED

    continuation = service.propose(USER_ID)

    assert continuation.state is S.AWAITING_USER_APPROVAL
    assert continuation.parent_plan_version == proposed.plan_version
    assert continuation.replan_kind is ReplanKind.RECOVERY
    assert continuation.recovery_mode is RecoveryAction.RESCHEDULE

    parent = env.plan_store.get(USER_ID, proposed.plan_version)
    child = env.plan_store.get(USER_ID, continuation.plan_version)
    assert [t.estimated_duration_min for t in child.plan.tasks] == [
        t.estimated_duration_min for t in parent.plan.tasks
    ]  # reschedule changes placement only, never content


# --------------------------------------------------------------------------- #
# Q. restart survival (SQLite)
# --------------------------------------------------------------------------- #


def test_restart_survival_resumes_approve_and_write_from_sqlite(
    tmp_path: Path,
) -> None:
    """A brand-new service over the same SQLite file — without re-onboarding —
    resumes the persisted run: approve and write succeed and status shows the
    active plan. This is the cross-process resumability guarantee."""
    db_path = tmp_path / "cycle.db"
    service, env, _clock = make_service(db_path=db_path)
    proposed = service.propose(USER_ID)
    assert proposed.state is S.AWAITING_USER_APPROVAL
    assert env.db is not None
    env.db.close()

    service2, env2, _clock2 = make_service(
        db_path=db_path,
        onboard=False,
        seed_claims=False,
        now=HAPPY_NOW + timedelta(hours=1),
    )

    approved = service2.approve(USER_ID)
    assert approved.state is S.CALENDAR_WRITE_APPROVED
    assert approved.plan_version == proposed.plan_version

    written = service2.write(USER_ID)
    assert written.state is S.ACTIVE_PLAN
    assert written.write_status == "success"

    status = service2.status(USER_ID)
    assert status.onboarded is True
    assert status.state is S.ACTIVE_PLAN
    assert status.active_plan_version == proposed.plan_version
    active = env2.plan_store.get_active(USER_ID)
    assert active is not None
    assert active.plan_version == proposed.plan_version


# --------------------------------------------------------------------------- #
# R. status is read-only
# --------------------------------------------------------------------------- #


def test_status_is_read_only_and_repeatable() -> None:
    """Two consecutive status calls return identical results and perform no
    state transition."""
    service, env, _clock = make_service()
    proposed = service.propose(USER_ID)

    first = service.status(USER_ID)
    second = service.status(USER_ID)

    assert first == second
    assert first.state is S.AWAITING_USER_APPROVAL
    assert first.plan_version == proposed.plan_version
    run = env.state.get_run(proposed.run_id)
    assert run is not None
    assert run.state is S.AWAITING_USER_APPROVAL


# --------------------------------------------------------------------------- #
# S. tuning file consumption (Phase 9d)
# --------------------------------------------------------------------------- #


def test_tuning_file_overrides_drift_thresholds_and_journals(tmp_path: Path) -> None:
    """The composition root actually consumes the tuning file: the classifier
    serves the overridden threshold and the change is journaled (axiom 07
    'no silent threshold changes')."""
    tuning_file = tmp_path / "tuning.toml"
    tuning_file.write_text(
        'justification = "Solo dogfooding: act on a single observation."\n'
        'dataset_reference = "manual prior"\n'
        "[drift_thresholds]\n"
        "duration_min_sample = 1\n",
        encoding="utf-8",
    )
    _service, env, _clock = make_service(tuning_path=tuning_file)
    assert env.tuning.drift_thresholds.duration_min_sample == 1
    entries = env.threshold_log_store.list_all()
    assert len(entries) == 1
    assert entries[0].config_section == "drift_thresholds"
    assert entries[0].threshold_field == "duration_min_sample"
    assert entries[0].prior_value == 5
    assert entries[0].new_value == 1


# --------------------------------------------------------------------------- #
# K. Read projections + guarded check-in (F-A)
# --------------------------------------------------------------------------- #


def test_me_returns_profile_email_and_timezone() -> None:
    service, _env, _clock = make_service()
    me = service.me(USER_ID)
    assert me.onboarded is True
    assert me.timezone == "UTC"
    assert me.profile is not None
    assert me.profile.target_role == "Backend SWE"
    # The in-memory dev build has no Google credential, so no email.
    assert me.email is None


def test_me_before_onboarding_is_empty() -> None:
    service, _env, _clock = make_service(onboard=False)
    me = service.me(USER_ID)
    assert me.onboarded is False
    assert me.profile is None
    assert me.timezone is None


def test_draft_view_exposes_pending_draft_and_canonical_hash() -> None:
    service, env, _clock = make_service()
    proposed = service.propose(USER_ID)
    view = service.draft_view(USER_ID)
    assert view.draft is not None
    assert view.hash_canonicalization_version == HASH_CANONICALIZATION_VERSION
    stored = env.state.get_draft(proposed.draft_schedule_id)
    assert stored is not None
    # The view's hash is the real canonical hash — exactly what propose surfaced
    # for approval (axiom 06: the user approves against this datum).
    assert view.payload_hash == canonical_payload_hash(stored, HASH_CANONICALIZATION_VERSION)
    assert view.payload_hash == proposed.draft_payload_hash
    assert {entry.task_id for entry in view.draft.entries} == set(PLAN_TASK_IDS)
    # Titles are joined from the draft's plan version so the grid can label
    # blocks (a draft entry carries only the task_id).
    assert set(view.task_titles) == set(PLAN_TASK_IDS)
    assert all(view.task_titles.values())
    # Dev build: free/busy is fetched server-side and unavailable here, so empty
    # — never a client-supplied list.
    assert view.free_busy == []


def test_draft_view_without_a_run_is_empty() -> None:
    service, _env, _clock = make_service()
    view = service.draft_view(USER_ID)
    assert view.draft is None
    assert view.payload_hash is None
    assert view.hash_canonicalization_version == HASH_CANONICALIZATION_VERSION


def test_today_lists_tasks_with_due_and_reported_flags() -> None:
    service, env, clock = make_service()
    proposed = _activate_plan(service)
    today = service.today(USER_ID)
    assert today.timezone == "UTC"
    assert {row.task_id for row in today.tasks} == set(PLAN_TASK_IDS)
    # Every block is in the future at HAPPY_NOW → not yet due, none reported.
    assert all(row.due is False for row in today.tasks)
    assert all(row.reported is False for row in today.tasks)
    # Advance the clock past every block → all due now.
    _advance_past_draft(env, clock, proposed.draft_schedule_id)
    assert all(row.due is True for row in service.today(USER_ID).tasks)


def test_today_without_active_plan_is_empty_but_keeps_timezone() -> None:
    service, _env, _clock = make_service()
    today = service.today(USER_ID)
    assert today.tasks == []
    assert today.timezone == "UTC"


def test_thresholds_view_reports_effective_defaults() -> None:
    service, _env, _clock = make_service()
    view = service.thresholds_view()
    assert view.sections  # the tunable registry is non-empty
    # No tuning overrides applied → every served value equals the code default.
    assert all(
        field.status == "default" for section in view.sections for field in section.fields
    )
    assert view.history == []


def test_accountability_view_empty_state_without_motivation_profile() -> None:
    service, _env, _clock = make_service()  # motivation_profile defaults to None
    view = service.accountability_view(USER_ID)
    assert view.has_motivation_profile is False
    assert view.state is None
    assert view.decision is None
    assert view.checkin_status is None


def test_accountability_view_flags_motivation_profile_present() -> None:
    service, _env, _clock = make_service(motivation_profile=_motivation_profile_payload())
    view = service.accountability_view(USER_ID)
    assert view.has_motivation_profile is True


def test_checkin_completed_records_telemetry() -> None:
    service, env, clock = make_service()
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)
    result = service.checkin(USER_ID, "dp_001", completed=True)
    assert result.ingested_count == 1
    stored = env.telemetry_store.list_for_task("dp_001")
    assert len(stored) == 1
    assert stored[0].completed is True


def test_checkin_missed_records_incomplete_telemetry() -> None:
    service, env, clock = make_service()
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)
    service.checkin(USER_ID, "dp_001", completed=False)
    stored = env.telemetry_store.list_for_task("dp_001")
    assert len(stored) == 1
    assert stored[0].completed is False


def test_checkin_rejects_task_not_yet_due() -> None:
    service, _env, _clock = make_service()
    _activate_plan(service)  # blocks are still in the future at HAPPY_NOW
    with pytest.raises(CycleError, match="not yet due"):
        service.checkin(USER_ID, "dp_001", completed=True)


def test_checkin_rejects_unknown_task() -> None:
    service, env, clock = make_service()
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)
    with pytest.raises(CycleError, match="not in the active schedule"):
        service.checkin(USER_ID, "ghost_999", completed=True)


def test_checkin_rejects_double_submit() -> None:
    service, env, clock = make_service()
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)
    service.checkin(USER_ID, "dp_001", completed=True)
    with pytest.raises(CycleError, match="already been reported"):
        service.checkin(USER_ID, "dp_001", completed=True)
