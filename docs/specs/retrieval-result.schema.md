# Retrieval Result Schema

## Owner

Retrieval index (`retrieval/`).

## Consumers

Retrieval evals, claim assembly (grounding-RAG G-G), audit views.

## Purpose

The ranked answer to one `retrieval-query` against one pinned corpus
snapshot. The result **names its evidence version**: `snapshot_id` rides on
the envelope so any downstream artifact (a claim record, an eval report) can
state exactly which corpus + chunking configuration produced it. Results are
chunk *references with provenance* (document, ordinal, char offsets,
breadcrumb) — chunk text stays in the index and is fetched by id, so results
stay small and auditable.

Determinism rule (axiom 08 discipline): ties break by `score` descending
then `chunk_id` ascending, and the contract itself verifies the ordering —
the same query against the same snapshot yields byte-identical results,
asserted by test.

## JSON Example

```json
{
  "snapshot_id": "snap_7d3a91c04b5e2f68",
  "query": {
    "query_text": "how to prepare for system design interviews",
    "track": "swe",
    "k": 2
  },
  "results": [
    {
      "rank": 1,
      "chunk_id": "chunk_9e21c04b5e2f68d3",
      "doc_id": "doc_2f6c1b8a9d4e0357",
      "ordinal": 4,
      "score": 3.4172,
      "start_char": 5120,
      "end_char": 6591,
      "breadcrumb": "Guide > Preparation"
    },
    {
      "rank": 2,
      "chunk_id": "chunk_04b5e2f68d39e21c",
      "doc_id": "doc_8b1e44d0a2c97f13",
      "ordinal": 0,
      "score": 2.1055,
      "start_char": 0,
      "end_char": 1433,
      "breadcrumb": null
    }
  ]
}
```

(IDs above are illustrative placeholders; real values are derived.)

## Field Semantics

| Field | Purpose |
| --- | --- |
| `snapshot_id` | The pinned corpus snapshot this result was computed against. Downstream artifacts must carry it forward when they cite these chunks. |
| `query` | The exact `retrieval-query` answered, embedded so the envelope is self-contained (`len(results) <= query.k` is contract-checkable). |
| `results` | Ranked chunk references, best first. May be empty (an honest miss beats a fabricated hit). |

### `results[]` entry

| Field | Purpose |
| --- | --- |
| `rank` | 1-based, contiguous (`1..len(results)`), in list order. |
| `chunk_id` | Stable chunk identity (`chunk_` + 16 hex chars), derived from `doc_id` + `ordinal` + the snapshot's chunking-params fingerprint. |
| `doc_id` | The parent document (doc-level relevance labels in the retrieval eval judge against this). |
| `ordinal` | The chunk's 0-based position within its document's chunking. |
| `score` | Retriever-relative relevance, **higher is better**. For the FTS5 retriever: BM25, negated (SQLite reports lower-is-better). For the hybrid retriever (G-E): reciprocal-rank-fusion mass over the BM25 and dense-cosine rankings. Either way a pure function of query + snapshot (+ the pinned embedding model and fusion params for hybrid); scores from different retrievers are not comparable, and no score is ever LLM-assigned (axiom 08: no LLM in the retrieval path). |
| `start_char` / `end_char` | Exact half-open slice of the document's normalized text this chunk covers (auditability: a claim can point back into the exact region). |
| `breadcrumb` | Section-heading trail (`"A > B"`) when the document structure exposed one; becomes claim provenance in G-G. |

## Invariants

- `ranks` are exactly `1..len(results)` in list order.
- Ordering matches the determinism rule: non-increasing `score`, with exact
  score ties ordered by `chunk_id` ascending.
- `chunk_id`s are unique within a result.
- `len(results) <= query.k`.
- `start_char < end_char`; `start_char >= 0`; `ordinal >= 0`.

## Invalid Examples

```json
{
  "snapshot_id": "snap_7d3a91c04b5e2f68",
  "query": {"query_text": "system design", "track": null, "k": 2},
  "results": [
    {"rank": 2, "chunk_id": "chunk_9e21c04b5e2f68d3", "doc_id": "doc_2f6c1b8a9d4e0357", "ordinal": 0, "score": 3.0, "start_char": 0, "end_char": 10, "breadcrumb": null}
  ]
}
```

Reason: ranks must be contiguous from 1.

```json
{
  "snapshot_id": "snap_7d3a91c04b5e2f68",
  "query": {"query_text": "system design", "track": null, "k": 2},
  "results": [
    {"rank": 1, "chunk_id": "chunk_9e21c04b5e2f68d3", "doc_id": "doc_2f6c1b8a9d4e0357", "ordinal": 0, "score": 1.0, "start_char": 0, "end_char": 10, "breadcrumb": null},
    {"rank": 2, "chunk_id": "chunk_04b5e2f68d39e21c", "doc_id": "doc_8b1e44d0a2c97f13", "ordinal": 1, "score": 2.0, "start_char": 0, "end_char": 10, "breadcrumb": null}
  ]
}
```

Reason: scores must be non-increasing in rank order (the tie-break rule is
part of the contract).

## Related Docs

- `retrieval-query.schema.md`
- `corpus-snapshot.schema.md` (chunking params are part of the snapshot pin)
- `../axioms/08-rag-source-claims.md`
- `../implementation-plans/loop-grounding-rag/02-retrieval-pipeline.md`
