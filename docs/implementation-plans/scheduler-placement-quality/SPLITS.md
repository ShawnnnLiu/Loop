# Context-Window Splits — Scheduler Placement Quality

Sizing companion to `README.md`. Each split below is **one fresh Claude Code
session ending in exactly one commit**, budgeted at roughly **300k total
session tokens** — reads, edits, test iterations, and gate runs included.

**This file supersedes the README's "one commit per lettered increment"
line** (user decision 2026-07-15): where a split bundles two increments,
they land as a single commit. The bundles were chosen so every commit is
still one coherent, reviewable change — in particular, P-C (the placement
behavior change) never shares a commit with another behavior change, and
the P-B "provably output-identical" equivalence proof lands *before* the
commit that breaks it.

Run splits 1–6 in order (the core spine). Splits 7–10 are the gated phases
(04 task splitting, 05 CP-SAT) — run them only if the quality report after
the spine shows the gaps those phases exist to close (README §gating).

## Budget model (heuristic priors — recalibrate after Split 1)

- **Fixed per-session overhead: ~55k.** CLAUDE.md + AGENTS.md + README +
  this file + the phase doc + axiom 05 + the scheduler region and its
  tests, before the first edit. Every fresh session pays this, which is
  why small increments are bundled rather than run one-per-session.
- **The dominant variable cost in this project is placement-instant test
  churn.** P-C, P-E, and P-F each move expected placement instants in
  `test_greedy.py` and the golden scenarios — every such increment budgets
  for iterative `make check` runs, not just the edits.
- Contract-loop increments (P-H, P-I, P-J) cost like the grounding-RAG
  spec loops: spec → Pydantic → fixtures → `make schemas` → tests.
- Estimates are ranges; the high end is the planning number. If Split 1
  lands far off its estimate, rescale the rest before starting Split 2.
- Deliberate slack: most splits target ~250k, not 300k. Overshoot is the
  real failure mode (a session dying mid-commit), and this suite's test
  churn is the least predictable cost in the repo.

## Overflow rule

Each split ends in one commit, but every split names an **internal
fallback boundary** — a point where the work already done is green and
honest on its own. If a session approaches budget mid-split, commit at
the fallback boundary (stating plainly in the commit message what is and
is not included) and start a fresh session with the same split's kickoff
prompt plus "the P-<x> portion is already committed; resume at P-<y>".

## The splits

| Split | Increments | One-commit theme | Est. total | Gate |
| --- | --- | --- | --- | --- |
| 1 | P-A + P-B | Axiom amendment, policy plumbing, candidate machinery — zero behavior change, equivalence proven | ~205k (55 + 60 + 90) | — |
| 2 | P-C + P-D | Scored placement live, weights in tuning.toml, quality-report CLI + fixture corpus | ~295k (55 + 140 + 100) | — |
| 3 | P-E + P-F | Regret insertion order + soft day quotas (one golden-churn pass for both) | ~245k (55 + 120 + 70) | — |
| 4 | P-G | Bounded polish pass + phase-02 acceptance evidence committed to doc notes | ~205k (55 + 130 + 20) | — |
| 5 | P-H | `PlacementEvidence` contract + evidence term (dormant-in-prod per binding scope note) | ~220k (55 + 165) | — |
| 6 | P-I | Revealed-preference store, producers, aggregation, data-control surfaces | ~255k (55 + 200) | — |
| 7 | P-J | Split contracts + `hash_canonicalization_version` v2, no behavior change | ~245k (55 + 190) | gated: 04 |
| 8 | P-K | Splitting algorithm + all downstream surfaces incl. SPA | ~300k (60 + 240) | gated: 04 |
| 9 | P-L | ortools ask + engine flag scaffolding | ~145k (55 + 90) | gated: 05 |
| 10 | P-M | CP-SAT model, shadow-mode parity, cutover | ~295k (55 + 240) | gated: 05 |

Splits 2, 8, and 10 are the tight ones — their fallback boundaries matter.
Split 9 is short by design: it opens with an ask-first dependency gate and
may stall there; burning a fresh 300k window on it costs nothing if the
ask is declined.

## Conventions that apply to every split

- **Branch:** `scheduler-placement-quality`, created in Split 1 from
  `main` after the currently-open PR stack merges (README §Sequencing).
  The plan folder itself rode the résumé-intake PR (commit `506f645`) —
  if `docs/implementation-plans/scheduler-placement-quality/` is missing
  from `main`, stop and ask. Splits 2–10 continue on the branch; if the
  expected prior-split commit is missing from `git log`, stop and ask.
