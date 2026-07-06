# 04 · Harness Engineering — Measurable Quality, Invisible Provider Failures

Priority: **fourth in sequence, but §1-2 are prerequisites for validating
everything in files 02 and 03.** The harness is the strongest layer in the
repo — five deterministic validation categories collapsing to typed reason
codes, bounded everything, defense-in-depth calendar writes, dual-enforced
import boundaries, CI-gated schema drift, ~1,463 offline tests. The gaps
cluster in two UX-relevant places: **the eval machinery has never measured
the real prompts**, and **provider failures are handled bluntly enough to
surface as user-visible stalls or wasted retries**.

What already works (do not disturb): the validation stack
(`validation/__init__.py:56-159`, `_summarize_reason` `:177-239`), repair
bounds (`contracts/validation_result.py:25`, `app/cycle.py:140, 768-776`),
the structurally privacy-safe call log (`llm_nodes/call_log.py:50-74`,
`extra="forbid"`, hashes only), calendar-write defense-in-depth
(`calendar_writer/manager.py:188-266, 614-694`), boundary enforcement
(`.importlinter` 16 contracts + grep supplement
`tests/boundaries/test_import_linter_contracts.py`), and CI
(`.github/workflows/ci.yml:25-29` running `make check`).

---

## 1. Capture real recordings and baseline the actual prompts

