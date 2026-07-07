# 04 · Task Splitting (Contract Change)

Make `splittable` actually split. Today it only softens the failure
message: a splittable task that fits nowhere yields
`NO_VALID_CONTIGUOUS_BLOCK` + `suggested_repair=SPLIT_TASK`
(`greedy.py:342-346`), and `TASK_TOO_LONG_SPLITTABLE` is reserved with no
producer — because `SchedulerOutput._scheduled_task_ids_unique`
(`contracts/scheduler_output.py:129`) forbids the multiple placements a
split needs.

This phase is **contract-heavy and has real blast radius** (approval hash,
calendar mappings, adjustment, SPA). It is worth doing only if the quality
report after 01–03 still shows long tasks failing on fragmented calendars.
Gate the phase on that evidence.

Increments: **P-J → P-K**, one commit each.

## P-J · Spec-first contract change

Update specs → contracts → fixtures → `make schemas` → tests, in that
order, all in this commit:

1. **`docs/specs/scheduler-output.schema.md`**: `ScheduledTask` gains
   optional `part_index: int ≥ 1` and `part_count: int ≥ 2` (both present
   or both absent). Uniqueness invariant becomes: task_ids unique among
   unsplit entries; `(task_id, part_index)` unique among parts; a task_id
   never appears both split and unsplit; parts of a task are
   non-overlapping and ordered by index. `scheduled_minutes(task)` =
   sum over parts = `estimated_duration_min` exactly.
2. **`docs/specs/draft-schedule.schema.md`**: draft entries mirror the part
   fields. **This changes the approved-payload canonical form ⇒ bump
   `hash_canonicalization_version`** and follow the axiom-06 recheck rule:
   old drafts verify under their recorded version; only new drafts use the
   new one. This is the single most dangerous edit in the project — the
   write-path recheck (`approved_payload_hash` against the live draft)
   must have explicit tests for both versions side by side.
3. **`docs/specs/calendar-event-mapping.schema.md`**: mapping key gains
   `part_index` (one calendar event per part; duplicate detection,
   verification reads, and rollback operate per part).
4. Amend axiom 05 (splitting policy, below) and the relevant line of
   axiom 06; update `contracts/` models, valid + invalid fixtures
   (invalid: overlapping parts, `part_index` without `part_count`, part
   minutes not summing, mixed split/unsplit task_id), `make schemas`.

No algorithm change in P-J; the scheduler still never emits parts. Gates
green proves the contracts are ready before behavior moves.

## P-K · Splitting algorithm + downstream surfaces

**When to split** (deterministic policy, written into axiom 05):

- Only tasks with `splittable=True`.
- Trigger 1: `estimated_duration_min > policy.max_session_length_min`
  (today's hard failure `TASK_TOO_LONG_UNSPLITTABLE` keeps firing for
  non-splittable tasks — unchanged).
- Trigger 2: no single feasible candidate exists, but a split placement
  does.
- Never split merely to chase a better score — contiguous placement wins
  whenever feasible (predictability beats optimality; write this into the
  axiom).

**How to split**: target part length `preferred_session_length_min`,
last part absorbs the remainder if `< MIN_PART_MIN` (30, tunable in
`[scheduler_placement]`); parts placed in index order, part *i+1* starts
after part *i* ends; placement of parts is all-or-nothing per task — if
the final part doesn't fit, the whole task fails with
**`TASK_TOO_LONG_SPLITTABLE`** (the reserved code finally gets its
producer) and a debug payload listing parts attempted, parts placed, and
the largest remaining block (new builder in `scheduler/debug.py`).

**Downstream surfaces, MVP scope** (enumerate-and-touch, one behavior per
bullet, tests each):

- **Calendar write manager**: one event per part; titles remain
  metadata-only per calendar safety; duplicate detection, verify-read, and
  rollback iterate parts via the extended mapping.
- **Adjustment** (`scheduler/adjustment.py`): a `DraftAdjustment` targets
  one part (`task_id` + `part_index`); moving a part re-runs the same hard
  rules plus a new advisory warning when parts end up out of index order
  (advisory, matching the ADR-0008 philosophy — the user may reorder their
  own parts).
- **Disposition / completion**: completion stays **task-level** —
  completing the task completes all its parts' calendar presence; no
  per-part dispositions (`task_disposition` spec untouched). The Today
  view shows one task with a "session 2 of 3" annotation, not three
  completables.
- **Telemetry**: one event per task; `scheduled_duration_min` = sum of
  parts (calibration pipeline unaffected).
- **SPA (Week/Today)**: render parts as linked blocks
  ("Graphs practice · 2/3"); drag continues to work per part via the
  adjustment change.
