# 01 · Scored Best-Fit Placement

The core upgrade: replace "first window's start wins" with "enumerate all
feasible candidate starts, pick the deterministic argmin of a cost
function." Task ordering, hard-constraint checks, and every failure path
stay exactly as they are.

Increments: **P-A → P-D**, one commit each. P-B is deliberately a
zero-behavior-change refactor so the actual policy change (P-C) is a single
reviewable commit.

## P-A · Axiom-05 amendment + policy plumbing

Spec/axiom first, no algorithm change yet.

1. **Amend `docs/axioms/05-scheduler-policy.md`**: add a "Scored placement"
   section defining candidate enumeration (window starts + a fixed
   15-minute intra-window grid), the integer cost function, the term list
   (names + sign conventions, see P-C), the tie-break
   `(cost, candidate_start)`, and the rule that weights are heuristic
   priors tunable only via `tuning.toml` (axiom-07 pattern). State
   explicitly: soft terms reorder feasible candidates and can never cause
   a task to fail that first-fit would have placed.
2. **Extend `SchedulingPolicy`** (`scheduler/policy.py:26`) with the
   captured-but-dropped profile fields, and carry them in
   `policy_from_user_profile` (`scheduler/policy.py:46`):
   - `prefer_evening_sessions: bool = False`
   - `prefer_weekend_long_blocks: bool = False`
   - `avoid_back_to_back_deep_work: bool = False`
   - `preferred_session_length_min: int` (from
     `UserProfile.preferred_session_length_min` — a **top-level** required
     `UserProfile` field at `contracts/user_profile.py:120`, `gt=0, le=720`,
     NOT under `Preferences`; used by the fragmentation term and later by
     splitting)
   The three bools exist on `UserProfile.Preferences`
   (`contracts/user_profile.py:79-86`) as bare `bool = False` fields — the
   *class* docstring ("Soft preferences used as tie-breakers when multiple
   schedules are valid") promises the tie-breaker behavior this increment
   finally delivers.
   `SchedulingPolicy` is region-local (not under `contracts/`), so no
   `make schemas`; the axiom's policy JSON block is its spec — update it.
3. Update `test_policy.py` (policy mirrors profile) for the new fields.

Acceptance: `make check` green; behavior unchanged (fields plumbed, unread).

## P-B · Candidate machinery, provably output-identical

Pure refactor. Introduce `scheduler/scoring.py`:

- `PlacementCandidate` (frozen dataclass: `start`, `end`, `window`,
  feasibility facts needed by terms).
- `enumerate_candidates(task, windows, state, policy)` — for P-B,
  **window starts only** (exactly today's candidate set), running the same
  feasibility checks `_try_place` runs today (`greedy.py:246-271`; the five
  checks are enumerated in the Implementation notes below).
- `select_placement(candidates, ...)` — argmin of cost with tie-break
  `(cost, start)`; cost is constant 0 in P-B.

Rewire `_try_place` through this machinery. With cost ≡ 0 and
window-start-only candidates, argmin-with-earliest-tie-break *is* first
fit, so outputs are byte-identical.

**Lock that claim with a test**: run every existing greedy/golden scenario
through old and new paths (keep the old `_try_place` body as a private
`_first_fit_reference` inside the test module, not in src) and assert
identical `SchedulerOutput.model_dump()`. Delete the reference after P-C
lands (it stops being true, deliberately).

Acceptance: `make check` green with **zero** test-expectation edits.

## P-C · Scoring terms v1 (the behavior change)

Enable the intra-window grid (every 15 min from window start, plus the
window start itself) and the cost terms. All integer arithmetic; each term
returns minutes-scaled ints; weights are ints (see P-D). Terms:

| Term | Sign | Definition (pure function of `SchedulerInput` + placement state) |
| --- | --- | --- |
| `daily_balance` | penalty | `max(0, used_today + duration − target_daily_min)` where `target_daily_min = min(policy.max_daily_study_min, ceil(total_plan_min / working_days_in_horizon))`. Kills the Monday pile-up. |
| `back_to_back` | penalty | positive when the gap to the adjacent study block (before or after) is `< BUFFER_MIN` (15); doubled when both blocks are deep and `avoid_back_to_back_deep_work`. |
| `fragmentation` | penalty | positive when the window remainder after placement is `0 < leftover < preferred_session_length_min` (an unusable sliver); zero when leftover is 0 or a usable block. |
| `deep_window_conservation` | penalty | non-deep task consuming a deep window (opportunity cost for scarce deep capacity). |
| `evening_preference` | bonus | candidate start in the 17:00–21:59 local band when `prefer_evening_sessions`. |
| `weekend_long_block` | bonus | weekend placement of a task with `duration > preferred_session_length_min` when `prefer_weekend_long_blocks` and `allow_weekends`. |

Notes:

- The intra-window grid strictly *adds* candidates, so anything first-fit
  placed remains placeable — failures can only decrease. It can also fix a
  real first-fit blind spot: today a deep task is rejected for a whole
  window if the deep-gap check fails at `window.start` even when a later
  start inside the window would satisfy it (`greedy.py:262-267`).
- Time-of-day banding reuses `derive_time_of_day_band(local_hour: int)`
  (`duration_estimation/pooled.py:59-67`) — do not invent a second band
  definition. **Import it directly**: `.importlinter` contract 10
  deliberately leaves `duration_estimation` out of the region-independence
  set so any region may import it (only the reverse direction,
  `duration_estimation → scheduler`, is forbidden). No lifting into
  `contracts/` is needed. The enum `TimeOfDayBand` itself lives at
  `contracts/pooled_duration_model.py:30-36` (MORNING 05:00–11:59,
  AFTERNOON 12:00–16:59, EVENING 17:00–21:59, NIGHT 22:00–04:59).
- **Deliberately update** the placement-instant tests
  (`test_greedy.py`, golden scenarios) to the new expected instants;
  reason_code / debug / routing assertions must not change. Add per-term
  unit tests (construct a two-window fixture where only that term
  discriminates) and a determinism test (schedule twice, byte-identical).

Acceptance: `make check` green; a fixture with 5 tasks × 3 free days no
longer stacks all tasks on day 1 at `no_events_before`.

## P-D · Weights in tuning.toml + quality report CLI

1. Add `[scheduler_placement]` to `backend/tuning.toml` (commented defaults,
   axiom-07 journaling like every other section): `w_daily_balance`,
   `w_back_to_back`, `w_fragmentation`, `w_deep_window_conservation`,
   `w_evening_preference`, `w_weekend_long_block`, `buffer_min`,
   `candidate_grid_min`. Wire through the existing tuning-load →
   threshold-change-log path (`docs/specs/threshold-change-log.schema.md`).
2. `score_schedule(output, inp) -> breakdown` in `scheduler/scoring.py`
   (pure; no contract change to `SchedulerOutput`), plus an operator CLI in
   `tools/` that prints per-day load, per-term totals, and band histogram
   for a given scheduler input fixture — the before/after evidence for the
   project's definition of done. Commit a short before/after comparison in
   this doc's phase notes when done.

Acceptance: overriding a weight in `tuning.toml` changes placement and
journals a threshold-change entry; CLI output on the fixture corpus shows
the improvement.

## Explicit non-goals for this phase

- No `MotivationProfile.quiet_hours` term — those are *notification* quiet
  hours (nudge semantics), not availability; repurposing them for placement
  would be a semantics change needing its own decision.
- No splitting, no day quotas, no evidence terms, no solver — later phases.
- No new `SchedulerInput` fields. User-derived *preferences* ride on
  `SchedulingPolicy`; operator-tunable *weights/knobs* arrive as a separate
  keyword-only `scoring` argument to `schedule()` (decision in the
  Implementation notes below — mirrors the existing `module_priority`
  precedent, `greedy.py:51`).

## Implementation notes (verified 2026-07-06 — these win over older prose)

### Verified reference map

- `_try_place`: def `greedy.py:240-245`, body `246-271`. Signature
  `_try_place(task: Task, windows: list[FreeWindow], inp: SchedulerInput,
  state: _PlacementState) -> _Placement | None`. It iterates
  `_live_windows(windows, state.busy)`. The **five hard checks**, in order:
  1. window too small: `window.duration_min < duration` (`:250`);
  2. deep-window requirement: `needs_deep and
     inp.policy.respect_deep_work_windows and not window.is_deep_work`
     (`:252`), where `needs_deep = task.required_focus_level is
     FocusLevel.DEEP`;
  3. candidate end past window end: `candidate_end > window.end` (`:256`);
  4. daily cap: `used_today + duration > inp.policy.max_daily_study_min`
     (`:260`), `used_today = state.minutes_per_day.get(day_key, 0)`;
  5. deep-gap: for deep tasks, gap since `state.last_deep_end[day_key]`
     `< inp.policy.min_break_between_deep_blocks_min` (`262-267`).
- `_PlacementState` (`greedy.py:42-48`, `@dataclass(slots=True)`):
  `busy: list[FreeBusyInterval]`, `minutes_per_day: dict[str, int]`
  (key = `dt.date().isoformat()`, `_day_key` at `:381-382`),
  `last_deep_end: dict[str, datetime]`. `_record_placement`
  (`greedy.py:274-297`) appends the placed interval to `busy`, re-sorts,
  bumps `minutes_per_day`, sets `last_deep_end` for deep tasks, and
  **re-enumerates free windows in place** (`290-297`) — the candidate
  machinery must keep flowing through `_live_windows(windows, state.busy)`
  so this stays true.
- `SchedulingPolicy` (`policy.py:26`) is a **frozen Pydantic model**
  (`extra="forbid"`), current fields at `policy.py:36-43`. House rule from
  the 2026-06-09 audit: any evolve-and-return of a frozen model goes through
  `model_validate`, never bare `model_copy(update=...)`.
- `SchedulerInput` (`inputs.py:35`, fields `40-47`) and `SchedulingPolicy`
  are region-local and **not** in `tools/export_schemas.py`'s `CONTRACTS`
  dict — adding fields to either does NOT require `make schemas`.
- `FreeWindow` (`windows.py:31`): frozen dataclass `start`, `end`,
  `is_deep_work`, property `duration_min`. Windows are sliced per local day
  during enumeration (`windows.py:66-78`) and split at deep-work boundaries
  (`_split_by_deep_work`, `89-132`) — **a window never spans midnight and
  never mixes deep/non-deep**, so a candidate's day and deepness are simply
  its window's.
- Tests: `backend/tests/scheduler/test_greedy.py`,
  `backend/tests/scheduler/test_policy.py` (single test
  `test_policy_mirrors_user_profile_constraints`), golden scenarios in
  `backend/tests/golden/test_scheduler_scenarios.py`.
  `test_deep_work_task_placed_in_deep_window` is `test_greedy.py:132` and
  asserts `start == datetime(2026, 5, 4, 18, 0, tzinfo=UTC)` (`145-146`).
- `policy_from_user_profile` (`policy.py:46`) currently copies
  `user.hard_constraints.{no_events_before, no_events_after, allow_weekends,
  min_break_between_deep_blocks_min, max_daily_study_min}`, hard-codes
  `respect_deep_work_windows=True`, maps `user.deep_work_windows`, and
  copies top-level `user.max_session_length_min`.

### P-B mechanics (pin these, don't re-derive)

- `PlacementCandidate` fields: `start: datetime`, `end: datetime`,
  `window: FreeWindow`. Everything else a term needs (day key, used_today,
  adjacency) is computed by the term functions from `(candidate, state,
  inp, scoring)` — don't cache derived facts on the candidate.
- `select_placement` total-order key: `(cost, candidate.start)`. This is
  total because free windows are disjoint and grid starts within a window
  are distinct, so no two candidates share a `start`.
- The P-B equivalence proof only holds because with window-start-only
  candidates and cost ≡ 0, argmin over `(0, start)` = earliest feasible
  window start = today's first fit. Keep `_first_fit_reference` (the copied
  old `_try_place` body) in the **test module only**.

### P-C exact formulas (all integer minutes; no floats anywhere)

Sign convention:
`cost(candidate) = Σ w_term × penalty_term − Σ w_term × bonus_term`,
each `penalty_term`/`bonus_term` a non-negative int; pick argmin by
`(cost, start)`. Helper: `ceil_div(a, b) = -(-a // b)`.

Computed once per `schedule()` call:
- `working_days` = number of distinct local dates carrying ≥ 1 enumerated
  free window (from the initial enumeration, before any placement).
- `total_plan_min` = Σ `estimated_duration_min` over tasks NOT in
  `completed_task_ids`.
- `target_daily_min = min(policy.max_daily_study_min,
  ceil_div(total_plan_min, working_days))`; guard: if `working_days == 0`,
  use `policy.max_daily_study_min` (nothing places anyway).

Per-candidate terms (`duration = task.estimated_duration_min`; the
candidate's day/deepness come from its window):

| Term | Kind | Exact value |
| --- | --- | --- |
| `daily_balance` | penalty | `max(0, used_today + duration − target_daily_min)` |
| `back_to_back` | penalty | For each side (before/after): find the nearest **placed study block** on the same local day (track placed blocks as `(start, end, task_is_deep)` in the scoring state — external calendar busy does NOT count); if it exists with `gap < scoring.buffer_min`, add `scoring.buffer_min − gap`; **double that side's contribution** iff `policy.avoid_back_to_back_deep_work` and the candidate task is deep and that adjacent block is deep. Gaps are whole minutes and ≥ 0 (overlap is impossible inside free windows). |
| `fragmentation` | penalty | `g(lead) + g(trail)` where `lead = minutes(window.start → candidate.start)`, `trail = minutes(candidate.end → window.end)`, and `g(x) = x if 0 < x < policy.preferred_session_length_min else 0`. (The grid introduces *leading* slivers too — penalize both sides.) |
| `deep_window_conservation` | penalty | `duration` if `window.is_deep_work` and the task is NOT deep, else 0. |
| `evening_preference` | bonus | `duration` if `policy.prefer_evening_sessions` and `derive_time_of_day_band(candidate.start.hour) == EVENING`, else 0. (Datetimes are already user-local wall-clock — see README.) |
| `weekend_long_block` | bonus | `duration` if `policy.prefer_weekend_long_blocks` and `policy.allow_weekends` and `candidate.start.date().weekday() in {5, 6}` and `duration > policy.preferred_session_length_min`, else 0. |

Grid: `candidate_starts(window) = {window.start + k × scoring.candidate_grid_min
minutes | k ≥ 0, start + duration ≤ window.end}` — the `k = 0` element IS
the window start, no special-casing needed.

**Marginal vs schedule-level:** the table above defines *marginal* values
used to pick a placement mid-loop. The P-D report (and the P-G polish
objective) use *schedule-level totals* re-derived from the finished
schedule: `daily_balance_total = Σ_days max(0, minutes(day) −
target_daily_min)`; `back_to_back_total` = Σ over same-day adjacent placed
pairs of `max(0, buffer_min − gap)` (deep-pair doubling rule applied once
per pair); `fragmentation_total` = Σ sliver minutes over the final live
windows; `deep_window_conservation_total` = Σ non-deep minutes placed in
deep windows; bonuses summed over placed blocks. Marginal sums and
schedule-level totals are NOT numerically identical (marginals are
path-dependent) — that is fine and expected; only the schedule-level
definitions are the audit/report/polish objective.

### P-D plumbing decisions (made here — do not relitigate)

- New frozen dataclass `PlacementScoringConfig` in `scheduler/scoring.py`
  with a module-level `DEFAULT_PLACEMENT_SCORING_CONFIG`. Fields, all
  `int`, defaults (heuristic priors, journaled as such): `w_daily_balance =
  3`, `w_back_to_back = 2`, `w_fragmentation = 1`,
  `w_deep_window_conservation = 2`, `w_evening_preference = 1`,
  `w_weekend_long_block = 1`, `buffer_min = 15`, `candidate_grid_min = 15`.
- Weights reach the scheduler as a new keyword-only parameter:
  `schedule(inp, *, module_priority=None, scoring: PlacementScoringConfig |
  None = None)` — `None` means defaults. This mirrors the existing
  `module_priority` kwarg and keeps `SchedulingPolicy` a pure mirror of the
  user profile (its existing test stays honest).
- Tuning wiring, exactly like `pooled_serving`: register
  `"scheduler_placement": (PlacementScoringConfig,
  DEFAULT_PLACEMENT_SCORING_CONFIG)` in `TUNABLE_SECTIONS`
  (`app/tuning.py:79-87`) and add a `scheduler_placement:
  PlacementScoringConfig` field to the frozen `EffectiveTuning` dataclass
  (`app/tuning.py:113-123`). `apply_tuning` then journals overrides through
  `ThresholdChangeLogStore` for free. `app/tuning.py` importing from
  `scheduler/` is fine — `app/` is the composition layer. Add the commented
  `[scheduler_placement]` block to `backend/tuning.toml` following the
  existing commented-section style. (Known pre-existing drift, not yours to
  fix: `claim_curation` is registered but has no commented block in the
  file.)
- Composition: pass `env.tuning.scheduler_placement` at the `schedule(...)`
  call site (`app/cycle.py:925-938`).
- `score_schedule(output, inp, scoring) -> breakdown` returns the
  schedule-level totals defined above (per-term ints, per-day minutes, band
  histogram of placed starts).
- CLI: `tools/show_placement_quality.py`, module-only invocation
  (`python -m agentic_calendar.tools.show_placement_quality`), `main(argv)`
  + `if __name__ == "__main__": raise SystemExit(main())` — the `show_*`
  read-only convention (`show_thresholds.py`, `show_metrics.py`). Input: a
  path to a serialized `SchedulerInput` JSON
  (`SchedulerInput.model_validate_json`); it runs `schedule()` and prints
  the breakdown. Fixture corpus: new directory
  `backend/tests/fixtures/placement_quality/*.json` (the existing
  `fixtures/valid|invalid` split is for contract fixtures — this corpus is
  input scenarios, so it gets its own subdirectory), shared by the CLI and
  the before/after tests.
