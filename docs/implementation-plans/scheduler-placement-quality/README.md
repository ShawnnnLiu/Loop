# Scheduler Placement Quality — Deterministic Best-Fit Placement

Status: **planned, not started.** Runs after `ux-quality-pass` merges (see
Sequencing). Branch: `scheduler-placement-quality` from `main`.

Provenance: brainstorm session 2026-07-05, grounded in a code exploration of
the scheduler region and a signal inventory across the codebase. All file
references re-verified 2026-07-06 on `resume-intake-onboarding` HEAD
(67f24f5), which contains every pending stack (ux-quality-pass,
calendar-authoritative-moves, completion-drop-memory, deleted-event-memory)
and is therefore the closest proxy to the post-merge `main` this project
branches from. Each phase doc now ends with an **Implementation notes**
section carrying the verified reference map and the exact formulas/decisions
— read it before writing code; where it disagrees with older prose in the
same doc, the notes win.

## The problem (root cause, one line of policy)

`_try_place` (`backend/src/agentic_calendar/scheduler/greedy.py:240`) walks
free windows sorted ascending by start, only ever considers
`candidate_start = window.start`, and returns on the first window that passes
the hard checks. There is no scoring, no comparison between feasible
placements, no sub-window scanning, and no day balancing — so every schedule
degenerates into "pack everything back-to-back at the first legal instant."
The task *ordering* (`ordering.py:67`, topo + module priority + cognitive
load) is fine; the *placement* policy is the whole problem.

Axiom 05 already anticipates swapping the placement core behind the stable
`schedule(SchedulerInput) -> SchedulerOutput` interface (paraphrasing
`docs/axioms/05-scheduler-policy.md:217` "Google OR-Tools CP-SAT is the
leading candidate" and `:224` "The CP-SAT migration is a backend-only
change. The Scheduler interface … does not change"). Note the real
signature carries one extra keyword-only param:
`schedule(inp, *, module_priority=None)` (`greedy.py:51`, re-exported from
`scheduler/__init__.py:11`). This project does that swap in measured,
deterministic stages.

## Signals that already exist and are unused by placement

Verified 2026-07-05:

- **Captured-then-dropped soft preferences** —
  `UserProfile.Preferences.{prefer_evening_sessions, prefer_weekend_long_blocks,
  avoid_back_to_back_deep_work}` (`contracts/user_profile.py:79-86`; the
  *class* docstring says "Soft preferences used as tie-breakers when multiple
  schedules are valid" — the fields themselves are bare `bool = False`, no
  per-field descriptions), but `policy_from_user_profile`
  (`scheduler/policy.py:46`) never copies them into `SchedulingPolicy`.
  Likewise `preferred_session_length_min` (top-level `UserProfile` field,
  `user_profile.py:120`, required `int`, `gt=0, le=720`; NOT under
  `Preferences`) never reaches the policy (only `max_session_length_min`,
  `user_profile.py:121`, does).
- **Time-of-day evidence, already bucketed** — `PooledDurationModel` buckets
  by `TimeOfDayBand × DayOfWeek × cognitive_load × category`;
  `PerUserRefinement.lookup(category, band)` exists. Serving *marginalizes
  the band away* (`duration_estimation/pooled.py:338`) precisely because the
  greedy loop fixes duration before choosing a slot. A placer that chooses
  slots can query by candidate band instead.
- **Revealed preferences, applied but never learned** — drag-to-adjust
  targets (`scheduler/adjustment.py:107` `validate_placements`, applied by
  `CycleService.adjust` at `app/cycle.py:1200`) and reconciliation adoptions
  (`app/cycle.py:1522-1528`, `mapping_store.record_external_edit` →
  `CalendarEventMapping.with_external_edit`,
  `contracts/calendar_event_mapping.py:134`) record where the user actually
  moves work, but nothing aggregates them.
- **Load signals** — `AccountabilityState.completion_rate_14d` /
  `behind_schedule_percent` (not consumed in this project's early phases;
  noted for later calibration).

## Design constraints (non-negotiable, from axiom 05 + contracts)

Every phase must preserve:

- **Purity + determinism.** `schedule` stays a pure function of
  `SchedulerInput`; no store reads, no clock, no randomness. Any new signal
  arrives *through the input contract* (extend `SchedulingPolicy` or add an
  input field, spec/axiom-first). Integer cost arithmetic; total-order
  tie-breaks.
- **Typed failure surface.** Producer set today: `DEPENDENCY_BLOCKED`
  (inline, `greedy.py:139`), `TASK_TOO_LONG_UNSPLITTABLE` (inline,
  `greedy.py:152`), `NO_VALID_CONTIGUOUS_BLOCK` and
  `DEEP_WORK_REQUIRED_UNAVAILABLE` (via `_failure_for`, `greedy.py:314`),
  `INSUFFICIENT_WEEKLY_CAPACITY` (via `_promote_capacity_failures`,
  `greedy.py:198`). Debug payload builders in `scheduler/debug.py` keep
  their required fields. The capacity-vs-fragmentation promotion is
  load-bearing: golden scenarios 1 and 12 pin the promote side
  (`backend/tests/golden/test_scheduler_scenarios.py:78,241` assert
  `INSUFFICIENT_WEEKLY_CAPACITY`) and the combined scenario-6/15 test pins
  the don't-promote side (`test_scenario_6_and_15_capacity_but_no_contiguous_block`,
  `:208`, asserts `NO_VALID_CONTIGUOUS_BLOCK` + `SPLIT_TASK`). There is no
  standalone "scenario 15" test; scenario source of truth is
  `docs/golden-test-cases.md`.
