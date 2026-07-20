# T-B — Manager Threading

Thread an optional `task_titles` map through `CalendarWriteManager` to all
**three** `create_event` call sites. The manager stays plan-ignorant (it
receives a plain mapping, honoring `.importlinter` `calendar-writer-is-leaf`)
and the map is optional, so every existing caller (operator CLIs in
`tools/`, tests, fakes) stays source-compatible with generic-title
behavior.

## Changes — `calendar_writer/manager.py`

- `approve_and_write` (`:188`): add keyword-only
  `task_titles: Mapping[str, str] | None = None`; thread into
  `_create_events`.
- `_create_events` (`:762`): add the param; at the create site (`:786`)
  pass `title=(task_titles or {}).get(entry.task_id)`.
- `reconcile_after_crash` (`:490`): add the same param; pass the title at
  **both** loops —
  - mapping-driven loop (`:557`): `title=(task_titles or {}).get(mapping.task_id)`;
  - draft-entry-driven loop (`:619`): `title=(task_titles or {}).get(entry.task_id)`.
- Docstring note on both public methods: titles are display-only and
  deliberately excluded from the approval hash — the approved artifact
  locks placement; titles come from the immutable approved plan version.
- `approve_and_remove` and `preview`: **unchanged** (no create calls).

A `task_id` missing from the map falls back per-event via
`.get()` → `None` → adapter fallback; a title lookup can never raise
mid-write.

## Tests — `tests/calendar_writer/test_manager.py`

Follow the existing `_draft`/`_make_manager` fixtures. Assert through the
in-memory adapter's recorded `summary` (verbatim, per T-A).

- `test_approve_and_write_passes_task_titles_to_adapter` — titles
  `{"t1": "...", "t2": "..."}` → each created event's `summary` matches
  its task's title.
- `test_approve_and_write_without_titles_leaves_summary_unset` — no map →
  `summary is None` (proves the manager doesn't invent a fallback; the
  fallback is the Google adapter's job).
- `test_reconcile_recreates_missing_events_with_titles` — cover **both**
  reconcile loops in one scenario: a pre-mapped task whose event is
  missing AND a draft entry that never got a mapping; both recreated
  events carry real titles.

## Acceptance

`uv run make test-fast` green. The feature is still inert end-to-end (no
caller passes titles yet) — that wiring is T-C.
