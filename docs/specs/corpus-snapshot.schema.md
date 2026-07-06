# Corpus Snapshot Schema

## Owner

Corpus registry (`retrieval/`).

## Consumers

Chunking and retrieval indexing, retrieval evals, claim assembly, audit views.

## Purpose

The snapshot is the pinning unit for eval reproducibility: a retrieval eval
(and later, claim assembly) runs against a `snapshot_id`, never against
"whatever the corpus is right now". Snapshots are immutable — a corpus change
produces a new snapshot, the same way plan mutations produce plan versions.

## JSON Example

```json
{
  "snapshot_id": "snap_7d3a91c04b5e2f68",
  "created_at": "2026-07-06T18:00:00Z",
  "doc_ids": ["doc_2f6c1b8a9d4e0357", "doc_8b1e44d0a2c97f13"],
  "content_hashes": [
    "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
  ]
}
```

(IDs and hashes above are illustrative placeholders; real values are derived —
see Field Semantics.)

## Field Semantics

| Field | Purpose |
| --- | --- |
| `snapshot_id` | Derived identity: `snap_` + first 16 hex chars of sha256 over the sorted, de-duplicated member `content_hash`es joined by `"\n"` (`derive_snapshot_id`). Byte-stable and order-independent: the same document set always yields the same id. |
| `created_at` | When the snapshot was created (UTC). Not part of the identity — recreating the same membership returns the existing snapshot. |
| `doc_ids` | Non-empty, unique, **sorted ascending** (canonical order, so serialized snapshots are byte-stable). |
| `content_hashes` | Parallel to `doc_ids`: `content_hashes[i]` is the `content_hash` of `doc_ids[i]`. Carrying the hashes makes the pin self-contained — the contract can verify `snapshot_id` without the registry. |

## Chunking parameters (reserved)

`chunking_params` joins the snapshot in the chunking increment (grounding-RAG
G-C) and becomes **part of the snapshot identity**, so an eval can never
silently run against re-chunked data. It is deliberately absent from this v1
contract: its shape is defined by the chunker, and this spec is updated first
when it lands (spec-first rule).

## Contract vs. Registry Responsibility

The contract enforces: `doc_ids` non-empty/unique/sorted, list lengths equal,
every hash well-formed, and `snapshot_id` equal to
`derive_snapshot_id(content_hashes)`.

The registry enforces what the contract cannot see: every `doc_id` resolves to
a registered document, and `content_hashes[i]` is really that document's hash.
The registry is the only snapshot producer; it exposes no mutation API —
immutability is structural, not policed.

## Invariants

- `snapshot_id` equals `derive_snapshot_id(content_hashes)`.
- `doc_ids` is non-empty, duplicate-free, sorted ascending.
- `len(content_hashes) == len(doc_ids)`; each is a 64-char lowercase sha256
  hex digest; `content_hashes[i]` belongs to `doc_ids[i]` (registry-enforced).
- Snapshots are immutable. A corpus change = a new snapshot with a new
  identity. Creating a snapshot with identical membership is a no-op that
  returns the existing snapshot (original `created_at` preserved).

## Invalid Examples

```json
{
  "snapshot_id": "snap_7d3a91c04b5e2f68",
  "created_at": "2026-07-06T18:00:00Z",
  "doc_ids": [],
  "content_hashes": []
}
```

Reason: a snapshot must pin at least one document.

```json
{
  "snapshot_id": "snap_ffffffffffffffff",
  "created_at": "2026-07-06T18:00:00Z",
  "doc_ids": ["doc_2f6c1b8a9d4e0357"],
  "content_hashes": [
    "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
  ]
}
```

Reason: `snapshot_id` does not match the derivation from `content_hashes`.

## Related Docs

- `corpus-document.schema.md`
- `../axioms/08-rag-source-claims.md` (corpus-registry subsection)
- `../implementation-plans/loop-grounding-rag/01-corpus-and-contracts.md`
- `../implementation-plans/loop-grounding-rag/02-retrieval-pipeline.md`
  (G-C adds `chunking_params`)
