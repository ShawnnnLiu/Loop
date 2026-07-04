# Task Disposition Schema

## Owner

Disposition memory substrate (`disposition/`; deterministic, append-only, never
an LLM). Mirrors `TelemetryEventStore` / `CheckinEventStore`.

## Consumers

- **Scheduler projection.** The union of `completed` + `dropped` task ids feeds
  `SchedulerInput.completed_task_ids`, so planning/scheduling stop treating
  finished or abandoned work as still pending (axiom 05 "current completion
  state"; axiom 11 `prerequisites_met`).
- **Drag-to-adjust advisory validator** (`scheduler/adjustment.py`). The
  completed/dropped set makes prerequisite ordering completion-relative
  (`../decisions/ADR-0008-advisory-manual-ordering.md`): a completed/dropped
  prerequisite never warns.
- **Deterministic drop transform** (`planning/drop.py`). Records a `dropped`
  disposition before scheduling the survivors.
- **Planner.** An **advisory** exclusion list (dropped/completed ids) so a full
  regeneration does not resurrect abandoned tasks (advisory only — hard
  "never resurrect" is axiom 20 Phase 2/3).
- **Read projections (`DraftView.deleted_task_ids`, `TodayTask.deleted`).** The
  `event_deleted` records for the active plan version mark tasks whose calendar
  event the user deleted externally, so the Week grid and Today list can show a
  distinct "deleted from calendar" state instead of the misleading
  written-checkmark. `event_deleted` is **surfacing-only**: it never joins the
  completed/dropped scheduler projection.

## Purpose

`TaskDispositionRecord` is the append-only, durable memory of what the user has
**completed**, **skipped**, or **dropped** — and, since the reconciliation
producer, of tasks whose calendar event the user **deleted externally**
(`event_deleted`). Before this record existed the system
had no durable memory of done/dropped work: `SchedulerInput.completed_task_ids`
was honored by the scheduler but never populated, and deleting a calendar event
recorded nothing about the task — so full regeneration rebuilt abandoned work
blind, and the drag validator blocked moves past prerequisites the user had
already finished.

A disposition is **observable behavior or an explicit user action** — a task the
user completed (mirrored from telemetry) or chose to drop — so it is a legitimate
deterministic input to scheduling and ordering. The store never decides a
disposition with an LLM; code records it from a completion signal or an explicit
drop intent.

Task identity is the durable `task_id`. Drops are a deterministic plan-version
edit that keeps surviving `task_id`s **stable** (`planning/drop.py`), so a
disposition keyed on `task_id` stays meaningful across plan versions; the
projection unions across all of a user's plan versions.

## JSON Example

```json
{
  "disposition_id": "disp_user123_plan004_dp_002_dropped",
  "user_id": "user_123",
  "plan_version": "plan_004",
  "task_id": "dp_002",
  "disposition": "dropped",
  "reason_code": "TASK_DROPPED_BY_USER",
  "source": "user",
  "created_at": "2026-06-24T19:00:00-07:00"
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `disposition_id` | string | Primary key; unique, used for dedup by the append-only store. For a `system` completion mirrored from telemetry it is **content-derived** from `(user_id, plan_version, task_id, disposition)` so re-ingest is idempotent. |
| `user_id` | string | Subject of the disposition. |
| `plan_version` | string | The immutable plan version the task belonged to when the disposition was recorded. |
| `task_id` | string | The durable task identity the disposition is about. |
| `disposition` | enum | `completed`, `skipped`, `dropped`, or `event_deleted`. |
| `reason_code` | typed `ReasonCode` or null | Why; see invariants. |
| `source` | enum | `user` (explicit action) or `system` (derived from an observable signal). |
| `created_at` | datetime | When the disposition was recorded (timezone-aware). |

## Allowed `disposition` Values

- `completed` — the user completed the task; mirrored from telemetry
  `completed: bool` with `source: system`.
- `dropped` — the user explicitly dropped an unfinished task via the drop action,
  with `source: user`.
- `skipped` — **reserved**: an explicit "skip without completing" action. No
  producer in this feature; defined now so the store and projection need no later
  enum change. It is **not** yet part of the completed/dropped scheduler
  projection.
- `event_deleted` — reconciliation observed that the task's calendar event was
  deleted from the dedicated external calendar (`source: system`, reason
  `EXTERNAL_EVENT_DELETED`). This is **event** memory, not task cancellation:
  the task stays in the plan and keeps its draft entry (axiom 06 lines 249–253 —
  "delete means cancelled" must be explicitly opt-in, never default). It is
  **never** part of the completed/dropped scheduler projection and never feeds
  the planner exclusion list; its only consumers are the read projections that
  surface the deletion to the user.

## Allowed `source` Values

- `user` — an explicit user action (a drop).
- `system` — derived deterministically from an observable signal (a telemetry
  completion; a reconciliation-observed external deletion).

## Control-Plane Boundary

A disposition is a deterministic input, not LLM-controlled state. The
`disposition`, its `reason_code`, and `source` are set by code from a completion
signal or an explicit drop intent; an LLM never assigns a disposition (mirroring
axiom 11's "code computes `prerequisites_met`" and the source-confidence rule).
The projection that reaches the scheduler and the advisory validator is a pure
set union — no prose drives it.

## Required Fields

All fields except `reason_code`, which is `null` for `completed` and required for
`dropped` and `event_deleted` (see invariants).

## Validation Rules / Invariants

- `created_at` must be timezone-aware.
- `disposition_id` uniqueness is enforced by the append-only store, not the model.
- `dropped` ⟹ `reason_code` is a set, typed `ReasonCode` — `TASK_DROPPED_BY_USER`
  for an explicit drop. (`DEPENDENT_DROP_PRUNED` is reserved for plan-diff
  field-changes when a survivor's edge is pruned, **not** a disposition.)
- `completed` ⟹ `reason_code` is `null` (completion is its own outcome; no failure
  code applies).
- `skipped` ⟹ `reason_code` optional.
- `event_deleted` ⟹ `reason_code` is a set, typed `ReasonCode` —
  `EXTERNAL_EVENT_DELETED` for the reconciliation producer. The
  `disposition_id` is content-derived from
  `(user_id, plan_version, task_id, disposition)` so repeated reconcile pulls
  are idempotent.
- `event_deleted` never enters the completed/dropped scheduler projection or the
  planner exclusion list (it is surfacing-only; the task remains planned).
- The record is `frozen=True` and forbids unknown fields, like the other
  immutable contracts in `contracts/`.

## Privacy Invariants

- A `TaskDispositionRecord` carries only identifiers (`user_id`, `plan_version`,
  `task_id`, `disposition_id`), enum values, and a typed `reason_code` — **never**
  raw calendar event titles or descriptions (axiom 06 line 91).
- It is private to the user and must never appear in sponsor reports.

## Invalid Examples

```json
{ "task_id": "dp_002", "disposition": "dropped", "reason_code": null }
```

Reason: a `dropped` disposition must carry a typed `reason_code`.

```json
{ "task_id": "dp_002", "disposition": "completed", "reason_code": "TASK_DROPPED_BY_USER" }
```

Reason: a `completed` disposition must have a `null` `reason_code`.

```json
{ "task_id": "dp_002", "disposition": "dropped", "reason_code": "TASK_DROPPED_BY_USER", "source": "user", "created_at": "2026-06-24T19:00:00" }
```

Reason: `created_at` must be timezone-aware.

## Relationships

- Feeds `SchedulerInput.completed_task_ids` (axiom 05 "current completion state").
- Read by the drag-to-adjust advisory validator for completion-relative ordering
  (`../decisions/ADR-0008-advisory-manual-ordering.md`).
- Recorded by `planning/drop.py` (`dropped`), the `ingest` completion mirror
  (`completed`), and the calendar reconciliation deleted branch
  (`event_deleted`; `calendar-reconciliation.schema.md`).
- Surfaced by the read projections (`DraftView.deleted_task_ids`,
  `TodayTask.deleted`) scoped to the active plan version.

## Related Docs

- `../axioms/05-scheduler-policy.md`
- `../axioms/11-prerequisite-logic.md`
- `../axioms/20-partial-syllabus-regeneration.md`
- `../decisions/ADR-0008-advisory-manual-ordering.md`
- `checkin-event.schema.md`
- `telemetry.schema.md`
- `draft-schedule.schema.md`
- `calendar-reconciliation.schema.md`
