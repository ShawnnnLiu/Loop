"""Tests for the embed CLI + the eval CLI's hybrid mode (G-E).

All offline: the embedding transport is a deterministic fake recording its
calls. Covers the dry-run-first contract, the hard token cap, idempotent
resume (cache hits skip provider calls), and the end-to-end seam — embed CLI
populates the cache, eval CLI grades ``--mode hybrid`` from it, and an
unpopulated cache is a loud typed error, never a silent BM25 run.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from agentic_calendar.contracts.corpus_snapshot import ChunkingParams
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.llm_nodes.voyage_embeddings import (
    EmbeddingBatch,
    EmbeddingConfig,
    EmbeddingInputType,
)
from agentic_calendar.retrieval import SqliteCorpusRegistry, SqliteVectorStore
from agentic_calendar.tools.embed_corpus import main as embed_main
from agentic_calendar.tools.run_retrieval_eval import main as eval_main

_COLLECTED = date(2026, 7, 6)
_CREATED_AT = datetime(2026, 7, 6, 18, 0, tzinfo=UTC)
_PARAMS = ChunkingParams(algorithm="structure_v1", target_chars=200, overlap_chars=0)

_URL_DESIGN = "https://example.com/system-design"
_URL_ML = "https://example.com/ml-pipelines"

_TEXTS = {
    _URL_DESIGN: (
        "System design interviews reward structured thinking.\n"
        "Capacity estimation and sharding come up constantly."
    ),
    _URL_ML: (
        "Machine learning pipelines need reproducible feature engineering.\n"
        "Monitor data drift after every deployment."
    ),
}


class FakeEmbeddingTransport:
    """Deterministic vectors (a pure function of the text); records calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def embed(
        self,
        texts: list[str],
        *,
        input_type: EmbeddingInputType,
        config: EmbeddingConfig,
    ) -> EmbeddingBatch:
        self.calls.append((input_type, len(texts)))
        vectors = [[1.0, float(len(text) % 5)] for text in texts]
        return EmbeddingBatch(
            vectors=vectors,
            total_tokens=sum(len(text) // 4 for text in texts),
            latency_ms=1,
        )


def _seed_corpus(tmp_path: Path) -> tuple[Path, str]:
    db_path = tmp_path / "corpus.db"
    registry = SqliteCorpusRegistry(SqliteDatabase(db_path))
    doc_ids = []
    for url, text in _TEXTS.items():
        document = CorpusDocument(
            doc_id=derive_doc_id(url, _COLLECTED),
            source_url=url,
            source_type=SourceType.UNCLASSIFIED,
            license_note="Public page; test fixture.",
            date_collected=_COLLECTED,
            track_tags=[CareerTrack.SWE],
            content_hash=content_hash_for(text),
            title=url,
        )
        registry.register(document, text=text)
        doc_ids.append(document.doc_id)
    snapshot = registry.create_snapshot(
        doc_ids, created_at=_CREATED_AT, chunking_params=_PARAMS
    )
    return db_path, snapshot.snapshot_id


def _write_queries(tmp_path: Path) -> Path:
    path = tmp_path / "queries.json"
    path.write_text(
        json.dumps(
            {
                "query_set_version": "retrieval-queries-test",
                "cases": [
                    {
                        "query_id": "rq_hit",
                        "query_text": "system design sharding",
                        "track": "swe",
                        "relevant_source_urls": [_URL_DESIGN],
                    },
                    {
                        "query_id": "rq_miss",
                        "query_text": "quantum chromodynamics",
                        "track": "swe",
                        "relevant_source_urls": [_URL_ML],
                    },
                ],
            }
        )
    )
    return path


def test_dry_run_estimates_without_any_provider_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    queries = _write_queries(tmp_path)
    transport = FakeEmbeddingTransport()
    rc = embed_main(
        [
            "--db", str(db_path), "--snapshot", snapshot_id,
            "--queries", str(queries), "--dry-run",
        ],
        transport=transport,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert transport.calls == []
    assert "to embed" in out
    assert "estimated" in out
    assert "dry run: no network calls made" in out
    assert SqliteVectorStore(SqliteDatabase(db_path)).count(model_name="voyage-3.5") == 0


def test_execute_caches_vectors_and_reports_measured_usage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    queries = _write_queries(tmp_path)
    transport = FakeEmbeddingTransport()
    rc = embed_main(
        ["--db", str(db_path), "--snapshot", snapshot_id, "--queries", str(queries)],
        transport=transport,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert [call[0] for call in transport.calls] == ["document", "query"]
    assert "measured" in out
    vectors = SqliteVectorStore(SqliteDatabase(db_path))
    assert vectors.count(model_name="voyage-3.5") > 0


def test_rerun_is_idempotent_and_makes_no_provider_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    queries = _write_queries(tmp_path)
    first = FakeEmbeddingTransport()
    assert (
        embed_main(
            ["--db", str(db_path), "--snapshot", snapshot_id, "--queries", str(queries)],
            transport=first,
        )
        == 0
    )
    second = FakeEmbeddingTransport()
    rc = embed_main(
        ["--db", str(db_path), "--snapshot", snapshot_id, "--queries", str(queries)],
        transport=second,
    )
    assert rc == 0
    assert second.calls == []
    assert "nothing to embed" in capsys.readouterr().out


class FailAfterFirstBatchTransport(FakeEmbeddingTransport):
    """Succeeds once, then raises — models a mid-run rate-limit exhaustion."""

    def embed(
        self,
        texts: list[str],
        *,
        input_type: EmbeddingInputType,
        config: EmbeddingConfig,
    ) -> EmbeddingBatch:
        if self.calls:
            from agentic_calendar.llm_nodes.anthropic_adapter import TransportError

            raise TransportError("provider rate limited: HTTP 429", retryable=True)
        return super().embed(texts, input_type=input_type, config=config)


def test_mid_run_failure_keeps_completed_batches_and_resumes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    flaky = FailAfterFirstBatchTransport()
    rc = embed_main(
        ["--db", str(db_path), "--snapshot", snapshot_id, "--batch-size", "1"],
        transport=flaky,
    )
    assert rc == 1
    assert "rate limited" in capsys.readouterr().err
    vectors = SqliteVectorStore(SqliteDatabase(db_path))
    cached_after_failure = vectors.count(model_name="voyage-3.5")
    assert cached_after_failure == 1  # the completed batch survived

    healthy = FakeEmbeddingTransport()
    rc = embed_main(
        ["--db", str(db_path), "--snapshot", snapshot_id, "--batch-size", "1"],
        transport=healthy,
    )
    assert rc == 0
    # The resume embedded only what the failed run had not cached.
    assert sum(count for _, count in healthy.calls) == (
        vectors.count(model_name="voyage-3.5") - cached_after_failure
    )


def test_token_cap_refuses_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    transport = FakeEmbeddingTransport()
    rc = embed_main(
        ["--db", str(db_path), "--snapshot", snapshot_id, "--max-tokens", "1"],
        transport=transport,
    )
    assert rc == 1
    assert transport.calls == []
    assert "exceeds the --max-tokens cap" in capsys.readouterr().err


def test_missing_database_is_a_loud_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = embed_main(
        ["--db", str(tmp_path / "absent.db"), "--snapshot", "snap_0000000000000000"],
        transport=FakeEmbeddingTransport(),
    )
    assert rc == 1
    assert "corpus database not found" in capsys.readouterr().err


def test_unknown_snapshot_is_a_loud_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, _ = _seed_corpus(tmp_path)
    rc = embed_main(
        ["--db", str(db_path), "--snapshot", "snap_0000000000000000"],
        transport=FakeEmbeddingTransport(),
    )
    assert rc == 1
    assert "is not in" in capsys.readouterr().err


def test_hybrid_eval_runs_from_the_populated_cache(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    queries = _write_queries(tmp_path)
    assert (
        embed_main(
            ["--db", str(db_path), "--snapshot", snapshot_id, "--queries", str(queries)],
            transport=FakeEmbeddingTransport(),
        )
        == 0
    )
    capsys.readouterr()
    rc = eval_main(
        [
            "--queries", str(queries), "--db", str(db_path),
            "--snapshot", snapshot_id, "--mode", "hybrid",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "retriever: hybrid (model voyage-3.5" in out
    assert "aggregate (2 cases" in out


def test_hybrid_eval_without_cache_is_a_loud_typed_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    queries = _write_queries(tmp_path)
    rc = eval_main(
        [
            "--queries", str(queries), "--db", str(db_path),
            "--snapshot", snapshot_id, "--mode", "hybrid",
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "not cached" in err
    assert "embed_corpus" in err
