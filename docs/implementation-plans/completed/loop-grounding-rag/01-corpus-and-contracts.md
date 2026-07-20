# 01 · Corpus Registry + Contracts (G-A, G-B)

The corpus is versioned evidence, not a scrape pile. Every document carries
provenance and license metadata at ingestion; every eval run pins a corpus
snapshot the same way prompt bytes are pinned today
(`tests/llm_nodes/test_prompt_versions.py` is the house pattern).

## G-A · Specs, contracts, registry (spec-first)

**New specs in `docs/specs/` (write these before any code):**

1. `corpus-document.schema.md` — the registered document:
   - `doc_id` (stable, derived — recommend `doc_` + short hash of
     canonical `source_url` + `date_collected`), `source_url`,
     `source_type` (computed by the **existing** classifier
     `source_claims/classification.py` — do not write a second one; company
     / engineering-blog / personal-blog context comes from the same
     `known_company_domains` hooks axiom 08 already defines),
     `license_note` (required, free-text: ToS basis for holding a snapshot),
     `date_collected`, `source_published_date` (nullable),
     `track_tags` (non-empty list from a closed track enum — the shared
     `CareerTrack` enum in `contracts/career_track.py`; the
     `resume-intake-onboarding` plan's skill taxonomy uses the same enum,
     and whichever branch lands first creates the module),
     `content_hash` (sha256 of the normalized text), `title`.
   - Invariants: hash matches stored content; tags from the enum; invalid
     fixtures with expected structured violations (house test pattern).
2. `corpus-snapshot.schema.md` — the pinning unit:
   - `snapshot_id` = hash over the sorted set of member `content_hash`es
     (byte-stable, order-independent), `created_at`, `doc_ids`,
     `chunking_params` (filled by G-C; part of the snapshot identity so an
     eval can never silently run against re-chunked data).
   - Invariant: snapshots are immutable; a corpus change = a new snapshot.

**Contracts:** one module per spec in `contracts/` (`corpus_document.py`,
`corpus_snapshot.py`), `extra="forbid"`, valid + invalid fixtures, then
`make schemas`.

**New region package `retrieval/`** (registry + later index/query):
- Register in `.importlinter`; it may import `contracts/` and `common/`
  only — notably **not** `source_claims/` (claim assembly in G-G lives on
  the composition side, keeping regions siblings, not dependents).
- `retrieval/registry.py`: `CorpusRegistry` over SQLite (own tables in the
  shared DB, matching the Phase 9 store pattern: stdlib `sqlite3`,
  parametrized shared test suite for an in-memory twin). Stores documents'
  normalized text + metadata; creates/loads snapshots; is the only writer.

**Axiom touch:** add a short "corpus registry" subsection to axiom 08 (it
already owns provenance rules) noting: documents store license notes, the
registry is snapshot-versioned for eval reproducibility, and corpus text is
public-web content — **never user data** (no résumé text, no calendar
anything may enter the corpus; keeps axiom 06 privacy trivially satisfied).

## G-B · Ingestion CLI (fetch is networked → gated)

`tools/ingest_corpus.py`, operator-run like every `tools/` CLI:

- Input: a hand-curated **source manifest** (checked-in JSON/TOML per
  track: URL, expected type, track tags, license note). Curation lives in
  the manifest, in review — not in crawler heuristics. No crawling: the
  tool fetches exactly the manifest's URLs.
- Fetch: stdlib `urllib.request` first; if HTML→text extraction proves too
  painful, adding a parser dependency (`beautifulsoup4` or `trafilatura`)
  is an **ask-first** decision. Respect robots.txt; per-request timeout;
  per-run fetch cap (guardrail like the capture tool's 33-call cap).
  Job-posting snapshots note their volatility in `license_note`
  (axiom 08 already expires them fastest: 45-day prior).
- Normalize deterministically (whitespace, encoding) → `content_hash` →
  register. Re-running on unchanged pages is a no-op (hash-idempotent).
- `--dry-run` prints what would be fetched/registered (house convention:
  every side-effecting tool supports dry-run).
- Every live run: **ask the user first**, report doc counts + per-type
  breakdown after.

Start with 3 tracks (SWE, MLE, AI engineer), ~30–60 docs each — enough for
real retrieval metrics, small enough to eyeball. Remaining tracks land in
G-I after the pipeline is proven.

## Test expectations

- Contract shape + invalid fixtures (structured violations).
- Registry: idempotent re-ingest, snapshot hash stability (same docs any
  order → same `snapshot_id`), immutability (mutating a snapshot member is
  impossible via the API).
- Classifier reuse: a manifest URL on a declared company domain classifies
  `official_job_posting` — through the existing function, no new rules.
- No network in tests: fetching is faked; fixtures carry canned HTML/text.

## Non-goals

- No scheduler/cron for ingestion; manual operator runs only in v1.
- No storage of rendered/JS pages (static fetch only); a doc that needs a
  headless browser is out of the v1 corpus.
