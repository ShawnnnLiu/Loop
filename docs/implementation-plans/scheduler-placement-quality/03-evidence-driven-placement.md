# 03 · Evidence-Driven Placement

Feed the scorer per-user, per-time-of-day evidence the system already
computes (pooled duration buckets, per-user refinements) plus a new
deterministic revealed-preference signal (drag-to-adjust + reconciliation
adoptions). This is the personalization payoff and the portfolio headline:
the system *learns where you work best* with counting and medians, no ML
(ADR-0004 intact).

Requires 01 (score terms); benefits from 02 but doesn't require it.

Increments: **P-H → P-I**, one commit each.

## P-H · `PlacementEvidence` input + evidence score term

The scheduler stays pure: evidence arrives through the input contract,
composed by the app layer.

1. **Spec first**: `docs/specs/placement-evidence.schema.md`, then
   `contracts/placement_evidence.py`, fixtures (valid + invalid), and
   `make schemas`. Shape:
   - `PlacementEvidence` = list of `EvidenceCell`:
     `{category: TaskCategory, time_of_day_band: TimeOfDayBand,`
     `multiplier: float, weighted_sample: float, source: POOLED | PER_USER_REFINED}`.
   - Reuse `TimeOfDayBand` from `contracts/pooled_duration_model.py:30` —
     one band definition in the codebase, ever.
   - Invalid fixtures: unknown band, negative sample, duplicate
     `(category, band)` cell.
2. **Composition** in `app/cycle.py` (where `SchedulerInput` is built,
   `:925-938`): derive cells from the pooled model and, when the
   power-user gate passes, `PerUserRefinement.lookup(category, band)`
   (`contracts/power_user.py:150`). Respect the existing consent gate
   (ADR-0007) — no consent, no pooled cells, scheduler runs evidence-free
   exactly as today. Apply the serving-floor discipline: cells below
   `weighted_sample ≥ pooled_serving.serving_floor` are not emitted.
   **Read the production-reality note in the Implementation notes below
   before building this** — in the solo MVP there is no pooled model to
   read and the power-user gate has no runtime call site; the scope
   decision there is binding.
3. **Scheduler**: `SchedulerInput.placement_evidence: PlacementEvidence`
   defaulting to empty (`scheduler/inputs.py:35`); new score term
   `evidence_affinity` — bonus proportional to `(1 − multiplier)` clamped
   to the calibration bounds for the candidate's `(task.category, band)`
   cell (user historically faster in that band ⇒ prefer it). Missing cell
   ⇒ term is exactly 0. Weight `w_evidence_affinity` in
   `[scheduler_placement]`.

**Scope guard (write it into the axiom amendment):** evidence biases
*where* a task goes, never *how long it is*. `estimated_duration_min` stays
whatever the Planner + calibration pipeline produced (axiom 17's transform
path, `duration_estimation/transform.py:62`). Coupling placement to
duration re-estimation would tangle two calibrated systems; the pooled
serving path's marginalization note (`pooled.py:338-341`) documents why the
band was unknown at estimation time — it stays unknown there.

Tests: consent-off ⇒ input identical to today (empty evidence, zero diffs);
cell present ⇒ deterministic placement shift into the favored band on a
two-band fixture; serving floor respected; contract fixtures round-trip.

## P-I · Revealed-preference counts

Two user actions are strong statements of preferred time-of-day that today
vanish after being applied:

- a drag-to-adjust move validated by `validate_placements`
  (`scheduler/adjustment.py:107`) and applied by `CycleService.adjust`
  (`app/cycle.py:1200`, save at `:1279`);
- an inbound reconciliation adoption (inside `reconcile`,
  `app/cycle.py:1522-1528`, `mapping_store.record_external_edit(...)`,
  which stamps `user_modified_bool=True` on the mapping via
  `CalendarEventMapping.with_external_edit`).

1. **Spec first**: `docs/specs/placement-preference.schema.md` +
   `contracts/placement_preference.py`:
   `PlacementPreferenceObservation` =
   `{user_id, task_id, category, time_of_day_band, observed_at, source: DRAG_ADJUST | RECONCILE_ADOPT}`.
   Store rows per observation (not pre-aggregated counts) so recency
   windows stay a pure read-time computation.
2. **Store**: SQLite table + in-memory twin following the disposition-store
   pattern (`disposition/disposition_store.py`); parametrized shared test
   suite like the other Phase-9 stores.
