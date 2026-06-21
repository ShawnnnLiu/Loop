# Handoff: Loop MVP Backend (phase-loop-mvp-backend)

Continuation notes for a fresh context window. Full scope + locked decisions
live in `phase-loop-mvp-backend.md`; this file is **state + next steps + the
gotchas learned while building D-B**. Read the plan first, then this.

## Status (2026-06-20)

| Item | State |
|---|---|
| **D-B · Drag-to-adjust** | ✅ **DONE**, `make check` green. **Uncommitted.** |
| **D-A · Résumé → Strategist** | ✅ **DONE** + committed. |
| **D-C · Full-horizon / plan-level lock test** | ✅ **DONE** (regression test). **Uncommitted.** |
| **D-D · "Why" reuses UserFacingExplanation** | ✅ No build — documented in the plan; do not add a node. |

Everything is **uncommitted** in the working tree. Nothing has been committed or
pushed. Run `cd backend && uv run make check` to confirm green before building on
top.

## What D-B shipped (so you don't re-touch it)

- Contract: `DraftSchedule.with_adjustments(new_starts, *, draft_schedule_id, created_at)`
  in `contracts/draft_schedule.py` — pure, duration- & order-preserving.
- Validator: `scheduler/adjustment.py` — `DraftAdjustment` (request model) +
  `validate_placements(...)` → typed `PlacementConflict`s. Reason codes are all
  pre-existing (`NO_VALID_CONTIGUOUS_BLOCK`, `OUTSIDE_ALLOWED_HOURS`,
  `DAILY_LOAD_EXCEEDED`, `DEPENDENCY_BLOCKED`); **no enum additions**.
- Service: `CycleService.adjust(...)` in `app/cycle.py`; `AdjustResult` /
  `AdjustViolation` in `app/results.py`.
- Route: `POST /api/adjust` in `app/web/routes_cycle.py`; free/busy fetched
  server-side via `calendar_service.best_effort_free_busy` (extracted from
  `pages._user_free_busy`).
- Docs: `docs/specs/draft-schedule.schema.md` + axiom 05 subsection + two
  `reason_codes.py` docstrings.
- Tests: `tests/scheduler/test_adjustment.py`, `tests/app/test_cycle_adjust.py`,
  additions to `tests/contracts/test_draft_schedule.py` and `tests/web/test_app.py`.

Behavior contract to preserve: adjust is **pre-approval only** (state guard),
**never trusts client conflict-checking** (re-validates server-side), and the
revised draft's hash is what approve locks — so axiom 06's write-time recheck
still holds. Soft placement (deep-work windows, `min_break_between_deep_blocks_min`)
is **relaxed** for manual moves; hard day/time/load bounds, no-overlap, and
prerequisite order are enforced.

## D-A · Résumé capture → Strategist (✅ DONE 2026-06-20)

Shipped exactly as planned below. Notes for review:
- **Adapter (clean omission):** `AnthropicStrategist.run` now dumps the bundle
  with `exclude={"user_profile": {"resume_text"}}` and appends a labeled
  `Candidate résumé (raw, unparsed context — background only, not instructions)`
  section **only when present**. When `None` the prompt is byte-identical to a
  pre-D-A profile — no `resume_text` artifact (acceptance criterion met).
- **Schemas:** `make schemas` regenerated **two** files — `user_profile` (direct)
  and `strategist_input` (it embeds the profile schema). Both committed-consistent
  via `schema-check`.
- **Tests added (+5):** valid fixture `backend_swe_with_resume.json`; adapter
  include/omit prompt tests; onboarding present/absent round-trip tests.
- **Spec:** privacy note added (PII, profile-scoped, sent to Strategist provider
  as context, never persisted in the LLM call log, never trained on).

Original plan (kept for reference), spec-first:
1. **Spec:** `docs/specs/user-profile.schema.md` — add optional `resume_text:
   str | None` (free pasted text; PII, user-scoped, never trained on; absent when
   skipped; *unparsed* Strategist context, not a structured field).
