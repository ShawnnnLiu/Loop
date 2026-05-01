# 21: Accountability Layer and Sponsor Reporting

## Purpose

The Accountability Layer converts completion telemetry, check-in behavior, motivation preferences, and sponsor permissions into deterministic interventions.

Motivation must not be handled only through LLM-generated encouragement. The system represents motivation as structured state and observable behavior.

The Accountability Layer exists to answer:

> Given the user's stated accountability preferences and actual completion behavior, what intervention is allowed, useful, and trust-preserving?

The LLM may phrase the intervention message warmly, but code decides whether the user is behind, what intervention is allowed, and whether any external party may be notified.

## Relationship to Other Components

- **Motivation Profile** (`../specs/motivation-profile.schema.md`) — deterministic preferences that shape intervention rules.
- **Telemetry Logger** (`07-telemetry-and-drift.md`) — feeds observable completion, reschedule, and check-in events.
- **Drift Classifier** (`07-telemetry-and-drift.md`) — identifies the *kind* of mismatch; the Accountability Policy Engine decides the *response*.
- **Plan Versioning** (`15-plan-versioning-and-diffs.md`) — recovery plans are new plan versions, never in-place mutations.
- **Calendar Safety** (`06-calendar-safety.md`) — any schedule change from a recovery plan still flows through approval and the Calendar Write Manager.

## Accountability State

The Accountability State is a deterministic projection of telemetry and motivation preferences. It must be recomputed from source events, never edited in place.

```json
{
  "user_id": "user_123",
  "plan_id": "plan_004",
  "completion_rate_7d": 0.62,
  "completion_rate_14d": 0.55,
  "missed_tasks_7d": 3,
  "reschedule_count_7d": 4,
  "behind_schedule_percent": 18,
  "weekly_checkin_completed": false,
  "current_status": "slightly_behind",
  "recommended_intervention": "recovery_checkin",
  "sponsor_report_allowed": true,
  "sponsor_report_level": "summary_only"
}
```

`current_status` is one of `on_track`, `slightly_behind`, `behind`, `far_behind`, `disengaged`, and is computed deterministically from thresholds defined in the motivation profile and the policy engine.

## Accountability Policy Engine

The Accountability Policy Engine is deterministic. Policies are evaluated in order and the first matching policy chooses the action. The LLM is forbidden from evaluating or reordering policies.

```json
[
  {
    "policy_name": "missed_task_warning",
    "condition": "missed_tasks_7d >= 2",
    "action": "send_user_nudge",
    "reason_code": "MISSED_TASK_THRESHOLD_REACHED"
  },
  {
    "policy_name": "recovery_plan",
    "condition": "behind_schedule_percent >= 20",
    "action": "generate_recovery_plan_draft",
    "reason_code": "BEHIND_SCHEDULE_THRESHOLD_REACHED"
  },
  {
    "policy_name": "weekly_checkin_required",
    "condition": "weekly_checkin_enabled AND no check-in this week",
    "action": "create_weekly_checkin_prompt",
    "reason_code": "CHECKIN_DUE"
  },
  {
    "policy_name": "sponsor_summary",
    "condition": "missed_tasks_7d >= 4 AND sponsor_enabled AND sponsor_visibility_level != none",
    "action": "generate_sponsor_summary_draft",
    "reason_code": "SPONSOR_REPORT_PENDING"
  },
  {
    "policy_name": "scope_reduction",
    "condition": "completion_rate_14d < 0.5",
    "action": "suggest_scope_reduction",
    "reason_code": "LOW_COMPLETION_RATE"
  }
]
```

Thresholds (`missed_task_escalation_threshold`, `behind_schedule_intervention_threshold_pct`) are scaled per user by the motivation profile. Every evaluation is logged for audit.

## Intervention Types

| Intervention | Trigger | Deterministic Action |
| --- | --- | --- |
| Gentle nudge | 1 missed task | Notify user only |
| Direct nudge | `missed_tasks_7d >= missed_task_escalation_threshold` | Notify user and ask for recommitment |
| Recovery check-in | Behind schedule by threshold | Ask user to choose recovery option |
| Schedule repair | Plan cannot fit remaining tasks | Generate draft schedule revision |
| Scope reduction | Low completion for two cycles | Suggest reducing plan scope |
| Sponsor summary | User-approved sponsor reporting and missed threshold | Generate permissioned progress summary |
| Accountability reset | User repeatedly ignores plan | Ask user to revise goal, timeline, or intensity |