**Problem (user experience — indirect but decisive).** Every quality claim in
this pass ("few-shot lifted first-try validity," "Sonnet planner reduced
repair rounds") is unverifiable today: the only committed eval recordings are
synthetic fixtures (`backend/evalsets/recordings/fixture_baseline.json`,
`fixture_improved.json`, both `model_name: "recorded-fixtures"`), and
`llm_nodes/eval.py:11-14` honestly admits fixtures "prove the harness, not
model quality." The live `*-v2-2026-06-23` prompts have **never been
measured** — schema-validity, repair-recovery, and post-repair-invalid rates
for the real system are unknown. There is no capture tool: recordings must be
hand-authored.

**Proposal.**
- Build `tools/capture_eval_recordings.py`: runs the real adapters over
  `backend/evalsets/eval_set_v1.json` cases (guarded like
  `tools/llm_smoke.py`'s `_GuardedTransport` cost ceiling, `:107-168`),
  writing an `EvalRecording` per case (attempt 0 + bounded repairs — the
  shape `eval.py:86-97` already defines, `MAX_RECORDED_ATTEMPTS = 3`
  `eval.py:35`).
- Immediately record the **baseline** for the current prompts, commit it, and
  re-record after each change in `02-prompt-engineering.md` (§1 few-shot,
  §2 prose voice, §6 model swaps), comparing via `compare_reports`
  (`eval.py:344-366`, already keyed on `prompt_version`).
- Grow `eval_set_v1.json` beyond 6 cases while at it — at minimum one case
  per repair-prone invariant (cycle in deps, uncovered module, over-capacity)
  and 2-3 prose-tone cases for the reflection/explanation rewrites.

**Why.** This is the difference between *believing* the UX improved and
*knowing* it did. Every subsequent proposal in files 02-03 cites this
section as its measurement plan. Real API calls cost real money — exactly
what the raised ceiling is for.

**Touchpoints.** New `tools/capture_eval_recordings.py` (pattern:
`tools/llm_smoke.py`), `backend/evalsets/`, `llm_nodes/eval.py` (no changes
expected — the harness is ready), `tools/run_llm_eval.py`.

**Axiom/spec implications.** Axiom 22 anticipates exactly this (eval runs on
prompt/model changes; before/after reports required). Capture runs contact
the LLM provider — **networked command, ask-before-run per `CLAUDE.md`**.

---

## 2. Let evals fail something (gate prompt regressions)

**Problem (user experience).** A prompt edit that tanks first-try validity
ships green today: `EvalThresholds` checks a single metric and is explicitly
non-gating ("they never gate CI," `eval.py:141-147`; `threshold_breaches`
`:310-319`), `tools/run_llm_eval.py` always exits 0 (docstring `:12-14`), and
CI never invokes it (`make check` doesn't include eval). Users experience
regressions as slower generation (more repair rounds) and worse plans.

**Proposal.**
- Add `--strict` to `run_llm_eval.py`: nonzero exit when thresholds breach.
- Extend `EvalThresholds` with floors for `schema_validity_rate` and
  `repair_recovery_rate` (values seeded from the §1 baseline, then
  calibrated — matching the repo's "heuristic priors until calibrated" rule).
- CI: a separate job (not inside `make check`) that runs strict eval **over
  committed recordings only** — deterministic, offline, no API calls in CI.
  Recording capture stays a manual, human-triggered step; grading the
  committed recordings gates the merge.
- Revisit axiom 22's "never gate CI" sentence: it predates real recordings.
  The amended rule should distinguish *live-call evals* (never in CI) from
  *recorded-output grading* (deterministic, safe to gate).

**Why.** The whole eval investment (Phase 8) protects the user only if a bad
prompt change can actually be stopped. Grading committed recordings is as
deterministic as the golden tests that already gate CI.

**Touchpoints.** `llm_nodes/eval.py:141-147, 310-319`,
`tools/run_llm_eval.py`, `.github/workflows/ci.yml`, `backend/Makefile`,
**`docs/axioms/22-llm-evaluation-and-observability.md` (amendment —
stop-and-confirm per `CLAUDE.md`)**.

**Axiom/spec implications.** Axiom 22 amendment as above. Observability
still never feeds runtime routing — this gates *merges*, not runs.

---

## 3. Semantic quality graders (measure "good guidance," not just "valid JSON")

**Problem (user experience).** The rubric surface is substring presence +
the 12-word psych denylist (`eval.py:203-213`); only 3 of 6 cases even carry
`required_substrings`. Nothing grades whether a plan's coverage emphasis is
sensible, dependencies are pedagogically ordered, task titles are specific,
or reflection prose is actually warm and useful — i.e., nothing measures the
qualities this version is about.

**Proposal (two tiers, deterministic first).**
- **Tier 1 — deterministic plan-quality metrics** (pure functions over the
  recorded `TaskPlan`): title specificity proxies (distinct titles, presence
  of module-topic terms), dependency-depth distribution, session-length
  variance vs. profile preference, coverage balance across high-priority
  modules. Cheap, objective, CI-safe.
- **Tier 2 — LLM-judge grading of prose nodes** (offline only, in the capture
  tool's orbit, never CI): a judge model scores reflection/explanation
  recordings against the voice spec from `02-prompt-engineering.md §2`
  (tone, specificity, actionable next step) on a small fixed rubric. Judge
  outputs are advisory numbers in the eval report, never gates and never
  runtime signals.
- Both report through the existing `NodeMetrics`/`EvalReport` path
  (`eval.py:99-135`) so `compare_reports` covers them.

**Why.** "Friendly" and "good guidance" need a number, or the model/prompt
experiments in file 02 will be judged by vibes. Tier 1 alone makes the
Planner experiments measurable.

**Touchpoints.** `llm_nodes/eval.py` (grader plug-in point around
`_grade_rubric` `:203-213`), new judge integration living in `llm_nodes/`
(the only LLM-import zone; judge is a new *use*, not a new node class),
`backend/evalsets/eval_set_v1.json` (rubric fields).

**Axiom/spec implications.** **Requires a deliberate decision**: axiom 01
allows exactly four LLM node classes; an eval-only judge is offline tooling,
not a workflow node, but the boundary deserves an explicit axiom-22/ADR
sentence ("LLM-judge grading permitted in offline eval tooling; its scores
are advisory and never control-plane"). Stop-and-confirm before building
Tier 2. Tier 1 has no implications.

---

## 4. Adapter resilience: timeout, backoff, error discrimination

**Problem (user experience).** Three bluntness issues in
`anthropic_adapter.py` turn provider weather into user-visible stalls:
- **No explicit timeout** — `messages.create` (`:138-144`) passes no
  `timeout=`; a hung call is bounded only by the SDK's generous default while
  the user watches the generation spinner.
- **No backoff** — retries are immediate `continue` (`:338`); during a rate
  limit or blip, all retries burn instantly and the run fails when waiting
  2-4 seconds would have succeeded.
- **No error discrimination** — every `anthropic.APIError` collapses to one
  retryable `TransportError` (`:145-147`): a 401/400 (permanent) is retried
  pointlessly, a 429/529 (transient) gets no patience, and the log records
  both as generic `LLM_CALL_FAILED`.

**Proposal.** Set an explicit per-call timeout budget in `AdapterConfig`
(seeded from observed p99 latency in the call log once §5 lands); add
exponential backoff with jitter between SDK retries (deterministic-seeded or
injected via the existing `Clock` for testability); split the error taxonomy
into retryable/non-retryable with distinct reason codes (e.g.
`LLM_AUTH_FAILED`, `LLM_RATE_LIMITED` — added to
`contracts/reason_codes.py`), so `ERROR_REQUIRES_USER` explanations can say
something true and specific (pairs with `01-loop-engineering.md §5`).

**Why.** "Reliable" at the seam where it's hardest: the user should never
distinguish a provider hiccup from normal generation, and when something is
genuinely wrong (expired key), the system should say so instead of retrying
into a generic failure.

**Touchpoints.** `anthropic_adapter.py:129-147` (transport), `:183-199`
(config), `:338-372` (retry loop), `contracts/reason_codes.py` (+ spec/schema
regen per the contract rules), `tests/llm_nodes/test_anthropic_adapter.py`
(FakeTransport error scripting).

**Axiom/spec implications.** New reason codes ⇒ spec-first: update the
relevant `docs/specs/`, contract model, fixtures, `make schemas`. Retry caps
stay `le=2` — backoff changes pacing, not budget.

---

## 5. A reader over the SQLite call log (see what users experience)

**Problem.** Rows the real cycle writes to `SqliteLlmCallLogStore`
(`llm_nodes/sqlite_call_log.py:48-86`) have no shipped reader:
`tools/trace_llm_calls.py` and `tools/run_llm_eval.py --calls` read only JSON
files produced by `llm_smoke --calls-out`. Post-deploy questions that decide
UX priorities — real p50/p99 generation latency, repair-round frequency per
node, cost per run, whether `cache_hit` flipped true after
`03-context-engineering.md §1` — are currently unanswerable without ad-hoc
SQL.

**Proposal.** Teach `trace_llm_calls.py` to read the SQLite store directly
(`--db` flag) and add a small `tools/llm_stats.py` aggregate view: per-node
validity/repair/latency/cost over a date range, plus simple threshold
warnings (e.g. p99 latency, cost per run) printed — not enforced — as the
observability counterpart of §2's gates. Deterministic read-only tooling in
`tools/`, no new dependencies.

**Why.** Every latency/quality claim in this pass needs production numbers,
and dogfooding (the current phase of the project) is exactly when this data
is being generated and lost.

**Touchpoints.** `tools/trace_llm_calls.py`, new `tools/llm_stats.py`,
`llm_nodes/sqlite_call_log.py` (read queries), `docs/axioms/22-*` (note the
tooling).

**Axiom/spec implications.** None — read-only, stays in `tools/` (allowed
LLM-adjacent zone), observability still can't feed runtime routing
(import-linter already enforces this).

---

## Deliberately deferred

- **Deterministic checkers for `user_profile` / `motivation_profile`**
  (`validation/__init__.py:11-13` marks them deferred): both arrive via
  onboarding forms with Pydantic parse-time rejection; no LLM produces them,
  so the missing repair loop has no UX consequence today.
- **Cost alerting/enforcement**: with the ceiling raised, §5's printed
  warnings suffice; hard budget enforcement (beyond `llm_smoke`'s guard)
  would fight this version's goal.
