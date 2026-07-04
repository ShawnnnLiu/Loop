# UX Quality Pass — Implementation Handoff

Status as of **2026-07-04**, branch **`ux-quality-pass`** (off `deleted-event-memory`,
whose PR is still open). **A + B + C tracks are COMPLETE — 11 commits, all gates
green** (backend `make check` 2691, frontend typecheck/lint/test(81)/build,
`make eval-gate`, boundaries 16 kept). **D + E remain** and are specified below
for implementation in fresh context windows, one increment per session if needed.

Read order for a fresh session: this file → `README.md` + the relevant numbered
plan file (`02-…`/`03-…`) → the code anchors named per increment.

## Approved decisions (user, 2026-07-04 — do not re-ask)

1. **Axiom 09 amendment + ALL THREE model upgrades** (Planner, Reflection,
   Explanation → Sonnet-tier now; Strategist stays Opus). → D3
2. **Axiom 22 amendment + CI gate** over committed recordings. → **DONE** in C3.
3. **Graders Tier 1 + Tier 2** (deterministic + offline LLM-judge). → **DONE** in C2.
4. **Live captures: agent runs them, asking before each run.** Baseline capture
   is currently **blocked on `ANTHROPIC_API_KEY`** (see next section).

## ⏸ IMMEDIATE NEXT STEP — baseline capture (user-unlocked, networked, ~<$1)

The D-track prompt/model changes are only measurable against a recording of the
**current** prompts. Run from `backend/` with the key in the environment:

```bash
ANTHROPIC_API_KEY=sk-... uv run python -m agentic_calendar.tools.capture_eval_recordings \
  --eval-set evalsets/eval_set_v2.json \
  --out evalsets/recordings/baseline_2026_07_04.json \
  --label baseline-2026-07-04 --live --judge
```

Guards: hard cap 33 adapter calls + 15 judge calls; cost ceiling ~$3 derived
from worst-case output caps (realistic spend well under $1). Then:

1. Grade + save the report:
   ```bash
   uv run python -m agentic_calendar.tools.run_llm_eval \
     --eval-set evalsets/eval_set_v2.json \
     --recording evalsets/recordings/baseline_2026_07_04.json \
     --out evalsets/reports/baseline_2026_07_04.report.json
   ```
2. Seed the gate: add the v2 pair to `backend/Makefile` `eval-gate` with
   `--min-schema-validity-rate` / `--min-repair-recovery-rate` set to the
   MEASURED baseline values (grading a committed recording is deterministic,
   so floors equal to measured always pass until a new recording lands).
3. Commit recording + report + Makefile change as its own commit
   ("UX pass: real eval baseline for the current prompts").

**Re-capture choreography for D-track** (ask the user before each live run):
after D1 → label `fewshot-YYYY-MM-DD`; after D2 → `voice-YYYY-MM-DD` (with
`--judge`); after D3 → `sonnet-YYYY-MM-DD`. Compare each via
`run_llm_eval --compare <previous report>` and put the deltas in the commit
message. Note: a re-capture's recording will trip the prompt-bytes test's
sibling expectation only if versions weren't bumped — bump `prompt_version`
constants + the pinned hashes in `tests/llm_nodes/test_prompt_versions.py`
in the SAME commit as any prompt edit.

## What was built (A/B/C) — one line per commit

| commit | increment |
|---|---|
| b5cc5c0 | plan docs committed |
| 8bdebc2 | **A2** prompt caching (breakpoint on base user block), prompt-bytes↔version pinned test, cache/ + axiom 18 honesty |
| ada4658 | **B1** write-failure recovery: rollback/retry signals+edges, `write_op_id`, `cycle.rollback`/`retry_write`, `/api/rollback` + `/api/retry-write`, 3-option Approval UI + confirm modal, `reconcile_after_crash` now covers never-attempted draft entries |
| 337b85c | **B2** REPLAN_REQUIRED surfaced: `replan` review mode + reason map, recovery-mode picker (ask_each_time), Today "needs attention" chip, `recovery_mode_pending_user_choice` on status |
| cead1cf | **B3** accountability answerable: `RECOMMITMENT_ACCEPTED` edge, `cycle.recommit` (user choice OVERRIDES drift-derived mode), `cycle.weekly_checkin` (first CheckinEvent producer), Accountability screen cards |
| 13e4d5c | **B4** drift classifier fed: `_drift_input` assembler (EVENT_DELETED→external conflicts, weekly cycles, fragmentation, declined/sponsor signals) |
| f75cf09 | **B5** prose-attachment store (spec+contract+fixtures+twins) persisting reflections/explanations; status replays them; Generation resume-on-mount + `/onboarding?step=` deep link; Week banner "Why?" disclosure |
| c263959 | **C1** adapter resilience: LLM_AUTH_FAILED/LLM_RATE_LIMITED, retryable taxonomy (APIConnectionError was escaping raw!), 300s timeout, exp backoff via injected sleeper |
| cd2ab7a | **C2** capture tool (`--validate-only` offline), eval_set_v2 (11 input-carrying cases), engine `attempt_recorder` hook, Tier-1 plan-quality metrics, Tier-2 judge (`eval_judge.py`, claude-sonnet-5) |
| 69583e8 | **C3** axiom 22 amended (recorded grading may gate; live never in CI), `--strict` + floors, `make eval-gate` + CI job, `trace_llm_calls --db`, `tools/llm_stats.py` |

