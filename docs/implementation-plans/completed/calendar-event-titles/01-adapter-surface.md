# T-A — Adapter Surface

Add an optional `title` to the adapter boundary and record it on the
in-memory fake for test observability. No manager or app changes in this
phase; with no caller passing a title, behavior is byte-identical.

## Changes

### `calendar_writer/adapter.py`

- `ExternalCalendarAdapter.create_event` protocol: add keyword-only
  `title: str | None = None`. Document it as: the task's human-readable
  title from the validated plan; `None` → adapter-specific generic
  fallback; **descriptions are never written**.
- `ExternalEventRecord`: add `summary: str | None = None`. The dataclass
  docstring already blesses optional-with-default additions as
  non-breaking (`adapter.py:9-11`), so existing equality assertions keep
  passing. Document the field: populated only by fakes for test
  observability; the Google adapter never ingests titles on read-back
  (inbound privacy rule).

### `calendar_writer/google_adapter.py`

- Add `_MAX_SUMMARY_LEN = 1024` (Google summary practical cap).
- `create_event` (`:306`): add keyword-only `title: str | None = None`;
  the body's summary becomes:

  ```python
  "summary": (title or "").strip()[:_MAX_SUMMARY_LEN] or EVENT_SUMMARY,
  ```

  (strip first, then cap, then fall back — whitespace-only titles must hit
  the fallback).
- `EVENT_SUMMARY` (`:41`): keep the value; docstring becomes "Fallback
  summary when the caller supplies no task title."
- `_to_record` (`:382`): leave `summary` unset; add a one-line comment that
  the summary is intentionally not ingested (inbound rule — titles are
  never read back or stored).
- Module docstring bullet "**No raw content.**" (`:16-20`): rewrite —
  outbound task titles ARE now written to the user's own dedicated
  calendar (user-approved posture change, 2026-07-16); descriptions are
  never written; the four metadata keys are unchanged; inbound titles are
  still never read back or stored. (Full claim-sweep checklist is in
  `04-docs-and-gates.md`; this bullet is the load-bearing one.)

### `calendar_writer/in_memory_adapter.py`

- `create_event` (`:95`): add keyword-only `title: str | None = None`;
  store `summary=title` on the `ExternalEventRecord` (`:124`) **verbatim —
  no fallback**, so tests can distinguish "no title passed" (`None`) from
  "fallback applied" (only the Google adapter applies `EVENT_SUMMARY`).

## Tests

Update:

- `tests/calendar_writer/test_google_adapter.py:241-282` — rewrite
  `test_create_event_body_is_content_free_and_utc` as
  `test_create_event_body_carries_title_and_utc`: pass
  `title="Review binary trees"`, assert
  `resource["summary"] == "Review binary trees"`; **keep** the UTC
  assertions, the exact-metadata assertion, and the body-keys pin
  (`set(resource)` still has no `description` key).

Add (Google adapter):

- `test_create_event_without_title_falls_back_to_generic_summary` —
  `title=None` and `title="   "` both yield `EVENT_SUMMARY`.
- `test_create_event_title_is_stripped_and_capped` — leading/trailing
  whitespace stripped; a >1024-char title is truncated to 1024.
- `test_read_event_does_not_ingest_summary` — a transport payload WITH a
  summary → `_to_record` result has `summary is None` (pins the inbound
  rule structurally).

Add (`tests/calendar_writer/test_in_memory_adapter.py`):

- create with `title="X"` → `record.summary == "X"`; create without →
  `record.summary is None`.

## Acceptance

`uv run make test-fast` green from `backend/`; no manager/app/test files
outside `tests/calendar_writer/` touched except as listed.