- **One commit per split**, spec/axiom-first ordering inside it. The
  kickoff prompts below authorize the end-of-session commit; never push.
- **Gates green before the commit:** `uv run make check` from `backend/`;
  Split 8 additionally runs the frontend gates (`npm run typecheck &&
  npm run lint && npm run test && npm run build` from `frontend/`).
- `graphify update .` after code changes.
- **Reference drift:** every phase doc's "Implementation notes" section
  was verified 2026-07-06 against `67f24f5`. If a cited line number no
  longer matches, trust the named symbol over the line number, and note
  the drift in the session summary.
- **Ask-user gates:** the only one in the whole project is the `ortools`
  dependency in Split 9. Everything else is local deterministic work —
  no networked commands anywhere.
- Each phase doc's Implementation notes **win over older prose** in the
  same doc — read them before writing code; decisions there are made and
  not to be relitigated.

## Split 1 — P-A + P-B · Foundation (zero behavior change) — ~205k

**Primary doc:** `01-scored-placement.md` (P-A, P-B + Implementation notes).

Scope highlights:
- Amend `docs/axioms/05-scheduler-policy.md` with the "Scored placement"
  section (candidate enumeration, integer cost, term list, tie-break,
  weights-as-priors rule, soft-terms-never-eliminate-feasibility rule).
- Extend `SchedulingPolicy` + `policy_from_user_profile` with the three
  dropped preference bools and `preferred_session_length_min`; update
  `test_policy.py`. No `make schemas` (region-local models).
- New `scheduler/scoring.py`: `PlacementCandidate`,
  `enumerate_candidates` (window starts only), `select_placement`
  (cost ≡ 0); rewire `_try_place` through it, keeping the five hard
  checks and `_live_windows` flow intact.
- Equivalence proof: every greedy/golden scenario through old and new
  paths, byte-identical `SchedulerOutput.model_dump()`;
  `_first_fit_reference` lives in the test module only.
- Commit this `SPLITS.md` here too if it is not already in the tree.

Fallback boundary: after P-A (policy plumbing is green and honest alone).

Acceptance: `make check` green with **zero** test-expectation edits.

Kickoff prompt:

```
Read docs/implementation-plans/scheduler-placement-quality/SPLITS.md
(Split 1), then README.md and 01-scored-placement.md in that folder
(P-A/P-B sections plus the Implementation notes, which win over older
prose). Then read docs/axioms/05-scheduler-policy.md, the scheduler
region (backend/src/agentic_calendar/scheduler/ — especially greedy.py,
policy.py, windows.py, ordering.py), contracts/user_profile.py, and
backend/tests/scheduler/ plus the golden scenarios. Create branch
scheduler-placement-quality from main (stop and ask if the plan folder is
missing from main). Implement P-A and P-B only, as ONE commit, per
CLAUDE.md (axiom-first; uv run make check green from backend/ with zero
test-expectation edits — that is the P-B proof). You may commit at the
end; do not push. Do not start P-C.
```

## Split 2 — P-C + P-D · Scored placement ships — ~295k (tight)

**Primary doc:** `01-scored-placement.md` (P-C, P-D + Implementation notes —
the exact term formulas, `PlacementScoringConfig` defaults, and the
tuning/CLI plumbing decisions are all pinned there).

Scope highlights:
- Enable the 15-min intra-window grid + the six integer cost terms
  (exact formulas in the doc's notes; sign convention
  `cost = Σ w·penalty − Σ w·bonus`, argmin by `(cost, start)`).
- Reuse `derive_time_of_day_band` — never a second band definition.
- **Deliberately update** placement-instant tests and golden expected
  instants; reason_code / debug / routing assertions must not change.
  Per-term unit tests (two-window fixtures) + determinism test.
- `PlacementScoringConfig` + defaults; new keyword-only `scoring` param on
  `schedule()`; `[scheduler_placement]` in `tuning.toml` via
  `TUNABLE_SECTIONS` + `EffectiveTuning`; pass at the `app/cycle.py` call
  site.
- `score_schedule` (schedule-level totals, NOT marginal sums) +
  `tools/show_placement_quality.py` + fixture corpus
  `backend/tests/fixtures/placement_quality/*.json`; record the first
  before/after numbers in the phase doc's notes.

Fallback boundary: after P-C's work is green (scoring live with in-code
defaults; tuning wiring + CLI + corpus resume as P-D).

