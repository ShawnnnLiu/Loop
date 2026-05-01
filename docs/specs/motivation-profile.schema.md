# Motivation Profile Schema

## Owner

Onboarding flow, Motivation Profiler, and Accountability Contract Manager.

## Consumers

Accountability Policy Engine (`../axioms/21-accountability-layer.md`), Sponsor Report Generator, Notification Layer. The Drift Classifier does not consume this schema; it operates only on observable telemetry.

## Purpose

Capture the user's accountability preferences and procrastination risk as structured, deterministic state. This is kept separate from the `user_profile` because:

- Planning constraints (timeline, weekly hours, availability) and motivation state (accountability intensity, sponsor visibility, pressure tolerance) have different update triggers and invalidation rules.
- Motivation state changes do not invalidate the syllabus or task plan; they affect the Accountability Policy Engine and notification behavior.
- Sponsor visibility and pressure tolerance carry stricter privacy boundaries than scheduling preferences.

The motivation profile is the deterministic source of truth the Accountability Policy Engine reads. It must never be inferred by the LLM. It is set explicitly during onboarding and updated only through explicit user action.

## JSON Example

```json
{
  "motivation_profile_id": "mot_001",
  "user_id": "user_123",
  "profile_version": "mot_v1",
  "self_motivation_level": "medium",
  "procrastination_risk": "high",
  "pressure_tolerance": "medium",
  "weekly_checkin_enabled": true,
  "weekly_checkin_day": "Sun",
  "weekly_checkin_time": "19:00",
  "missed_task_escalation_threshold": 2,
  "behind_schedule_intervention_threshold_pct": 20,
  "recovery_mode_preference": "reschedule",
  "sponsor_enabled": false,
  "sponsor_visibility_level": "none",
  "sponsor_id": null,
  "nudge_channel_preference": "in_app",
  "quiet_hours": {
    "start": "22:00",
    "end": "08:00"
  },
  "created_at": "2026-04-28T12:00:00-07:00",
  "updated_at": "2026-04-28T12:00:00-07:00"
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `self_motivation_level` | enum: `low`, `medium`, `high` | Sets default accountability intensity |
| `procrastination_risk` | enum: `low`, `medium`, `high` | Decides whether nudges should be aggressive |
| `pressure_tolerance` | enum: `low`, `medium`, `high` | Prevents hostile motivational pressure |
| `weekly_checkin_enabled` | boolean | Whether weekly check-ins are required |
| `weekly_checkin_day` | enum: `Mon`–`Sun` | Day the weekly check-in prompt is generated |
| `weekly_checkin_time` | string (`HH:MM`) | Local time the check-in is generated |
| `missed_task_escalation_threshold` | integer | Missed tasks in 7 days that trigger escalation |
| `behind_schedule_intervention_threshold_pct` | integer | Behind-schedule percentage that triggers recovery |
| `recovery_mode_preference` | enum: `reschedule`, `scope_reduction`, `extend_timeline`, `ask_each_time` | Default behind-schedule response |
| `sponsor_enabled` | boolean | Whether sponsor reporting is active |
| `sponsor_visibility_level` | enum: `none`, `summary_only`, `milestone_progress`, `task_completion` | Controls sponsor visibility |
| `sponsor_id` | string or null | Foreign key to `sponsors` table |
| `nudge_channel_preference` | enum: `in_app`, `email`, `push` | Where notifications are delivered |
| `quiet_hours` | object with `start`/`end` (`HH:MM`) | Range during which no nudges are sent |

## Required Fields

Required at onboarding:

- `self_motivation_level`
- `procrastination_risk`
- `pressure_tolerance`
- `weekly_checkin_enabled`

Required only if `weekly_checkin_enabled` is `true`:

- `weekly_checkin_day`
- `weekly_checkin_time`

Required only if `sponsor_enabled` is `true`:

- `sponsor_visibility_level` (must not be `none`)
- `sponsor_id`

## Defaults

If not provided at onboarding, apply:

- `missed_task_escalation_threshold`: `2`
- `behind_schedule_intervention_threshold_pct`: `20`
- `recovery_mode_preference`: `ask_each_time`
- `sponsor_enabled`: `false`
- `sponsor_visibility_level`: `none`
- `nudge_channel_preference`: `in_app`
- `quiet_hours`: `{ "start": "22:00", "end": "08:00" }`

## Validation Rules

- If `sponsor_enabled` is `true`, `sponsor_id` must reference a valid sponsor record.
- If `sponsor_enabled` is `true`, `sponsor_visibility_level` must not be `none`.
- If `sponsor_enabled` is `false`, `sponsor_visibility_level` must be `none`.
- `missed_task_escalation_threshold` must be between `1` and `14`.
- `behind_schedule_intervention_threshold_pct` must be between `5` and `50`.
- `weekly_checkin_time` must be a valid `HH:MM` string.
- `quiet_hours.start` and `quiet_hours.end` must be valid `HH:MM` strings.
- Updates produce a new `profile_version` and refresh `updated_at`.

## Update Policy

Motivation profile changes do not invalidate the syllabus, task plan, or schedule. They affect only the accountability layer.

| Motivation Change | Invalidate Syllabus? | Invalidate Tasks? | Invalidate Schedule? | Invalidate Accountability Contract? |
| --- | --- | --- | --- | --- |
| `self_motivation_level` changed | No | No | No | Maybe |
| `procrastination_risk` changed | No | No | No | Maybe |
| `pressure_tolerance` changed | No | No | No | Maybe |
| `weekly_checkin_enabled` toggled | No | No | No | Yes |
| `sponsor_enabled` toggled | No | No | No | Yes |
| `sponsor_visibility_level` changed | No | No | No | Yes |
| `missed_task_escalation_threshold` changed | No | No | No | Yes |
| `recovery_mode_preference` changed | No | No | No | No |

## Privacy Boundary

The motivation profile contains sensitive preferences. It must not be:

- exposed in sponsor reports;
- included in cross-user training data without explicit opt-in;
- used by the LLM to generate personality-like inferences;
- stored in plain calendar event metadata.

The LLM may read selected fields (for example, `pressure_tolerance`) to adjust the tone of user-facing messages, but must not read `sponsor_id`, `sponsor_visibility_level`, or numeric threshold values.

## Invalid Examples

```json
{ "sponsor_enabled": true, "sponsor_visibility_level": "none" }
```

Reason: sponsor enabled but visibility is `none`.

```json
{ "sponsor_enabled": false, "sponsor_visibility_level": "task_completion" }
```

Reason: sponsor disabled but a non-`none` visibility level is set.

```json
{ "missed_task_escalation_threshold": 0 }
```

Reason: below the minimum of `1`.

```json
{ "behind_schedule_intervention_threshold_pct": 75 }
```

Reason: above the maximum of `50`.

```json
{ "weekly_checkin_enabled": true, "weekly_checkin_time": "25:00" }
```

Reason: invalid `HH:MM` value.

## Relationships

- The Accountability Policy Engine (`../axioms/21-accountability-layer.md`) reads this profile to evaluate intervention rules.
- The Sponsor Report Generator reads `sponsor_enabled` and `sponsor_visibility_level` to determine permission.
- The Notification Layer reads `nudge_channel_preference` and `quiet_hours`.
- `user_profile.motivation_profile_id` references this object.

## Related Docs

- `user-profile.schema.md`
- `../axioms/01-system-boundaries.md`
- `../axioms/12-edge-case-policy-engine.md`
- `../axioms/21-accountability-layer.md`
