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
  ],
  "chunking_params": {
    "algorithm": "structure_v1",
    "target_chars": 1600,
    "overlap_chars": 200
  }
}
```

(IDs and hashes above are illustrative placeholders; real values are derived —
see Field Semantics.)

## Field Semantics

| Field | Purpose |
| --- | --- |
| `snapshot_id` | Derived identity: `snap_` + first 16 hex chars of sha256 over the chunking fingerprint (see `chunking_params`) followed by the sorted, de-duplicated member `content_hash`es, joined by `"\n"` (`derive_snapshot_id`). Byte-stable and order-independent in the members: the same document set under the same chunking parameters always yields the same id. |
| `created_at` | When the snapshot was created (UTC). Not part of the identity — recreating the same membership with the same chunking parameters returns the existing snapshot. |
| `doc_ids` | Non-empty, unique, **sorted ascending** (canonical order, so serialized snapshots are byte-stable). |
| `content_hashes` | Parallel to `doc_ids`: `content_hashes[i]` is the `content_hash` of `doc_ids[i]`. Carrying the hashes makes the pin self-contained — the contract can verify `snapshot_id` without the registry. |
| `chunking_params` | The exact chunking configuration this snapshot's derived chunks (and therefore its retrieval index, labels, and metrics) are valid for. **Part of the snapshot identity** via the fingerprint `"{algorithm}:{target_chars}:{overlap_chars}"` (`chunking_fingerprint`), so an eval can never silently run against re-chunked data — new parameters are a new snapshot, never an in-place change. |

### `chunking_params` object

| Field | Purpose |
| --- | --- |
| `algorithm` | Closed identifier of the chunking algorithm; currently only `"structure_v1"` (structure-aware: heading sections first, paragraph fallback, bounded hard split). A change to chunking *behavior* is a new algorithm value — the byte-identical re-chunk property is pinned per algorithm. |
| `target_chars` | Soft maximum chunk size in characters of the normalized text (`> 0`). A chunk closes before a unit that would push it past this target; only a single oversized unit is hard-split. |
| `overlap_chars` | Maximum tail overlap carried into the next chunk, in characters (`>= 0`, `< target_chars`). Overlap snaps to unit boundaries, so it is an upper bound, not an exact length. |

Defaults (`target_chars=1600`, `overlap_chars=200`, exposed as
`DEFAULT_CHUNKING_PARAMS` in `retrieval/chunking.py`) are heuristic priors in
the axiom-08 sense — chunk size is an eval ablation, not a tuned constant.

## Contract vs. Registry Responsibility

The contract enforces: `doc_ids` non-empty/unique/sorted, list lengths equal,
every hash well-formed, `chunking_params` well-formed (`overlap_chars <
target_chars`, known `algorithm`), and `snapshot_id` equal to
`derive_snapshot_id(content_hashes, chunking_params)`.

The registry enforces what the contract cannot see: every `doc_id` resolves to
a registered document, and `content_hashes[i]` is really that document's hash.
The registry is the only snapshot producer; it exposes no mutation API —
immutability is structural, not policed.

## Invariants

- `snapshot_id` equals `derive_snapshot_id(content_hashes, chunking_params)`.
- `doc_ids` is non-empty, duplicate-free, sorted ascending.
- `len(content_hashes) == len(doc_ids)`; each is a 64-char lowercase sha256
  hex digest; `content_hashes[i]` belongs to `doc_ids[i]` (registry-enforced).
- `chunking_params.overlap_chars < chunking_params.target_chars`.
- Snapshots are immutable. A corpus change *or a chunking-parameter change* =
  a new snapshot with a new identity. Creating a snapshot with identical
  membership and identical chunking parameters is a no-op that returns the
  existing snapshot (original `created_at` preserved).

## Invalid Examples

```json
{
  "snapshot_id": "snap_7d3a91c04b5e2f68",
  "created_at": "2026-07-06T18:00:00Z",
  "doc_ids": [],
  "content_hashes": [],
  "chunking_params": {
    "algorithm": "structure_v1",
    "target_chars": 1600,
    "overlap_chars": 200
  }
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
  ],
  "chunking_params": {
    "algorithm": "structure_v1",
    "target_chars": 1600,
    "overlap_chars": 200
  }
}
```

Reason: `snapshot_id` does not match the derivation from `content_hashes` +
`chunking_params`.

```json
{
  "snapshot_id": "snap_7d3a91c04b5e2f68",
  "created_at": "2026-07-06T18:00:00Z",
  "doc_ids": ["doc_2f6c1b8a9d4e0357"],
  "content_hashes": [
    "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
  ],
  "chunking_params": {
    "algorithm": "structure_v1",
    "target_chars": 200,
    "overlap_chars": 200
  }
}
```

Reason: `overlap_chars` must be strictly less than `target_chars` (equal
overlap would make chunking non-progressing).

## Related Docs

- `corpus-document.schema.md`
- `../axioms/08-rag-source-claims.md` (corpus-registry subsection)
- `../implementation-plans/loop-grounding-rag/01-corpus-and-contracts.md`
- `../implementation-plans/loop-grounding-rag/02-retrieval-pipeline.md`
  (G-C added `chunking_params`; G-D consumes the pinned chunks)
