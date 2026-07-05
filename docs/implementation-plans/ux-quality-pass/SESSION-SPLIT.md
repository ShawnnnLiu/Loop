# UX Quality Pass — Remaining-Work Session Split

Written 2026-07-05. Carves the remaining increments (baseline capture, D1, D2,
D4, E) into **five pieces, each sized to finish inside one ~300k-token context
window** (estimates are rough, deliberately padded below 300k so gate re-runs
and surprises fit). `HANDOFF.md` holds the full per-increment specs and the
approved decisions — this file only draws session boundaries, adds sizing, and
gives a copy-paste kickoff prompt per piece.

**Ordering is fixed: 1 → 2 → 3 → 4 → 5.** Do not reorder — captures must
bracket prompt changes (baseline before any prompt-byte edit; a labeled
re-capture after each prompt-editing piece).

Conventions for every piece (from HANDOFF — repeated once here, not per piece):

- One commit per increment listed inside the piece (a piece may hold 2 commits).
- Backend gates from `backend/`: `make check`. Frontend (when touched):
  `npm run typecheck && lint && test && build`. `graphify update .` after code
  changes.
- Any prompt-byte edit bumps `prompt_version` + the pinned hash in
  `tests/llm_nodes/test_prompt_versions.py` in the SAME commit (test enforces).
- Every live capture is networked: **ask the user before each run.**
- If a piece finishes with lots of headroom, it MAY roll into the next piece's
  scope — but never split a capture from the prompt change it measures.

---

## Piece 1 — Baseline capture + D1a (few-shot + repair unification)

**Est: ~180–260k tokens. Commits: 2.**

