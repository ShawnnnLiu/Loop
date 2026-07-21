# 08 · Mastery Memory — Completions That Shape the Next Plan

Added 2026-07-19, same status as the rest of the folder: **planning only,
nothing implemented.** This doc amends `06-…` (one carefully scoped
exception to the non-interference rule) and extends `02-…` (strategist
plumbing) and the telemetry spec. It closes a specific gap: **completed
work is remembered forever, but nothing stops the next full generation
from assigning the same skills again.**

## The gap, precisely

Three layers already exist or are planned; none of them is skill mastery
memory:

| Layer | Status | What it remembers | Why it doesn't close the gap |
| --- | --- | --- | --- |
| `TaskDispositionRecord` (`../../specs/task-disposition.schema.md`) | **shipped** | completed/dropped `task_id`s, forever, across plan versions; advisory Planner exclusion list | task-*identity* memory — a fresh generation invents new `task_id`s for the same skill and sails past it |
| Knowledge-map tiers (`06-…`) | planned | per-node mastery (`training → honed → proven`) computed from completed minutes | display-only by the non-interference rule; generation never sees it |
| `unfilled_slots` (`02-…` §6, `03-…`) | planned | which evidence pillars are missing | slot granularity — it targets missing pillars, it cannot say "retrieval fundamentals is done, stop assigning it" |

Result: a user who honed `skill.rag` over six weeks, then changes timeline
or pathway and regenerates, gets retrieval fundamentals proposed again from
scratch. Mastery memory fixes that: **honed skills are excluded from fresh
primary study; low-confidence work earns bounded review allocations
instead.**

## The amendment to `06-…` — gating vs. advisory context

The non-interference rule exists to prevent a second prerequisite engine:
the map must never gate the Planner, the Scheduler, task availability,
or what a user may do. **That rule is unchanged.** What this doc adds is a
narrow, explicitly typed exception in the *other* direction:

> **Mastery tiers, computed deterministically by the kernel, may enter
> `StrategyConstraints` as typed advisory fields that shape what the
> Strategist proposes — exactly the `unfilled_slots` mechanism. They flow
> forward into generation, never downward into unlocks.**

The distinction that keeps this legal under the thesis: gating decides what
the user (or scheduler) *may do* — forbidden. Advisory typed context
decides what the LLM is *asked to propose*, disposed by a deterministic
output gate — the pattern this folder already uses for slot gaps. The
Planner and Scheduler remain untouched; `06-…`'s "Planner and Scheduler
never see the map" stays true verbatim. Mastery shaping happens at one
place only: the Strategist prompt and its deterministic gate.

## Signal capture — `solve_confidence` triage at completion

Mastery from minutes alone can't distinguish "did it, could do it again"
from "did it, was lost the whole time." A one-tap triage at completion
supplies that axis.

Amendment to `telemetry.schema.md`: new **optional** field on the
telemetry event —

| Field | Semantics |
| --- | --- |
| `solve_confidence` | closed enum `confident · unsure · needed_help`; the user's self-report at completion of whether they could solve/apply the material unaided. Optional — skipping the triage is always allowed (empty-over-fabrication). Only valid when `completed: true`. |

Invariants added: `solve_confidence` present ⟹ `completed: true`; value in
the closed enum (invalid fixture: `"solve_confidence": "easy"`). It is a
distinct axis from the existing `subjective_difficulty` (how hard it felt
vs. whether you own it now); both stay optional and independent.

Rules carried over from the house posture:

- **The user reports it; code records it; an LLM never assigns it** (the
  axiom-11 / source-confidence rule, verbatim).
