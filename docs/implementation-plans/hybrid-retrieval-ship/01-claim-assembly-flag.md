# Split 1: The Flag

Offline.
No network, no spend, no corpus database changes.
One commit.

## Files Touched

| File | Change |
| --- | --- |
| `backend/src/agentic_calendar/tools/refresh_claims.py` | `assemble_claims` signature, `main` wiring, two new CLI args, report line |
| `backend/src/agentic_calendar/tools/embed_corpus.py` | `--claim-queries` option |
| `backend/tests/tools/test_refresh_claims.py` | `_assemble` helper, new hybrid tests |
| `backend/tests/tools/test_embed_corpus.py` | claim-query coverage test |

Do not touch `retrieval/fusion.py`, `retrieval/vectors.py`, `retrieval/index.py`, `retrieval/eval.py`, or any contract.
They are already correct for this work.

## Change 1: `assemble_claims` Ranking Seam

`assemble_claims` is at `refresh_claims.py:355` (verified 2026-09-10 at `7408345`; trust the symbol over the line number).
Today it takes `index: SqliteChunkIndex` and uses it for two different jobs: `index.search(...)` at line 379 for ranking, and `index.get_chunk(...)` at line 384 for chunk lookup.
`HybridSearcher` implements only `search`, which is why the seam has to split.

Change the signature to:

```python
def assemble_claims(
    *,
    registry: CorpusRegistry,
    index: SqliteChunkIndex,
    searcher: ChunkSearcher,
    snapshot_id: str,
    query_set: ClaimQuerySet,
    manifest: CorpusManifest,
    priors: ConfidencePriors = DEFAULT_CONFIDENCE_PRIORS,
    max_excerpt_chars: int = DEFAULT_MAX_EXCERPT_CHARS,
    min_excerpt_chars: int = DEFAULT_MIN_EXCERPT_CHARS,
) -> AssemblyReport:
```

`searcher` is required and keyword-only, per locked decision D1.
Inside the function, change only the ranking call:

```python
result = searcher.search(
    RetrievalQuery(query_text=query.query_text, track=query.track, k=query_set.k),
    snapshot_id=snapshot_id,
)
```

Leave `index.get_chunk(...)` and `registry.get_document(...)` exactly as they are, including the existing assertion comment about store corruption.
Nothing else in the function body changes.
Determinism, dedup order, corroboration linking, and the skip counters all stay byte-identical for a given ranking.

Import `ChunkSearcher` from `agentic_calendar.retrieval.eval`.
It is at `eval.py:46-54`, a `runtime_checkable` `Protocol` declaring exactly `search(self, query: RetrievalQuery, *, snapshot_id: str) -> RetrievalResult`, and both `SqliteChunkIndex` and `HybridSearcher` already satisfy it.
Add `HybridSearcher` and `SqliteVectorStore` to the existing `from agentic_calendar.retrieval import (...)` block at `refresh_claims.py:90-94`.

Update the function docstring to say that ranking comes from `searcher` and chunk and document lookup from `index` and `registry`, and that the two are separate so the retriever is swappable without the lookup path moving.

## Change 2: CLI Wiring

In `main` (`refresh_claims.py:529`), add two arguments next to the existing `--snapshot` argument:

```python
parser.add_argument(
    "--mode",
    choices=("bm25", "hybrid"),
    default="bm25",
    help="Retriever for claim assembly: bm25 (default, the shipped posture) or hybrid (RRF over BM25 + dense cosine).",
)
parser.add_argument(
    "--embedding-model",
    default="voyage-3.5",
    help="Vector-cache model name for --mode hybrid.",
)
```

After `index.build(registry, snapshot)`, construct the searcher:

```python
searcher: ChunkSearcher = index
if args.mode == "hybrid":
    searcher = HybridSearcher(
        index, SqliteVectorStore(corpus_db), model_name=args.embedding_model
    )
```

Pass `searcher=searcher` into the `assemble_claims(...)` call.

`assemble_claims` can now raise `MissingEmbeddingsError`, which is an `AgenticCalendarError`.
`main` currently has no try/except around the assembly call.
Wrap the `assemble_claims(...)` call in `try: ... except AgenticCalendarError as exc:` that prints `f"error: {exc}"` to stderr and returns 1, matching the handling style in `run_retrieval_eval.py:143-145`.
Import `AgenticCalendarError` from `agentic_calendar.common.errors`.
Do not catch and continue.
A missing vector must stop the run, never degrade it to BM25.

Print the retriever line before the outcome report, mirroring `run_retrieval_eval.py:147-154`:

```python
if args.mode == "hybrid":
    print(
        f"retriever: hybrid (model {args.embedding_model}, "
        f"rrf_k={searcher.params.rrf_k}, "
        f"candidate_depth={searcher.params.candidate_depth})"
    )
else:
    print("retriever: bm25")
```

Update the module docstring's usage block to show `--mode hybrid` and to state that hybrid reads cached vectors only, that a missing vector is a typed error pointing at the embed CLI, and that the claim store is additive across retrievers per D4.

