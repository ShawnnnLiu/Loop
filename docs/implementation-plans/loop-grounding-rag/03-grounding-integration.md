# 03 · Grounding Integration (G-G claim assembly + population, G-H end-to-end eval)

The integration seam is already built — `StrategistInput.source_claims`
(`contracts/strategist_input.py:26`), the prompt slot
(`anthropic_adapter.py:826-835` + system rule 5), the live read at
`app/cycle.py:405-412`, and the syllabus validator's claim-reference checks.
What's missing is the producer: nothing populates `env.claim_store`, so
production runs are ungrounded today. This file closes that gap and then
measures it.

## G-G · Deterministic claim assembly → the sanctioned ingestor

**The key design decision (made here, explicitly):** v1 claim assembly is
**deterministic** — no LLM.

- A retrieved chunk becomes a claim as a **bounded verbatim excerpt**
  (the chunk's text, trimmed at sentence boundaries to the contract's size
  expectations) plus provenance: `source_url`, section breadcrumb,
  `date_collected`, `source_published_date` from the corpus document.
- Why not LLM distillation: turning chunks into synthesized `claim_text`
  via a model would create a fifth LLM node class — axiom 01 / CLAUDE.md
  allow exactly four, so that path is a stop-and-ask **amendment**, not an
  implementation detail. Park it as an explicit v2 option: "ClaimExtraction
  node — propose amendment only if verbatim excerpts measurably underperform
  distilled claims in G-H." The eval decides whether it's worth asking.
- The spec's atomicity note already concedes atomicity is semantic, not
  contract-checkable; verbatim excerpts are honest about being excerpts.
  Curation pressure goes into the *manifest* (G-B): prefer sources whose
  sections read as claims (role ladders, interview guides).

**Production path (composition side, not `retrieval/`):**

- `tools/refresh_claims.py`, operator-run: query the pinned snapshot per
  track/company target, assemble raw claim records, feed them through the
  **existing** `SourceClaimIngestor` — the only sanctioned producer, which
  strips and recomputes `source_type`, `confidence_score`, `bucket`,
  `expires_at` (spec: "Contract vs. Kernel Responsibility"). The pipeline
  never writes those fields. Company context (`known_company_domains`,
  `engineering_blog_hosts`) comes from `CompanyTarget`s exactly as axiom 08
  Phase 5 hooks specify.
- Write to the already-wired `SqliteSourceClaimStore`
  (`app/environment.py:306`). Supports `--dry-run` (prints claims + computed
  scores without writing) and reports counts per source type/bucket.
- Corroboration/contradiction links: **v1 leaves them empty except
  exact-duplicate corroboration** (identical normalized excerpt from
  distinct source URLs → mutual `corroborating_claim_ids`). Anything
  fuzzier is similarity-threshold guesswork the deterministic scorer would
  then amplify — out of v1, recorded as an open question.
- Sizing: the store's serving side is curated (below), so claim volume is
  bounded before it ever reaches a prompt.

**Serving-side curation:** the UX pass D1 filter at the strategist call
site (expiry drop, confidence floor, per-company cap, drop-logging) is the
other half of this increment. If D1 shipped, **reuse it untouched** — G-G
just makes the filter finally see non-empty input. If D1 was cut, implement
it here to its HANDOFF spec (`../ux-quality-pass/HANDOFF.md`, D1 bullet 4).

## G-H · End-to-end eval: grounded vs. ungrounded (the actual deliverable)

Reuses the recordings harness exactly as the draft hoped — it exists
(capture tool → committed recordings → `run_llm_eval` → `make eval-gate`).

- **Eval set:** extend the strategist cases in a new
  `eval_set_v3.json` (append-only versioning per axiom 22): each grounded
  case carries a realistic `source_claims` payload drawn from the real
  corpus (claims produced by G-G, pinned in the case); each has an
  ungrounded twin (`source_claims: []` — i.e., today's production).
- **Tier-1 deterministic graders** (new pure functions in
  `llm_nodes/eval.py`, style of `plan_quality_metrics` at `:337`):
  - *citation coverage* — fraction of syllabus units citing ≥1 claim id
    valid in the case's claim set (unknown-id rejection already exists in
    validation; the eval-side rate makes it a before/after number);
  - *claim utilization* — fraction of supplied claims cited at least once
    (detects prompt-stuffing that the model ignores);
  - *high-confidence share* — fraction of citations pointing at
    `high`/`medium` bucket claims (axiom 08's preference order, measured).
- **"Unsupported-claim rate", operationalized honestly:** whether prose
  *content* is semantically supported by cited sources is a judgment call —
  that is **Tier-2 territory**: extend the judge rubric
  (`llm_nodes/eval_judge.py`) with a groundedness score, advisory-only,
  never a gate, exactly like tone/specificity today. The *gateable* proxy
  stays Tier-1 citation coverage. The writeup reports both, labeled.
- **Runs:** capture grounded + ungrounded recordings (networked, ask first,
  cap stated — reuse the capture tool's call-cap pattern), grade both,
  `run_llm_eval --compare`, deltas in the commit message (house
  convention). If the D-track baseline recording exists, it doubles as an
  extra ungrounded reference point.
- **Gate:** once the grounded recording is committed, add its pair to
  `make eval-gate` with floors at measured values (same seeding rule as the
  UX pass HANDOFF step 2).

## Axiom/spec implications

- Axiom 08: gains a sentence that claim assembly is deterministic
  (verbatim-excerpt) in v1 and that LLM distillation requires an axiom 01
  amendment. Nothing else changes — this increment is axiom 08's original
  intent finally exercised.
- `docs/specs/llm-call-log.schema.md` untouched (strategist calls already
  logged); no new node classes; supervisor/routing untouched.

## Test expectations

- Assembly determinism (same snapshot + params → identical claim records
  pre-ingestion); ingestor strips pipeline-supplied score fields (negative
  fixture).
- Exact-duplicate corroboration linking; no fuzzy linking exists (test that
  near-duplicates do *not* link — the restraint is the behavior).
- `refresh_claims --dry-run` writes nothing; live run is idempotent by
  claim identity.
- A golden-style case: populated store → strategist input carries curated
  claims → generated syllabus cites them → validator accepts; and the
  expired-claim case filters pre-prompt (D1's test, now with real data).