3. **Producers**: the two call sites above record an observation with the
   *target* band of the move (band of the new start, in the user's tz —
   reuse `derive_time_of_day_band`). No raw event titles anywhere
   (calendar-safety rule).
4. **Aggregation → evidence**: in the P-H composition step, fold
   observations from the last 90 days with `count ≥ 3` per
   `(category, band)` into `PlacementEvidence` cells (source tag
   `REVEALED` added to the enum; spec updated in the same commit). The
   min-evidence threshold and window go into `[scheduler_placement]`
   (`revealed_min_observations`, `revealed_window_days`) as heuristic
   priors.
5. This is per-user data about the user's own behavior — no pooling, no
   consent-gate extension needed beyond what already covers telemetry-like
   storage; note that reading in the data-access audit surface if the
   existing pattern requires it (check `docs/specs/data-access-audit.schema.md`
   before deciding — if dispositions are audited, observations are too).

Tests: producer fires on adopt + on drag-apply (and not on rejected
moves); aggregation threshold and window respected; end-to-end fixture
where three evening drags of `PRACTICE` tasks pull the next replan's
`PRACTICE` placements into the evening band; determinism.

## Acceptance criteria (phase)

- With no consent, no history, and no observations, scheduler output is
  byte-identical to the 02 baseline.
