# Sponsor Report Schema

## Owner

Sponsor Report Generator (`../axioms/21-accountability-layer.md`).

## Consumers

Sponsor Report Delivery Service, Notification Layer, audit log,
`UserFacingExplanationNode` (wording of `suggested_support_action` only).

## Purpose

A `SponsorReport` is the deterministic, privacy-filtered payload sent to a
trusted third party. It is generated only when sponsor reporting is enabled and
permitted, and it passes through a deterministic privacy filter **before** any
LLM wording. The LLM may phrase `suggested_support_action`; it never selects the
included fields, the status, or the visibility level.

## Phase Boundary: Progress Input

The completion numbers in a sponsor report come from a deterministic progress
snapshot supplied by the caller. In Phase 3 the snapshot is an explicit input
(`SponsorReportInput`); the telemetry pipeline that *computes* it from raw
completion events is Phase 4, and the Accountability Policy Engine that decides
*when* to trigger a report is Phase 7. Phase 3 owns the schema, the privacy
filter, the permission gate, the approval gate, and delivery logging.

## Visibility Levels

The `visibility_level` controls how much detail the report carries. Higher
levels are supersets of lower ones, but **every** level is subject to the
privacy denylist below.

| Level | Included |
| --- | --- |
| `none` | Nothing; no report is generated. |
| `summary_only` | `status`, `completion_summary`, `milestone_summary`, `suggested_support_action`, `next_checkpoint_date`. |
| `milestone_progress` | Everything in `summary_only`. (Milestone status is the salient detail.) |
| `task_completion` | Everything above plus `task_completion_summary` (counts only, never task titles). |

`task_completion_summary` is present **only** at `task_completion` level and must
be absent at every lower level. Downgrading visibility (e.g. `task_completion →
summary_only`) takes effect on the next generated report and the higher-level
field must be stripped.

## JSON Example

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
  "task_completion_summary": null,
  "suggested_support_action": "Ask the student to complete the essay outline before Friday.",
  "next_checkpoint_date": "2026-05-17",
  "trigger_reason_code": "SPONSOR_REPORT_PENDING",
  "generated_at": "2026-05-10T19:10:00-07:00",
  "requires_user_approval_before_send": true
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `report_id` | string | Primary key. |
| `user_id` | string | Subject of the report. |
| `sponsor_id` | string | Recipient sponsor row. |
| `plan_id` | string | Plan the progress refers to. |
| `visibility_level` | enum (non-`none` `SponsorVisibility`) | Permission level applied. |
| `status` | enum `AccountabilityStatus` | `on_track`, `slightly_behind`, `behind`, `far_behind`, `disengaged`. |
| `completion_summary` | object | `completed_sessions`, `planned_sessions`, `on_track_percent`. |
| `milestone_summary` | list of `{milestone, status}` | Milestone-level status; `status` is an `AccountabilityStatus`. |
| `task_completion_summary` | object or null | Counts only; present iff `visibility_level == task_completion`. |
| `suggested_support_action` | string or null | LLM-phrasable support suggestion (privacy-filtered). |
| `next_checkpoint_date` | date or null | Next checkpoint the sponsor may anchor on. |
| `trigger_reason_code` | enum `ReasonCode` | The trigger that produced the draft (`SPONSOR_REPORT_PENDING`). |
| `generated_at` | datetime | Generation time. |
| `requires_user_approval_before_send` | boolean | Approval gate; defaults to `true`. |

`completion_summary` fields:

| Field | Type | Rule |
| --- | --- | --- |
| `completed_sessions` | int ≥ 0 | Must not exceed `planned_sessions`. |
| `planned_sessions` | int ≥ 0 | |
| `on_track_percent` | int in `[0, 100]` | |

`task_completion_summary` fields (when present):

| Field | Type | Rule |
| --- | --- | --- |
| `completed_tasks` | int ≥ 0 | Must not exceed `total_tasks`. |
| `total_tasks` | int ≥ 0 | |

## Privacy Denylist (always rejected)

A report is rejected with `SPONSOR_VISIBILITY_VIOLATION` if any field carries:

- raw calendar event titles;
- raw calendar event descriptions;
- essay drafts;
- private notes;
- sensitive emotional reflections;
- health information;
- relationship information;
- inferred psychological labels;
- unapproved task-level details.

The privacy filter runs on the structured payload **before** LLM wording and
again on the final payload **before** send (`21-accountability-layer.md`,
golden scenario 25). `milestone` names and `suggested_support_action` text are
scanned for denylisted markers.

## Required Fields

- `report_id`, `user_id`, `sponsor_id`, `plan_id`
- `visibility_level` (must not be `none`)
- `status`
- `completion_summary`
- `milestone_summary` (may be an empty list)
- `trigger_reason_code`
- `generated_at`
- `requires_user_approval_before_send`

## Validation Rules

- `visibility_level` must not be `none` (a `none`-level report is never built).
- `task_completion_summary` must be `null` unless `visibility_level` is
  `task_completion`.
- `completed_sessions <= planned_sessions`; both non-negative.
- `on_track_percent` in `[0, 100]`.
- `completed_tasks <= total_tasks` when `task_completion_summary` is present.
- `generated_at` must be timezone-aware.
- `trigger_reason_code` must be a defined `ReasonCode`.

## Approved Payload Hash

Delivery requires an explicit user approval that records the report's canonical
content hash (see `notification-log.schema.md` and the Sponsor Report Delivery
Service). The hash covers exactly the permitted, visibility-filtered fields, so
that the content the user approved is byte-for-byte the content delivered. A
mismatch means the draft changed after approval and blocks delivery.

## Invalid Examples

```json
{ "visibility_level": "none" }
```

Reason: a `none`-level report must never be constructed.

```json
{ "visibility_level": "summary_only", "task_completion_summary": { "completed_tasks": 3, "total_tasks": 5 } }
```

Reason: task-level detail present below `task_completion` visibility.

```json
{ "completion_summary": { "completed_sessions": 8, "planned_sessions": 6, "on_track_percent": 72 } }
```

Reason: completed exceeds planned.

```json
{ "completion_summary": { "completed_sessions": 4, "planned_sessions": 6, "on_track_percent": 140 } }
```

Reason: `on_track_percent` out of range.

## Related Docs

- `sponsor.schema.md`
- `notification-log.schema.md`
- `motivation-profile.schema.md`
- `telemetry.schema.md`
- `../axioms/21-accountability-layer.md`
- `../axioms/06-calendar-safety.md`
