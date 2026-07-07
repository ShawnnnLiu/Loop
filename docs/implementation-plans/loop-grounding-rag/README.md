# Loop Grounding Layer — Retrieval-Backed Source Claims

Status: **planned, not started.** Runs after the UX quality pass completes
(see Sequencing) and, per the source draft, second to the out-of-repo
fine-tuning project.

Provenance: refined 2026-07-04 from
`../generated-plans-ideas/Loop-Grounding-Layer-RAG-Project-Plan.docx` (a
web-agent draft with less repo context). The draft's core inversion is kept
verbatim — **build the grounding layer, not the counselor; the deliverable
is the eval, not the app** — but the plan below is re-based on what already
exists in this repo, which is much more than the draft knew.

## What already exists (the draft planned to build much of this)

Verified 2026-07-04 on branch `ux-quality-pass`:

- **The whole claim contract stack**: axiom 08 (`docs/axioms/08-rag-source-claims.md`),
  `docs/specs/source-claim.schema.md`, `contracts/source_claim.py`, and the
  `source_claims/` kernel (URL-rule classification, deterministic confidence
  scoring + priors, expiration, ingestion, SQLite + in-memory stores) — all
  built and tested in Phase 5.
- **The injection path**: `StrategistInput.source_claims`
  (`contracts/strategist_input.py:26`), serialized into the strategist
  prompt (`llm_nodes/anthropic_adapter.py:826-835`), with system-prompt rule
  5 instructing citation via `source_claim_ids`; the syllabus validator
  already rejects unknown/expired claim references.
- **The live wiring**: `app/cycle.py:405-412` reads
  `env.claim_store.all()` and passes claims to the strategist;
  `app/environment.py:306` wires `SqliteSourceClaimStore` in production.
- **The eval machinery** (Phase 8 + UX pass C): eval sets with real inputs
  (`backend/evalsets/eval_set_v2.json` — its strategist case already carries
  `source_claims`), capture → committed recordings → deterministic
  re-grading, `make eval-gate` in CI, Tier-1 graders (`llm_nodes/eval.py`),
  Tier-2 advisory judge (`llm_nodes/eval_judge.py`).
- **A budget line waiting to be used**: axiom 09 carries an embedding price
  assumption ("~$0.02 per 1M tokens; **not yet exercised**") and an
  onboarding line item "RAG retrieval (8 queries)".

**And the punchline the draft couldn't see:** nothing populates the claim
store. `SourceClaimIngestor` has zero production call sites; the live
strategist always runs with `source_claims=[]`. The evidence path is
complete and *inert*. So:

1. This project is **not** "integrate retrieval into Loop" — the integration
   seam is done. It is: build the corpus + retrieval pipeline that *feeds*
   the existing sanctioned producer, and measure the effect.
2. The "ungrounded" arm of every before/after eval is simply **the product
   as it runs today**. The baseline is free and honest.

## Corrections to the draft (axiom conflicts it would have hit)

- **"Claims with confidence" — confidence is never assigned by the pipeline,
  an LLM, or a reranker.** The `source_claims` ingestor is the only
  sanctioned producer of `source_type` / `confidence_score` / `bucket` /
  `expires_at`; it strips those fields from any input and recomputes them
  (spec: "Contract vs. Kernel Responsibility"). Retrieval supplies text +
  provenance + dates; scoring stays deterministic (axiom 08).
- **Claim extraction cannot silently become a fifth LLM node.** Turning
  chunks into distilled `claim_text` via a model would add an LLM node class
  beyond the four allowed (CLAUDE.md, axiom 01) — a stop-and-ask amendment.
  v1 therefore uses **deterministic claim assembly** (verbatim bounded
  excerpts with provenance); an extraction node is an explicitly-gated
  later option. See `03-…`.
- **Anthropic has no embeddings endpoint.** Dense retrieval means a new
  provider (e.g. Voyage) or a local model — either way a new dependency and
  an ask-first gate. So BM25 via SQLite FTS5 (stdlib, matching the Phase 9
  SQLite discipline) is the v1 retriever, and dense/hybrid is a measured
  ablation, not the foundation. The draft's own "hybrid vs. BM25-only is a
  headline ablation" framing survives — inverted into BM25-first.
