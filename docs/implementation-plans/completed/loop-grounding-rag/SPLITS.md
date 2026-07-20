# Session Splits — ≤300k tokens per fresh-context session

Status: sizing companion to `README.md`. Each split below is one fresh
Claude Code session (clean-context handoff convention), budgeted to stay
at or under **300k total session tokens** — reads, edits, test iterations,
and gate runs included.

## Budget model (heuristic priors — recalibrate after Split 1)

- **Fixed per-session overhead: ~50k.** CLAUDE.md + AGENTS.md + the plan
  docs + relevant axioms/specs + code exploration before the first edit.
  Every fresh session pays this, which is why increments are grouped
  rather than run one-per-session.
- **Per-increment cost** scales with: new specs/contracts (spec → Pydantic
  → fixtures → `make schemas` → tests is the expensive loop), new region
  packages (`.importlinter`, parametrized store suites), and eval/gate
  plumbing. Estimates below are ranges; the high end is the planning
  number.
- These are priors in the axiom-08 sense: unverified until Split 1
  actually runs. If Split 1 lands far off its estimate, rescale the rest
  before starting Split 2.

## Overflow rule (why the ceiling is safe)

Every increment is a commit boundary (one commit per lettered increment,
gates green per commit). If a session approaches budget mid-split, stop at
the last green commit and start a fresh session with the same split's
kickoff prompt plus "G-<x> is already committed; resume at G-<y>". No
split ever needs to land atomically.

## The splits

| Split | Increments | Plan docs | Est. total | Notes |
| --- | --- | --- | --- | --- |
| 1 | G-A specs/contracts/registry · G-B ingestion CLI | `01-…` | ~260k (50 + 130 + 80) | Heaviest contract work; fetch runs are ask-first |
| 2 | G-C chunking · G-D FTS5 + query set + retrieval gate | `02-…` §G-C/G-D | ~240k (50 + 60 + 130) | Mid-split user checkpoint: hand-labeling queries |
| 3 | G-E hybrid embeddings · G-F reranker — **conditional** | `02-…` §G-E/G-F | ~240k (50 + 110 + 80) | Entirely gated; may shrink to G-E only or be skipped |
| 4 | G-G claim assembly + population · G-H end-to-end eval | `03-…` | ~290k (50 + 110 + 130) | Tightest split — fallback boundary after G-G's commit |
| 5 | G-I freshness + tracks · G-J writeup | `04-…` | ~200k (50 + 90 + 60) | Mostly reporting + prose; cheapest |

Splits 1 → 2 → 4 → 5 are the mandatory spine. Split 3 slots between 2 and
4 only if the user approves an embeddings provider; skipping it changes
nothing downstream (G-G queries whatever retriever exists — BM25-only is
the shipped v1 posture).

## Split 1 · Corpus & contracts (G-A, G-B) — ~260k

- **Scope:** `corpus-document` + `corpus-snapshot` specs, contracts,
  valid/invalid fixtures, `make schemas`; new `retrieval/` region
  (`.importlinter` entry, imports `contracts/` + `common/` only);
  `CorpusRegistry` over SQLite with the parametrized in-memory twin suite;
  axiom 08 "corpus registry" subsection; `tools/ingest_corpus.py` with
  manifest, dry-run, fetch caps; 3-track starter manifest (SWE, MLE, AI
  engineer, ~30–60 docs each).
- **Cost drivers:** two full spec-first loops + a new region package
  (G-A ~130k); the CLI with faked-fetch tests (G-B ~80k).
- **Mid-split gates:** every live ingestion fetch is networked → ask
  first. The `CareerTrack` enum may already exist if a
  `resume-intake-onboarding` branch landed first — check before creating.
- **Exit state:** 2 commits, `make check` green, a registered 3-track
  corpus + pinned first snapshot on disk (or dry-run-only if the user
  defers the live fetch — that blocks G-D labeling, say so at handoff).

## Split 2 · Retrieval core + eval gate (G-C, G-D) — ~240k

- **Scope:** `retrieval/chunking.py` with `ChunkingParams` on the
  snapshot, byte-identical re-chunk property test; FTS5 index + feature
  detection (typed setup error); `retrieval-query`/`retrieval-result`
  specs + contracts; determinism tie-break; `retrieval_queries_v1.json`
  labeled set; `retrieval/eval.py` recall@k / MRR / nDCG with
  hand-computed fixtures; `make retrieval-eval` CI gate + broken-floor
  harness proof.
- **Cost drivers:** G-D is a second double-spec loop plus eval plumbing
  (~130k); G-C is small (~60k).
- **Mid-split user checkpoint:** the ~50–100 query labels are
  hand-labeled by the user against the pinned snapshot — the session
  drafts candidates, the user judges. Budget the back-and-forth, not just
  the file write.
- **Exit state:** 2 commits, `make retrieval-eval` green with floors
  seeded from the first measured run.

## Split 3 · Gated ablations (G-E, G-F) — conditional, ~240k if both run

- **Scope (only after the provider ask):** embedding transport in
  `llm_nodes/` (sibling of `AnthropicTransport`, call-logged, never
  through `_GenerationEngine`); `content_hash`-keyed vector cache in
  SQLite; RRF fusion; hybrid-vs-BM25 ablation table in the commit message.
  G-F only if hybrid leaves measured headroom, with the
  quality-delta-per-ms report.
- **Session opens with the gate, not code:** present Voyage-vs-local (and
  rerank options for G-F) and stop until the user decides. If declined,
  the split's deliverable is one commit annotating axiom 09's embedding
  line "still not exercised — BM25-only grounding shipped" (that line
  otherwise belongs to Split 5's G-J checklist; do it wherever the
  decision actually happens).
