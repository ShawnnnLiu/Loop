# Hybrid Retrieval: Ship It Behind A Flag

Status: Split 1 implemented 2026-10-24 on `hybrid-retrieval-ship`; splits 2 and 3 not started.
Anchors verified against `main` at `7408345` on 2026-09-10.
Split 1 was built on `main` at `909496f` (PR #65 merged after planning), which added a third `assemble_claims` call site in `tools/build_grounded_eval_set.py`; it passes `searcher=index` explicitly per D1.

## Why This Plan Exists

The hybrid retriever already exists, is tested, and is measured.
`HybridSearcher` in `backend/src/agentic_calendar/retrieval/fusion.py` fuses the BM25 arm and a dense-cosine arm under reciprocal rank fusion, and the G-E ablation measured it at MRR 0.8500 -> 0.9311 (+0.0811) on the 6-track corpus.
It was then deliberately parked: `docs/writeups/grounding-an-llm-planner.md` records "BM25 stays the shipped retriever" because the serving path reads the assembled claim store rather than live retrieval ranks.

That decision was correct for the serving path and wrong for the *assembly* path.
Claim assembly is exactly where retrieval ranking converts into product value: `assemble_claims` takes the top-k chunks per claim query and turns them into the evidence excerpts the Strategist cites.
At fixed k, a better ranking means better evidence in the prompt.
Hybrid's measured win is almost entirely ranking rather than recall, which is precisely the shape of win that helps here.

This plan ships hybrid as an opt-in retriever for claim assembly, measures it on the current pinned snapshot, and gates it.
BM25 remains the default and remains the untouched CI gate.

## What "Shipped" Means Here

Three concrete deliverables:

1. `tools/refresh_claims.py` grows `--mode {bm25,hybrid}`, so the claim store can be assembled from hybrid ranks.
2. The embedding cache covers the pinned serving snapshot `snap_0217291f46e331b9`, so `--mode hybrid` actually runs instead of raising `MissingEmbeddingsError`.
3. `make retrieval-eval-hybrid` exists as a second gate with its own floors, measured on that snapshot, alongside the untouched `make retrieval-eval`.

## Current State, Measured 2026-09-10

Measured directly against `backend/corpus/corpus.db` at `7408345`.

| Fact | Value |
| --- | --- |
| Pinned serving/eval snapshot | `snap_0217291f46e331b9`, 188 documents, 2798 chunks (2763 unique texts) |
| Cached document vectors covering that snapshot | 704 of 2763 unique texts |
| Missing document vectors | 2076, approximately 746,341 tokens by the chars/4 prior |
| Estimated embed cost | approximately $0.045 at voyage-3.5 $0.06/1M |
| Eval query vectors (`evalsets/retrieval_queries_v2.json`, 75 cases) | all 75 cached, 0 missing |
| Claim query vectors (`corpus/claim_queries_v4.json`, 38 queries) | **0 of 38 cached**, approximately 455 tokens |
| Total cached vectors in store | 806 document + 75 query, all `voyage-3.5` |

Two consequences the executor must not rediscover the hard way:

The 806 cached document vectors are leftovers from the older 55-document snapshot `snap_26c44499e582a96a`, not from the pinned one.
Only 704 of them happen to match text that survived into the pinned snapshot.
The published +0.0811 MRR delta was measured on that older snapshot, so **hybrid's performance on the current 188-document corpus is unmeasured** and this plan must measure it rather than assume it.

The claim queries have no cached query vectors at all, and the embed CLI's `--queries` flag loads a *retrieval eval* query set (`load_query_set`), not a claim query set.
Hybrid claim assembly therefore needs a new `--claim-queries` option on the embed CLI.
This is the non-obvious gap in the work and is specified in `02-embed-run.md`.

## Locked Decisions

These are settled.
The executor implements them and does not relitigate them.

**D1. `assemble_claims` takes a required `searcher` keyword.**
The function keeps its `index: SqliteChunkIndex` parameter for chunk and document lookup and gains a required keyword-only `searcher: ChunkSearcher` for ranking.
No default value.
A default would let a mis-wiring silently fall back to BM25, which is the exact failure mode `MissingEmbeddingsError` was written to prevent.
All call sites pass it explicitly.

**D2. The flag spelling is `--mode {bm25,hybrid}`, default `bm25`.**
This matches `tools/run_retrieval_eval.py` exactly, so both tools that choose a retriever use one vocabulary.
There is no collision with dry-run: that distinction is already carried by `--dry-run` and `--app-db`.
`--embedding-model` defaults to `voyage-3.5` and is only meaningful under `--mode hybrid`, again matching the eval CLI.

**D3. No contract change.**
`SourceClaim` does not gain a retriever-provenance field.
Do not touch `docs/specs/source-claim.schema.md`, `contracts/source_claim.py`, the source-claim fixtures, or the generated schemas.
Rationale: claim ids are content-derived, the serving path never reads retriever provenance, and a spec change here would ripple through fixtures and schema generation for zero served value.
Retriever, embedding model, and fusion params are recorded in the CLI's printed report and in the committed run report artifact instead.

**D4. Hybrid claim refresh is additive, not a replacement.**
Running `refresh_claims --mode hybrid` against a store that already holds BM25-sourced claims ingests new claims and leaves existing ones in place.
`derive_claim_id` is content-derived, so excerpts both retrievers find collapse to the same id and dedup naturally.
No retirement or purge pass is in scope.
Rationale: the claim store is auditable history (its own docstring says so), claims carry expiry, and the D1 curation filter already bounds what reaches a prompt.

**D5. BM25 gate is untouched.**
`make retrieval-eval` keeps its floors at 0.7644 / 0.7144 / 0.6910 and keeps grading BM25.
Hybrid gets a *separate* `make retrieval-eval-hybrid` target with its own floors, set to the values measured in split 3.
Do not raise, lower, or re-baseline the BM25 floors.
Neither target joins `check` in this plan, matching the existing "not wired into CI yet" posture recorded in the Makefile comment.

**D6. The vector store stays SQLite. No pgvector, no FAISS, no ANN index.**
This is an explicit non-goal.
`SqliteVectorStore` holds packed float32 blobs and `HybridSearcher` does brute-force cosine over the track-filtered chunk universe.
At 2798 chunks that is milliseconds, and the existing `vectors.py` docstring records "no vector database" as a deliberate scope guard.
The `put_many` / `get` / `get_many` / `missing` interface is narrow enough that a pgvector-backed implementation could be swapped in later without touching `fusion.py`, which is the point of the seam.
If a future plan wants that swap, it is a separate plan with its own justification, and the justification cannot be "hybrid needs it" because hybrid does not.

**D7. No reranker.**
It stays a recorded negative result per the writeup.
Revisit only if the corpus grows an order of magnitude.

**D8. Fusion params stay at their defaults.**
`rrf_k=60`, `candidate_depth=50`.
These are recorded heuristic priors.
No sweep is in scope; a sweep would require a re-label pass to be meaningful.

**D9. No LLM anywhere in claim assembly.**
Unchanged from today.
Embedding calls happen only in `tools/embed_corpus.py`, which is the ask-first networked CLI, and only in split 2.

## Non-Goals

- Changing the serving path to call a retriever at request time.
- A v3 retrieval label pass over the expanded corpus (a real follow-up, but separate).
- Graph-based retrieval. The knowledge-map DAG is prerequisite structure, not a retrieval strategy.
- Any change to chunking, k, or snapshot pinning.

## Split Map

See `SPLITS.md` for sizing and kickoff prompts.

| Split | Content | Network | Blocked by |
| --- | --- | --- | --- |
| 1 | `--mode` flag, `assemble_claims` refactor, `--claim-queries` on the embed CLI, tests | no | nothing |
| 2 | Operator embed run for the pinned snapshot, commit updated `corpus.db` | **yes, paid** | split 1 |
| 3 | Hybrid baseline measurement, `retrieval-eval-hybrid` gate, claim-delta report, writeup update | no | split 2 |

Split 1 is deliberately first and deliberately offline: the code lands and is fully tested with seeded fake vectors before anyone spends money.

## Evidence Ledger

The executor fills these rows in the commit that produces them.
Empty rows are honest; invented rows are not.

| # | Split | Claim | Measured value | Command |
| --- | --- | --- | --- | --- |
| 1 | 1 | `make test-fast` green after the refactor | 4815 passed, 32 deselected, 0 failed (21.81 s); the 32 golden/boundary/subprocess tests also pass; `make lint`, `make typecheck` (272 files), `make boundaries` (21 kept) green; `test_committed_v10_matches_regeneration` still byte-identical through the BM25 call site | `make test-fast` from `backend/` |
| 2 | 1 | Hybrid claim assembly produces a different claim set than BM25 on the test corpus | Yes. 7-doc test corpus, seeded 2-d fake vectors, one query at k=3: BM25 assembles [mirror, guide, variant], hybrid assembles [old-notes, mirror, variant]; 2 of 3 claim ids shared, old-notes lifted from BM25 rank 5 to fused rank 1. At k=10 over the 2-query fixture set the 4-claim set is identical and only the order differs | `uv run pytest tests/tools/test_refresh_claims.py -k hybrid` from `backend/` |
| 3 | 2 | Document vectors embedded for `snap_0217291f46e331b9` | | |
| 4 | 2 | Measured tokens and cost for the live embed run | | |
| 5 | 2 | Claim-query vectors embedded | | |
| 6 | 3 | Hybrid recall@5 / MRR / nDCG@5 on `snap_0217291f46e331b9`, v2 labels, k=5 | | |
| 7 | 3 | BM25 baseline re-confirmed unchanged | | |
| 8 | 3 | Claim store delta: BM25 claims, hybrid claims, overlap | | |