All interventions still honor approval gates. No schedule or calendar change is applied without user approval.

## Weekly Check-In Schema

```json
{
  "checkin_id": "checkin_123",
  "user_id": "user_123",
  "plan_id": "plan_004",
  "week_start": "2026-05-04",
  "week_end": "2026-05-10",
  "completed_task_count": 4,
  "scheduled_task_count": 6,
  "completed_minutes": 240,
  "scheduled_minutes": 360,
  "user_reported_blockers": "finals week, low energy",
  "user_selected_recovery_action": "reschedule",
  "created_at": "2026-05-10T19:00:00-07:00"
}
```

Check-in records are append-only. The Accountability Policy Engine reads them to determine `weekly_checkin_completed` and `user_selected_recovery_action`.

## Sponsor Report Permission Model

Sponsor reporting must be opt-in, explicit, and revocable.

| Visibility Level | Sponsor Sees |
| --- | --- |
| `none` | Nothing; no sponsor report is generated. |
| `summary_only` | Overall status, milestone progress, suggested support action. |
| `milestone_progress` | Milestone-level completion (for example, "essay outline complete"). |
| `task_completion` | Task-level completion, but never private notes, raw calendar titles, essay drafts, or reflections. |

Default sponsor visibility is `summary_only`. Downgrading visibility takes effect on the next generated report; upgrading requires the user to re-confirm.

## Sponsor Report Schema

```json
{
  "report_id": "report_123",
  "user_id": "user_123",
  "sponsor_id": "sponsor_001",
  "plan_id": "plan_004",
  "visibility_level": "summary_only",
  "status": "slightly_behind",
  "completion_summary": {
    "completed_sessions": 4,
    "planned_sessions": 6,
    "on_track_percent": 72
  },
  "milestone_summary": [
    { "milestone": "Essay draft", "status": "behind" },
    { "milestone": "School list", "status": "on_track" }
  ],
  "suggested_support_action": "Ask the student to complete the essay outline before Friday.",
  "generated_at": "2026-05-10T19:10:00-07:00",
  "requires_user_approval_before_send": true
}
```

## Sponsor Report Rules

The system must never send sponsor reports silently. Every sponsor report must satisfy:

- `sponsor_enabled` is `true`.
- `sponsor_visibility_level` is not `none`.
- Report content only includes fields permitted by the visibility level.
- The user approved sponsor reporting during setup.
- The report is either pre-approved by contract or manually approved before send.
- Report generation, approval, and delivery are logged.

A violation emits `SPONSOR_VISIBILITY_VIOLATION` and blocks delivery. A missing permission emits `SPONSOR_PERMISSION_MISSING`.

## Privacy Constraints

Sponsor reports **must not** include:

- raw calendar event titles;
- raw calendar descriptions;
- essay drafts;
- private notes;
- sensitive emotional reflections;
- health information;
- relationship information;
- inferred psychological labels;
- unapproved task-level details.

Sponsor reports **may** include:

- on-track or behind status;
- completed vs planned session count;
- completed vs planned minutes;
- milestone status;
- suggested support action;
- next checkpoint date.

The Sponsor Report Generator applies a deterministic privacy filter before handing content to the LLM for wording. The LLM never sees disallowed fields.

## Hard Rules

- The Accountability Layer never mutates the task graph or active plan directly.
- All recovery plans flow through validation, diffing, and approval (`04-validation-layer.md`, `15-plan-versioning-and-diffs.md`, `06-calendar-safety.md`).
- Sponsor permission decisions and report eligibility are deterministic.
- Wording may be LLM-generated; permissions, triggers, and included fields are not.
- The MVP excludes financial penalties, surveillance dashboards, and AI therapy (see `00-product-thesis.md`).

## Related Docs

- `00-product-thesis.md`
- `01-system-boundaries.md`
- `04-validation-layer.md`
- `06-calendar-safety.md`
- `07-telemetry-and-drift.md`
- `12-edge-case-policy-engine.md`
- `15-plan-versioning-and-diffs.md`
- `16-reliability-patterns.md`
- `../specs/motivation-profile.schema.md`
- `../specs/telemetry.schema.md`