- **Exit state:** 1–2 commits with ablation deltas, or a recorded
  decision to skip.

## Split 4 · Grounding + end-to-end eval (G-G, G-H) — ~290k, tightest

- **Scope:** `tools/refresh_claims.py` (query snapshot → verbatim-excerpt
  claim records → existing `SourceClaimIngestor` → wired
  `SqliteSourceClaimStore`, dry-run, idempotent); exact-duplicate-only
  corroboration (+ the near-duplicates-do-NOT-link restraint test); D1
  serving filter reused untouched (or built to its HANDOFF spec if D1 was
  cut); axiom 08 sentence on deterministic assembly. Then
  `eval_set_v4.json` grounded/ungrounded twins (named `v3` at planning
  time; renamed when résumé intake's `eval_set_v3.json` reached main
  first), three Tier-1 graders
  (citation coverage, claim utilization, high-confidence share), Tier-2
  groundedness rubric (advisory), captures, `run_llm_eval --compare`,
  eval-gate floors.
- **This is the ceiling split.** If context runs hot after G-G's commit,
  stop there — G-H in a fresh session is a natural resume (its kickoff
  needs only `03-…` + the eval harness, not the assembly internals).
- **Mid-split gates:** grounded + ungrounded captures are networked and
  cost real API money → ask per run, with the cap stated.
- **Exit state:** 2 commits, populated claim store, committed recordings,
  before/after deltas in the G-H commit message, eval-gate extended.

## Split 5 · Freshness, tracks, writeup (G-I, G-J) — ~200k

- **Scope:** corpus/claims stats view (extend `tools/show_metrics.py` or
  sibling — decide in-repo); staleness threshold recorded as a prior;
  manifest expansion 3 → 5–10 tracks, each with labeled queries
  (append-only version bump) + re-run retrieval metrics + G-H cases where
  eval personas use the track; the writeup + eval appendix + honesty
  checklist; axiom 09 cost-table touch per whether G-E shipped.
- **Mid-split gates:** new-track ingestion fetches (ask per run); any
  fresh captures for new-track grounded cases (ask, cap stated).
- **Exit state:** 2 commits; the definition-of-done page exists in
  `docs/` with all three artifacts (retrieval metrics, before/after
  citation rates, ablation table) traceable to committed data.

## Kickoff prompts (copy-paste into a fresh session, per split)

Split 1:

```
Read docs/implementation-plans/completed/loop-grounding-rag/README.md, then
docs/implementation-plans/completed/loop-grounding-rag/SPLITS.md (Split 1), then
docs/implementation-plans/completed/loop-grounding-rag/01-corpus-and-contracts.md,
then docs/axioms/08-rag-source-claims.md,
docs/specs/source-claim.schema.md, and the source_claims/ region (reuse
its classifier — do not write a second one). Implement G-A then G-B, one
commit per increment, per the CLAUDE.md operating contract (spec-first,
gates green per commit, ask before any live fetch). Start by restating
the increments and any open decisions, then begin G-A.
```

Split 2:

```
Read docs/implementation-plans/completed/loop-grounding-rag/README.md, then
docs/implementation-plans/completed/loop-grounding-rag/SPLITS.md (Split 2), then
docs/implementation-plans/completed/loop-grounding-rag/02-retrieval-pipeline.md
(G-C and G-D only), then the retrieval/ region as committed by Split 1,
llm_nodes/eval.py (Tier-1 metric style), and docs/axioms/22 (eval gating
split). Implement G-C then G-D, one commit per increment, per the
CLAUDE.md operating contract. The labeled query set is hand-labeled by
me — draft candidates and stop for my labels before wiring floors. Start
by restating the increments, then begin G-C.
```

Split 3 (conditional):

```
Read docs/implementation-plans/completed/loop-grounding-rag/README.md, then
docs/implementation-plans/completed/loop-grounding-rag/SPLITS.md (Split 3), then
docs/implementation-plans/completed/loop-grounding-rag/02-retrieval-pipeline.md
(G-E and G-F only), then llm_nodes/anthropic_adapter.py (the transport
seam) and docs/axioms/09 (pricing). Do NOT write code yet: present the
embeddings-provider options (Voyage API vs. local model) with costs and
dependency implications, and wait for my decision. Then implement G-E
(and G-F only if hybrid leaves measured headroom), one commit per
increment, ablation deltas in commit messages.
```

Split 4:

```
Read docs/implementation-plans/completed/loop-grounding-rag/README.md, then
docs/implementation-plans/completed/loop-grounding-rag/SPLITS.md (Split 4), then
docs/implementation-plans/completed/loop-grounding-rag/03-grounding-integration.md,
then docs/axioms/08-rag-source-claims.md, the source_claims/ ingestor,
app/cycle.py (the claims read + D1 filter), and the eval harness
(llm_nodes/eval.py, eval_judge.py, the capture tool). Implement G-G then
G-H, one commit per increment, per the CLAUDE.md operating contract.
Captures are networked and cost money — ask before each with the cap. If
context runs long after G-G's commit, stop and tell me to relaunch for
G-H. Start by restating the increments, then begin G-G.
```

Split 5:

```
Read docs/implementation-plans/completed/loop-grounding-rag/README.md, then
docs/implementation-plans/completed/loop-grounding-rag/SPLITS.md (Split 5), then
docs/implementation-plans/completed/loop-grounding-rag/04-evaluation-and-writeup.md,
then docs/axioms/09 (cost table rules) and tools/show_metrics.py.
Implement G-I then G-J, one commit per increment, per the CLAUDE.md
operating contract (ask before new-track fetches and any fresh
captures). Apply the G-J honesty checklist to the writeup before calling
it done. Start by restating the increments, then begin G-I.
```
