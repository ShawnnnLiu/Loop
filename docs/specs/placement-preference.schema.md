# Placement Preference Schema

## Owner

App layer (`app/cycle.py` producers and aggregation; store
`app/placement_preference.py`). Feeds the revealed-preference tier of
`placement-evidence.schema.md` (axiom 05 "Revealed-preference term").

## Consumers

Placement-evidence composition (`app/cycle.py`), the data-control CLI
(`tools/user_data.py`), engineering review.

## Purpose

Two user actions are strong statements of preferred time-of-day that used
to vanish after being applied: a drag-to-adjust move (validated by
`scheduler/adjustment.py` and applied by `CycleService.adjust`) and an
inbound reconciliation adoption (an external calendar edit adopted by
`CycleService.reconcile`). A `PlacementPreferenceObservation` is the
append-only record of one such action: "the user moved a PRACTICE task so
it starts in the evening band."

Rows are stored **per observation, never pre-aggregated**, so recency
windows stay a pure read-time computation. Aggregation is deterministic
counting under journaled thresholds — no ML (ADR-0004), no decay
functions, no learned weights.

## Shape

`PlacementPreferenceObservation`:

| Field | Type | Rules |
| --- | --- | --- |
| `observation_id` | string | non-empty; unique per store (duplicate append rejects) |
| `user_id` | string | non-empty |
| `task_id` | string | non-empty; the moved task — never a raw event title (calendar-safety rule) |
| `category` | `TaskCategory` | the task-plan category vocabulary (`contracts/common_types.py`), read from the plan in scope at record time |
| `time_of_day_band` | `TimeOfDayBand` | the pooled-duration band vocabulary (`contracts/pooled_duration_model.py`) — one band definition in the codebase, ever |
| `observed_at` | datetime | timezone-aware; the app clock at record time |
| `source` | enum | `drag_adjust` \| `reconcile_adopt` |

`time_of_day_band` is the band of the move's **target start** in the
user's timezone (`derive_time_of_day_band(local_start.hour)`) — the band
the user moved work *into*, not out of.

## Producer Rules

- **`drag_adjust`** — recorded by `CycleService.adjust` only after the
  server-side re-validation finds no conflicts and the adjusted draft is
  saved. A rejected move records nothing. One observation per adjusted
  task.
- **`reconcile_adopt`** — recorded by `CycleService.reconcile` only for
  deltas whose disposition is `ADOPTED` (a valid external move/resize
  adopted into a fresh draft). Never for rejected moves and never for
  `event_deleted` dispositions — deleted-from-calendar is surfacing-only
  by prior decision (task-disposition spec).
- No other producer exists. Scheduler-chosen placements are never
  observations: only an explicit user repositioning states a preference.

## Aggregation Rules (app layer)

Folded into `PlacementEvidence` during composition (the P-H helper):

- Observations with `observed_at` within the last `revealed_window_days`
  days of the app clock, grouped by `(category, time_of_day_band)`.
- A group with `count >= revealed_min_observations` emits one `revealed`
  `EvidenceCell` with `weighted_sample = float(count)` and no
  `multiplier` (forbidden for the revealed source — there is no duration
  claim, only a location preference).
- Defaults `revealed_min_observations = 3`, `revealed_window_days = 90` —
  heuristic priors in `[scheduler_placement]` (axiom 07). The clock is
  read in the app layer only; the scheduler sees cells, never rows.

## Privacy And Data Controls

- Per-user data about the user's own behavior: no cross-user pooling and
  no consent-gate extension (ADR-0007 gates pooled tiers; this is not
  one). Reads are NOT audited — `DataAccessPurpose` has no
  disposition-read purpose, and observations are the same data class as
  task dispositions (`data-access-audit.schema.md` decision).
- The store exposes user-scoped list and delete surfaces, and the
  `tools/user_data.py` view / export / delete controls cover
  `placement_preferences` rows like every other per-user store.
- `task_id` and enums only — never raw calendar event titles or
  descriptions (axiom 06).

## Store Rules

- Append-only journal in insertion order (the `app/threshold_log.py`
  twin-in-one-module pattern: protocol + in-memory + SQLite).
- A duplicate `observation_id` always rejects the append with a typed
  error; observations are immutable facts, never edited.
- `delete_for_user` exists solely for the data-control surface and
  returns the removed-row count.

## JSON Example

```json
{
  "observation_id": "prefobs_001",
  "user_id": "user_123",
  "task_id": "dp_001",
  "category": "practice",
  "time_of_day_band": "evening",
  "observed_at": "2026-07-16T18:05:00-07:00",
  "source": "drag_adjust"
}
```

## Validation Rules

- `observation_id`, `user_id`, and `task_id` are non-empty strings.
- `category` and `time_of_day_band` must be members of their shared
  vocabularies.
- `observed_at` must be timezone-aware.
- `source` is `drag_adjust` or `reconcile_adopt`.

## Invalid Examples

```json
{ "observation_id": "prefobs_002", "observed_at": "2026-07-16T18:05:00", "...": "..." }
```

Reason: naive `observed_at` (no UTC offset).

```json
{ "source": "scheduler_placed", "...": "..." }
```

Reason: unknown source — scheduler-chosen placements are never
observations.

```json
{ "task_id": "", "...": "..." }
```

Reason: empty `task_id`.

## Related Docs

- `placement-evidence.schema.md`
- `task-disposition.schema.md`
- `data-access-audit.schema.md`
- `../axioms/05-scheduler-policy.md`
- `../axioms/06-calendar-safety.md`
- `../decisions/ADR-0004-no-per-user-ml-model-in-mvp.md`
- `../implementation-plans/scheduler-placement-quality/03-evidence-driven-placement.md`
