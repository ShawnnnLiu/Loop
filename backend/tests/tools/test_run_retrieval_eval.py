"""Tests for the retrieval-eval gate CLI.

Includes the harness proof: a deliberately broken floor makes the strict run
exit non-zero (mirrors the ``fixture_baseline`` convention — a gate that
cannot fail is not a gate). Everything is offline: tmp-file SQLite corpus,
no network.
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
from agentic_calendar.retrieval import SqliteCorpusRegistry
from agentic_calendar.tools.run_retrieval_eval import main

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
    # rq_hit retrieves its relevant doc at rank 1; rq_miss labels a document
    # its query terms never match, so aggregate metrics sit strictly between
    # 0 and 1 — both floor outcomes are provable.
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


def test_report_prints_per_case_and_aggregate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    queries = _write_queries(tmp_path)
    rc = main(
        ["--queries", str(queries), "--db", str(db_path), "--snapshot", snapshot_id]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "[rq_hit] recall@5=1.0000" in out
    assert "[rq_miss] recall@5=0.0000" in out
    assert "no relevant doc retrieved" in out
    assert f"snapshot {snapshot_id}" in out
    assert "recall@5=0.5000 mrr=0.5000 ndcg@5=0.5000" in out


def test_strict_gate_passes_on_measured_floors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    queries = _write_queries(tmp_path)
    rc = main(
        [
            "--queries", str(queries), "--db", str(db_path),
            "--snapshot", snapshot_id, "--strict",
            "--min-recall", "0.5", "--min-mrr", "0.5", "--min-ndcg", "0.5",
        ]
    )
    assert rc == 0
    assert "floors: all metrics at or above their floors" in capsys.readouterr().out


def test_strict_gate_fails_on_broken_floor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The harness proof: floors above the measured values must fail the run.
    db_path, snapshot_id = _seed_corpus(tmp_path)
    queries = _write_queries(tmp_path)
    rc = main(
        [
            "--queries", str(queries), "--db", str(db_path),
            "--snapshot", snapshot_id, "--strict",
            "--min-recall", "0.99", "--min-mrr", "0.5", "--min-ndcg", "0.5",
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "FLOOR BREACH" in err
    assert "mean_recall_at_k" in err


def test_strict_requires_all_three_floors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    queries = _write_queries(tmp_path)
    rc = main(
        [
            "--queries", str(queries), "--db", str(db_path),
            "--snapshot", snapshot_id, "--strict", "--min-recall", "0.5",
        ]
    )
    assert rc == 1
    assert "must all be given together" in capsys.readouterr().err


def test_unknown_snapshot_is_a_loud_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, _ = _seed_corpus(tmp_path)
    queries = _write_queries(tmp_path)
    rc = main(
        [
            "--queries", str(queries), "--db", str(db_path),
            "--snapshot", "snap_0000000000000000",
        ]
    )
    assert rc == 1
    assert "is not in" in capsys.readouterr().err


def test_label_url_missing_from_snapshot_is_a_loud_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, snapshot_id = _seed_corpus(tmp_path)
    queries = tmp_path / "queries.json"
    queries.write_text(
        json.dumps(
            {
                "query_set_version": "retrieval-queries-test",
                "cases": [
                    {
                        "query_id": "rq_bad_label",
                        "query_text": "anything",
                        "relevant_source_urls": ["https://example.com/not-ingested"],
                    }
                ],
            }
        )
    )
    rc = main(
        ["--queries", str(queries), "--db", str(db_path), "--snapshot", snapshot_id]
    )
    assert rc == 1
    assert "not-ingested" in capsys.readouterr().err


def test_missing_database_is_a_loud_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    queries = _write_queries(tmp_path)
    rc = main(
        [
            "--queries", str(queries), "--db", str(tmp_path / "absent.db"),
            "--snapshot", "snap_0000000000000000",
        ]
    )
    assert rc == 1
    assert "corpus database not found" in capsys.readouterr().err