- **Never raise; draft-only.** `schedule` converts internal errors to FAILED
  output (`greedy.py:62-65`); `CalendarEventStatus.DRAFT_ONLY` remains the
  only status; no calendar writes.
- **Contract stability.** `SchedulerOutput` invariants hold (unique
  `scheduled_tasks` task_ids — until phase 04 amends the spec; non-empty
  `repair_options` on non-success). Public API stays
  `schedule(SchedulerInput) -> SchedulerOutput`.
- **Local-time semantics.** `app/cycle.py:924` anchors the horizon in the
  user's tz (`env.clock.now().astimezone(onboarding.tzinfo())`) so
  `no_events_before/after` and deep-work windows read as local wall-clock;
  candidate enumeration must keep this. Corollary the scoring terms may rely
  on: every datetime inside the scheduler is already user-local wall-clock —
  the scheduler itself stays tz-agnostic and just reads `.hour`/`.date()`.
- **Soft preferences never eliminate feasibility.** The 2-iteration
  Planner↔Scheduler cap (`MAX_SCHEDULER_PLANNER_ITERATIONS = 2`,
  `app/cycle.py:177`, enforced at `:950`) means a feasible-but-plainer
  schedule beats an aggressive one that fails. Preference terms only reorder
  feasible candidates.
- **No per-user ML** (ADR-0004): everything here is counting, medians, and
  weighted sums — auditable deterministic aggregation, consistent with
  ADR-0007's pooled-personalization pattern.

Tests that lock the *current* first-fit behavior down to exact instants
(e.g. `test_deep_work_task_placed_in_deep_window` asserts
`2026-05-04T18:00`) are the old policy encoded as tests — they change
*deliberately, with the axiom update*, in the increment that changes
placement. Golden assertions on reason_codes, debug payload fields, and
Supervisor routing never change.

## Files / increments (one commit per lettered increment)

| File | Increments |
| --- | --- |
| `01-scored-placement.md` | P-A axiom-05 amendment + policy plumbing · P-B candidate machinery, provably output-identical · P-C scoring terms v1 (behavior change) · P-D tuning.toml weights + quality report CLI |
| `02-day-balancing-and-polish.md` | P-E regret-based insertion order · P-F day-quota balancing · P-G bounded polish pass |
| `03-evidence-driven-placement.md` | P-H `PlacementEvidence` input (pooled time-of-day buckets → score term) · P-I revealed-preference counts (drag + reconciliation adoptions) |
| `04-task-splitting.md` | P-J spec-first contract change (parts, hash canonicalization bump) · P-K splitting algorithm + downstream surfaces |
| `05-cpsat-solver.md` | P-L ortools gate + engine flag scaffolding · P-M CP-SAT model, shadow-mode parity, cutover |

Phases 01–02 are pure quality wins inside the scheduler region and should
ship first. 03 is the personalization payoff. 04 and 05 are independent of
each other; both are contract-heavy and gated — do them only if the earlier
phases leave measurable gaps.

## Sequencing

- **After `ux-quality-pass` merges.** No file overlap with the
  `loop-grounding-rag` or `loop-recruiter-readiness` tracks except light
  `app/cycle.py` touches in P-H/P-I — rebase-friendly.
- Branch from `main`; usual conventions: one commit per increment,
  spec/axiom-first for every contract or policy-shape change
  (`docs/axioms/05-scheduler-policy.md` and `docs/specs/` before Pydantic
  before fixtures before `make schemas`), gates green per commit
  (`uv run make check` from `backend/`), `graphify update .` after code
  changes.
- Each phase is a clean-context handoff: start a fresh session with the
  kickoff prompt below, pointed at the phase doc.

## Ask-user gates (standing, per the operating contract)

- **P-L only:** adding `ortools` is a new dependency — ask first, with the
  pinned version. Nothing else in this project needs a new dependency or a
  networked command.
- Everything else is local deterministic work: read/edit/test without
  additional confirmation.

## Definition of done (whole project)

1. On a fixture corpus of realistic plans, the schedule-quality report
   (P-D) shows placements spread across days, deep tasks in deep windows,
   breathing gaps between sessions, and evening/weekend preferences honored
   — versus the baseline's earliest-instant pile-up. Before/after numbers,
   not vibes.
2. All golden scenarios still pass with unchanged reason_codes, debug
   fields, and Supervisor routing; determinism property tests (same input →
   byte-identical output, twice) pass at every phase.
3. Every weight and threshold introduced is journaled as a heuristic prior
   in `backend/tuning.toml` with the axiom-07 disclosure.

If placement quality improves but a golden reason_code moved, it isn't done
— it's a regression with better aesthetics.

## Kickoff prompt (copy-paste into a fresh session, per phase)

```
Read docs/implementation-plans/scheduler-placement-quality/README.md, then
docs/implementation-plans/scheduler-placement-quality/<PHASE-DOC>.md, then
docs/axioms/05-scheduler-policy.md and the scheduler region
(backend/src/agentic_calendar/scheduler/). Implement the increments of
<PHASE-DOC> in order, one commit per increment, following the repo's
CLAUDE.md operating contract (spec/axiom-first, gates green per commit,
ask before dependencies). Start by restating the increments and any open
decisions the doc flags, then begin P-<X>.
```
