# Check-In Event Schema

## Owner

Weekly check-in flow (`../axioms/21-accountability-layer.md`).

## Consumers

Accountability State projection, Accountability Policy Engine, completion
dashboard, recovery-plan flow.

## Purpose

`CheckinEvent` is the append-only record of one completed weekly check-in.
Axiom 21 requires check-in records to be append-only; the Accountability
Policy Engine reads them to determine `weekly_checkin_completed` and
`user_selected_recovery_action`. A check-in is observable behavior — the user
explicitly submitted it — so it is a legitimate deterministic input to the
policy engine.

Whether a check-in is **due** or **missed** is *not* stored on this record; it
is computed deterministically by the check-in evaluator from the motivation
profile cadence (`weekly_checkin_day`, `weekly_checkin_time`), the clock, and
the presence or absence of a `CheckinEvent` for the cycle (reason codes
`CHECKIN_DUE` / `CHECKIN_MISSED`).

## JSON Example

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

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `checkin_id` | string | Primary key; unique, used for dedup by the store. |
| `user_id` | string | Subject of the check-in. |
| `plan_id` | string | Active plan the check-in reports against. |
| `week_start` | date | First day of the reported cycle. |
| `week_end` | date | Last day of the reported cycle; exactly `week_start + 6 days`. |
| `completed_task_count` | integer ≥ 0 | Scheduled tasks completed in the cycle. |
| `scheduled_task_count` | integer ≥ 0 | Tasks scheduled in the cycle. |
| `completed_minutes` | integer ≥ 0 | Minutes of scheduled work completed. |
| `scheduled_minutes` | integer ≥ 0 | Minutes of work scheduled. |
| `user_reported_blockers` | string or null | Free-text blockers, max 2000 chars. |
| `user_selected_recovery_action` | enum or null | `reschedule`, `scope_reduction`, `extend_timeline`. |
| `created_at` | datetime | When the user submitted the check-in. |

## Control-Plane Boundary

`user_selected_recovery_action` is the **only** field of this record that may
influence routing: it is an explicit enum choice made by the user, and the
recovery-plan flow consumes it deterministically.

`user_reported_blockers` is free text. It is private to the user, must never
appear in sponsor reports, and must never be parsed to drive workflow state.
The LLM may read it to phrase a supportive user-facing response, nothing more.

## Required Fields

All fields except `user_reported_blockers` and `user_selected_recovery_action`,
which default to null. A check-in with no recovery selection is valid: the user
may be on track, or may defer the choice to the recovery flow.

## Validation Rules

- `week_end` must be exactly 6 days after `week_start`.
- `completed_task_count`, `scheduled_task_count`, `completed_minutes`,
  `scheduled_minutes` must each be ≥ 0.
- `user_reported_blockers` is limited to 2000 characters.
- `created_at` must be timezone-aware.
- `checkin_id` uniqueness is enforced by the append-only store, not the model.

`completed_*` values are intentionally **not** capped by their `scheduled_*`
counterparts: a user may complete more minutes than scheduled. Downstream
behind-schedule math clamps at zero instead.

## Invalid Examples

```json
{ "week_start": "2026-05-04", "week_end": "2026-05-12" }
```

Reason: the cycle must span exactly 7 days (`week_end = week_start + 6 days`).

```json
{ "completed_task_count": -1 }
```

Reason: counts must be non-negative.

```json
{ "user_selected_recovery_action": "ask_each_time" }
```

Reason: `ask_each_time` is a *preference* (motivation profile), not a
selectable recovery action; a submitted check-in records a concrete choice or
null.

## Relationships

- The check-in evaluator (`accountability/`) combines this record with the
  `AccountabilityContract` cadence to produce `CHECKIN_DUE` / `CHECKIN_MISSED`.
- The Accountability State projection reads it for `weekly_checkin_completed`.
- The recovery-plan flow reads `user_selected_recovery_action`.

## Related Docs

- `motivation-profile.schema.md`
- `accountability-contract.schema.md`
- `accountability-state.schema.md`
- `../axioms/21-accountability-layer.md`
- `../axioms/16-reliability-patterns.md`
