# 05 · CP-SAT Placement Engine (Gated Endgame)

Axiom 05 reserves this swap: "OR-Tools CP-SAT may replace the greedy core
without changing the Scheduler interface." Do it only after 01–02 (and
ideally 03) are live, because CP-SAT with a bad objective just produces
bad schedules faster — the scored terms ARE the objective, and they must
be proven first. Gate the phase on the quality report showing residual
gaps greedy+polish can't close (e.g. tight multi-constraint weeks where
regret ordering still strands tasks).

Increments: **P-L → P-M**, one commit each.

## P-L · Dependency gate + engine flag scaffolding

1. **Ask the user before adding `ortools`** (operating contract). Propose a
   pinned version in the ask; it lands in `backend/pyproject.toml` extras
   only after explicit yes. Lazy-import inside the engine module (same
   discipline as the Anthropic SDK's lazy import in `llm_nodes/`), so
   environments without the extra still run greedy.
2. Engine selection is **composition-root config, not policy state**:
   `schedule(inp, *, engine: PlacementEngine = GREEDY)` with the enum in
   the scheduler region. Wiring correction (verified): `app/environment.py`
   does NOT read env vars — `build_environment` takes explicit params
   (`app/environment.py:273-281`). Follow the existing pattern: read
   `SCHEDULER_ENGINE=greedy|cpsat` (default greedy) in the web entrypoint
   (`app/web/server.py` — precedent `SHARED_DB_PATH` at `:50`,
   `TUNING_PATH` at `:57`) and in operator CLIs that need it (precedent:
   `tools/run_cycle.py:141` reads `ANTHROPIC_API_KEY`), then pass the
   parsed enum as an explicit `build_environment` parameter stored on
   `AppEnvironment`. It is not a `SchedulingPolicy` field — users don't
   choose solvers, operators do.
3. New module `scheduler/cpsat.py` behind the flag; in P-L it raises the
   region's typed error if selected without the extra installed, and
   `schedule` translates that to a FAILED output (never-raise contract,
   `greedy.py:62-65`) — plus a unit test for exactly that path.
4. `.importlinter`: `ortools` usage confined to `scheduler/cpsat.py`.

Acceptance: default behavior byte-identical everywhere; flag plumbed;
`make boundaries` green.

## P-M · Model, shadow-mode parity, cutover

**Model** (all integer, minutes since horizon start):

- One optional interval variable per task (per part, if 04 landed), domain
  restricted to enumerated free windows (reuse `enumerate_free_windows` —
  the window/day/tz semantics live in one place, `windows.py:44`).
- `NoOverlap` across all intervals; precedence `end_dep ≤ start_task` for
  dependencies; per-day capacity as sum-of-durations-per-day ≤
  `max_daily_study_min`; deep tasks restricted to deep windows when
  `respect_deep_work_windows`; deep-gap constraint mirroring
  `greedy.py:262-267`.
- Objective, lexicographic via scaling: maximize count (or
  priority-weighted count) of scheduled tasks first, then minimize the
  **same integer cost terms** from `scheduler/scoring.py` — one source of
  truth for what "good" means; the solver imports the term functions'
  tables, never re-implements them.

**Determinism** (this is the make-or-break constraint; write the findings
into axiom 05):

- `num_search_workers = 1`, fixed `random_seed`, fixed parameter set.
- **Never a wall-clock limit** — wall-clock cutoffs make results
  machine-dependent. Budget with a deterministic limit
  (`max_deterministic_time` / conflict-count style), chosen so fixture
  plans solve to proven optimality; record the budget in
  `[scheduler_placement]`.
- Determinism test: same input solved twice (and under `-p no:randomly` CI
  conditions) ⇒ byte-identical `SchedulerOutput`.

**Typed failure surface** — the hard part, solved by *not* asking the
solver to explain itself:

- Run the existing deterministic prechecks first: per-task
  window-fit / deep-window-existence / dependency gates and the capacity
  math, producing `DEPENDENCY_BLOCKED`, `TASK_TOO_LONG_UNSPLITTABLE`,
  `DEEP_WORK_REQUIRED_UNAVAILABLE`, and the
  capacity-vs-fragmentation distinction exactly as today
  (`_promote_capacity_failures`, `greedy.py:198`).
- The solver then only decides placement among precheck-survivors; a
  survivor the solver leaves unplaced gets `NO_VALID_CONTIGUOUS_BLOCK`
  with the standard debug builder (candidate windows checked = the
  domain it was given).
- **Fallback rule**: solver infeasible, budget-exhausted-without-solution,
  or import error ⇒ return the greedy engine's result for the same input.
  CP-SAT can only ever match-or-beat greedy in production; never a new
  failure mode. Log the fallback through the normal telemetry surface.

**Shadow mode before cutover**: a test-only harness (plus an operator CLI
in `tools/`) runs both engines across the golden scenarios and the fixture
corpus, asserting: CP-SAT schedules ≥ as many tasks, total cost ≤ greedy's,
reason_codes on failures identical, and both engines byte-stable. Flip the
env-var default only after those numbers are committed to this doc's phase
notes; greedy remains one env var away permanently.

## Acceptance criteria

- All golden scenarios pass under both engines with identical
  reason_codes, debug fields, and Supervisor routing.
- Parity harness shows CP-SAT ≥ greedy on scheduled count and ≤ on cost
  for every fixture; at least one fixture demonstrates a strict win
  (constructed: interleaved constraints where greedy+polish strands a
  task and the solver places it).
- Determinism tests green; `make check` + `make boundaries` green; the
  ortools extra absent ⇒ everything still passes with engine=greedy.

## Explicit non-goals

- No wall-clock-bounded "anytime" solving (determinism rule above).
- No solver-side re-derivation of reason codes or repair options —
  prechecks own the failure taxonomy.
- No user-facing engine choice; no per-user engine state.
- No removal of the greedy engine — it is the permanent fallback and the
  parity baseline.

## Implementation notes (verified 2026-07-06)

- Reference sanity: `greedy.py:62-65` (never-raise wrapper — it catches
  `SchedulerError` and returns a typed FAILED output, per the 2026-06-09
  audit decision), `greedy.py:198` (`_promote_capacity_failures`),
  `greedy.py:262-267` (deep-gap), `windows.py:44`
  (`enumerate_free_windows`) — all correct as cited.
- The lazy-import precedent to copy is the Anthropic SDK discipline in
  `llm_nodes/`; the boundaries gate is `make boundaries` (lint-imports plus
  a grep-style SDK-confinement test) — mirror whichever mechanism today
  confines the LLM SDK when confining `ortools` to `scheduler/cpsat.py`.
- Shadow-mode corpus = `backend/tests/golden/test_scheduler_scenarios.py`
  scenarios plus the P-D fixture corpus
  (`backend/tests/fixtures/placement_quality/`); the parity CLI follows the
  module-only `tools/` convention (`python -m
  agentic_calendar.tools.<name>`, `main(argv)`), e.g.
  `tools/compare_placement_engines.py`.
- The objective imports the P-C/P-F term implementations and the
  `PlacementScoringConfig` weights from `scheduler/scoring.py` — the
  solver never re-implements a term table, and the deterministic budget
  knob joins `[scheduler_placement]` (journaled like every other prior).
