# 03 · Context Engineering — Memory, Goal-Awareness, and Latency

Priority: **third.** The context layer decides whether the system *feels like
it knows the user*. Today it has excellent hygiene (nothing leaks in that
shouldn't) but weak memory (signal it already paid for is thrown away) and no
input curation (noise goes in unbounded).

Where everything lives: context assembly is entirely in
`backend/src/agentic_calendar/llm_nodes/anthropic_adapter.py`
(strategist `:645-676`, planner `:705-772`, reflection `:799-825`,
explanation `:852-870`), gathered at call sites in
`backend/src/agentic_calendar/app/cycle.py` (`:363-383`, `:415-424`,
`:514-521`, `:1623-1634`, `:406-408`, `:727-729`). Everything is canonical
sorted JSON (`_canonical_json`, `:262-263`).

What already works (do not disturb): résumé fencing and non-persistence
(`:659-669`; `call_log.py` `extra="forbid"`); **no external calendar text
ever enters a prompt or store** (free/busy intervals only,
`routes_cycle.py:151-161`; reconcile reads instants only,
`cycle.py:1146-1147`); telemetry never reaches a prompt (only typed
`DriftEvent`s reach Reflection); minimal surface per node (Explanation sees
only a `ValidationResult`; Planner receives only typed scalars — no free-text
injection path, `:727-745`); COMPLETED ∪ DROPPED disposition threading into
planner exclusions (`cycle.py:569-580` → `:746-751`), with EVENT_DELETED
deliberately withheld (`cycle.py:640-655`, axiom 06).

---

## 1. Turn on prompt caching (latency is UX)

**Problem (user experience).** No `cache_control` breakpoint exists anywhere
in `src/` — the static system prompts are re-sent, re-processed, and re-billed
on **every call and every repair retry**. The adapter even instruments
`cache_read_input_tokens` and sets `LlmCallLog.cache_hit`
(`anthropic_adapter.py:175, 492, 513`) — a flag that can never be true. The
user feels this as generation-screen wait time, especially across repair
rounds.

**Proposal.** Add a `cache_control: {"type": "ephemeral"}` breakpoint on each
system prompt in `AnthropicMessagesTransport.complete`
(`anthropic_adapter.py:138-144`). After `02-prompt-engineering.md §1-2` the
system prompts get longer (exemplars), which makes caching *more* valuable,
not less. Verify via the already-logged `cache_hit` flag flipping true on
repair rounds.

**Why.** Even with a raised cost ceiling, time-to-first-plan is a core
smoothness metric, and repair retries currently pay full prompt-processing
latency each round. This is a one-line-per-call change with existing
observability.

**Touchpoints.** `anthropic_adapter.py:138-144`;
`tests/llm_nodes/test_anthropic_adapter.py` (FakeTransport signature).

**Axiom/spec implications.** Axiom 18 (caching strategy) *supports* caching
stable prompt scaffolding; nothing user-personal is being cached by the
provider beyond the request itself. Worth one sentence in axiom 18 noting
provider-side prompt caching is in scope.

---

## 2. Persist reflection summaries and feed them back (continuity of voice)

**Problem (user experience).** Reflection prose is generated on drift
(`cycle.py:1626-1634`), returned once as `IngestResult.reflection`
(`app/results.py:200`), rendered by the SPA — and then discarded. Verified:
no store persists it and no later prompt receives it. The product can never
say "last week you tended to run over on system-design tasks; this plan
shortens those blocks" — the sentence *it already wrote* is gone.

**Proposal.**
- Persist `ReflectionSummary` (append-only store keyed by run/plan-version,
  same pattern as dispositions in `disposition/`).
- Feed the last N (2-3) summaries into two places:
  - the **Reflection node's own context** (`anthropic_adapter.py:799-825`),
    so successive reflections read as a continuing conversation rather than
    amnesiac observations;
  - the **replan path's Planner context** as a small advisory block alongside
    `excluded_tasks` (`:746-751`) — behavioral hints ("sessions over 60min
    frequently missed") the Planner may use for session sizing.
- Surface the history in the SPA (Accountability screen has room:
  `frontend/src/screens/Accountability.tsx`).

**Why.** This is the cheapest path to "the system knows me." The signal is
already generated and already paid for; only storage + re-injection are
missing. Continuity across weeks is what separates a coach from a report.

**Touchpoints.** New store module (pattern: `disposition/`),
`app/cycle.py:1626-1634` (persist), `anthropic_adapter.py:799-825` and
`:705-772` (inject), `app/environment.py:200-232` (wire store),
**new spec file in `docs/specs/`** for the persisted shape (spec-first),
`frontend/src/screens/Accountability.tsx`.

**Axiom/spec implications.** Reflection stays LLM-explains-only — the
summaries must enter prompts as *advisory context*, never parsed into
control-plane state (axiom: no LLM prose controls workflow state). The psych
denylist already gates what gets persisted.

**Open questions.** Retention window (recommended: last 3 summaries, plan
version-scoped) and whether the user can delete them (recommended: yes —
they're derived personal data).

---

## 3. Prior-plan-aware replans (stop reshuffling what the user already accepted)

**Problem (user experience).** On replan, the Planner regenerates from the
frozen syllabus plus an **id-only** exclusion list (`cycle.py:415, 514`) — it
never sees the previous `TaskPlan`. So a replan can rename, resize, and
reorder every surviving task even when only one module drifted. To the user,
the plan they curated and approved gets shuffled arbitrarily — the drag
adjustments and familiarity they invested are destroyed. The code already
acknowledges the gap: reproducing a dropped task is merely *logged*
(`cycle.py:711-715`, "advisory exclusion only … partial regen is Phase 2/3"),
and `docs/axioms/20-partial-syllabus-regeneration.md:46` specs a constrained
delta-regeneration prompt that was never implemented.

**Proposal (staged, lighter than full axiom-20 partial regen).**
- Stage 1 (context-only): include the prior `TaskPlan` (or the surviving
  subset) in the replan Planner context with the instruction to **preserve
  task ids, titles, and durations for tasks unaffected by the replan reason**,
  changing only what the recovery mode requires. Deterministic validation is
  unchanged — the model is merely anchored.
- Stage 2 (deterministic diff surfacing): compute a plan-version diff
  (old vs new) deterministically and show it at approval ("3 tasks changed,
  14 preserved"), so the user reviews the *delta*, not a wall of blocks.
  `PlanVersion.generation_history` (`cycle.py:796-813`) already stores
  lineage for this.
- Full axiom-20 delta-regeneration (validator-enforced preservation) remains
  future work; stage 1+2 capture most of the UX value.

**Why.** Approval fatigue is the biggest friction in the core loop; a replan
that visibly respects what the user already approved is dramatically easier
to re-approve. "Smooth" here means *the plan feels stable under adjustment*.

**Touchpoints.** `app/cycle.py:437-475` (`_propose_replan`), `:514-521`
(planner call), `anthropic_adapter.py:705-772` (context block),
`planning/` (diff helper), `frontend/src/screens/Approval.tsx` /
`ScheduleReview.tsx` (diff view), `docs/axioms/20-*` (mark stage 1 as its
interim step).

**Axiom/spec implications.** Axiom 20 is explicitly the home for this;
stage 1 needs a note there that context-anchoring precedes validator-enforced
preservation. Plan immutability (versions, never mutation) is untouched.

**Open questions.** Token cost of embedding the prior plan (bounded: plans
are small relative to the 16k output budget; measure with the call log).

---

## 4. Give the Planner the user's goal (guidance that sounds like *their* goal)

**Problem (user experience).** The Planner receives exactly six derived
scheduling scalars (`anthropic_adapter.py:727-745`) — never `goal`,
`target_role`, `target_companies`, or `known_weaknesses`. Task titles and
emphasis therefore cannot reflect *why* the user is studying. The audit
called this "defensible" under cost discipline (those fields shaped the
syllabus upstream); under a guidance-quality goal it's a gap — generic task
titles read as template output, not coaching.

**Proposal.** Add a small typed block to the Planner context — `goal`,
`target_role`, `known_weaknesses` (typed fields from `UserProfile`, not free
text beyond what onboarding already validated) — with instructions to use it
for task titling/emphasis only, not for structure. Structure remains governed
by the syllabus + validators.

**Why.** "Prepare STAR stories for Stripe behavioral rounds" and "Behavioral
prep session 2" are the same task structurally; only one feels like guidance.
Cheap tokens, direct perceived-quality lift.

**Touchpoints.** `anthropic_adapter.py:705-772` (context), `:554-577` (system
prompt note), `app/cycle.py:415-424, 514-521` (pass profile),
`docs/specs/` planner-input contract if one exists (spec-first check),
`tests/llm_nodes/test_anthropic_adapter.py` (context-block assertions).

**Axiom/spec implications.** None structural — validation still gates
everything. Keep the block typed-fields-only to preserve the "no free-text
injection into Planner" property the audit praised.

---

## 5. Curate source claims before they reach the Strategist

**Problem (user experience).** `claims = list(env.claim_store.all())`
(`cycle.py:375`) — every claim, unfiltered: no confidence floor, no top-N, no
expiry check before serialization (expiry is only enforced by the
*post-generation* syllabus validator, `cycle.py:387-393`, so stale
`claim_text` still steers and pollutes generation, then causes a rejection +
repair round if cited). Noise in → noise out: weak or expired claims degrade
syllabus quality and can cost a full repair cycle.

**Proposal.** A deterministic pre-serialization filter at the call site:
drop expired claims (`SourceClaim.is_expired` already exists), apply the
deterministic confidence floor (scoring already exists in
`source_claims/scoring.py` / `priors.py` — reuse, don't re-score), and cap
per-company claim count with highest-confidence-first ordering. Log what was
dropped (count + reason) for auditability.

**Why.** Better guidance *and* fewer avoidable repair rounds. Determinism is
preserved — this is a filter, not a ranking model.

**Touchpoints.** `app/cycle.py:363-383` (call site),
`source_claims/` (reuse scoring/expiration), tests in
`tests/source_claims/` + a golden scenario where an expired claim is
filtered pre-prompt rather than rejected post-generation.

**Axiom/spec implications.** Axiom 08 (source confidence is deterministic) is
upheld — the filter uses the deterministic scores. Axiom 18's "do not cache
expired claims" spirit extends naturally to "do not prompt with them."

---

## 6. Decide the fate of the `cache/` package (housekeeping)

**Problem.** The axiom-18 `cache/` package (keys, store, cohort,
invalidation) is complete but **unwired**: no `Cache` in `AppEnvironment`
(`app/environment.py:200-232`), no construction in `build_environment`, no
reference from adapter or cycle; only `tools/export_schemas.py` and
`tools/inspect_cache.py` touch it. Its docstring advertises a Strategist
short-circuit that never runs (`cache/__init__.py:6-7`).

**Proposal.** With the cost ceiling raised, response-caching for freshness-
sensitive syllabi is *less* attractive, not more. Recommended: **do not wire
it in this pass** — instead update `cache/__init__.py` and axiom 18 to state
plainly that the package is a realized-but-unwired kernel awaiting the RAG
phase, so future audits stop re-flagging it. (Alternative, if generation
latency remains painful after §1: wire only the syllabus-reuse short-circuit
for identical `StrategistInput` hashes — deterministic, safe, invisible.)

**Why.** An advertised behavior that never runs is a bs-detector magnet and a
maintenance trap; one honest paragraph resolves it.

**Touchpoints.** `cache/__init__.py:6-7`, `docs/axioms/18-caching-strategy.md`.

**Axiom/spec implications.** Doc-only under the recommended option.

---

## Deliberately *not* proposed: input token budgets

The audit found no input-side token counting anywhere (verified — no
`count_tokens`/truncation in `llm_nodes/` or `app/`). Under the previous cost
posture that was a gap; under this version's posture, **rich context is the
point** — §2, §3, §4 deliberately add input tokens. The protections that
matter are targeted curation (§5) and output-truncation detection, which
already exists (`stop_reason == "max_tokens"` retry,
`anthropic_adapter.py:377, 398-421`, with the 16k budget rationale at
`:202-210`). Add a simple input-size log field only if §2/§3 push prompts to
sizes worth watching.
