# Corpus Document Schema

## Owner

Corpus registry (`retrieval/`) and the operator ingestion CLI
(`tools/ingest_corpus.py`).

## Consumers

Chunking and retrieval indexing (grounding layer), claim assembly, retrieval
evals, audit views.

## Purpose

The retrieval corpus is versioned evidence, not a scrape pile. Every document
enters the registry with provenance, license, and track metadata attached, and
its text pinned by a content hash — so a corpus snapshot can be referenced by
evals the same way prompt bytes are pinned today. Corpus text is public-web
content only; user data (résumé text, calendar data) never enters the corpus.

## JSON Example

```json
{
  "doc_id": "doc_2f6c1b8a9d4e0357",
  "source_url": "https://engineering.acme.com/interview-guide",
  "source_type": "company_engineering_blog",
  "license_note": "Public engineering-blog post; snapshot held for research quotation under fair use, verbatim excerpts limited and attributed.",
  "date_collected": "2026-07-06",
  "source_published_date": "2026-05-01",
  "track_tags": ["swe", "ai_engineer"],
  "content_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "title": "How we run backend interviews"
}
```

(`doc_id` and `content_hash` above are illustrative placeholders; real values
are derived — see Field Semantics.)

## Field Semantics

| Field | Purpose |
| --- | --- |
| `doc_id` | Stable derived identifier: `doc_` + first 16 hex chars of sha256 over `"{source_url}\n{date_collected.isoformat()}"`. Recomputed and enforced by the contract (`derive_doc_id`). |
| `source_url` | Provenance link — the exact URL fetched. |
| `source_type` | Deterministic classification via the **existing** URL-rule classifier (`source_claims/classification.py`) with operator-declared host context (axiom 08). Never LLM-assigned; the contract checks only that the value is a known `SourceType`. |
| `license_note` | Required free text: the ToS/licensing basis for holding a snapshot of this document. Job-posting snapshots note their volatility here. |
| `date_collected` | When the fetch happened. |
| `source_published_date` | Publication date of the source, when determinable; `null` otherwise. |
| `track_tags` | Non-empty list of `CareerTrack` values (closed enum, `contracts/career_track.py`, shared with the skill taxonomy). No duplicates. |
| `content_hash` | sha256 hex digest (64 lowercase hex chars) of the **normalized** document text (`content_hash_for` in the contract module). |
| `title` | Human-readable document title. |

## `CareerTrack` (shared closed enum)

`track_tags` values come from `contracts/career_track.py` — the closed track
enum shared with the résumé-intake skill taxonomy
(`skill-taxonomy.schema.md`, planned). Starting members: `swe`, `mle`,
`ai_engineer`. New tracks are added to the enum in review, never free-typed.

## Contract vs. Registry Responsibility

The Pydantic contract (`backend/src/agentic_calendar/contracts/corpus_document.py`)
enforces **shape and internal consistency**: `doc_id` matches its derivation,
`content_hash` is well-formed, `track_tags` non-empty and duplicate-free,
`source_published_date` not after `date_collected`.

The **registry** (`retrieval/registry.py`) enforces what the contract cannot
see: the stored text actually hashes to `content_hash` (checked on register
and on read), registered documents are immutable (same `doc_id` with
different content is a typed conflict, never an overwrite), and re-registering
an identical document is a no-op (hash-idempotent re-ingest).

Document **text** is stored by the registry alongside the metadata record; it
is not a contract field, so the metadata schema stays small and exportable.

## Invariants

- `doc_id` equals `derive_doc_id(source_url, date_collected)`.
- `content_hash` is 64 lowercase hex chars and matches the stored normalized
  text (registry-enforced).
- `track_tags` is non-empty, all values from `CareerTrack`, no duplicates.
- `source_published_date`, when present, is not after `date_collected`.
- `license_note` is non-empty — a document without a recorded license basis
  may not enter the registry.
- Registered documents are immutable; a changed page is a new fetch on a new
  `date_collected` (hence a new `doc_id`), never an in-place update.
- Corpus text is public-web content only; no user data.

## Invalid Examples

```json
{
  "doc_id": "doc_2f6c1b8a9d4e0357",
  "source_url": "https://example.com/a",
  "source_type": "company_engineering_blog",
  "license_note": "ok",
  "date_collected": "2026-07-06",
  "track_tags": [],
  "content_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "title": "T"
}
```

Reason: `track_tags` must be non-empty.

```json
{
  "doc_id": "doc_0000000000000000",
  "source_url": "https://example.com/a",
  "source_type": "company_engineering_blog",
  "license_note": "ok",
  "date_collected": "2026-07-06",
  "track_tags": ["swe"],
  "content_hash": "not-a-hash",
  "title": "T"
}
```

Reason: `content_hash` must be a 64-char lowercase sha256 hex digest; `doc_id`
must match its derivation.

## Related Docs

- `corpus-snapshot.schema.md`
- `source-claim.schema.md` (shared `SourceType`)
- `../axioms/08-rag-source-claims.md` (classification rules, corpus-registry
  subsection)
- `../implementation-plans/loop-grounding-rag/01-corpus-and-contracts.md`