Acceptance: 5-tasks × 3-free-days fixture no longer stacks day 1;
overriding a weight in tuning.toml changes placement and journals a
threshold-change entry.

Kickoff prompt:

```
Read docs/implementation-plans/scheduler-placement-quality/SPLITS.md
(Split 2), then README.md and 01-scored-placement.md in that folder (P-C
and P-D, plus the Implementation notes — the term formulas and plumbing
decisions there are binding). Verify the Split 1 commit exists on branch
scheduler-placement-quality — if not, stop and ask. Then read
scheduler/scoring.py as committed by Split 1, greedy.py, app/tuning.py,
backend/tuning.toml, tools/show_thresholds.py (CLI convention), and the
placement-instant tests in backend/tests/scheduler/test_greedy.py plus
the golden scenarios. Implement P-C and P-D as ONE commit per CLAUDE.md:
update placement-instant expectations deliberately, never reason_code/
debug/routing assertions; uv run make check green from backend/. If
context runs hot after P-C's work is green, commit P-C alone (say so in
the message) and tell me to relaunch for P-D. You may commit at the end;
do not push. Do not start P-E.
```

## Split 3 — P-E + P-F · Ordering + day balancing — ~245k

**Primary doc:** `02-day-balancing-and-polish.md` (P-E, P-F + Implementation
notes — the selection rule, output-ordering rule, and quota/earliness
specifics are pinned there).

Scope highlights:
- Regret-based insertion within the ready set: selection key
  `(single_candidate_flag, regret)` max, ties by ascending `_sort_key`;
  fail-fast rule for zero-candidate ready tasks; **output ordering stays
  `topological_order` position** (byte-determinism, minimal golden diffs);
  `DEPENDENCY_BLOCKED` semantics unchanged; small axiom-05 edit.
- Per-day soft quotas feeding the `daily_balance` term (precomputed quota
  map) + the tiny `earliness` term (`w_earliness = 1`); crunch fixture
  proves `INSUFFICIENT_WEEKLY_CAPACITY` promotion fires on exactly the
  same inputs as before (golden 1/12 and 6_and_15 untouched).
- Bundling rationale: both increments move placement instants — one
  golden-churn pass instead of two.

Fallback boundary: after P-E is green (quotas + earliness resume as P-F).

Acceptance: stranded-deep-task fixture schedules fully under regret order;
6 equal tasks × 3 equal free days → 2/2/2 not 6/0/0; crunch failures
identical to baseline.

Kickoff prompt:

```
Read docs/implementation-plans/scheduler-placement-quality/SPLITS.md
(Split 3), then README.md and 02-day-balancing-and-polish.md in that
folder (P-E and P-F, plus the Implementation notes — the P-E selection
rule and output-ordering rule are binding). Verify Splits 1–2 commits
exist on branch scheduler-placement-quality — if not, stop and ask. Then
read scheduler/greedy.py (the placement loop and completed_or_placed
gate), scheduler/ordering.py, scheduler/scoring.py, and the golden
scenarios. Implement P-E and P-F as ONE commit per CLAUDE.md: golden
reason_code/debug/routing assertions must not change; placement instants
update deliberately; uv run make check green from backend/. If context
runs hot after P-E is green, commit P-E alone and tell me to relaunch
for P-F. You may commit at the end; do not push. Do not start P-G.
```

## Split 4 — P-G · Bounded polish + phase-02 evidence — ~205k

**Primary doc:** `02-day-balancing-and-polish.md` (P-G + Implementation
notes — objective, relocation feasibility, and scan order are pinned).

Scope highlights:
- At most 2 sweeps between the main loop and
  `_promote_capacity_failures`; objective = **schedule-level totals from
  `score_schedule`**, never marginal sums; strict integer improvement.
- Relocation feasibility: the five hard checks with the block's own
  occupancy removed; dependency order **both directions**; deep-gap
  checked against **both** neighbors.
- Moves only — never unschedules, never touches `unscheduled_tasks`;
  assert reason codes/debug untouched anyway. Idempotence at the fixed
  point; determinism.
- Close phase 02: run the P-D quality report on the corpus and commit the
  before/after numbers into the phase doc's notes (the README
  definition-of-done evidence). This split is deliberately under target —
  P-G is the most delicate algorithm in the spine.

Fallback boundary: none needed at this size; if somehow hot, the report
numbers can trail into Split 5's session.

Kickoff prompt:

