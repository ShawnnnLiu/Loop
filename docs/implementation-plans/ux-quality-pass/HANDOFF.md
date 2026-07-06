# UX Quality Pass — Implementation Handoff

Status as of **2026-07-04**, branch **`ux-quality-pass`** (off `deleted-event-memory`,
whose PR is still open). **A + B + C tracks are COMPLETE — 11 commits, all gates
green** (backend `make check` 2691, frontend typecheck/lint/test(81)/build,
`make eval-gate`, boundaries 16 kept). **D3 is also DONE** (12th commit, same
gates green; see the D3 section for what changed and what its landing means for
capture choreography). **D1 + D2 + D4 + E remain** and are specified below
for implementation in fresh context windows, one increment per session if needed.

Read order for a fresh session: this file → `README.md` + the relevant numbered
plan file (`02-…`/`03-…`) → the code anchors named per increment.

**Session split (2026-07-05):** `SESSION-SPLIT.md` carves the remaining work
into five one-context-window pieces (baseline+D1a / D1b+capture / D2 /
D4 / E) with per-piece kickoff prompts — start each fresh session from there.

## Approved decisions (user, 2026-07-04 — do not re-ask)

1. **Axiom 09 amendment + ALL THREE model upgrades** (Planner, Reflection,
   Explanation → Sonnet-tier now; Strategist stays Opus). → D3
2. **Axiom 22 amendment + CI gate** over committed recordings. → **DONE** in C3.
3. **Graders Tier 1 + Tier 2** (deterministic + offline LLM-judge). → **DONE** in C2.
4. **Live captures: agent runs them, asking before each run.** Baseline capture
   is currently **blocked on `ANTHROPIC_API_KEY`** (see next section).

## ✅ DONE 2026-07-05 — baseline capture (was: ⏸ IMMEDIATE NEXT STEP)

Ran as specified below (labeled `baseline-2026-07-05`, the actual date):
16 calls, ~$0.1591; schema validity 1.0000, repair recovery n/a, rubric
1.0000; judge scores recorded (explanation_repair_exhausted tone=2 is the
D2 target). Gate seeded with measured floors. Commit `f869fef`. **D1a is
also done** (commit `42edd48`, prompts at strategist-v3/planner-v3
2026-07-05); the section below is kept for the run/grade/seed recipe that
future captures reuse.

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
**D3 (Sonnet swap) landed 2026-07-04 BEFORE any capture ran** (baseline was
blocked on the API key), so there is no pre-Sonnet baseline to record and no
separate `sonnet-…` capture step anymore. The first capture IS the baseline
and will record the Sonnet-tier models — that is fine: D1/D2 prompt changes
are measured on the model tier they will ship on. Choreography now: baseline
capture first (per the section above), then after D1 → label
`fewshot-YYYY-MM-DD`; after D2 → `voice-YYYY-MM-DD` (with `--judge`).
Compare each via `run_llm_eval --compare <previous report>` and put the
deltas in the commit message. Report the per-run cost from `call_aggregates`
in the baseline commit message (this absorbs D3's deferred cost-delta
measurement). Note: a re-capture's recording will trip the prompt-bytes
test's sibling expectation only if versions weren't bumped — bump
`prompt_version` constants + the pinned hashes in
`tests/llm_nodes/test_prompt_versions.py` in the SAME commit as any prompt
edit.

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
- **D1b's claim cap keys on the source-url HOST, not "company"** — company
  identity is not a contract field (it exists only at ingestion via
  operator-declared domains), so the deterministic per-company cap is a
  per-source-host cap (`www.` stripped; subdomains are distinct buckets;
  host-less URLs share one bucket).
- **D1b curation knobs are a `claim_curation` tuning section**
  (`min_confidence=0.30`, `max_per_host=5`), not bare constants — heuristic
  priors journal through the axiom-07 threshold change log like every other
  deterministic knob. The floor sits deliberately below the 0.35
  personal-anecdote base: axiom 08 admits anecdotes "labeled low
  confidence", so the default floor must not silently ban them.

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

### D3 — Axiom 09 amendment + all-three Sonnet swap — ✅ DONE 2026-07-04

Implemented as specified (plan 02§6, user-approved). What shipped:

- Axiom 09 amended first: Sonnet-tier line ($3/$15 sticker deliberately, not
  the intro $2/$10 that lapses 2026-08-31), all cost tables regenerated
  (~$1.70/mo expected, sensitivity $0.85–$3.40), **monthly cap raised
  $4 → $8** to preserve the recorded ~5× headroom intent (hourly cap is
  call-count-based, unchanged), plan-pricing margin re-checked (5–12% of
  revenue — still fine), change-log entry + tokenizer (+~30%) caveat added.
- `PLANNER_CONFIG`/`REFLECTION_CONFIG`/`EXPLANATION_CONFIG` →
  `claude-sonnet-5` at $3/$15; Strategist stays `claude-opus-4-8`.
- **Thinking pinned off at the transport** (`thinking={"type":"disabled"}` in
  `AnthropicMessagesTransport.complete`) — resolves gotcha (a) for ALL
  callers including the 256-cap eval judge; enabling thinking is a future
  eval-driven decision. Asserted in the transport regression test.
- Cache-minimum comment updated (sonnet-5 unlisted in the provider table —
  verify via cache_read tokens on the first capture); config-block comment
  rewritten; `test_happy_path…` model + cost-math assertions updated.
- No prompt bytes changed → no `prompt_version` bumps; prompt-bytes pinned
  hashes untouched.
- **Measurement deferred** (capture still blocked on API key): the first
  baseline capture doubles as the Sonnet measurement — see the re-capture
  choreography note above.

### D4 — Prior-plan-aware replans (plan 03§3; no capture needed) — ✅ DONE 2026-07-05

Implemented as specified (commits `b198179` stage 1, `88edd57` stage 2).
Deviations/decisions to know:

- **Stage 1 also passes `replan_mode`** (typed `RecoveryAction`) beside
  `prior_plan_tasks` — "preserve unless affected by the replan reason" is
  under-determined if the prompt never learns the reason; the mode is the
  typed driver (scope_reduction / extend_timeline are the only LLM-routed
  modes). Planner at `planner-v5-2026-07-05`.
- **The diff is recomputed on read, not persisted** — `DraftView.plan_diff`
  (compact `PlanDiffView`) derives from the two persisted plan versions on
  every `/api/draft` fetch; the spec's `plan_diff_log` persistence stays
  future work. `ProposeResult.plan_diff` carries the full `PlanDiff`
  contract on replan continuations (reason maps RECALIBRATION →
  USER_DURATION_CALIBRATION, else DRIFT_REMEDIATION, uniformly — code
  cannot attribute per-field causes in a regenerated plan).
- **Title-only rewording counts as "changed", never "preserved"**, but the
  plan-diff contract has no change type for it — it appears in the change
  lines and counts only (vocabulary gap documented in `planning/diff.py`;
  extending the contract enum is a future spec-first change if wanted).
- **`DraftView.plan_diff` covers any parented draft** (replan,
  recalibration, drop), not just replans — the Approval line shows for
  drops too, consistently.
- Axiom 20 carries the interim-step note (context anchoring + diff
  surfacing precede validator-enforced preservation).

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
> and D3 are done (12 commits, gates green); follow the handoff exactly for
> the next remaining increment (baseline capture steps if not yet done, then
> D1 → D2 → D4 → E), one commit per increment, asking me before any
> networked capture run.