1. **Baseline capture + gate seeding** (HANDOFF "⏸ IMMEDIATE NEXT STEP",
   verbatim): live capture `baseline_2026_07_04.json` (relabel to the actual
   date) with `--judge`, grade via `run_llm_eval`, seed `make eval-gate` v2
   floors with the MEASURED values, report per-run cost from `call_aggregates`
   in the commit message (this absorbs D3's deferred cost measurement).
   One commit: recording + report + Makefile.
   - **HARD GATE:** requires `ANTHROPIC_API_KEY` + user go-ahead. If the key
     is unavailable, STOP the piece — do not proceed to D1a, or the pre-change
     comparison point is lost forever.
2. **D1a** — the adapter/engine-centric half of HANDOFF §D1:
   - Few-shot exemplars: one compact valid exemplar per structured prompt
     (Planner 3-task mini-plan, Strategist 2-module mini-syllabus), marked
     illustrative.
   - Repair unification: one typed-violation formatter (field path →
     constraint → offending value) used by BOTH channels; parse
     `ValidationError.errors()`; keep the literal "rejected by deterministic
     validation" marker; add the unparseable-case required-keys reminder.
   - Bump both prompt versions + pinned hashes. One commit.
   - **No capture in this piece after D1a** — the `fewshot-…` capture waits
     until D1b lands (Piece 2) so it measures all of D1 at once.

**Kickoff prompt:**

> Continue the UX quality pass on branch `ux-quality-pass`. Read
> `docs/implementation-plans/ux-quality-pass/SESSION-SPLIT.md` and
> `HANDOFF.md` first, then do **Piece 1**: baseline capture + eval-gate
> seeding (ask me before the live run; stop if no API key), then D1a
> (few-shot exemplars + repair unification). One commit each, gates green.

## Piece 2 — D1b (goal block + claim curation) + `fewshot` capture

**Est: ~150–220k tokens. Commits: 2 (D1b; then recording+report).**

1. **D1b** — the context-assembly half of HANDOFF §D1:
   - Goal block: typed `goal` / `target_role` / `known_weaknesses` from
     UserProfile into Planner context; system-prompt note that it steers
     titling/emphasis only, not structure (→ Planner version bump + hash).
   - Claim curation at `_propose_fresh`: drop expired via
     `SourceClaim.is_expired(now)`, confidence floor, per-company cap sorted
     confidence-desc; log dropped count+reason (heuristic priors — document);
     tests incl. golden-style expired-claim-filtered case.
2. **Measure D1 as a whole**: ask user → live capture labeled
   `fewshot-YYYY-MM-DD` → `run_llm_eval --compare` vs the baseline report →
   deltas in the commit message.

**Kickoff prompt:**

> Continue the UX quality pass on branch `ux-quality-pass`. Read
> `docs/implementation-plans/ux-quality-pass/SESSION-SPLIT.md` and
> `HANDOFF.md` first, then do **Piece 2**: D1b (goal block + claim curation),
> then the `fewshot` capture + compare vs baseline (ask me before the live
> run). One commit per increment, gates green.

## Piece 3 — D2: prose voice rewrite + reflection injection + `voice` capture

**Est: ~200–280k tokens (largest remaining). Commits: 2 (D2; recording+report).**

Full HANDOFF §D2 in one window:

- Voice specs for `_REFLECTION_SYSTEM` / `_EXPLANATION_SYSTEM` (coach not
  clinician; length bound; happened → suggests → one next step; positive +
  one NEGATIVE labeling exemplar; explanations name the reason_code's plain
  meaning + next action). Review/extend the psych denylist in
  `reflection_summary.py` (stays deterministic). Version bumps + hashes.
- Inject last ~3 persisted reflections (B5 prose store, kind=REFLECTION,
  `list_for_user`) into the reflection node's context AND the REPLAN planner
  context as an advisory behavioral-hints block beside `excluded_tasks` —
  advisory prose only, never parsed, never control-plane.
- SPA: reflection history list on Accountability via a small read projection.
- Measure: ask user → capture `voice-YYYY-MM-DD` **with `--judge`** →
  compare judge scores + rubric rates vs baseline; deltas in commit message.

If the window runs tight, the SPA history list is the one deferrable
sub-item — push it into Piece 4 rather than skipping the capture.

**Kickoff prompt:**

> Continue the UX quality pass on branch `ux-quality-pass`. Read
> `docs/implementation-plans/ux-quality-pass/SESSION-SPLIT.md` and
> `HANDOFF.md` first, then do **Piece 3**: D2 (voice rewrite + reflection
> injection + SPA reflection history), then the `voice` capture with
> `--judge` + compare (ask me before the live run). Gates green both sides.

## Piece 4 — D4: prior-plan-aware replans (no capture)

**Est: ~180–250k tokens. Commits: 1 (or 2 if stage 1/stage 2 split cleanly).**

Full HANDOFF §D4:

- Stage 1: REPLAN path only (`_propose_replan` → planner call) — prior
  TaskPlan's surviving subset into Planner context with
  preserve-ids/titles/durations-unless-affected instruction; Planner
  system-prompt note + version bump + hash.
- Stage 2: deterministic old→new diff ("3 changed, 14 preserved") — REUSE
  `contracts/plan_diff.py` (contract/spec/schema exist); add the compute
  helper in `planning/`; surface on Approval and/or Week banner for replan
  drafts (SPA).
- Axiom 20 note: stage-1 context anchoring precedes validator-enforced
  preservation (Phase 2/3 stays future work).
- No live capture needed. Prompt bump because stage 1 edits the Planner
  system prompt.

**Kickoff prompt:**

> Continue the UX quality pass on branch `ux-quality-pass`. Read
> `docs/implementation-plans/ux-quality-pass/SESSION-SPLIT.md` and
> `HANDOFF.md` first, then do **Piece 4**: D4 prior-plan-aware replans
> (stage 1 context anchoring + stage 2 deterministic plan diff surfaced in
> the SPA). No capture needed. Gates green both sides.

## Piece 5 — E: wrap-up, smoke, audit

**Est: ~150–250k tokens (audit findings are the variance). Commits: 1–3
(README flip; audit fixes if any; keep them separable).**

Full HANDOFF §E:

- Full gates both sides; `graphify update .`.
- Real-browser smoke via the keyless dev server
  (`uv run python -m agentic_calendar.app.web`): failed write → 3-option
  recovery; parked replan → banner + picker; recommitment answer →
  "review updated plan".
- bs-detector audit of the WHOLE branch (all ~18+ commits by then); fix
  findings.
- Flip `README.md` status to implemented with per-section outcome notes
  (what shipped, what deviated — pull from HANDOFF's deviations list).
- Final memory update (`ux-quality-pass-plan.md`).

**Kickoff prompt:**

> Finish the UX quality pass on branch `ux-quality-pass`. Read
> `docs/implementation-plans/ux-quality-pass/SESSION-SPLIT.md` and
> `HANDOFF.md` first, then do **Piece 5**: full gates, real-browser smoke of
> the three recovery flows, bs-detector audit of the whole branch + fix
> findings, README status flip, memory update.

---

## Progress tracker (update as pieces land)

| piece | scope | status |
|---|---|---|
| 1 | baseline capture + D1a | **DONE 2026-07-05** — baseline `f869fef` (11 cases, 16 calls, ~$0.16; validity 1.0, gate seeded), D1a `42edd48` (v3 prompts) |
| 2 | D1b + fewshot capture | **DONE 2026-07-05** — D1b `476a361` (goal block, planner-v4; claim curation + `claim_curation` tuning section; per-host-cap deviation in HANDOFF), fewshot capture (11 calls, ~$0.157, no judge per choreography; validity/rubric flat at 1.0, depth −1.33, tasks/module +0.39) |
| 3 | D2 + voice capture | pending |
| 4 | D4 replans | pending |
| 5 | E wrap-up | pending |