```
Read docs/implementation-plans/scheduler-placement-quality/SPLITS.md
(Split 4), then README.md and 02-day-balancing-and-polish.md in that
folder (P-G plus the Implementation notes — objective and feasibility
rules there are binding). Verify Splits 1–3 commits exist on branch
scheduler-placement-quality — if not, stop and ask. Then read
scheduler/greedy.py, scheduler/scoring.py (score_schedule), and the
fixture corpus under backend/tests/fixtures/placement_quality/.
Implement P-G as ONE commit per CLAUDE.md (moves only; reason codes and
debug payloads untouchable by construction — assert it; determinism +
idempotence tests). Then run tools/show_placement_quality.py on the
corpus and record before/after numbers in the phase doc's notes, in the
same commit. Gate: uv run make check green from backend/. You may commit
at the end; do not push. Do not start P-H.
```

## Split 5 — P-H · Evidence input contract + term — ~220k

**Primary doc:** `03-evidence-driven-placement.md` (P-H + Implementation
notes — **read the production-reality note first; its scope decision is
binding**: composition takes pooled artifact / refinement as optional
params, both `None` in the solo MVP; do NOT wire the power-user gate;
nothing may describe pooled-evidence placement as live).

Scope highlights:
- Spec first: `docs/specs/placement-evidence.schema.md` →
  `contracts/placement_evidence.py` (EvidenceCell shape decisions in the
  notes: `multiplier: float | None` bounded [0.5, 2.0], conditional
  validator by source, uniqueness on `(category, band, source)`) → valid +
  invalid fixtures → register in `tools/export_schemas.py` →
  `make schemas`.
- `SchedulerInput.placement_evidence` defaulting to empty (no schema regen
  for SchedulerInput itself); `evidence_affinity` integer term per the
  notes' exact form (`mult_pct` conversion, PER_USER_REFINED wins over
  POOLED); `w_evidence_affinity = 1`.
- Composition helper in `app/cycle.py` with consent-gate mechanics
  mirrored from the pooled-serving check; serving-floor discipline.
- Tests: consent-off ⇒ byte-identical to Split 4 baseline; deterministic
  band shift on a two-band fixture; contract fixtures round-trip.

Kickoff prompt:

```
Read docs/implementation-plans/scheduler-placement-quality/SPLITS.md
(Split 5), then README.md and 03-evidence-driven-placement.md in that
folder (P-H plus Implementation notes — the production-reality note is a
binding scope decision). Verify Splits 1–4 commits exist on branch
scheduler-placement-quality — if not, stop and ask. Then read
contracts/pooled_duration_model.py (TimeOfDayBand),
contracts/common_types.py (TaskCategory), app/cycle.py (the
SchedulerInput build and the consent-gated pooled check), an existing
spec + contract + fixture trio for house style, and scheduler/scoring.py.
Implement P-H as ONE commit per CLAUDE.md order: spec → contract →
fixtures → make schemas → composition → term → tests. Gate: uv run make
check green from backend/. You may commit at the end; do not push. Do
not start P-I.
```

## Split 6 — P-I · Revealed preferences — ~255k

**Primary doc:** `03-evidence-driven-placement.md` (P-I + Implementation
notes — store location, producer anchor points, aggregation defaults, and
the audit decision are all pinned).

Scope highlights:
- Spec + contract for `PlacementPreferenceObservation` (REVEALED enum
  member added to the P-H contract in the same commit; per-observation
  rows, not pre-aggregated).
- Store: `app/placement_preference.py` (threshold_log twin-in-one-module
  precedent); `AppEnvironment` registration in all four spots;
  parametrized shared suite.
- Producers: drag-adjust (in `CycleService.adjust`, after conflicts empty
  and draft saved; category from the in-scope plan index) and
  reconciliation adoption (inside the `if adopt:` block; NEVER for
  `event_deleted` or rejected reconciliations). No raw event titles.
- Aggregation → REVEALED cells (`count ≥ 3`, 90-day window, both in
  `[scheduler_placement]`); flat `w_revealed_affinity = 2` bonus; clock
  read in the app layer only.
- **Data-control completeness:** `tools/user_data.py` view/export/delete
  must all gain the new rows — the bs-detector will flag the gap.
- End-to-end test: three evening drags of PRACTICE tasks pull the next
  replan's PRACTICE placements into the evening band.

Fallback boundary: after store + producers are green (aggregation → cells
+ user_data surfaces resume).

Kickoff prompt:

