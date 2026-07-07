# 02 · Retrieval Pipeline (G-C, G-D gate-worthy; G-E, G-F gated ablations)

Order inverted from the web draft: **BM25/FTS5 is the foundation** (stdlib,
deterministic, zero new dependencies), dense embeddings and reranking are
measured ablations that must each earn their place. The draft's own metric
framing ("which components pay for themselves?") is what justifies the
inversion.

## G-C · Deterministic chunking

- `retrieval/chunking.py`: structure-aware splitting (headings/sections
  first, paragraph fallback), target size + overlap as explicit
  `ChunkingParams` recorded on the corpus snapshot (G-A), so chunk size is
  an eval ablation rather than a guess — rerunning with different params is
  a *new snapshot*, never an in-place change.
- Stable `chunk_id` = `doc_id` + ordinal + params hash. Property test:
  re-chunking a pinned snapshot is byte-identical output.
- Each chunk keeps: source doc pointer, section-heading breadcrumb (becomes
  claim provenance in G-G), char offsets (auditability: a claim can point
  back into the exact document region).

## G-D · FTS5 retrieval + labeled query set + the retrieval eval gate

**Index & query:**

- SQLite FTS5 index over chunks (BM25 ranking is built into FTS5), one
  index per snapshot. **Feature-detect FTS5 at startup** (stdlib builds
  almost always have it; macOS system Python and the Docker image both need
  a one-line verification in CI) — a missing FTS5 is a typed setup error,
  not a silent fallback.
- Typed contracts (spec-first): `retrieval-query.schema.md` /
  `retrieval-result.schema.md` — query text, track filter, `k`;
  result = ranked chunk refs + scores + `snapshot_id`.
- **Determinism rule:** ties break by (`score` desc, `chunk_id` asc);
  results carry the snapshot id so any downstream artifact names its
  evidence version. Same query + same snapshot → byte-identical results,
  asserted by test.

**Labeled query set (the draft's ~50–100 queries):**

- `backend/evalsets/retrieval_queries_v1.json`, append-only + versioned
  like the LLM eval sets (`eval_set_v2.json` precedent). Each case:
  `query_id`, query text, track, and relevant `doc_id`s (doc-level
  relevance labels — chunk-level labeling is not worth the labeling cost in
  v1; a chunk hit counts if its parent doc is relevant).
- Hand-labeled by the user (the drafts' point that the tracks were chosen
  to be judgeable by eye is exactly this step). Labels reference a pinned
  snapshot.

**Metrics & gating — stronger than the draft assumed:**

- `retrieval/eval.py`: recall@k, MRR, nDCG as pure functions
  (mirror the Tier-1 style of `llm_nodes/eval.py:337`).
- Because retrieval has **no LLM anywhere**, this eval is a pure function
  over checked-in data (queries + labels + snapshot) — it runs as ordinary
  pytest and **may gate CI directly**, per amended axiom 22's split
  ("gating splits by determinism"). Add `make retrieval-eval` mirroring
  `eval-gate`; floors seeded from the first measured run (heuristic priors
  until enough labels accumulate — axiom 08 calibration honesty applies to
  these floors too).

## G-E · Dense embeddings + hybrid fusion — GATED (new provider)

**Do not start without the user approving a provider.** Anthropic has no
embeddings endpoint; options to present: Voyage AI (API — new key, new
external service, per-call cost matching axiom 09's dormant ~$0.02/1M
line) vs. a local model (heavy dependency; conflicts with the slim-deps
posture). Decision recorded in the commit.

- Boundary decision (flag in review): the embedding client is an external
  model-provider SDK, so it lives where LLM SDKs are allowed — a sibling
  transport in `llm_nodes/` next to `AnthropicTransport`
  (`anthropic_adapter.py:101-117`; the eval judge already demonstrates a
  non-workflow-node use of that seam). `retrieval/` consumes vectors as
  plain data via the composition root — it never imports the SDK. The
  embedding call is **not** one of the four LLM node classes and must not
  route through `_GenerationEngine` (no contract/repair semantics apply);
  it does get call-logged (tokens/cost/latency) like the judge is.
- Embeddings cached by `content_hash` (embed once per chunk per model);
  vectors in a plain SQLite table; brute-force cosine over a few thousand
  chunks is milliseconds — **no vector database** (scope guard).
- Fusion: reciprocal rank fusion over BM25 + dense lists (deterministic,
  same tie-break rule).
- Ship only with the ablation: hybrid vs. BM25-only on the G-D query set,
  same snapshot, table in the commit message (house convention: deltas in
  commit messages).

## G-F · Reranking — GATED (dependency + latency budget)

Only after G-E, and only if hybrid still leaves headroom (misses in the
labeled set that fusion ordering could fix). A cross-encoder means a torch
stack — for this repo that is a big ask; present alternatives (hosted
rerank API = another external service; or skip). **Earn-its-latency rule
kept from the draft, made concrete:** report quality delta (nDCG/MRR) per
added ms on the eval set; the user decides against an explicit latency
budget for generation-time retrieval. If it doesn't pay, the ablation
result itself is the deliverable (an honest "reranking didn't earn its
place at this corpus size" is portfolio signal too — say it in the writeup).

## Test expectations

- Chunking determinism property; FTS5 feature-detection error path (typed).
- Query determinism (tie-break) and snapshot-stamping.
- Metric functions against tiny hand-computed fixtures (recall/MRR/nDCG
  arithmetic verified by hand, the way Tier-1 grader tests do it).
- `make retrieval-eval` green on the pinned snapshot; a deliberately
  broken-floor case proving the gate can fail (mirrors the
  `fixture_baseline` "harness proof" convention).