## Deviations from the plan docs (load-bearing — do not "fix" back)

- **02§3 temperature: deliberately NOT implemented.** Opus 4.8 400s on
  sampling params; Sonnet 5 rejects non-default values → sampling is
  API-pinned on every target tier. Documented at the adapter config block;
  eval comparability rests on the prompt-bytes pinned test instead.
- **03§1 cache breakpoint sits on the base USER-prompt block, not system** —
  system prompts alone are below the 4096-token provider minimum and would
  silently never cache. Repair suffix travels as a second content block so
  the base block stays byte-stable (prompt_hash bytes unchanged).
- **`reconcile_after_crash` gained logic** (plan said "no manager change"):
  it now also creates draft entries the crashed write never attempted —
  otherwise a mid-write crash "healed" into a verified plan with silently
  missing events. `retry_write` falls back to a full `approve_and_write`
  when zero mappings exist (reconcile over nothing would false-succeed).
- **`/api/retry-write`** (not `/reconcile-after-crash`) — avoids collision
  with the existing inbound-sync `/api/reconcile`.
- **eval-gate pairs `fixture_improved`**, not `fixture_baseline` — baseline
  deliberately contains a failing case (harness proof) and must keep failing.
- **The judge is NOT a workflow node**: no engine, no call-log rows; axiom 22
  now says so explicitly. Don't wire it into `LlmNodeName`.

## Remaining increments (D + E)

Conventions for every increment: commit per increment; backend gates from
`backend/` (`make check`), frontend `npm run typecheck && lint && test &&
build`; `graphify update .` after code changes; rebuild-don't-model_copy;
spec-first for contract changes (`make schemas`); prompt edits ALWAYS bump
`prompt_version` + pinned hash together (test enforces it).

### D1 — Few-shot exemplars + repair unification + goal block + claim curation (plan 02§1, 02§4, 03§4, 03§5)

- All prompts live in `llm_nodes/anthropic_adapter.py` (`_STRATEGIST_SYSTEM`,
  `_PLANNER_SYSTEM`; configs carry `prompt_version`).
- Few-shot: one compact valid exemplar per structured prompt — Planner: 3-task
  mini-plan (correct DAG, module coverage, NO `prerequisites_met`); Strategist:
  2-module mini-syllabus with `source_claim_ids`. Mark as illustrative shape.
- Repair unification: one formatter producing a typed violation list (field
  path → constraint → offending value) used by BOTH channels — engine schema
  rejections (currently raw `str(ValidationError)`; parse `.errors()`) and the
  unparseable case (add a top-level-required-keys reminder). Keep the literal
  "rejected by deterministic validation" marker (tests assert it). The
  planner's inbound channel (`AnthropicPlanner.run` repair block) already
  embeds canonical JSON — align both on the new formatter.
- Goal block: Planner context gains typed `goal`, `target_role`,
  `known_weaknesses` from UserProfile (titling/emphasis only, not structure —
  say so in the system prompt). `app/cycle.py` already passes `user_profile`
  to the planner.
- Claim curation: at the strategist call site in `_propose_fresh`
  (`claims = list(env.claim_store.all())`): drop expired
  (`SourceClaim.is_expired(now)`), floor on stored `confidence_score`,
  cap per company sorted confidence-desc; log dropped count+reason
  (heuristic priors, document). Tests + a golden-style case: expired claim
  filtered pre-prompt.
- **Measure**: bump both prompt versions + hashes; ask user → capture
  `fewshot-…` → compare vs baseline; deltas in the commit message.

### D2 — Prose voice rewrite + reflection injection (plan 02§2 + 03§2 leftover)

