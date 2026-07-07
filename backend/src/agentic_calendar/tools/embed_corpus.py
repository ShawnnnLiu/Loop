"""Populate the retrieval vector cache for one pinned snapshot (G-E).

Usage::

    uv run python -m agentic_calendar.tools.embed_corpus \\
        --db corpus/corpus.db --snapshot snap_xxxxxxxxxxxxxxxx \\
        --queries evalsets/retrieval_queries_v1.json [--dry-run] \\
        [--max-tokens 1000000]

This is the ONLY place embedding provider calls happen (ask-first networked
command, same protocol as ingestion fetches). ``--dry-run`` prints what would
be embedded — chunk/query counts, cache hits, estimated tokens and cost —
without any network call; prefer it first. The live run enforces a hard
token cap and reports measured tokens, estimated cost, and latency (the
embedding analog of the capture tool's call cap + cost guard; embeddings
stay outside the node-keyed LlmCallLog taxonomy like the eval judge does).

Composition seam: this CLI is where ``llm_nodes`` (the Voyage transport) and
``retrieval`` (the vector cache) meet — the regions never import each other.
Cache identity means re-running is cheap: already-embedded texts are skipped,
so a run interrupted by the cap or a provider error resumes where it left
off.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.corpus_document import content_hash_for
from agentic_calendar.llm_nodes.voyage_embeddings import (
    EmbeddingConfig,
    EmbeddingInputType,
    EmbeddingTransport,
    VoyageEmbeddingsTransport,
)
from agentic_calendar.retrieval import (
    SqliteChunkIndex,
    SqliteCorpusRegistry,
    SqliteVectorStore,
)
from agentic_calendar.retrieval.eval import load_query_set

#: Conservative chars-per-token prior for the dry-run estimate only; the
#: live run reports the provider's measured count.
_CHARS_PER_TOKEN_ESTIMATE = 4


class TokenCapExceededError(AgenticCalendarError):
    """The estimated embed volume exceeds the run's hard token cap."""

    def __init__(self, *, estimated_tokens: int, cap: int) -> None:
        self.estimated_tokens = estimated_tokens
        self.cap = cap
        super().__init__(
            f"estimated {estimated_tokens} tokens exceeds the --max-tokens "
            f"cap of {cap}; raise the cap deliberately or narrow the run"
        )


def _pending_texts(
    texts: list[str],
    vectors: SqliteVectorStore,
    *,
    model_name: str,
    input_type: str,
) -> list[str]:
    """Texts with no cached vector, first-seen order, de-duplicated."""
    unique = list(dict.fromkeys(texts))
    by_hash = {content_hash_for(text): text for text in unique}
    missing = vectors.missing(
        list(by_hash), model_name=model_name, input_type=input_type
    )
    return [by_hash[content_hash] for content_hash in missing]


def _estimate_tokens(texts: list[str]) -> int:
    return sum(len(text) for text in texts) // _CHARS_PER_TOKEN_ESTIMATE