- With evidence present, the quality-report CLI shows band histograms
  shifting toward the evidenced bands, and every shift is explainable by a
  printed evidence cell (auditability — the report gains an "evidence
  applied" section).
- `make check` green per increment; specs, fixtures, generated schemas,
  and `graphify update .` all current.

## Explicit non-goals

- No duration changes from evidence (scope guard above).
- No cross-user pooling of revealed preferences.
- No decay functions or learned weights — a count threshold and a recency
  window, nothing smarter, until calibration data says otherwise.
- No wiring of the power-user eligibility gate (production-reality note
  below).

## Implementation notes (verified 2026-07-06 — these win over older prose)

### Production-reality note (binding scope decision for P-H)

Two facts, verified:

- The cycle currently calls `resolve_effective_multipliers(...)` with
  `model=None` — "no pooled model exists in the solo MVP"
  (`app/cycle.py:739`). There is no pooled-model artifact store to read.
- `evaluate_power_user_eligibility` (`duration_estimation/power_user.py:75`)
  has **no runtime call site anywhere** — the refinement tier is scaffolded
  contracts + pure functions only.

Decision: the P-H composition helper takes the pooled artifact and the
per-user refinement as **optional parameters** (both `None` in the solo
MVP → zero POOLED/PER_USER_REFINED cells → scheduler runs evidence-free,
which is also the consent-off path). Do NOT wire the eligibility gate in
this project. Pooled/refined cells are exercised end-to-end by tests and
fixtures; the **live** personalization payoff in solo dogfooding is P-I's
REVEALED cells, which need no pooled model. Honesty requirement (this repo
has been burned by inert-in-prod claim paths before): nothing user-facing
or in `docs/` may describe pooled-evidence placement as live until a
pooled artifact actually flows in production.

Consent-gate mechanics for when pooled cells DO flow: mirror the existing
check at `app/cycle.py:727-731` — `env.consent_gate.check(user_id,
DataAccessPurpose.POOLED_SERVING, DataAccessor.SERVING_PIPELINE)`; gate
impl `consent/gate.py:77-106`, decision fields `.allowed` /
`.reason_code`.

### P-I landed (2026-07-16) — phase complete

- Spec `placement-preference.schema.md` + contract
  `contracts/placement_preference.py` (`PlacementPreferenceObservation`,
  `PlacementPreferenceSource` = DRAG_ADJUST | RECONCILE_ADOPT); registered
  in `export_schemas.py`; valid + invalid fixtures. `EvidenceSource` gained
  `REVEALED` (multiplier-forbidden, pre-built validator now exercised; the
  "revealed cell with a multiplier" invalid fixture exists).
- Store `app/placement_preference.py` (threshold_log twin pattern:
  protocol + in-memory + SQLite in one module; `list_for_user` /
  `delete_for_user` for data controls); registered in `AppEnvironment`
  (all four spots); parametrized shared suite incl. restart survival.
- Producers: `CycleService.adjust` (after conflicts-empty + draft saved;
  one observation per adjusted task, category from the in-scope plan) and
  `reconcile` (ADOPTED deltas only — never rejected moves, never
  `event_deleted`). Both via `_record_placement_observation`
  (`prefobs_`-prefixed ids, band of the user-local target start).
- Aggregation in `_placement_evidence`: observations within
  `revealed_window_days` (90), grouped by `(category, band)`, emit a
  REVEALED cell at `count >= revealed_min_observations` (3);
  `weighted_sample = float(count)`; clock read in the app layer only.
- Scoring: `revealed_lookup` (frozen key set) +
  `revealed_affinity_bonus` (flat `duration` on match); cost gains
  `- w_revealed_affinity x bonus`; `w_revealed_affinity = 2`; all three
  knobs on `PlacementScoringConfig` (`[scheduler_placement]`, journaled
  commented defaults in `tuning.toml`); `ZERO_WEIGHTS` zeroes the weight.
- Quality report gained the "evidence applied" section (human + `--json`),
  printing the input's cells; corpus totals stayed byte-identical
  (124 / 267 / -36 / 235).
- End-to-end test: three evening drags of the PRACTICE task pull the next
  replan's PRACTICE placement into the evening band
  (`test_three_evening_drags_pull_practice_into_the_evening_band`).
- `tools/user_data.py` docstring + CLI tests cover `placement_preferences`
  rows in view, export, and delete.

### P-H landed (2026-07-16) — surfaces P-I builds on

- Contract: `contracts/placement_evidence.py` (`PlacementEvidence`,
  `EvidenceCell`, `EvidenceSource`, `MULTIPLIER_SOURCES`,
  `EVIDENCE_MULTIPLIER_MIN/MAX`); registered in `export_schemas.py`.
- Scheduler: `SchedulerInput.placement_evidence` (default empty);
  `scoring.evidence_lookup` (dict `(category, band) → mult_pct`,
  REFINED overwrites POOLED, multiplier-less cells skipped — REVEALED
  rides that skip for free) + `scoring.evidence_affinity_adjustment`
  (signed percent-minutes; caller does `w × adj // 100`), threaded as an
  optional `evidence=` kwarg through `candidate_cost` / `rank_placement`
  / `select_placement`; wired in `greedy._schedule_validated`.
  `w_evidence_affinity = 1` on `PlacementScoringConfig`;
  `ZERO_WEIGHTS` zeroes it; `make_input` in `tests/scheduler/_helpers.py`
  grew a `placement_evidence` kwarg. The polish objective (`score_blocks`)
  deliberately does NOT carry the term — `PlacedBlock` has no category;
  band-symmetric moves are not strict improvements, so polish cannot
  undo an evidence shift on the two-band fixtures.
- Composition: `CycleService._placement_evidence(onboarding, *,
  pooled_model=None, refinement=None)` in `app/cycle.py` — P-I's
  aggregation folds REVEALED cells in here. Consent gate consulted only
  when an artifact is offered (dormant path writes zero audit rows);
  floor applies to both tiers; cells sorted `(category, band, source)`.
- Axiom 05 gained "Evidence-affinity term" + a dormant-in-production
  rollout paragraph.

### P-H contract + scoring specifics

- `EvidenceCell` shape decisions:
  - `multiplier: float | None` with contract bounds `ge=0.5, le=2.0`
    (matching the calibration clamp band, `PooledTrainingConfig` /
    `RefinementConfig` `multiplier_min=0.5 / multiplier_max=2.0`).
    Validator: `multiplier` REQUIRED for `POOLED | PER_USER_REFINED`,
    FORBIDDEN (`None`) for `REVEALED` (P-I adds that enum member; put the
    conditional validator in from the start).
  - Uniqueness invariant: no duplicate `(category, time_of_day_band,
    source)` — NOT `(category, band)`, because a `(category, band)` may
    legitimately carry both a POOLED and a REVEALED cell.
  - Invalid fixtures: unknown band; negative `weighted_sample`; duplicate
    `(category, band, source)`; POOLED cell with `multiplier=None`;
    REVEALED cell with a multiplier; multiplier outside `[0.5, 2.0]`.
  - `TaskCategory` imports from `contracts/common_types.py:54` (NOT
    `task_plan.py`); members: CONCEPT_REVIEW, PRACTICE, MOCK_INTERVIEW,
    PROJECT, REFLECTION, REVIEW.
  - New contract ⇒ register it in `tools/export_schemas.py` `CONTRACTS`
    and run `make schemas` (unlike `SchedulerInput` itself, which is
    region-local and unregistered — adding `placement_evidence` to it needs
    no schema regen).
- `evidence_affinity` term — exact integer form (keeps the all-int cost
  arithmetic; `multiplier` is the only float and is converted once):
  - `mult_pct = round(cell.multiplier * 100)` (int in `[50, 200]`).
  - Cost contribution for a candidate whose `(task.category, band(start))`
    matches a POOLED/PER_USER_REFINED cell:
    `w_evidence_affinity * (mult_pct − 100) * duration // 100` **added** to
    cost — negative (bonus) when the user is historically faster in that
    band (`mult < 1`), positive (penalty) when slower. Missing cell ⇒ 0.
    Python `//` floors toward −∞ on negatives; that is fine —
    determinism, not symmetry, is the requirement. If both a POOLED and a
    PER_USER_REFINED cell match, PER_USER_REFINED wins (more specific);
    state that in the spec.
  - Default `w_evidence_affinity = 1`, in `[scheduler_placement]`.

### P-I specifics

- **REVEALED scoring** (the `(1 − multiplier)` formula cannot apply — no
  multiplier): a candidate whose `(task.category, band)` matches a REVEALED
  cell gets a flat bonus, cost `−= w_revealed_affinity * duration`.
  Default `w_revealed_affinity = 2` (stronger than the generic bonuses —
  it is the user's own explicit behavior). REVEALED cells carry
  `weighted_sample = float(observation count)`, `multiplier = None`.
- **Store decision**: follow the `app/threshold_log.py` precedent (protocol
  + in-memory + SQLite twins in ONE app-layer module), not the
  `disposition/` own-package precedent — observations are produced and
  consumed only by the app layer, so `app/placement_preference.py` avoids
  any `.importlinter` change. Parametrized shared suite at
  `backend/tests/app/test_placement_preference.py` (mirror
  `test_threshold_log.py`). Registration in `AppEnvironment` needs all
  four spots: dataclass field (near `disposition_store`,
  `app/environment.py:249`), in-memory branch (`:306` block), SQLite branch
  (`:328` block), and the `AppEnvironment(...)` constructor call (`:375`).
- **Producer: drag-adjust** — in `CycleService.adjust`, after conflicts
  are empty and the draft is saved (`app/cycle.py:1279`). The user-local
  start is already computed (`adjustment.start.astimezone(tz)`,
  `:1240-1243`, `tz = onboarding.tzinfo()`); `category` is NOT on
  `DraftAdjustment` (`adjustment.py:44` — `task_id` + `start` only) but the
  plan is in scope: index `{t.task_id: t.category for t in
  plan_version.plan.tasks}` (plan loaded at `:1237`), no store fetch.
  Band = `derive_time_of_day_band(local_start.hour)`;
  `observed_at = env.clock.now()`.
- **Producer: reconciliation adoption** — inside `reconcile`'s
  `if adopt:` block (`app/cycle.py:1522-1528`); the adopted start is
  `seen_start` (unpacked at `:1509`); convert with
  `seen_start.astimezone(onboarding.tzinfo())` before reading `.hour`.
  Record ONLY for adopted moves — never for `event_deleted` dispositions
  (deleted-from-calendar is surfacing-only by prior decision) and never
  for rejected reconciliations.
- **Aggregation**: helper next to the `SchedulerInput` build
  (`app/cycle.py:925-938`): observations where `observed_at ≥
  env.clock.now() − revealed_window_days`, grouped by `(category, band)`,
  emitting a REVEALED cell when `count ≥ revealed_min_observations`.
  Defaults `revealed_min_observations = 3`, `revealed_window_days = 90`,
  both `int` in `[scheduler_placement]`. Purity holds: the clock is read in
  the app layer, the scheduler sees only the resulting cells.
- **Audit decision** (verified): `DataAccessPurpose`
  (`contracts/data_access_audit.py:26-34`) has no disposition-read purpose
  — dispositions are NOT audited, so placement observations (same class:
  per-user data about the user's own behavior) are NOT audited either. No
  spec change.
- **Data-control completeness**: `tools/user_data.py` (view / export /
  delete one user's data) MUST gain the placement-preference rows in all
  three surfaces — a per-user store invisible to export/delete would be a
  real data-control gap, and the bs-detector will flag it.
