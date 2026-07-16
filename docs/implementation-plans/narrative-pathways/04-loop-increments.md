# 04 · Loop Increments — NP-A … NP-F

*(The knowledge-map increments KT-A…KT-D live in `06-knowledge-tree.md` and
slot in after NP-B / NP-D / NP-E respectively — or run as a second wave
after NP-F.)*

One commit per lettered increment, house conventions throughout: spec/axiom
first, `uv run make check` green from `backend/` per commit, frontend gates
(`npm run typecheck && lint && test && build`) for NP-E, `graphify update .`
after code changes, ask before anything networked. No new dependencies are
anticipated anywhere in this plan.

Branch from `main` after the currently open PRs merge. Overlap with other
planned tracks is light and additive (`routes_cycle.py` / `app/cycle.py` /
onboarding frontend — the same rebase-friendly seams the RI plan noted).

## NP-A — Axioms, specs, contracts, fixtures

The full checklist in `02-…` §Spec-first: axiom 00 deterministic-ownership
line, axiom 03 spec registration, two new specs, four amended specs, Pydantic
contracts (`pathway_template.py`, `pathway_selection.py`; amendments to
`user_profile.py`, `resume_extraction.py`, `resume_intake_input.py`,
`strategy_constraints.py`, syllabus module), valid/invalid fixtures with
expected structured violations, `make schemas`. New reason codes registered
wherever the repo's typed-code enum lives, with tests.

Gate: contract/fixture/schema suites green; nothing consumes the new fields
yet.

## NP-B — `narrative/` kernel + pathway registry with seed content

- `narrative/` package: `slot_coverage`, `pathway_fit`, `story_progress`
  (pure functions per `02-…` §5), exhaustive unit tests including the
  one-item-one-slot greedy assignment, override precedence, deterministic
  tie-breaks, and pinned-version behavior.
- Registry module (decide placement: sibling `pathways/registry.py` vs a
  second registry in `templates/` — either respects boundaries; prefer
  `templates/` if the completeness-test pattern reuses cleanly).
- `.importlinter` updated for the new package; `make boundaries` green.
- **Seed content** (curated in this commit's review, prestige-denylist test
  applied): 2–4 pathways per live track. Starting set, drafted from the
  career-track-expansion research:
  - `swe`: **Backend & Infrastructure** (depth services, data layer,
    production ops, public artifact), **Full-Stack Product Engineer**
    (frontend surface, backend depth, shipped-product evidence, user-facing
    polish), **AI-Integration Engineer** (cross-listed `swe`/`ai_engineer`;
    LLM feature depth, integration breadth, eval/telemetry literacy, public
    artifact).
  - `mle`: **Applied ML Specialist** (modeling depth ×2, deployment
    evidence, data engineering breadth, writeup).
  - `ai_engineer`: AI-Integration Engineer (shared) + **LLM Systems
    Engineer** (orchestration/eval depth, retrieval project, cost/latency
    evidence, public artifact).
  Content review is the curation gate; counts and slot definitions are
  priors to revise freely before implementation.

Gate: kernel + registry suites green; still no user-visible behavior.

## NP-C — Intake extension

- `ResumeIntakeNode` prompt + adapter: propose `kind` + `theme_tags` per
  item; `allowed_themes` added to `resume-intake-input` bundle; membership
  enforced in the existing bounded repair loop; fixture twin updated.
- Prompt-budget re-check recorded in the commit message (taxonomy slice +
  theme slice, tokens).
- Eval set v4 per `03-…` §Eval additions; capture CLI re-registration;
  strict gate re-pinned (the RI-E discipline).

Gate: backend suites + eval fixtures green. Live Haiku smoke is optional,
networked, ask-first (~$0.02).

## NP-D — API, persistence, strategist plumbing

- `GET /api/pathways?track=` → registry cards + per-user deterministic
  coverage (auth'd; computed via the kernel, no LLM).
- `POST /api/onboard` accepts optional `pathway_selection` (+ the
  slot-override shape); Tuning-side profile-update path accepts
  pathway change with the invalidation semantics from `02-…` §7 (new
  profile version → cycle re-run, existing machinery).
- Composition root: build `unfilled_slots` into `StrategyConstraints` when a
  selection exists; Strategist prompt addition + deterministic output gate
  for the three new validation rules; validation-layer tests for each new
  reason code, valid and invalid fixtures both.
- "Mark evidence" endpoint: appends a confirmed evidence item
  (kind/tags/note) to the profile — plain profile edit, no LLM, no plan
  invalidation.

Gate: full `uv run make check`; golden orchestration cases re-run (this
touches the cycle).

## NP-E — Frontend

- Wizard 4 → 5 steps (`frontend/src/lib/intake.ts` `STEP_LABELS` + tests):
  **Your story** step with character-sheet strip, pathway cards (slot
  pills: filled/partial/empty), select/skip, consequence preview on select.
- Review-step additions from NP-C: `kind` + `theme_tags` editors on each
  evidence item (closed dropdowns; "no tag" allowed).
- Progress screen **Story** panel: pillars with slot states, "mark
  evidence" flow; Tuning screen **Change pathway** with replan warning.
- Skip path regression-tested: no selection stored → zero UI or payload
  difference from today anywhere downstream.
- Vitest for the intake-state changes and card ordering rendering; the
  house CDP smoke recipe (ux-quality-pass memory) covers select → replan →
  story panel in a real browser.

Gate: frontend four gates + backend `make test-fast` (API contract tests).

## NP-F — Explanation targets, observability, docs

- `UserFacingExplanationNode`: fit-note (batched per card set) and
  story-summary targets; deterministic post-checks (denylist, length);
  call-log target enum + axiom 09 budget lines; trace-view CLI unchanged
  (records flow through existing plumbing).
- `docs/dogfooding.md`: how to exercise the story loop end to end.
- README of this folder flipped from "planning docs only" to implemented
  status, per-increment commit table (house pattern).

Gate: full backend + frontend gates; optional ask-first live smoke of both
targets.

## Definition of done (whole feature)

1. In the keyless dev server, a user can: extract a résumé → see tagged
   evidence → review the Your-story step → select **AI-Integration
   Engineer** → approve a generated plan in which up to `max_slot_modules`
   modules name the pillars they build toward → later "mark evidence" and
   watch the pillar fill — verified in a real browser.
2. A user who skips the step gets today's product, byte-identical payloads,
   forever.
3. Every ranking, gap, and progress state on screen is reproducible by
   calling the `narrative/` kernel on the stored profile — no LLM output
   participates in any of them.
4. Changing pathway versions the profile, invalidates the syllabus, and
   never resets evidence.
5. All new failure paths surface typed reason codes with fixtures proving
   it; `uv run make check` and the frontend gates green; `.importlinter`
   passing with the new package row.

If the cards render but the ordering came from anything other than
`pathway_fit` over confirmed evidence, it isn't done — determinism of the
story layer is the contract.