- **Reconciliation**: an external move of one part adopts per part (the
  mapping key change carries this mostly for free; test it explicitly).

## Acceptance criteria

- Fragmented-calendar fixture: a 180-min splittable task that fails today
  schedules as 2–3 parts; the same task with `splittable=False` still
  fails `TASK_TOO_LONG_UNSPLITTABLE` with an unchanged debug shape.
- `TASK_TOO_LONG_SPLITTABLE` has a producer, a debug builder, golden
  coverage, and Supervisor routing identical to the other scheduler
  failures.
- Hash-recheck tests pass for drafts under both canonicalization versions;
  write → verify → rollback round-trips per part in the fake-adapter
  harness.
- Full `make check` + frontend gates green.

## Explicit non-goals

- No per-part completion or per-part telemetry.
- No splitting of non-splittable tasks under any pressure — the Planner
  owns that bit.
- No score-motivated splitting (policy above).
- No migration of existing approved drafts — old versions verify under
  their recorded canonicalization version, per axiom.

## Implementation notes (verified 2026-07-06 — these win over older prose)

Both inline references above are correct as cited (`greedy.py:342-346`,
`contracts/scheduler_output.py:129`; `TASK_TOO_LONG_SPLITTABLE` is indeed
reserved-without-producer, a deliberate 2026-06-09 audit decision).

### Hash-version bump — exact anchor points

The canonicalization machinery is already version-aware, which makes P-J's
"most dangerous edit" mechanical:

- `canonical_payload_hash(draft, version)` in `contracts/hashing.py:69-77`;
  version registry `register_canonicalizer` / `get_canonicalizer` at
  `:45-66`; the v1 canonicalizer at `:101-127`. P-J registers a
  `_canonicalize_v2` that includes the part fields, alongside v1 — never
  replacing it.
- The version constant producers stamp:
  `HASH_CANONICALIZATION_VERSION = "v1"` at `app/cycle.py:192` (flip to
  `"v2"`), plus a second literal `"v1"` in
  `tools/_calendar_cli_common.py:140` — grep for `"v1"` before declaring
  done.
- The write-path recheck already recomputes under the *recorded* version:
  `CalendarWriteManager._validate_approval`
  (`calendar_writer/manager.py:680`) calls
  `canonical_payload_hash(draft, approval.hash_canonicalization_version)`
  at `:736` and raises `ApprovalHashMismatchError` (`749-757`); entry
  points `approve_and_write` (`:216`) and `reconcile_after_crash` (`:513`).
  The "both versions side by side" test = one approval recorded under v1
  verifying against a v1-shaped draft, one under v2 with parts, both
  through the real manager.

### Downstream anchor points

- Mapping: `contracts/calendar_event_mapping.py:54-62` (fields; model is
  `extra="forbid"`, NOT frozen); store impls to extend are
  `calendar_writer/store.py` (in-memory) and
  `calendar_writer/sqlite_store.py`, shared suite
  `backend/tests/calendar_writer/test_store.py`.
- Adjustment: `DraftAdjustment` is `scheduler/adjustment.py:44` (`task_id`
  + `start` only — it gains an optional `part_index`); validation
  `validate_placements` at `:107`; apply path `CycleService.adjust`
  (`app/cycle.py:1200`).
- SPA: block identity is built in `buildWeekPlan`
  (`frontend/src/lib/weekplan.ts:108-118`, `key: entry.task_id`) and
  rendered in `frontend/src/components/WeekPlanView.tsx:170` — parts need a
  composite key (`` `${task_id}#${part_index}` ``) while `taskId` stays the
  bare id for lookups.

### Golden-scenario honesty flag (write this into the P-K commit)

`test_scenario_6_and_15_capacity_but_no_contiguous_block`
(`backend/tests/golden/test_scheduler_scenarios.py:208`) pins the
don't-promote side of capacity-vs-fragmentation using a **splittable** task
that today fails `NO_VALID_CONTIGUOUS_BLOCK` + `suggested_repair=SPLIT_TASK`.
Once splitting has a producer, that exact input may legitimately schedule
as parts (or fail `TASK_TOO_LONG_SPLITTABLE`) — this is the one golden
scenario whose *reason_code assertion changes by design* in P-K. Amend
`docs/golden-test-cases.md` and the test in the same commit, and preserve
the promotion boundary with a replacement non-splittable variant so
capacity-vs-fragmentation stays pinned. The README's "golden reason_codes
never change" rule explicitly yields to a spec-first contract change here —
that is what "gated, contract-heavy" means.