```
Read docs/implementation-plans/scheduler-placement-quality/SPLITS.md
(Split 6), then README.md and 03-evidence-driven-placement.md in that
folder (P-I plus Implementation notes — store/producer/aggregation
decisions there are binding). Verify Splits 1–5 commits exist on branch
scheduler-placement-quality — if not, stop and ask. Then read
app/threshold_log.py (the store precedent) and its test module,
app/environment.py (all four registration spots), app/cycle.py (adjust,
reconcile, and the SchedulerInput build), scheduler/adjustment.py, and
tools/user_data.py. Implement P-I as ONE commit per CLAUDE.md
(spec-first; producers fire only on adopted/applied moves; user_data
gains view/export/delete coverage). Gate: uv run make check green from
backend/. You may commit at the end; do not push. This closes the core
spine — end by running the quality report and restating the README
definition-of-done status honestly.
```

## Split 7 — P-J · Split contracts (GATED on 04's evidence) — ~245k

Run only if the post-spine quality report still shows long tasks failing
on fragmented calendars (README + doc 04 gating).

**Primary doc:** `04-task-splitting.md` (P-J + Implementation notes — the
hash-version anchor points make the "most dangerous edit" mechanical).

Scope highlights:
- Specs in order: scheduler-output (part fields + new uniqueness
  invariants), draft-schedule (**bump `hash_canonicalization_version` to
  v2** — register `_canonicalize_v2` alongside v1, flip the producer
  constant, grep for the second `"v1"` literal in
  `tools/_calendar_cli_common.py`), calendar-event-mapping (per-part key).
- Axiom 05 splitting policy + axiom 06 line; contracts, valid + invalid
  fixtures (overlapping parts, index-without-count, minutes not summing,
  mixed split/unsplit), `make schemas`.
- Both-versions-side-by-side hash-recheck tests through the real
  `CalendarWriteManager`.
- No algorithm change — the scheduler still never emits parts.

Kickoff prompt:

```
Read docs/implementation-plans/scheduler-placement-quality/SPLITS.md
(Split 7), then README.md and 04-task-splitting.md in that folder (P-J
plus Implementation notes). Confirm with me that the 04 gate is met (the
quality report shows long splittable tasks still failing) before writing
anything. Verify the spine commits exist on branch
scheduler-placement-quality. Then read docs/specs/
scheduler-output.schema.md, draft-schedule.schema.md,
calendar-event-mapping.schema.md, contracts/hashing.py,
calendar_writer/manager.py (_validate_approval), and docs/axioms/06.
Implement P-J only as ONE commit, spec-first, per CLAUDE.md — contracts
ready, zero behavior change, hash-recheck tests for v1 and v2 side by
side. Gate: uv run make check green from backend/. You may commit at the
end; do not push. Do not start P-K.
```

## Split 8 — P-K · Splitting behavior + surfaces (GATED) — ~300k (tightest)

**Primary doc:** `04-task-splitting.md` (P-K + Implementation notes —
including the golden-scenario honesty flag: `6_and_15` is the ONE golden
whose reason_code assertion changes by design; preserve the promotion
boundary with a non-splittable replacement variant and amend
`docs/golden-test-cases.md` in the same commit).

Scope highlights:
- When/how to split per the axiom policy (contiguous wins whenever
  feasible; all-or-nothing per task; `TASK_TOO_LONG_SPLITTABLE` finally
  gets its producer + new debug builder).
- Downstream surfaces, one behavior per bullet, tests each: calendar
  write manager per part; adjustment (`part_index` + advisory
  out-of-order warning); completion stays task-level; telemetry sums
  parts; SPA linked blocks with composite key `${task_id}#${part_index}`;
  reconciliation per part.
- Gates: full `make check` AND the frontend suite.

Fallback boundary: backend surfaces complete (scheduler + writer +
adjustment + telemetry) with SPA + reconciliation tests resuming in a
fresh window — the fallback commit message must say the frontend surface
is pending.

Kickoff prompt:

