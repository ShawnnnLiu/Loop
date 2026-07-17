# Calendar Event Titles — Overview

Google Calendar events created by the app all carry the same summary,
`"Career prep study block"`. This plan replaces that with the task's real
title on **new writes only**. Planned 2026-07-16; references verified the
same day against the working tree of `resume-intake-onboarding`.

## Why the generic title exists today

It was a deliberate privacy posture, not an accident. The adapter module
docstring states it directly ("task titles and descriptions never reach
the external calendar, mirroring the rule that they are never stored
(axiom 06)"). Structurally:

- `EVENT_SUMMARY = "Career prep study block"` is a module constant at
  `backend/src/agentic_calendar/calendar_writer/google_adapter.py:41`.
- `GoogleCalendarAdapter.create_event` (`google_adapter.py:306`) has **no
  title parameter** — the only free-text field on the wire is the constant.
- `DraftScheduleEntry` (`contracts/draft_schedule.py:28`) carries only
  `task_id`/`start`/`end`/`calendar_event_status`; the real title is not in
  scope anywhere in the write path.

Meanwhile the SPA approval screen already shows real titles —
`CycleService.draft_view()` builds `{task.task_id: task.title}` at
`app/cycle.py:2686`. Only the calendar surface is generic, which makes the
Google calendar useless for telling study blocks apart.

## User decisions (locked 2026-07-16)

1. **Real task title** as the event summary (not prefixed, not generic).
2. **New writes only** — no backfill/rename of existing events; old events
   keep the generic title until naturally replaced by a replan.
3. **Descriptions stay absent.** The summary is the only content field.
4. The **inbound rule is untouched**: raw calendar titles/descriptions read
   back from Google are still never stored (`CLAUDE.md` "Do not store raw
   calendar event titles or descriptions", `AGENTS.md:91`). This plan
   changes the *outbound* posture only, on the user's own dedicated
   calendar.

## Why the change is safe

Nothing functional reads the event title. Verified:

- **Duplicate detection** uses `privateExtendedProperty` metadata
  (`query_events_by_metadata`, `google_adapter.py:365`), never the summary
  (axiom 06: "Duplicate detection uses metadata, not title matching").
- **Reconciliation** (`app/cycle.py:1318-1417`) reads events by stored
  `calendar_event_id` and classifies by comparing times only;
  `ExternalEventRecord` (`calendar_writer/adapter.py:30`) has no summary
  field at all today.
- **Rollback** uses stored `calendar_event_mapping` + metadata.
- **`approved_payload_hash`**: `_canonicalize_v1`
  (`contracts/hashing.py:101-127`) enumerates its fields explicitly —
  `draft_schedule_id`, `plan_version`, per-entry
  `task_id`/`start`/`end`/`calendar_event_status`. The title is excluded by
  construction; approvals, the write-time recheck, and
  `hash_canonicalization_version` are all unaffected. **Canonicalization
  must not change** in this plan.
- Exactly **one test** pins the summary
  (`tests/calendar_writer/test_google_adapter.py:241-282`), via the
  imported constant.
- Titles come from the immutable, already-approved plan version — which
  *is* covered by the approval — so the approval gate's meaning is intact:
  the hash locks placement; the title is display data derived from the
  approved plan.

## Approach: pass a `task_id → title` map from the app layer

The app layer (`CycleService`) looks up the plan version and passes
`task_titles: Mapping[str, str]` into the write manager, which passes a
per-entry `title` to `adapter.create_event(title=...)`. Missing/empty
titles fall back to the existing `EVENT_SUMMARY` constant.

Rejected alternatives:

- **`title` field on `DraftScheduleEntry`** — a contract change (spec doc,
  fixtures, `make schemas`, persisted-draft compatibility) that also forces
  a second change to `ScheduledTask`/`from_scheduler_output` since the
  scheduler output has no title either; and it weakens the draft's own
  docstring claim that it "carries only the fields whose values must be
  locked at approval time".
- **Plan-store dependency in the manager** — violates `.importlinter`
  contract `calendar-writer-is-leaf` (`calendar_writer` may depend only on
  `common`/`contracts`/`approval`).

## Phases

| Phase | Doc | Content |
| --- | --- | --- |
| T-A | `01-adapter-surface.md` | Adapter protocol + `ExternalEventRecord.summary` + Google/in-memory adapters, fallback + sanitization, adapter tests |
| T-B | `02-manager-threading.md` | `task_titles` on `approve_and_write` / `reconcile_after_crash`, all three create sites, manager tests |
| T-C | `03-app-wiring-and-e2e.md` | `cycle.py` helper + `write()`/`retry_write()` call sites, cycle E2E + write-recovery tests |
| T-D | `04-docs-and-gates.md` | Docstring/axiom claim sweep, full gates, wrap-up checklist |

Sizing and the kickoff prompt live in `SPLITS.md` (single split, T-A→T-D).

## Reference table (verified 2026-07-16)

If a cited line number no longer matches, trust the named symbol over the
line number and note the drift in the session summary.

| Symbol | Location |
| --- | --- |
| `EVENT_SUMMARY` | `calendar_writer/google_adapter.py:41` |
| `GoogleCalendarAdapter.create_event` | `google_adapter.py:306` |
| `GoogleCalendarAdapter._to_record` | `google_adapter.py:382` |
| `ExternalCalendarAdapter.create_event` protocol | `calendar_writer/adapter.py:51` |
| `ExternalEventRecord` | `calendar_writer/adapter.py:30` |
| `InMemoryCalendarAdapter.create_event` | `calendar_writer/in_memory_adapter.py:95` |
| `CalendarWriteManager.approve_and_write` | `calendar_writer/manager.py:188` |
| `CalendarWriteManager.reconcile_after_crash` | `calendar_writer/manager.py:490` (create sites at `:557` mapping-driven, `:619` draft-entry-driven) |
| `CalendarWriteManager._create_events` | `calendar_writer/manager.py:762` (create site `:786`) |
| `build_event_metadata` | `calendar_writer/metadata.py:19` |
| `Task.title` | `contracts/task_plan.py:35` (`str`, `min_length=1`) |
| `_canonicalize_v1` | `contracts/hashing.py:101-127` |
| `CycleService.write` | `app/cycle.py:1690` (`approve_and_write` call `:1752`) |
| `CycleService.retry_write` | `app/cycle.py` (`reconcile_after_crash` call `:2004`, fallback `approve_and_write` `:2014`) |
| `draft_view` title map | `app/cycle.py:2686` |
| Pinned summary test | `tests/calendar_writer/test_google_adapter.py:241-282` |
| Protocol stub needing new kwarg | `tests/app/test_cycle.py:918` (`_QueryRaisingAdapter`) |