- Enum only, no free text, rides the existing append-only telemetry store —
  **no new store for the signal itself** (the map-overlay store — grants,
  set-points, additions, custom groups/nodes, notes — is `06-…`'s).
- Private to the user; never in sponsor reports (telemetry privacy rules
  unchanged).
- UI: one optional tap on the existing check-off flow ("Got it · Shaky ·
  Needed help" — copy is a design decision, m2); zero new required
  friction. No triage recorded means no signal, not a penalty.

## Mastery computation — the basis fold (extends decision d2)

`06-…`'s honed bar is `mastery basis ≥ honed_fraction × expected_minutes`.
The **basis fold** is stated once here, normatively, so kernel and tests
can't drift. Three sources, all append-only, folded in `created_at` order
(deterministic tie-break by record id):

1. **Telemetry accumulation** — each completion on a linked task adds

   ```
   effective_minutes(completion) = minutes × confidence_weight(solve_confidence)
   ```

   Minutes attribution follows `06-…` exactly (telemetry `actual` where
   recorded, planned otherwise; full minutes count toward every linked
   node). Confidence weights are heuristic priors in `tuning.toml` beside
   `honed_fraction` (threshold-change-log entries like every other prior):

   | `solve_confidence` | weight (prior) |
   | --- | --- |
   | `confident` | 1.0 |
   | absent (no triage) | 1.0 — the signal is opt-in; not reporting is never punished |
   | `unsure` | 0.5 |
   | `needed_help` | 0.25 |

2. **`MasteryGrant`s** (`06-…` overlay) — onboarding and evidence-confirm
   flows append positive `credit_minutes` when confirmed evidence matches
   a node (sizing is m6). Grants only ever add — **onboarding never
   subtracts** (the `06-…` add-only rule).

3. **`MasterySetPoint`s** (`06-…` overlay) — an explicit per-node user
   action that **rebases** the accumulator to
   `tier_fraction[target_tier] × honed_fraction × expected_minutes`
   (fractions are `tuning.toml` priors: `discovered 0 · training 0.5 ·
   honed 1.0`; `proven` is not settable — it stays evidence-gated).
   Checking off a node = a set-point to `honed`; "I'm rusty" = a set-point
   downward. Later completions and grants accumulate on top of the new
   base. (Set-points on personal custom nodes exist too but are pure
   display state — custom nodes have no telemetry linkage, take no grants,
   and never project into constraints; `06-…` content classes.)

Two definitions fall out, both pure functions over the folded basis:

- **Mastered** — a node whose tier is ≥ `honed`. Since `proven ⊃ honed`,
  proven nodes are mastered too; vocabulary-added nodes participate
  identically (personal custom nodes never do — they are display-only).
- **Review-flagged** — a node whose *raw* minutes meet the honed bar but
  whose *weighted* basis does not: the work happened, the confidence
  didn't. These are the "not sure I could do it again" skills the user's
  triage flagged for revisiting.

Properties, stated normatively:

- **Mastery never decays and never regresses on its own.** Completions and
  grants only add; low confidence slows a climb but demotes nothing. The
  **only** thing that lowers a node is an explicit user `MasterySetPoint`
  — no decay timers (the `06-…` exclusion stands — see non-goals), no
  system-side demotion, no onboarding-side subtraction, ever.
- **Memory is skill-keyed, account-owned, and permanent.** The fold runs
  over **all plan versions** of the profile lineage (the disposition-store
  union pattern), keyed by the node's `skill_id` — taxonomy ids are
  global, so mastery survives replans, timeline changes, and pathway
  changes. The map is the account's display projection of the same
  accumulated data.
- **Deterministic end to end.** Weights and fractions are `tuning.toml`
  priors; the fold is code; no prose participates. The kernel exports
  **one** fold used by both `map_state` and the mastery aggregation.

## The mastery slice — `StrategyConstraints` extension

`strategy-constraints.schema.md` gains optional fields (defaults preserve
`{}`-is-valid; absent lists = no mastery shaping = today's behavior):

| Field | Semantics |
| --- | --- |
| `mastered_node_ids` | node ids whose skills are mastered, over the **account map** — generated nodes plus user additions — so the gate compares directly against module tags |
| `review_node_ids` | node ids whose skills are review-flagged; disjoint from `mastered_node_ids` (contract invariant) |
| `max_review_modules` | bound on modules training only mastered/review nodes per syllabus (default 2) |
| `max_review_minutes` | per-module minutes cap for such modules (default 60) |

Composition root (the `unfilled_slots` seam): when a pathway is selected
and mastery data exists, project the skill-keyed fold onto the account's
knowledge map and populate the slice. Every id must resolve to the account
map — a composition-time guarantee backed by a contract invariant. Two
loops close here by construction: a node the user **set-pointed downward**
falls out of `mastered_node_ids`, so the next generation offers it for
study again; a node the user **added from the career vocabulary** enters the
vocabulary and the mastery projection, so missed skills become plannable
and, once honed, stop being re-assigned.

Strategist prompt addition: mastered nodes are *done* — do not propose
primary study modules whose training targets are all mastered; for
review-flagged nodes, propose at most `max_review_modules` short review
modules, each within `max_review_minutes`, tagged with the nodes they
review and saying so in `reason`. (`reason` is user-facing honesty,
checked non-empty only — **the gate never parses prose**.)

Deterministic output gate (new validation checks, existing categories):

- A module whose `knowledge_node_ids` are all ∈ `mastered_node_ids ∪
  review_node_ids` is a **review module**: its `estimated_minutes` must be
  ≤ `max_review_minutes` → else `MASTERY_REVIEW_BOUND_EXCEEDED`.
- Count of review modules ≤ `max_review_modules` →
  `REVIEW_MODULE_LIMIT_EXCEEDED`.
- Mixed modules (mastered + unmastered nodes) are **legitimate and
  unbounded** — new work naturally touches old skills; only all-mastered
  modules are review-bounded. Untagged modules are untouched, as in KT-C.

That's the complete new runtime reason-code list: two codes. The
exclusion instruction ("don't re-assign mastered skills") is advisory —
enforced by the prompt and absorbed by the review bounds, mirroring the
Planner exclusion list's advisory posture in the disposition spec; a hard
never-reassign gate would fight legitimate mixed modules and is deferred
(open decision m4).

## What this deliberately is not

- **Not a second prerequisite engine.** Nothing here gates unlocks, task
  availability, scheduling, or user actions. The `06-…` non-interference
  rule is amended only by the advisory-context exception above.
- **Not spaced repetition.** No decay timers, no review intervals, no
  scheduling by forgetting curves. Review allocation happens only at
  generation time, bounded and visible in the plan the user approves.
  Interval-based review is a real product idea and a real scope expansion —
  it gets its own open decision (m5), never a rider.
- **Not competence certification.** "Mastered" claims *the planned work
  happened and the user reported confidence*, or *the user explicitly
  claimed it* (a set-point, labeled "self-assessed" in the node drawer) —
  self-report, honestly labeled. The `06-…` line extends verbatim: the
  system never certifies competence it can't observe.
- **Not LLM-touched.** Mastery sets, review flags, weights, and bounds are
  all computed by code; the LLM only receives them as typed constraints
  and proposes within them.
- **Inert without a pathway.** No selection → no node tags → no mastery
  data → absent fields → byte-identical behavior to today (the NP skip-path
  guarantee extends).

## Increments — MM-A … MM-C (one commit each, house gates)

Sequenced after the KT series: MM-A needs KT-A's contracts, MM-B needs
KT-B's kernel, fold, and committed maps, MM-C needs KT-C's strategist
plumbing. KT-D (the map UI) is independent — mastery memory ships with or
without the map screen.

- **MM-A — contracts.** Spec amendments (`telemetry.schema.md`
  `solve_confidence` + invariants; `strategy-constraints.schema.md` mastery
  slice + disjointness invariant), the two reason codes registered,
  `tuning.toml` confidence-weight priors + threshold-change-log entries,
  Pydantic + valid/invalid fixtures (confidence-on-incomplete,
  out-of-enum, overlapping mastered/review lists, over-bound review
  module), `make schemas`. (The overlay record types — grants, set-points, additions, custom
  groups/nodes, notes — and the set-point tier fractions are KT-A/KT-B
  material per `06-…`; MM-A adds only the confidence axis and the slice.)
- **MM-B — capture + fold weighting.** Completion endpoint accepts
  `solve_confidence`; one-tap triage on the check-off flow, built against
  the reference component
  `docs/design-reference/design-loop/accountability.jsx` (`CheckInDemo`):
  insert it as a sibling of the completed-reveal "How long, really?" row
  that already appears when a block is marked `✓ Completed`, reusing the
  design-system chip/pill grammar (`docs/design-reference/claude_code_handoff/DESIGN-SYSTEM.md`)
  so it adds no required friction and no layout shift (+ vitest;
  skippable). Review-flagged nodes get no new MM surface: they are
  display-only data that KT-D's knowledge-map drawer renders (alongside
  the "self-assessed" set-point label), consistent with the `06-…`
  non-interference posture; this is a scoping decision, not an omission.
  Confidence weighting added into KT-B's
  basis fold (`map_state` and the mastery aggregation consume the one
  shared implementation); exhaustive fold tests: weighting per enum value,
  absent-signal neutrality, grant/completion/set-point interleavings and
  ordering ties, cross-plan-version union, skill-keyed survival across
  pathway change, review-flag boundary cases, no-automatic-regression
  property (only a set-point lowers).
- **MM-C — strategist wiring.** Composition-root projection (skill →
  account-map node ids, user additions included), prompt addition,
  deterministic gate for both reason codes, validation tests per code
  (valid and invalid fixtures), golden orchestration cases re-run (this
  touches the cycle).

Definition-of-done items extend `04-…` verbatim, plus: regenerate after
honing a skill in the keyless dev server and verify the new syllabus
contains no primary module for it and at most the bounded review
allocation — reproducible by calling the kernel on stored data, in a real
browser.

## Open decisions (m-series; adds to the README list)

- **m1 · Confidence weights**: `1.0 / 1.0-absent / 0.5 / 0.25` proposed —
  heuristic priors until calibrated, like everything in `tuning.toml`.
  Absent-means-neutral is the one hill: opt-in signals must never punish
  non-reporting.
- **m2 · Triage surface + copy**: one-tap on task check-off (proposed) vs.
  batched into the weekly check-in. Check-off is closer to the moment of
  truth; check-in is lower friction. Copy ("Got it · Shaky · Needed help")
  lands with MM-B either way.
- **m3 · Mastered = honed or proven?** `honed` proposed — requiring an
  artifact before the system stops re-assigning fundamentals punishes
  exactly the users doing the work; `proven` remains the display crown.
- **m4 · Advisory exclusion vs. hard gate**: advisory + bounded review
  modules (proposed, matches the disposition spec's Planner posture) vs. a
  hard `MASTERED_SKILL_REASSIGNED` rejection. Revisit with dogfood evidence
  if the Strategist ignores the instruction in practice.
- **m5 · Interval review (spaced repetition)**: out of scope here;
  deliberately parked. If dogfooding shows honed skills rotting, design it
  as its own feature with its own axiom conversation — not as a tweak to
  these weights. Note the user already holds the manual version of this
  lever: a downward set-point re-opens a skill for study.
- **m6 · Grant sizing**: how much basis a confirmed onboarding evidence
  match grants. Straight-to-honed proposed (`1.0 ×` the honed bar — the
  user showed the work already exists; making them re-study their own
  résumé is the exact failure this doc removes) vs partial credit.
  `tuning.toml` prior either way; grants are add-only regardless.
