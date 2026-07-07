# 02 · Day Balancing + Polish

Global schedule shaping that a task-at-a-time greedy cannot see, kept
strictly deterministic and bounded. Requires 01 (the scorer is the
vocabulary these increments speak).

Increments: **P-E → P-G**, one commit each. P-F and P-G are independent of
each other; P-E should land first because it changes *which* task is placed
next and the later increments' tests assume it.

## P-E · Regret-based insertion order

Problem it fixes: static topo order places flexible easy tasks early; by
the time an inflexible task (deep-only, long) is reached, its few viable
slots are gone. Classic fix from routing heuristics: place the task that
has the most to lose first.

- In the placement loop (`greedy.py:133`), instead of consuming
  `topological_order` linearly, maintain the **ready set** (dependencies
  completed-or-placed — same gate as today, `greedy.py:134-143`). Each
  round, for every ready task compute best and second-best candidate cost
  via `enumerate_candidates`/cost from 01; place the task with the largest
  regret `= second_best − best` (a task with a single feasible candidate
  has infinite regret — place it first). Tie-break by the existing
  `_sort_key` (`ordering.py:67`) so determinism and the
  priority/cognitive-load semantics survive.
- Topology stays a hard gate: a task whose dependency is unplaced is not
  in the ready set, so `DEPENDENCY_BLOCKED` semantics are unchanged. A
  ready task with zero candidates fails through `_failure_for` exactly as
  today, in the round it is reached.
- Complexity is O(rounds × ready × candidates) — fine at MVP plan sizes
  (tens of tasks); note the bound in the axiom amendment.
- `ordering.topological_order` remains for tie-break keys and for the
  Planner-facing ordering surface; document that placement order is now
  regret-driven within topological readiness (small axiom-05 edit, same
  commit).

Tests: a fixture where first-come order strands a deep 120-min task but
regret order places it; determinism (twice, byte-identical); all existing
reason_code paths unchanged.

## P-F · Day-quota balancing (soft quotas, not hard assignment)

