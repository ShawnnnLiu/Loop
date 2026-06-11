"""Typed ``ReasonCode`` enum (cross-cutting).

Every failure in the system carries a ``ReasonCode``. The enum is the single
source of truth used by validation, the scheduler, the supervisor, telemetry
(later phases), and user-facing explanations (axiom 16).

Add new codes here when a new failure mode appears; the type checker will
then surface every site that must handle them. Phase 1 covers the codes
needed by the planning core; calendar/telemetry/sponsor codes will be added
in their respective phases.

Sources:
    * ``docs/axioms/04-validation-layer.md`` (validation / repair codes)
    * ``docs/axioms/05-scheduler-policy.md`` (scheduler codes)
    * ``docs/axioms/06-calendar-safety.md`` (calendar-safety codes; Phase 2)
    * ``docs/axioms/12-edge-case-policy-engine.md`` (policy codes)
    * ``docs/axioms/15-plan-versioning-and-diffs.md`` (diff reason codes)
    * ``docs/axioms/16-reliability-patterns.md`` (canonical list)
"""

from __future__ import annotations

from enum import StrEnum


class ReasonCode(StrEnum):
    """All typed failure / outcome codes in the system.

    Codes are uppercase ``SCREAMING_SNAKE_CASE`` strings so they survive a
    JSON round-trip unchanged and so they read identically in logs, telemetry,
    and user-facing explanations.
    """

    # --- Validation (axiom 04 + axiom 16) ---
    VALIDATION_FAILED = "VALIDATION_FAILED"
    """Generic validation failure; prefer a more specific code where possible."""

    SCHEMA_INVALID = "SCHEMA_INVALID"
    """Pydantic / shape validation failed (required field missing, bad enum, etc.)."""

    TASK_GRAPH_INVALID = "TASK_GRAPH_INVALID"
    """One or more graph-integrity checks failed (cycle, orphan, duplicate, self-dep)."""

    MODULE_COVERAGE_INSUFFICIENT = "MODULE_COVERAGE_INSUFFICIENT"
    """A required syllabus module has no tasks, or coverage is silently dropped."""

    USER_FIT_VIOLATED = "USER_FIT_VIOLATED"
    """Plan exceeds capacity, session length, or other profile-derived bounds."""

    SCHEDULING_PRECONDITION_FAILED = "SCHEDULING_PRECONDITION_FAILED"
    """The plan is not in a state the scheduler can consume."""

    REPAIR_LIMIT_EXCEEDED = "REPAIR_LIMIT_EXCEEDED"
    """Two failed repair attempts; route to ``error_requires_user``."""

    FORBIDDEN_FIELD_PRESENT = "FORBIDDEN_FIELD_PRESENT"
    """An LLM-produced artifact contained a field code is required to compute
    (e.g. ``task_plan.prerequisites_met``)."""

    # --- Scheduler (axiom 05) ---
    NO_VALID_CONTIGUOUS_BLOCK = "NO_VALID_CONTIGUOUS_BLOCK"
    INSUFFICIENT_WEEKLY_CAPACITY = "INSUFFICIENT_WEEKLY_CAPACITY"
    DEPENDENCY_BLOCKED = "DEPENDENCY_BLOCKED"

    OUTSIDE_ALLOWED_HOURS = "OUTSIDE_ALLOWED_HOURS"
    """Reserved (axiom 05 / 16). **No Phase 1 producer.**

    The Phase 1 scheduler defensively clips candidate windows to
    ``[no_events_before, no_events_after]`` inside ``windows.py`` before
    any placement happens, so this code is structurally unreachable today.
    It remains in the enum so future phases that loosen the clip can emit
    it without breaking downstream consumers."""

    DAILY_LOAD_EXCEEDED = "DAILY_LOAD_EXCEEDED"
    """Reserved (axiom 05 / 16). **No Phase 1 producer.**

    The greedy placement loop currently skips windows where
    ``used_today + duration > max_daily_study_min`` and lets the task fall
    through to ``NO_VALID_CONTIGUOUS_BLOCK`` (or the capacity-promotion
    path). Distinguishing daily-load failures from contiguous-block
    failures is deferred to Phase 2, when richer Scheduler diagnostics
    land alongside the approval UI."""

    DEEP_WORK_REQUIRED_UNAVAILABLE = "DEEP_WORK_REQUIRED_UNAVAILABLE"
    TASK_TOO_LONG_UNSPLITTABLE = "TASK_TOO_LONG_UNSPLITTABLE"

    TASK_TOO_LONG_SPLITTABLE = "TASK_TOO_LONG_SPLITTABLE"
    """Reserved (axiom 05 / 16). **No Phase 1 producer.**

    The greedy MVP never splits: a splittable task that exceeds every window
    falls through to ``NO_VALID_CONTIGUOUS_BLOCK`` with
    ``suggested_repair=SPLIT_TASK`` in its debug payload, and the user
    approves the split via the repair loop. Emitting this code requires a
    scheduler that actually performs splits — which also needs a contract
    change, since ``SchedulerOutput._scheduled_task_ids_unique`` forbids the
    multiple placements per ``task_id`` a split would produce. Both land
    together in the Phase 3 scheduler upgrade (OR-Tools swap, axiom 05)."""

    # --- Supervisor / state machine (axiom 02 + axiom 16) ---
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    USER_APPROVAL_REQUIRED = "USER_APPROVAL_REQUIRED"
    ERROR_REQUIRES_USER = "ERROR_REQUIRES_USER"

    # --- Profile / capacity changes (axiom 12) ---
    PROFILE_MAJOR_CHANGE = "PROFILE_MAJOR_CHANGE"
    CAPACITY_CHANGE = "CAPACITY_CHANGE"

    # --- Calendar safety (axiom 06) ---
    APPROVAL_MISSING = "APPROVAL_MISSING"
    """A calendar write was attempted with no matching ``approval_event_id``
    (axiom 06 line 60)."""

    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    """The approval's ``expires_at`` is at or before ``clock.now()``; user
    must re-approve (axiom 06 lines 195-197)."""

    APPROVAL_HASH_MISMATCH = "APPROVAL_HASH_MISMATCH"
    """Recomputed payload hash does not equal the recorded
    ``approved_payload_hash``. **P1 incident** (axiom 06 line 208)."""

    APPROVAL_HASH_ALGORITHM_UNSUPPORTED = "APPROVAL_HASH_ALGORITHM_UNSUPPORTED"
    """``ApprovalEvent.hash_algorithm`` is not in the allowed set; reject
    (axiom 06 line 165; approval-event spec lines 55-59)."""

    CALENDAR_WRITE_LOCK_BUSY = "CALENDAR_WRITE_LOCK_BUSY"
    """Another in-flight write holds the per-user lock; caller may retry
    after backoff (axiom 06 line 103, axiom 13)."""

    CALENDAR_WRITE_LOCK_EXPIRED = "CALENDAR_WRITE_LOCK_EXPIRED"
    """Lock token's TTL elapsed mid-write, or the cleanup job evicted a
    zombie. Treated as ``EXTERNAL_SYNC_FAILED`` and surfaces the manual-retry
    UI (axiom 06 lines 224-247)."""

    CALENDAR_WRITE_DUPLICATE_DETECTED = "CALENDAR_WRITE_DUPLICATE_DETECTED"
    """Pre-write metadata query found events already tagged with this
    ``run_id``; do not write blindly (axiom 06 lines 120-122)."""

    CALENDAR_WRITE_FAILED = "CALENDAR_WRITE_FAILED"
    """External adapter's ``create_event`` raised. Reconcile by ``run_id``
    (axiom 06 lines 110-118)."""

    CALENDAR_VERIFICATION_FAILED = "CALENDAR_VERIFICATION_FAILED"
    """Post-write read-back found mismatched metadata or scheduled times
    (axiom 06 lines 124-130)."""

    CALENDAR_ROLLBACK_FAILED = "CALENDAR_ROLLBACK_FAILED"
    """Adapter ``delete_event`` raised during rollback; mark
    ``rollback_failed`` and escalate (axiom 06 line 136)."""

    EXTERNAL_SYNC_FAILED = "EXTERNAL_SYNC_FAILED"
    """Partial-failure terminal: some events confirmed missing; no auto-retry.
    Surfaces the manual-retry UI (axiom 06 lines 228-232)."""

    # --- Plan diff (axiom 15 / spec plan-diff) ---
    DEEP_WORK_WINDOW_CONFLICT = "DEEP_WORK_WINDOW_CONFLICT"
    """Field changed "to fit your deep work windows" (plan-diff spec line 137).
    **No Phase 2 producer**; ships with the contract so the diff service can
    emit it without a follow-on enum change."""

    USER_DURATION_CALIBRATION = "USER_DURATION_CALIBRATION"
    """Field changed "based on your recent pace" (plan-diff spec line 138).
    **No Phase 2 producer.**"""

    DEPENDENCY_RESCHEDULED = "DEPENDENCY_RESCHEDULED"
    """Field changed "because a prerequisite moved" (plan-diff spec line 139).
    **No Phase 2 producer.**"""

    WEEKLY_CAPACITY_REBALANCE = "WEEKLY_CAPACITY_REBALANCE"
    """Field changed "to balance your weekly load" (plan-diff spec line 140).
    **No Phase 2 producer.**"""

    EXTERNAL_CALENDAR_CONFLICT = "EXTERNAL_CALENDAR_CONFLICT"
    """Field changed "because of an event on your calendar" (plan-diff spec
    line 141). **No Phase 2 producer.**"""

    USER_PROFILE_CHANGE = "USER_PROFILE_CHANGE"
    """Field changed "based on your profile update" (plan-diff spec line 142).
    **No Phase 2 producer.**"""

    DRIFT_REMEDIATION = "DRIFT_REMEDIATION"
    """Field changed "to adapt to your recent completion pattern" (plan-diff
    spec line 143). **No Phase 2 producer.**"""

    # --- Accountability / sponsor reporting (axiom 21 / axiom 16) ---
    SPONSOR_REPORT_PENDING = "SPONSOR_REPORT_PENDING"
    """A sponsor report draft was produced and awaits user approval before
    send (axiom 21 line 74; sponsor-report spec). Recorded on the draft as its
    ``trigger_reason_code`` and on the ``drafted`` notification-log entry.

    The Phase 3 Sponsor Report Generator emits this whenever it successfully
    builds a draft. The *policy trigger* that decides a report is warranted
    (e.g. ``missed_tasks_7d >= 4``) is the Phase 7 Accountability Policy
    Engine; Phase 3 owns the draft, filter, and gates."""

    SPONSOR_PERMISSION_MISSING = "SPONSOR_PERMISSION_MISSING"
    """Report generation or delivery was attempted without valid permission:
    ``sponsor_enabled`` is false, ``sponsor_visibility_level`` is ``none``, the
    profile's ``sponsor_id`` does not match, or the sponsor row is not in
    ``accepted`` status (axiom 21 line 171; Phase 3 acceptance criteria). Blocks
    send."""

    SPONSOR_VISIBILITY_VIOLATION = "SPONSOR_VISIBILITY_VIOLATION"
    """The privacy filter found denylisted content (raw calendar titles, essay
    drafts, private notes, psychological labels) or a field exceeding the
    visibility level (axiom 21 line 171; golden scenarios 19, 25). Blocks send
    and flags the notification-log entry for engineering review."""

    ACCOUNTABILITY_CONTRACT_INACTIVE = "ACCOUNTABILITY_CONTRACT_INACTIVE"
    """The accountability contract is disabled, so no intervention or sponsor
    report fires (axiom 16 line 41; golden scenarios 18, 24). This is the
    Phase 7 Accountability Policy Engine's short-circuit classification when
    the *whole contract* is off; at the Phase 3 generator level a
    sponsor-disabled profile blocks with ``SPONSOR_PERMISSION_MISSING`` instead."""

    CHECKIN_DUE = "CHECKIN_DUE"
    """The weekly check-in instant has passed for this cycle, no
    ``CheckinEvent`` exists yet, and the grace window is still open (axiom 16
    accountability set; golden scenario 21). Produces a check-in prompt, never
    a recovery draft."""

    CHECKIN_MISSED = "CHECKIN_MISSED"
    """The grace window after the check-in due instant elapsed with no
    ``CheckinEvent`` (axiom 16 accountability set). Same
    ``create_weekly_checkin_prompt`` action as ``CHECKIN_DUE``; the distinct
    code keeps prompt-vs-overdue observable in audit and telemetry."""

    MISSED_TASK_THRESHOLD_REACHED = "MISSED_TASK_THRESHOLD_REACHED"
    """``missed_tasks_7d`` reached the contract's effective escalation
    threshold (axiom 21 ``missed_task_warning``; golden scenario 16). Triggers
    a private user nudge only — never a sponsor notification."""

    BEHIND_SCHEDULE_THRESHOLD_REACHED = "BEHIND_SCHEDULE_THRESHOLD_REACHED"
    """``behind_schedule_percent`` reached the contract's effective
    intervention threshold (axiom 21 ``recovery_plan``; golden scenario 22).
    Triggers a recovery-plan draft; the active plan is never mutated in
    place."""

    LOW_COMPLETION_RATE = "LOW_COMPLETION_RATE"
    """``completion_rate_14d`` fell below the contract's
    ``low_completion_rate_floor`` (axiom 21 ``scope_reduction``). Triggers a
    scope-reduction suggestion routed through the plan-version pipeline."""

    RECOVERY_PLAN_REQUIRED = "RECOVERY_PLAN_REQUIRED"
    """The recovery flow produced (or requires) a recovery artifact: the
    deterministic reschedule fast path's draft version, or the typed planner
    request for ``scope_reduction`` / ``extend_timeline`` modes (axiom 16
    accountability set; axiom 15 — always a new draft plan version)."""

    ACCOUNTABILITY_MISMATCH = "ACCOUNTABILITY_MISMATCH"
    """The drift classifier observed repeated misses *plus* declined
    accountability interventions (axiom 07 drift table; golden scenario 23).
    Maps 1:1 from ``DriftType.ACCOUNTABILITY_MISMATCH``; the policy response is
    ``revise_accountability_contract``, never a sponsor notification."""

    SPONSOR_PRESSURE_MISMATCH = "SPONSOR_PRESSURE_MISMATCH"
    """The drift classifier observed sponsor reporting being disabled after
    repeated reports (axiom 07 drift table: external pressure is not helping).
    Defined by the drift-event spec, mirroring ``ACCOUNTABILITY_MISMATCH``.
    Maps 1:1 from ``DriftType.SPONSOR_PRESSURE_MISMATCH``; the policy response
    is ``switch_to_private_recovery``."""

    USER_RECOMMITMENT_REQUIRED = "USER_RECOMMITMENT_REQUIRED"
    """The escalation-level (direct) nudge or accountability reset asks the
    user to explicitly recommit to plan, timeline, or intensity (axiom 16
    accountability set; recommitment-event spec). Recorded on the
    ``RecommitmentRequest``; the user's answer is a ``RecommitmentEvent``."""

    # --- Drift classification (axiom 07 / drift-event spec; Phase 4) ---
    #
    # One ``DRIFT_*`` code per ``DriftType``, mapped 1:1 by
    # ``contracts.drift_event.DRIFT_TYPE_TO_REASON_CODE``. These carry a
    # deterministic drift classification into the system-wide typed vocabulary
    # so replan routing, telemetry, and explanations all speak the same codes.
    # All thresholds behind these are uncalibrated heuristic priors (axiom 07).
    DRIFT_CAPACITY_MISMATCH = "DRIFT_CAPACITY_MISMATCH"
    """User completes too little of scheduled weekly minutes across cycles."""

    DRIFT_DURATION_UNDERESTIMATE = "DRIFT_DURATION_UNDERESTIMATE"
    """Median ``actual / scheduled`` ratio runs high for a category; estimates
    are too low. Feeds ``increase_duration_estimates_for_category``."""

    DRIFT_DURATION_OVERESTIMATE = "DRIFT_DURATION_OVERESTIMATE"
    """Median ``actual / scheduled`` ratio runs low for a category; estimates
    are too high. Feeds ``decrease_duration_estimates_for_category``."""

    DRIFT_TOPIC_AVOIDANCE = "DRIFT_TOPIC_AVOIDANCE"
    """One category is repeatedly missed/rescheduled while others complete."""

    DRIFT_EXTERNAL_CONFLICT = "DRIFT_EXTERNAL_CONFLICT"
    """Misses correlate with external calendar conflicts / manual reschedules;
    reschedule, do not change curriculum."""

    DRIFT_LOW_ENGAGEMENT = "DRIFT_LOW_ENGAGEMENT"
    """Many skipped tasks across categories; ask the user to adjust scope."""

    DRIFT_DEPENDENCY_BLOCKED = "DRIFT_DEPENDENCY_BLOCKED"
    """Downstream tasks blocked by an incomplete prerequisite; reschedule the
    prerequisite first. Distinct from the scheduler's ``DEPENDENCY_BLOCKED``
    (a placement failure) — this is a telemetry-observed execution pattern."""

    DRIFT_CALENDAR_FRAGMENTATION = "DRIFT_CALENDAR_FRAGMENTATION"
    """Total free time exists but the largest block is too small for deep-work
    tasks; split tasks or ask the user to open larger blocks."""

    # --- RAG / source claims (axiom 08; Phase 5) ---
    #
    # Source claims are auditable evidence with a deterministic confidence score
    # and an expiry. The LLM never assigns confidence; ingestion computes it.
    # These codes carry syllabus-claim integrity failures into the system-wide
    # typed vocabulary so the Strategist repair loop and explanations speak the
    # same codes. All scoring magnitudes behind them are uncalibrated heuristic
    # priors (axiom 08).
    SOURCE_CLAIM_VALIDATION_FAILED = "SOURCE_CLAIM_VALIDATION_FAILED"
    """A syllabus references source claims that are missing or expired, or a
    company-specific module cites no claim while the strategy constraint
    requires one. Summary code for the ``ORPHAN_SOURCE_CLAIM`` /
    ``EXPIRED_SOURCE_CLAIM`` / ``COMPANY_MODULE_MISSING_CLAIM`` violations,
    mirroring how ``MODULE_COVERAGE_INSUFFICIENT`` summarizes coverage."""

    SOURCE_CLAIM_EXPIRED = "SOURCE_CLAIM_EXPIRED"
    """A single source claim is past its ``expires_at`` and must be refreshed
    before it can drive new syllabus generation (axiom 08 expiration policy).
    Parallels ``APPROVAL_EXPIRED``; used by the refresh path and user-facing
    explanations. The syllabus validator summarizes with
    ``SOURCE_CLAIM_VALIDATION_FAILED``. **No Phase 5 validator producer** — it
    ships for the claim-refresh job and explanation surface."""

    # --- Consent and data controls (ADR-0007; Phase 6) ---
    #
    # Cross-user data use is consent-gated (axiom 07: no cross-user training
    # data without opt-in). The consent gate and the data-control operations
    # carry these codes on every ``data_access_audit`` entry, defined by the
    # consent-record / data-access-audit specs (per axiom 16's "other reason
    # codes are defined in specs" note).
    CONSENT_MISSING = "CONSENT_MISSING"
    """A consent-scoped access found no ``ConsentRecord`` for the user and
    scope (or none for the required consent version). The access is denied
    and the caller falls back deterministically; pooled absence never blocks
    planning (ADR-0007)."""

    CONSENT_REVOKED = "CONSENT_REVOKED"
    """The latest ``ConsentRecord`` for the user and scope is ``revoked``.
    Denied at training time and serving time alike — revocation takes effect
    on the very next gate check (consent-record spec lifecycle)."""

    DATA_EXPORTED = "DATA_EXPORTED"
    """The user's data was exported as JSON by the data-control path. Recorded
    on the ``allowed`` audit entry so every export is provable from the audit
    log alone (data-access-audit spec)."""

    DATA_DELETED = "DATA_DELETED"
    """The user's data was deleted from every registered store. Recorded on
    the ``allowed`` audit entry, which is itself retained — the deletion's
    audit trail survives the deletion (data-access-audit spec)."""

    # --- Pooled duration model (ADR-0007; Phase 6b) ---
    #
    # Serving fallback codes defined by the pooled-duration-model spec.
    # Pooled failure never blocks planning: each code marks why the pooled
    # tier was skipped before the chain fell back deterministically.
    POOLED_MODEL_UNAVAILABLE = "POOLED_MODEL_UNAVAILABLE"
    """No pooled artifact exists, or the artifact failed contract validation
    (e.g. ``content_hash`` mismatch). The serving chain falls back to the
    per-user category multiplier, then the heuristic baseline."""

    POOLED_BUCKET_SPARSE = "POOLED_BUCKET_SPARSE"
    """The pooled artifact has no bucket matching the serving query, or the
    combined weighted sample is below the serving floor (heuristic prior).
    Same deterministic fallback as ``POOLED_MODEL_UNAVAILABLE``."""