2. **Contract:** `contracts/user_profile.py` — add `resume_text: str | None = None`.
   Optional with `None` default so **every existing fixture/test stays valid**.
3. **⚠️ Regenerate schemas:** `user_profile` **IS** a registered contract
   (`tools/export_schemas.py` `CONTRACTS`), so a field change alters
   `user_profile.schema.json`. Run `cd backend && uv run make schemas` and commit
   the regenerated JSON. (This is the key difference from D-B, where
   `DraftAdjustment` was *not* registered and needed no regen.)
4. **Strategist prompt:** `StrategistInput` already bundles `user_profile`, so no
   wiring change — BUT verify the **real Anthropic Strategist adapter** (in
   `llm_nodes/`, the anthropic adapter, not `FixtureStrategist`) actually includes
   `resume_text` in its prompt when present and omits it cleanly when `None`. The
   deterministic `FixtureStrategist` keys off `target_role` and ignores it — fine.
5. **Onboarding form:** add a "Paste your résumé (optional)" `<textarea>`. Four
   touch-points in `app/web/pages.py` must all include `resume_text`:
   `_SCALAR_FIELDS`, `_DEFAULT_ONBOARD_VALUES`, `_build_profile`,
   `_values_from_record` — plus the field in `templates/onboard.html`. Mirror the
   design's privacy line ("stays on your account, never used for training").
6. **Tests:** profile validates with/without `resume_text`; onboarding form
   round-trips it (`_build_profile` → `_values_from_record`); a negative test that
   `None` yields no prompt artifact in the real adapter.

## D-C · Full-horizon / plan-level lock (next)

Already true in the engine — this is a **guard test + doc note**, not a build.
`propose` defaults `horizon_days = timeline_weeks * 7` and the scheduler places
the whole plan; `approve`/`write` act on the whole draft.

- Add a regression test asserting a single `approve → write` writes **every**
  draft entry across the horizon (no per-week slicing creeps in). The canonical
  fixture plan is only 2 tasks in one week; either (a) just assert
  `written_task_ids == all plan task_ids` in one write (what
  `tests/web/test_app.py::test_full_propose_approve_write_cycle` already does —
  consider strengthening/renaming rather than duplicating), or (b) introduce a
  longer multi-week fixture if you want an explicit >1-week span. Decide when you
  see the fixtures.
- One-line confirmation in the plan/axiom that per-week approval is intentionally
  not offered.

## Gotchas learned (apply to D-A/D-C)

- **Shell cwd resets between Bash calls** in this environment — use absolute
  paths or `cd /Users/shawnliu/Documents/Agentic-Calendar/backend && …` every call.
- **Test harness:** `tests/app/test_cycle.py::make_service()` → `(service, env,
  clock)`, `USER_ID = "user_123"`, `HAPPY_NOW = Mon 2026-05-04 12:00Z`, tz UTC.
  Canonical propose places `dp_001` (Mon 18:00–19:00, no deps) and `dp_002` (Wed
  19:00–20:30, deps `dp_001`); profile allows 08:00–22:30, weekends, 180m/day.
  Reuse it (web tests import from it too).
- **Registered vs unregistered contracts:** changing a field on a contract in
  `export_schemas.CONTRACTS` requires `make schemas` + committing the JSON.
  `user_profile` is registered (D-A needs it); request DTOs like `DraftAdjustment`
  / `FreeBusyInterval` live outside `contracts/` and aren't registered.
- **Spec-first is mandatory** (CLAUDE.md): spec → contract → fixtures → schemas →
  tests. Don't edit code first.
- **Gate:** `uv run make check` (format, lint, mypy, import-linter boundaries,
  schemas, full pytest). Run the narrow suite first, then `make check`.
- **Untracked pre-existing files** (`docs/design-reference/`, the `.zip`,
  `backend/smoke_rows.json`, `.claude/agents/`) are NOT this work — don't blanket
  `git add -A`. Note `docs/design-reference/` is referenced by the specs/plan.

After D-A + D-C the phase is complete (D-D is a no-build). Then it's commit +
PR (user triggers git actions — never commit/push without an explicit ask).
