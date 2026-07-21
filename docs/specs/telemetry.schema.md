# Telemetry Schema

## Owner

Task completion flow, calendar sync, and telemetry service.

## Consumers

Drift classifier, metrics, duration calibration, user-facing summaries.

## Purpose

Capture the minimum operational telemetry needed to measure plan fit, completion, scheduling friction, and drift. The MVP is privacy-first: do not store raw private calendar details when derived metadata is enough.

## JSON Example

```json
{
  "telemetry_event_id": "tel_123",
  "task_id": "dp_002",
  "scheduled_duration_min": 90,
  "actual_duration_min": 135,
  "completed": true,
  "completion_timestamp": "2026-05-06T20:42:00-07:00",
  "user_reschedule_count": 2,
  "subjective_difficulty": 4,
  "data_quality": "complete",
  "duration_estimated": false,
  "captured_offline": false,
  "synced_at": "2026-05-06T20:43:00-07:00"
}
```

## Required Fields

- `telemetry_event_id`
- `task_id`
- `scheduled_duration_min`
- `completed`
- `user_reschedule_count`
- `data_quality`

When `completed` is `true`:

- `actual_duration_min` (or computed default with `duration_estimated: true`)
- `completion_timestamp` (or computed default with `data_quality` set accordingly)

## Optional Fields

- `subjective_difficulty` - 1 to 5 self-report.
- `captured_offline` - boolean; true when the event was logged while the client was offline.
- `synced_at` - timestamp at which the event reached the server.
- `duration_estimated` - boolean; true when the system filled in `actual_duration_min` because the user did not provide it.
- `solve_confidence` - closed enum (see below); the user's one-tap self-report at completion of whether they could solve or apply the material unaided. A distinct axis from `subjective_difficulty` (how hard it *felt* vs. whether the user *owns it now*); both stay optional and independent. Feeds the mastery basis fold (`../implementation-plans/narrative-pathways/08-mastery-memory.md`).

## Allowed `solve_confidence` Values

- `confident` - "I could do this again unaided."
- `unsure` - "I got through it but I'm shaky."
- `needed_help` - "I leaned on help the whole way."

The signal is opt-in: skipping the triage is always allowed and is never a penalty (empty-over-fabrication). The user reports it; code records it; an LLM never assigns it (axiom 08 source-confidence rule). Enum only, no free text, on the existing append-only telemetry store - no new store.

## Allowed `data_quality` Values

- `complete` — all fields user-provided.
- `partial_estimated` — duration or timestamp inferred (for example, `actual_duration_min` defaulted to `scheduled_duration_min`).
- `offline_synced` — captured offline and synced later.
- `manual_backfill` — entered hours or days after the fact.

The calibration engine weights these differently. `complete` events count fully. `manual_backfill` events count at **0.5 weight**. The drift classifier may exclude `partial_estimated` events when sample size is otherwise sufficient.

## Privacy Rules

The MVP **must not** store:

- Raw calendar event titles.
- Raw calendar event descriptions.
- Unrelated calendar metadata.
- Sensitive user notes.
- Cross-user training data without opt-in.

The MVP **may** store:

- Free/busy blocks.
- Generated event IDs for app-created events.
- Task completion state.
- Scheduled duration.
- Actual duration.
- Reschedule count.
- Subjective difficulty when the user provides it.
- Solve-confidence self-report when the user provides it. Private to the user; never surfaced in sponsor reports.
- Data-quality tagging metadata defined above.

## Invariants

- `scheduled_duration_min` must be a positive integer.
- `actual_duration_min` is required when `completed` is `true`. If absent, the system defaults to `scheduled_duration_min` and sets `duration_estimated: true` and `data_quality: "partial_estimated"`.
- `completion_timestamp` is required when `completed` is `true`. If absent, the system defaults to the scheduled end time and tags the event accordingly.
- `user_reschedule_count` is a non-negative integer.
- `subjective_difficulty` is an integer in `[1, 5]` when present.
- `solve_confidence`, when present, must be one of `confident`, `unsure`, `needed_help`, and requires `completed: true` (a confidence self-report on an uncompleted task is contradictory).
- `data_quality` must be one of the allowed values.
- `telemetry_event_id` is unique; reingestion uses the id for deduplication.
- Telemetry events are append-only and never silently mutated.
- `captured_offline: true` events must always carry `data_quality: "offline_synced"` (or a stricter value if backfilled later).

## Offline Completion Handling

The MVP allows offline completion as a narrow exception (see `../axioms/19-always-online-mvp.md`). The completion queue on the client must produce events conforming to this schema, with provisional timestamps and `data_quality` set to `offline_synced` (or `partial_estimated` if values were also defaulted).

On reconnect, the server is authoritative for plan structure; the client is authoritative for completion intent. Reconciliation conflicts (for example, a task was deleted server-side before the offline event) must be surfaced in a reconciliation dialog, not silently resolved.

## Invalid Examples

```json
{ "completed": true, "actual_duration_min": null }
```

Reason: completed event lacks actual duration and was not flagged as estimated.

```json
{ "scheduled_duration_min": -30, "completed": false, "data_quality": "complete" }
```

Reason: invalid duration.

```json
{
  "task_id": "dp_002",
  "calendar_event_title": "Solve memoization practice set",
  "completed": true
}
```

Reason: storing raw calendar titles violates privacy rules.

```json
{
  "completed": true,
  "captured_offline": true,
  "data_quality": "complete"
}
```

Reason: offline events must carry `data_quality: "offline_synced"` or stricter.

```json
{ "subjective_difficulty": 7, "completed": true }
```

Reason: difficulty out of range.

```json
{ "solve_confidence": "confident", "completed": false }
```

Reason: `solve_confidence` requires `completed: true`.

```json
{ "solve_confidence": "easy", "completed": true }
```

Reason: `solve_confidence` outside the closed enum (`confident`, `unsure`, `needed_help`).

## Related Docs

- `../axioms/07-telemetry-and-drift.md`
- `../axioms/17-duration-estimation.md`
- `../axioms/19-always-online-mvp.md`
- `drift-event.schema.md`
- `calendar-event-mapping.schema.md`