Decision, made here so the implementer doesn't relitigate: **soft quotas
feeding the `daily_balance` term**, not a hard two-phase assign-to-day. A
hard pre-assignment creates a new failure mode ("day infeasible, reshuffle
across days") that would need its own repair loop and reason_code story;
quotas get ~all the benefit with zero new failure surface. Revisit hard
assignment only if the quality report still shows lopsided days.

- Compute per-day soft quotas up front in `_schedule_validated`:
  `quota(day) = min(policy.max_daily_study_min, ceil(total_plan_min / working_days))`,
  where working days come from the enumerated windows (respects weekends,
  busy-saturated days contribute what capacity they actually have).
- Replace the P-C `daily_balance` term's global target with the per-day
  quota, and add a mild **earliness pressure** term so the schedule still
  fills earlier days *slightly* first (`w_earliness × days_from_horizon_start`)
  — otherwise a pure balance objective scatters work arbitrarily late and
  risks colliding with the capacity-promotion math.
- Invariant to test explicitly: quota terms are soft — when total load
  requires exceeding quotas (crunch weeks), tasks still place, and the
  `INSUFFICIENT_WEEKLY_CAPACITY` promotion (`greedy.py:198`) fires on
  exactly the same inputs as before (golden scenarios 1/12/15 untouched).

Tests: 6 equal tasks × 3 equal free days → 2/2/2 not 6/0/0; crunch fixture
(load > capacity) produces identical failures to baseline; weights
journaled via `[scheduler_placement]` additions (`w_earliness`).

## P-G · Bounded polish pass

Greedy-with-scoring still leaves artifacts (early placements made before
later constraints materialized). A bounded, deterministic local search
cleans them up.

- After the main loop and before `_promote_capacity_failures`: at most
  **2 sweeps**. Each sweep scans placed blocks in `(start, task_id)` order;
  for each block, enumerate feasible relocations (same candidate machinery,
  with the block's own occupancy removed from state) and apply the single
  best strictly-improving move per block; feasibility checks are the full
  hard-rule set, so a polish move can never break daily caps, deep-window
  rules, or ordering relative to dependencies (recheck: dependent starts
  after dependency ends — polish must enforce this explicitly since the
  greedy loop got it implicitly from placement order).
- Polish **moves** blocks; it never unschedules, never reschedules a failed
  task, never touches `unscheduled_tasks`. Reason codes and debug payloads
  are therefore untouchable by construction — assert it anyway.
- Determinism: fixed sweep count, fixed scan order, strict-improvement
  acceptance ⇒ terminating and reproducible. Test idempotence at the
  fixed point: if sweep 2 makes no move, running polish again makes no
  move.

Tests: constructed fixture where greedy leaves an improvable placement and
polish finds the known optimum; no-op on already-good schedules
(byte-identical output); dependency-order preservation under relocation;
determinism.

## Acceptance criteria (phase)

- Quality-report CLI (P-D) on the fixture corpus shows: per-day load spread
  within ±1 task of even on balanced fixtures; the stranded-deep-task
  fixture schedules fully; zero reason_code / debug / routing diffs across
  all golden scenarios.
- `make check` green per increment; `graphify update .` run after each.

## Explicit non-goals

- No hard day assignment / cross-day repair loop (decision above).
- No simulated annealing, randomized restarts, or anything stochastic —
  strict improvement only; determinism is an axiom, not a preference.
- No change to the Planner↔Scheduler iteration protocol
  (`MAX_SCHEDULER_PLANNER_ITERATIONS = 2`, `app/cycle.py:177`, enforced at
  `:950`).

## Implementation notes (verified 2026-07-06 — these win over older prose)

Reference sanity: the placement loop is `for task in ordered_tasks:` at
`greedy.py:133`; the dependency gate is the `completed_or_placed` set
(seeded from `inp.completed_task_ids` at `:131`, checked `134-143`, task
ids added on placement at `:175`). `_sort_key` (`ordering.py:67`) returns
`(priority_rank, cognitive_rank, task.task_id)` with `cognitive_rank =
-task.cognitive_load`. All correct as cited in the prose above.

### P-E selection rule (pin this, don't re-derive)

Each round, over the current ready set (deps completed-or-placed):

1. Compute `candidates(t)` and per-candidate costs for every ready task
   `t` against the *current* state (recompute every round — state changed).
2. **Fail-fast rule:** every ready task with **zero** candidates is failed
   through `_failure_for` *this round*, in `_sort_key` order, and removed
   (it never enters `completed_or_placed`, so its dependents eventually
   fail `DEPENDENCY_BLOCKED` exactly as today).
3. Among tasks with ≥ 1 candidate, place exactly one: the task maximizing
   the key `(single_candidate_flag, regret)` where `single_candidate_flag
   = 1` if it has exactly one candidate else 0, and `regret = second_best_cost
   − best_cost` (0 when all candidates tie). Break ties by **ascending**
   `_sort_key`. No infinity sentinel needed — the flag IS the infinity.
4. Loop until the ready set is empty; tasks never reached (dependency
   failed upstream) fail `DEPENDENCY_BLOCKED` with `blocked_by` = deps not
   in `completed_or_placed`.

**Output ordering rule (byte-determinism):** emit both
`scheduled_tasks` and `unscheduled_tasks` sorted by the task's position in
`topological_order` — NOT by placement round. This keeps output ordering
identical to today whenever placements coincide, and keeps golden diffs
minimal. `_promote_capacity_failures` runs after, unchanged.

### P-F specifics

- `working_days` = number of distinct local dates with ≥ 1 enumerated free
  window (initial enumeration). Guard `working_days == 0` → quota =
  `policy.max_daily_study_min`.
- `quota(day)` uses the P-C `target_daily_min` formula; the `daily_balance`
  term's target simply becomes per-day capable of later refinement — for
  this increment `quota(day)` is the same value for every day (the formula
  has no per-day inputs yet); the point of the rename is the term now reads
  quotas from a precomputed map, which P-F tests can override.
- `earliness` penalty (new term, same sign convention):
  `day_index = (candidate.start.date() − horizon_start.date()).days` (int
  ≥ 0); term value = `day_index`. Default `w_earliness = 1`. Deliberately
  tiny: minutes-scaled terms (hundreds) dominate it, so it acts as
  fill-earlier tie pressure, which is exactly the intent.

### P-G specifics

- **Objective = schedule-level total cost** from `score_schedule`
  (schedule-level definitions in doc 01's notes) — never sum of marginals.
  Accept a relocation iff `total_after < total_before` (strict, integer).
- Relocation feasibility for block `b` (all must hold):
  1. re-run the five hard checks with `b`'s own interval removed from the
     scoring state (`busy`, `minutes_per_day`, placed-blocks list);
  2. dependency order both directions: `b.start ≥ max(end of b's
     dependencies)` and `b.end ≤ min(start of b's dependents)` among placed
     blocks;
  3. deep-gap pairwise: if `b` is deep, after the move every same-day
     consecutive deep-block pair still has gap ≥
     `policy.min_break_between_deep_blocks_min` (check BOTH neighbors —
     the greedy append-only loop only ever checked the previous one).
- Scan order: snapshot placed blocks at sweep start, process in
  `(start, task_id)` order; per block apply at most the single best
  strictly-improving move, key `(total_after, new_start)`; at most 2
  sweeps; stop early if a sweep makes no move.
