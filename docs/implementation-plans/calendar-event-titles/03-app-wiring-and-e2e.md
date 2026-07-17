# T-C — App Wiring + End-to-End Tests

Wire the title map from the app layer into both write paths. This is the
phase where the feature goes live; it is also where the silent-regression
risk lives (a missed call site quietly keeps the generic title — there is
no error signal).

## Changes — `app/cycle.py`

- New private helper on `CycleService`:

  ```python
  def _task_titles_for(self, user_id: str, plan_version: str | None) -> dict[str, str]:
  ```

  Returns `{}` when `plan_version` is `None` or the plan is not found —
  log a **warning** in that branch so the fallback is observable, but
  never fail an approved write over a display field. Otherwise
  `{t.task_id: t.title for t in plan.plan.tasks}` — the same expression
  `draft_view()` already uses (`:2686`); reuse the helper there if it
  stays a drop-in (`draft_view` looks up via
  `env.plan_store.get(user_id, draft.plan_version)` — same call).
- `write()` (`approve_and_write` call at `:1752`): pass
  `task_titles=self._task_titles_for(user_id, run.plan_version)`.
  The `approve_and_remove` branch (drop writes) is **unchanged**.
- `retry_write()`: pass the same map at **both** call sites — the
  `reconcile_after_crash` call (`:2004`) AND the fallback
  `approve_and_write` call (`:2014`). Missing either silently regresses
  retried writes to the generic title.
- No changes in `app/web/routes_cycle.py` (it calls
  `service.write`/`retry_write`), the environment wiring, or the operator
  CLIs — `tools/write_calendar.py`, `verify_calendar.py`,
  `rollback_calendar.py` intentionally keep the fallback (scenario drafts,
  in-memory adapter only); add a brief comment at their
  `approve_and_write` calls saying so.

Also update the protocol stub `_QueryRaisingAdapter.create_event`
(`tests/app/test_cycle.py:918`) with the new `title` kwarg so it remains a
faithful stub.

## Tests

- Cycle E2E (`tests/app/test_cycle.py`, near
  `test_dry_run_previews_without_side_effects_then_write_activates`,
  ~`:783`): full propose → approve → write with `make_service()`; then
  read `env.calendar_adapter` (in-memory) events and assert each event's
  `summary` equals the corresponding `Task.title` from
  `env.plan_store.get(USER_ID, plan_version).plan.tasks`.
- Retry path (`tests/app/test_write_recovery.py`, pattern of
  `test_retry_after_verification_failure_recreates_missing_and_activates`):
  assert recreated events carry real titles. **This test pins the
  highest-risk regression** (the two easy-to-miss reconcile call sites).
- Fallback observability: a write whose plan lookup fails yields events
  with `summary is None` at the in-memory adapter (i.e., generic title in
  prod) and the warning log — only if an existing test fixture makes this
  cheap to arrange; do not build new machinery for it.

## Acceptance

`uv run make test-fast` green; the two new tests fail if either `write()`
or `retry_write()` drops the map.