- **Retrieval eval is stronger than the draft assumed.** With no LLM in the
  retrieval path and a pinned corpus snapshot, recall@k / MRR / nDCG are
  pure functions over checked-in data — they run as ordinary CI-gating
  tests, no recordings needed. Only the end-to-end arm (generation quality)
  needs the capture/recording machinery.

## Scope (unchanged from the draft)

In: 5–10 career tracks (start 3: SWE, MLE, AI engineer), a deliberately
curated corpus (hundreds of docs), chunking → BM25 (→ hybrid → rerank as
ablations) → citation-attached claims → strategist injection → two-layer
eval. Out (scope guards, all kept): open-web crawling at scale, a counselor
UI, hundreds of majors, admissions advice. The "Axiom" counselor vision gets
one sentence in the writeup, nothing in the code.

## Files / increments (one commit per lettered increment)

| File | Increments |
| --- | --- |
| `01-corpus-and-contracts.md` | G-A specs + contracts + registry · G-B ingestion CLI (fetch gated) |
| `02-retrieval-pipeline.md` | G-C chunking · G-D FTS5 retrieval + labeled query set + retrieval eval gate · G-E hybrid embeddings (gated) · G-F reranker (gated) |
| `03-grounding-integration.md` | G-G claim assembly + store population + curation · G-H end-to-end grounded-vs-ungrounded eval |
| `04-evaluation-and-writeup.md` | G-I freshness + remaining tracks · G-J writeup + eval appendix |

Session sizing: `SPLITS.md` groups these into 5 fresh-context sessions of
≤300k tokens each, with per-split kickoff prompts.

## Sequencing

- **After the UX quality pass merges.** D1 (claim curation) edits the exact
  call site this project feeds (`app/cycle.py` `_propose_fresh` claims line)
  — landing both in parallel guarantees a conflict, and D1's
  pre-serialization filter (expiry, confidence floor, per-company cap) is
  the serving-side half of this project. If D1 somehow doesn't ship, G-G
  absorbs it (`03-…` says how).
- **Cross-plan consumer:** the `resume-intake-onboarding` plan's skill
  taxonomy (`../resume-intake-onboarding/06-skill-taxonomy.md`) shares the
  closed `CareerTrack` enum with G-A's corpus documents, and its gated
  increment RI-F enriches taxonomy entries with corpus evidence (alias
  occurrence counts over a pinned snapshot via the G-D FTS5 index) once
  G-A–G-D exist. Evidence annotates vocabulary entries; it never creates
  them — and corpus content remains public-web only (no résumé text), per
  the axiom-08 note above.
- Branch from `main`; the usual conventions apply: one commit per increment,
  spec-first for every contract (`docs/specs/` before Pydantic before
  fixtures before `make schemas`), `.importlinter` updated with any new
  package, gates green per commit, `graphify update .` after code changes.
- The `cache/` package stays **unwired** (the ux-pass honesty note calls it
  a realized-but-unwired kernel "awaiting the RAG phase"): this phase is
  about *fresh* evidence, and response-caching freshness-sensitive syllabi
  remains unattractive. Revisit only if grounded generation latency hurts;
  its claim-expiry invalidation hooks are ready if so.

## Ask-user gates (standing, per the operating contract)

- Every corpus **fetch** is a networked command → ask before each ingestion
  run (same protocol as eval captures in the UX pass HANDOFF).
- New dependencies (embeddings SDK or local model, reranker, any HTML
  parser beyond stdlib) → ask before adding, with the specific package and
  why. G-E/G-F do not start without this.
- End-to-end captures cost real API money → ask before each, with the cap.

## Definition of done (kept verbatim from the draft)

A recruiter can read one page and see (a) retrieval metrics on a labeled
set, (b) a measured drop in unsupported claims in generated plans, and
(c) an honest ablation showing which components mattered. If any of the
three is missing, it isn't done — it's a demo.