## Change 3: `--claim-queries` On The Embed CLI

Hybrid needs a query-side vector for every claim query, and today zero of the 38 in `corpus/claim_queries_v4.json` are cached.
The embed CLI's existing `--queries` loads a retrieval *eval* query set via `load_query_set` and cannot read a claim query set.

Add to `embed_corpus.py`:

```python
parser.add_argument(
    "--claim-queries",
    type=Path,
    default=None,
    help="Claim query set (corpus/claim_queries_v*.json) whose query texts get embedded for hybrid claim assembly.",
)
```

Import `load_claim_queries` from `agentic_calendar.tools.refresh_claims`.
A tools-to-tools import is allowed: `agentic_calendar.tools` appears in no `.importlinter` contract, because it is the composition root where regions are assembled.

In the body, after the existing `--queries` handling that builds `query_texts`, extend the same list from the claim query set.
Both go into the vector cache under `input_type="query"`, because they are both query-side texts and the cache identity is `(content_hash, model_name, input_type)`.

```python
total_claim_queries = 0
if args.claim_queries is not None:
    claim_set = load_claim_queries(args.claim_queries)
    total_claim_queries = len(claim_set.queries)
    query_texts.extend(
        _pending_texts(
            [q.query_text for q in claim_set.queries],
            vectors,
            model_name=config.model_name,
            input_type="query",
        )
    )
```

Deduplicate `query_texts` before estimating and embedding, since an eval query and a claim query could share text:
`query_texts = list(dict.fromkeys(query_texts))`.

Extend the printed summary with a claim-query count line in the same shape as the existing query line, reporting total, cached, and to-embed.
Update the module docstring usage block.

## Tests

### `tests/tools/test_refresh_claims.py`

The `_assemble` helper is at line 181 and calls `assemble_claims(registry=..., index=index, ...)`.
Change it to pass `searcher=index` alongside `index=index`.
That single edit keeps all nine existing assembly tests passing unchanged, which is the point: BM25 behavior must be provably identical after the refactor.

Add a `_build_corpus`-based hybrid fixture following the pattern already proven in `tests/retrieval/test_fusion.py`.
Read `test_fusion.py:76-130` first.
Seed deterministic fake vectors straight into `SqliteVectorStore` with `put_many`.
No embedding provider goes anywhere near these tests.

Add these tests:

1. `test_hybrid_assembly_uses_the_fused_ranking` - seed vectors that invert the BM25 order for one claim query, assemble with `searcher=HybridSearcher(...)`, and assert the resulting `claim_id` order differs from the BM25 assembly over the same corpus and query set. Assert on claim ids, not prose.
2. `test_hybrid_assembly_without_vectors_raises_typed_error` - assemble with a `HybridSearcher` over an empty vector store and assert `MissingEmbeddingsError` is raised, asserting on `exc.value.model_name`, `exc.value.input_type`, and `exc.value.missing_count`. This is the no-silent-fallback proof.
3. `test_hybrid_assembly_is_deterministic` - two hybrid assemblies over the same inputs produce identical claim id lists, mirroring the existing `test_assembly_is_deterministic` at line 288.
4. `test_cli_rejects_hybrid_without_cached_vectors` - run `main` through `_cli_args(..., "--mode", "hybrid", "--dry-run")` against a corpus with no vectors, assert the return code is 1 and that stderr names the embed CLI. Note that `_cli_args` at line 418 takes `*extra`, so no helper change is needed.
5. `test_cli_dry_run_hybrid_prints_the_retriever_line` - seed vectors, run with `--mode hybrid --dry-run`, assert stdout contains `retriever: hybrid`, the model name, `rrf_k=60`, and `candidate_depth=50`.

Also assert in one test that the default `--mode` is bm25 by checking that a plain `--dry-run` run prints `retriever: bm25` and succeeds with no vectors in the store at all.
That is the guard that the flag is genuinely opt-in.

### `tests/tools/test_embed_corpus.py`

Add `test_dry_run_counts_claim_queries` - pass `--claim-queries` pointing at a written-out `ClaimQuerySet` fixture and assert the dry-run output reports the right to-embed count and makes no network call.
The existing tests already inject a deterministic fake `EmbeddingTransport`; follow that pattern and do not add a new one.

Add `test_claim_query_texts_land_in_the_cache_as_query_type` - run the live path against the fake transport and assert the cached vectors are retrievable via `vectors.get(content_hash_for(text), model_name=..., input_type="query")`.

## Hard Constraints

- No network calls in this split. If a test needs a vector, seed it.
- Do not modify `corpus/corpus.db`. Check `git status` before committing and confirm it is clean.
- Do not change any file in `contracts/`, `docs/specs/`, or `schemas/`.
- Do not change the `retrieval/` package.
- Do not change the Makefile. That is split 3.
- Do not add a `searcher` default value.
- BM25 remains the default in every code path.

## Gates Before The Commit

Run from `backend/`:

```bash
make test-fast
make lint
make typecheck
make boundaries
```

All four green.
Then fill ledger rows 1 and 2 in `00-overview.md` in the same commit.