def _embed_and_cache(
    transport: EmbeddingTransport,
    vectors: SqliteVectorStore,
    texts: list[str],
    *,
    input_type: EmbeddingInputType,
    config: EmbeddingConfig,
) -> tuple[int, int, int]:
    """Embed ``texts`` batch by batch, caching after every batch.

    Returns (written, tokens, ms). Per-batch caching is what makes the
    resume claim real: a run that dies at batch 30 of 36 has 29 batches on
    disk, and the rerun's cache check skips them — matters under tight
    provider rate limits, where one exhausted retry window fails the run.
    """
    if not texts:
        return 0, 0, 0
    written = 0
    total_tokens = 0
    total_ms = 0
    batch_count = -(-len(texts) // config.batch_size)
    for number, offset in enumerate(range(0, len(texts), config.batch_size), start=1):
        batch_texts = texts[offset : offset + config.batch_size]
        batch = transport.embed(batch_texts, input_type=input_type, config=config)
        written += vectors.put_many(
            [
                (content_hash_for(text), vector)
                for text, vector in zip(batch_texts, batch.vectors, strict=True)
            ],
            model_name=config.model_name,
            input_type=input_type,
        )
        total_tokens += batch.total_tokens
        total_ms += batch.latency_ms
        print(
            f"  {input_type} batch {number}/{batch_count}: "
            f"{len(batch_texts)} text(s), {batch.total_tokens} tokens, "
            f"{batch.latency_ms} ms",
            flush=True,
        )
    return written, total_tokens, total_ms


def main(
    argv: list[str] | None = None,
    *,
    transport: EmbeddingTransport | None = None,
) -> int:
    """CLI entry point. ``transport`` is injectable for tests."""
    parser = argparse.ArgumentParser(
        description=(
            "Embed a pinned snapshot's chunks (and optionally a labeled query "
            "set's query texts) into the retrieval vector cache. Networked and "
            "ask-first; prefer --dry-run first."
        )
    )
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument(
        "--snapshot", required=True, help="Pinned snapshot id (snap_ + 16 hex)."
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=None,
        help="Labeled query set whose query texts to embed as input_type=query.",
    )
    parser.add_argument("--model", default=None, help="Embedding model override.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help=(
            "Texts per provider request (default 128). Lower this to pace a "
            "run under tight provider rate limits (free-tier accounts allow "
            "only a few small requests per minute; the transport's backoff "
            "then rides out each per-minute window)."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1_000_000,
        help="Hard cap on estimated tokens for one live run (default 1M).",
    )
    args = parser.parse_args(argv)

    defaults = EmbeddingConfig()
    config = EmbeddingConfig(
        model_name=args.model if args.model is not None else defaults.model_name,
        batch_size=(
            args.batch_size if args.batch_size is not None else defaults.batch_size
        ),
    )

    if not args.db.exists():
        print(f"error: corpus database not found: {args.db}", file=sys.stderr)
        return 1

    try:
        db = SqliteDatabase(args.db)
        registry = SqliteCorpusRegistry(db)
        snapshot = registry.get_snapshot(args.snapshot)
        if snapshot is None:
            print(
                f"error: snapshot {args.snapshot!r} is not in {args.db}",
                file=sys.stderr,
            )
            return 1
        index = SqliteChunkIndex(db)
        index.build(registry, snapshot)
        vectors = SqliteVectorStore(db)

        chunks = index.list_chunks(snapshot.snapshot_id)
        chunk_texts = _pending_texts(
            [chunk.text for chunk in chunks],
            vectors,
            model_name=config.model_name,
            input_type="document",
        )
        query_texts: list[str] = []
        total_queries = 0
        if args.queries is not None:
            query_set = load_query_set(args.queries)
            total_queries = len(query_set.cases)
            query_texts = _pending_texts(
                [case.query_text for case in query_set.cases],
                vectors,
                model_name=config.model_name,
                input_type="query",
            )

        estimated_tokens = _estimate_tokens(chunk_texts) + _estimate_tokens(query_texts)
        estimated_cost = config.estimate_cost_usd(estimated_tokens)
        print(
            f"snapshot {snapshot.snapshot_id}: {len(chunks)} chunks "
            f"({len(chunks) - len(chunk_texts)} cached, {len(chunk_texts)} to embed); "
            f"{total_queries} queries "
            f"({total_queries - len(query_texts)} cached, {len(query_texts)} to embed)"
        )
        print(
            f"model {config.model_name}: estimated ~{estimated_tokens} tokens, "
            f"~${estimated_cost:.4f} (chars/{_CHARS_PER_TOKEN_ESTIMATE} prior; "
            "live run reports measured usage)"
        )

        if args.dry_run:
            print("dry run: no network calls made, cache unchanged")
            return 0

        if estimated_tokens > args.max_tokens:
            raise TokenCapExceededError(
                estimated_tokens=estimated_tokens, cap=args.max_tokens
            )
        if not chunk_texts and not query_texts:
            print("nothing to embed: cache already covers this run")
            return 0

        effective_transport: EmbeddingTransport = (
            transport if transport is not None else VoyageEmbeddingsTransport()
        )
        doc_written, doc_tokens, doc_ms = _embed_and_cache(
            effective_transport,
            vectors,
            chunk_texts,
            input_type="document",
            config=config,
        )
        query_written, query_tokens, query_ms = _embed_and_cache(
            effective_transport,
            vectors,
            query_texts,
            input_type="query",
            config=config,
        )
        measured_tokens = doc_tokens + query_tokens
        print(
            f"embedded {doc_written} chunk vector(s) + {query_written} query "
            f"vector(s); measured {measured_tokens} tokens, "
            f"~${config.estimate_cost_usd(measured_tokens):.4f}, "
            f"{doc_ms + query_ms} ms"
        )
        print(
            f"vector cache now holds {vectors.count(model_name=config.model_name)} "
            f"vector(s) for {config.model_name}"
        )
    except AgenticCalendarError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