```
Read docs/implementation-plans/scheduler-placement-quality/SPLITS.md
(Split 8), then README.md and 04-task-splitting.md in that folder (P-K
plus Implementation notes, including the golden-scenario honesty flag).
Verify the Split 7 commit exists on branch scheduler-placement-quality —
if not, stop and ask. Then read scheduler/greedy.py, scheduler/debug.py,
scheduler/adjustment.py, calendar_writer/ (manager + stores),
frontend/src/lib/weekplan.ts and components/WeekPlanView.tsx, and
backend/tests/golden/test_scheduler_scenarios.py plus
docs/golden-test-cases.md. Implement P-K as ONE commit per CLAUDE.md.
Gates: uv run make check from backend/ AND npm run typecheck && npm run
lint && npm run test && npm run build from frontend/. If context runs
hot once the backend surfaces are green, commit them honestly (message
states SPA pending) and tell me to relaunch. You may commit at the end;
do not push.
```

## Split 9 — P-L · Engine flag + ortools gate (GATED on 05) — ~145k

Short by design: it opens with the project's only ask-first dependency
gate and must leave scaffolding green before any model work.

**Primary doc:** `05-cpsat-solver.md` (P-L + Implementation notes).

Scope highlights:
- **Open with the ask**: propose `ortools` with a pinned version; write
  no code until the user decides. If declined, the split's deliverable is
  a recorded decision, nothing else.
- Lazy import (Anthropic-SDK discipline); env-var `SCHEDULER_ENGINE`
  read in `app/web/server.py` + relevant CLIs, passed as an explicit
  `build_environment` param — composition-root config, never policy
  state.
- `scheduler/cpsat.py` stub: typed error without the extra, translated to
  FAILED output by the never-raise wrapper, with a unit test for exactly
  that path; `.importlinter` confines ortools to the module.

Acceptance: default behavior byte-identical everywhere; `make boundaries`
green.

Kickoff prompt:

```
Read docs/implementation-plans/scheduler-placement-quality/SPLITS.md
(Split 9), then README.md and 05-cpsat-solver.md in that folder (P-L plus
Implementation notes). Confirm with me that the 05 gate is met (residual
quality gaps greedy+polish cannot close). Do NOT write code yet: propose
adding ortools with a pinned version and wait for my explicit yes — if I
decline, record the decision and stop. On yes, implement P-L only as ONE
commit per CLAUDE.md (lazy import, SCHEDULER_ENGINE env var in the web
entrypoint per the SHARED_DB_PATH precedent, cpsat.py stub with the
typed-error-to-FAILED test, .importlinter confinement). Gates: uv run
make check and make boundaries green from backend/. You may commit at
the end; do not push. Do not start P-M.
```

## Split 10 — P-M · CP-SAT model + parity + cutover (GATED) — ~295k (tight)

**Primary doc:** `05-cpsat-solver.md` (P-M + Implementation notes).

Scope highlights:
- Model: optional interval per task (per part if 04 landed), domains from
  `enumerate_free_windows`; NoOverlap, precedence, daily caps, deep
  windows, deep-gap; objective imports the `scheduler/scoring.py` term
  implementations and weights — never re-implements them.
- Determinism: single worker, fixed seed, **deterministic budget, never
  wall-clock**; solved-twice byte-identical test.
- Failure surface: deterministic prechecks own every reason_code; solver
  only places precheck-survivors; **fallback rule** — infeasible /
  budget-exhausted / import error ⇒ return greedy's result for the same
  input.
- Shadow parity: harness + `tools/compare_placement_engines.py` across
  golden scenarios + the fixture corpus (CP-SAT ≥ greedy on scheduled
  count, ≤ on cost, identical failure reason_codes, both byte-stable);
  commit the numbers to the phase doc's notes; flip the env-var default
  only after.

Fallback boundary: model + prechecks + fallback green with the default
still `greedy` (parity harness + cutover resume in a fresh window).

Kickoff prompt:

```
Read docs/implementation-plans/scheduler-placement-quality/SPLITS.md
(Split 10), then README.md and 05-cpsat-solver.md in that folder (P-M
plus Implementation notes). Verify the Split 9 commit exists on branch
scheduler-placement-quality and that the ortools extra is installed — if
not, stop and ask. Then read scheduler/cpsat.py, scheduler/scoring.py,
scheduler/windows.py, greedy.py (prechecks and _promote_capacity_
failures), and the golden scenarios + fixture corpus. Implement P-M as
ONE commit per CLAUDE.md: prechecks own the failure taxonomy, greedy is
the permanent fallback, determinism is budget-based never wall-clock,
parity numbers land in the phase doc's notes before the default flips.
Gates: uv run make check + make boundaries green from backend/, with and
without the ortools extra. If context runs hot once model + prechecks +
fallback are green under the greedy default, commit that honestly and
tell me to relaunch for the parity harness and cutover. You may commit
at the end; do not push.
```
