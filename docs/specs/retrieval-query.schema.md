# Retrieval Query Schema

## Owner

Retrieval index (`retrieval/`).

## Consumers

Retrieval evals, claim assembly (grounding-RAG G-G), operator CLIs.

## Purpose

One typed request against the chunk index of a pinned corpus snapshot. The
query is deliberately tiny: text, an optional career-track filter, and a
result budget. There is no LLM anywhere in the retrieval path — the query is
compiled to an FTS5 match expression deterministically, so the same query
against the same snapshot always produces byte-identical results (see
`retrieval-result.schema.md`).

## JSON Example

```json
{
  "query_text": "how to prepare for system design interviews",
  "track": "swe",
  "k": 5
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `query_text` | Natural-language query text (non-empty). Compiled deterministically to a bag-of-words FTS5 expression: word tokens are extracted, quoted, and OR-joined (standard BM25 bag-of-words semantics — a heuristic prior, not a tuned choice). Text with no word tokens matches nothing. |
| `track` | Optional `CareerTrack` filter: only chunks of documents tagged with this track are searched. `null` searches the whole snapshot. |
| `k` | Maximum number of ranked chunks to return (`1..100`). The upper bound is a scope guard: retrieval serves claim assembly and evals, not pagination. |

## Invariants

- `query_text` is non-empty.
- `track`, when present, is a member of the closed `CareerTrack` enum.
- `1 <= k <= 100`.

## Invalid Examples

```json
{
  "query_text": "",
  "track": "swe",
  "k": 5
}
```

Reason: `query_text` must be non-empty.

```json
{
  "query_text": "system design",
  "track": "swe",
  "k": 0
}
```

Reason: `k` must be at least 1.

## Related Docs

- `retrieval-result.schema.md`
- `corpus-snapshot.schema.md`
- `../axioms/08-rag-source-claims.md` (corpus-registry subsection)
- `../implementation-plans/completed/loop-grounding-rag/02-retrieval-pipeline.md`