- Voice specs for `_REFLECTION_SYSTEM` / `_EXPLANATION_SYSTEM`: audience,
  "coach not clinician", length bound, structure (what happened → what it
  suggests → one concrete next step), 1-2 positive exemplars + one NEGATIVE
  labeling exemplar. Explanations must name the reason_code's plain meaning +
  the next action (pairs with B5's resume surface). Review/extend the psych
  denylist (`reflection_summary.py`) while there — stays deterministic.
- Inject last ~3 persisted reflections (B5's prose store, kind=REFLECTION,
  `list_for_user`) into (a) the reflection node's context (continuity) and
  (b) the REPLAN planner context as an advisory behavioral-hints block next to
  `excluded_tasks`. Advisory prose only — never parsed, never control-plane.
- SPA: reflection history list on Accountability (data already available via
  a small read projection; add one).
- **Measure**: version bumps + hashes; ask user → capture `voice-…` WITH
  `--judge` → compare judge scores + rubric rates vs baseline.

### D3 — Axiom 09 amendment + all-three Sonnet swap (plan 02§6; user approved)

- **Amend `docs/axioms/09-cost-and-metrics.md` FIRST**: tiering line (:~122)
  → frontier Strategist / **Sonnet-tier** Planner+Reflection+Explanation;
  pricing table; re-check the $4/month cap + hourly cap against the new
  envelope; change-log entry.
- Verified facts (claude-api skill, 2026-07-04): **`claude-sonnet-5`**,
  $3/$15 per MTok (intro $2/$10 through 2026-08-31). **Gotchas:**
  (a) omitting `thinking` on Sonnet 5 runs ADAPTIVE THINKING — thinking
  tokens count inside `max_tokens`; either set `thinking={"type":"disabled"}`
  in the transport for structured nodes or raise budgets deliberately
  (prose nodes at 1024 will truncate under thinking — decide with eval data);
  (b) non-default sampling params are REJECTED (temperature note already in
  code); (c) new tokenizer ≈ +30% tokens vs Sonnet 4.6-era counts — cost
  estimates shift; (d) confirm prompt-cache minimum for Sonnet 5 when
  measuring cache_hit (Opus/Haiku = 4096; Sonnet 5 unlisted in the table).
- Swap `PLANNER_CONFIG`/`REFLECTION_CONFIG`/`EXPLANATION_CONFIG` model +
  prices (+ judge already on sonnet-5). Update the config-block comment.
  `test_happy_path…` asserts the planner model string — update.
- **Measure**: ask user → capture `sonnet-…` → compare. Report the per-run
  cost delta from `call_aggregates` in the commit message.

### D4 — Prior-plan-aware replans (plan 03§3; no capture needed)

- Stage 1: in the REPLAN path only (`_propose_replan` → planner call), include
  the prior TaskPlan's surviving subset in the Planner context with a
  preserve-ids/titles/durations-unless-affected instruction. Planner system
  prompt note + version bump + hash.
- Stage 2: deterministic old→new plan diff surfaced at approval/review
  ("3 changed, 14 preserved"). **Reuse `contracts/plan_diff.py`** (contract +
  spec + schema exist; no compute helper in `planning/` yet — add one).
  SPA: diff line on Approval and/or the Week banner for replan drafts.
- Axiom 20 note: stage-1 context anchoring precedes validator-enforced
  preservation (the axiom's Phase 2/3 design stays future work).

### E — Wrap-up

- Full gates both sides; `graphify update .`; flip
  `docs/implementation-plans/ux-quality-pass/README.md` status to
  implemented (keep per-section outcome notes: what shipped, what deviated).
- Real-browser smoke via the keyless dev server
  (`uv run python -m agentic_calendar.app.web` serves the built SPA): drive a
  failed write → 3-option recovery; a parked replan → banner + picker; a
  recommitment answer → "review updated plan".
- bs-detector audit of the whole branch (convention from past phases); fix
  findings; final memory update
  (`~/.claude/projects/.../memory/ux-quality-pass-plan.md`).

## Kickoff prompt for the next context window (copy-paste)

> Continue implementing the UX quality pass on branch `ux-quality-pass`.
> Read `docs/implementation-plans/ux-quality-pass/HANDOFF.md` first — A/B/C
> tracks are done (11 commits, gates green); follow the handoff exactly for
> the next remaining increment (baseline capture steps if not yet done, then
> D1 → D2 → D3 → D4 → E), one commit per increment, asking me before any
> networked capture run.
