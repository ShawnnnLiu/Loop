"""Tests for the freshness stats CLI (grounding-RAG G-I). Fully offline.

The load-bearing properties: the expired boundary is inclusive and the stale
window reuses ``ConfidencePriors.stale_ramp_days`` (no second threshold), the
per-track view joins claims to corpus documents by document URL with the
``#fragment`` breadcrumb stripped (multi-track documents count in each track,
unjoinable claims report as unmapped instead of vanishing), the decay flag is
strictly-greater-than the recorded prior, and the CLI is read-only reporting —
both databases are optional, either alone works.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from agentic_calendar.contracts.corpus_snapshot import ChunkingParams
from agentic_calendar.contracts.source_claim import (
    SourceClaim,
    SourceType,
    bucket_for_score,
)
from agentic_calendar.retrieval import SqliteCorpusRegistry
from agentic_calendar.source_claims.priors import DEFAULT_CONFIDENCE_PRIORS
from agentic_calendar.source_claims.sqlite_store import SqliteSourceClaimStore
from agentic_calendar.tools.corpus_stats import (
    DECAY_STALE_SHARE_THRESHOLD,
    build_claims_report,
    build_corpus_report,
    document_url_of,
    main,
)

_NOW = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
_TODAY = date(2026, 7, 6)
_RAMP = DEFAULT_CONFIDENCE_PRIORS.stale_ramp_days

_PARAMS = ChunkingParams(algorithm="structure_v1", target_chars=400, overlap_chars=0)


def _claim(
    claim_id: str,
    *,
    source_url: str,
    expires_at: date,
    source_type: SourceType = SourceType.COMPANY_ENGINEERING_BLOG,
) -> SourceClaim:
    """A contract-valid claim with a chosen expiry (scores are irrelevant here)."""
    score = 0.75
    return SourceClaim(
        claim_id=claim_id,
        claim_text="A bounded verbatim excerpt long enough to state something.",
        source_url=source_url,
        source_type=source_type,
        date_collected=min(_TODAY, expires_at),
        confidence_score=score,
        confidence_bucket=bucket_for_score(score),
        expires_at=expires_at,
    )


# --------------------------------------------------------------------------- #
# claims report
# --------------------------------------------------------------------------- #


def test_expired_boundary_is_inclusive_and_stale_window_reuses_the_ramp_prior() -> None:
    claims = [
        _claim("claim_a", source_url="https://x.example/a", expires_at=_TODAY),
        _claim(
            "claim_b",
            source_url="https://x.example/b",
            expires_at=_TODAY + timedelta(days=1),
        ),
        _claim(
            "claim_c",
            source_url="https://x.example/c",
            expires_at=_TODAY + timedelta(days=_RAMP),
        ),
        _claim(
            "claim_d",
            source_url="https://x.example/d",
            expires_at=_TODAY + timedelta(days=_RAMP + 1),
        ),
    ]
    report = build_claims_report(claims, today=_TODAY, tracks_by_document_url=None)
    assert (report.overall.expired, report.overall.stale_window, report.overall.fresh) == (
        1,
        2,
        1,
    )
    assert report.overall.total == 4


def test_claims_group_by_source_type() -> None:
    claims = [
        _claim("claim_a", source_url="https://x.example/a", expires_at=_TODAY),
        _claim(
            "claim_b",
            source_url="https://x.example/b",
            expires_at=_TODAY + timedelta(days=365),
            source_type=SourceType.PERSONAL_ANECDOTE,
        ),
    ]
    report = build_claims_report(claims, today=_TODAY, tracks_by_document_url=None)
    assert set(report.by_source_type) == {"company_engineering_blog", "personal_anecdote"}
    assert report.by_source_type["company_engineering_blog"].expired == 1
    assert report.by_source_type["personal_anecdote"].fresh == 1


def test_track_join_strips_fragments_counts_multitrack_in_each_and_reports_unmapped() -> None:
    join = {
        "https://x.example/doc": {"swe", "mle"},
        "https://y.example/doc": {"swe"},
    }
    claims = [
        # Breadcrumb fragment must not defeat the join.
        _claim(
            "claim_a",
            source_url="https://x.example/doc#section-heading",
            expires_at=_TODAY,
        ),
        _claim(
            "claim_b",
            source_url="https://y.example/doc",
            expires_at=_TODAY + timedelta(days=365),
        ),
        _claim(
            "claim_c",
            source_url="https://unregistered.example/page",
            expires_at=_TODAY + timedelta(days=365),
        ),
    ]
    assert document_url_of(claims[0].source_url) == "https://x.example/doc"
    report = build_claims_report(claims, today=_TODAY, tracks_by_document_url=join)
    by_track = {row.track: row for row in report.by_track}
    assert set(by_track) == {"swe", "mle"}
    assert by_track["mle"].counts.total == 1  # the multi-track doc's claim
    assert by_track["swe"].counts.total == 2
    assert report.unmapped_claims == 1
    # The unmapped claim still counts in overall and by-source-type views.
    assert report.overall.total == 3


def test_decay_flag_is_strictly_greater_than_the_prior() -> None:
    join = {
        "https://half.example/doc": {"half_stale"},
        "https://most.example/doc": {"mostly_stale"},
    }
    claims = [
        # half_stale: 1 of 2 expired → exactly the 0.50 threshold → NOT decaying.
        _claim("claim_a", source_url="https://half.example/doc", expires_at=_TODAY),
        _claim(
            "claim_b",
            source_url="https://half.example/doc",
            expires_at=_TODAY + timedelta(days=365),
        ),
        # mostly_stale: 2 of 3 stale-or-expired → 0.667 → decaying.
        _claim("claim_c", source_url="https://most.example/doc", expires_at=_TODAY),
        _claim(
            "claim_d",
            source_url="https://most.example/doc",
            expires_at=_TODAY + timedelta(days=_RAMP),
        ),
        _claim(
            "claim_e",
            source_url="https://most.example/doc",
            expires_at=_TODAY + timedelta(days=365),
        ),
    ]
    report = build_claims_report(claims, today=_TODAY, tracks_by_document_url=join)
    by_track = {row.track: row for row in report.by_track}
    assert DECAY_STALE_SHARE_THRESHOLD == 0.50
    assert by_track["half_stale"].counts.stale_or_expired_share == 0.5
    assert not by_track["half_stale"].decaying
    assert by_track["mostly_stale"].decaying


# --------------------------------------------------------------------------- #
# corpus report
# --------------------------------------------------------------------------- #


def _register(
    registry: SqliteCorpusRegistry,
    url: str,
    *,
    collected: date,
    published: date | None,
    tracks: list[CareerTrack],
) -> str:
    text = f"Corpus text for {url} long enough to be a plausible page body."
    document = CorpusDocument(
        doc_id=derive_doc_id(url, collected),
        source_url=url,
        source_type=SourceType.UNCLASSIFIED,
        license_note="Public page; test fixture.",
        date_collected=collected,
        source_published_date=published,
        track_tags=tracks,
        content_hash=content_hash_for(text),
        title=url,
    )
    registry.register(document, text=text)
    return document.doc_id


def _build_corpus(tmp_path: Path) -> Path:
    corpus_db = tmp_path / "corpus.db"
    registry = SqliteCorpusRegistry(SqliteDatabase(corpus_db))
    doc_a = _register(
        registry,
        "https://x.example/doc",
        collected=_TODAY - timedelta(days=10),
        published=_TODAY - timedelta(days=100),
        tracks=[CareerTrack.SWE, CareerTrack.MLE],
    )
    doc_b = _register(
        registry,
        "https://y.example/doc",
        collected=_TODAY - timedelta(days=30),
        published=None,
        tracks=[CareerTrack.SWE],
    )
    registry.create_snapshot(
        [doc_a], created_at=_NOW - timedelta(days=20), chunking_params=_PARAMS
    )
    registry.create_snapshot(
        [doc_a, doc_b], created_at=_NOW - timedelta(days=3), chunking_params=_PARAMS
    )
    return corpus_db


def test_corpus_report_ages_per_track_and_snapshot_ages(tmp_path: Path) -> None:
    corpus_db = _build_corpus(tmp_path)
    registry = SqliteCorpusRegistry(SqliteDatabase(corpus_db))
    report = build_corpus_report(registry, today=_TODAY)
    assert report.documents == 2
    assert report.snapshots == 2
    assert report.oldest_snapshot_age_days == 20
    assert report.newest_snapshot_age_days == 3
    by_track = {row.track: row for row in report.by_track}
    assert set(by_track) == {"swe", "mle"}
    swe = by_track["swe"]
    assert swe.documents == 2
    assert (swe.collected_age.min_days, swe.collected_age.max_days) == (10, 30)
    assert swe.collected_age.median_days == 20.0
    assert swe.published_age is not None and swe.published_age.count == 1
    assert by_track["mle"].published_age is not None
    assert by_track["mle"].published_age.min_days == 100


def test_corpus_report_with_no_snapshots_has_no_ages(tmp_path: Path) -> None:
    corpus_db = tmp_path / "corpus.db"
    registry = SqliteCorpusRegistry(SqliteDatabase(corpus_db))
    report = build_corpus_report(registry, today=_TODAY)
    assert report.documents == 0
    assert report.oldest_snapshot_age_days is None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_app_db(tmp_path: Path) -> Path:
    app_db = tmp_path / "app.db"
    store = SqliteSourceClaimStore(SqliteDatabase(app_db))
    store.append(
        _claim("claim_a", source_url="https://x.example/doc#intro", expires_at=_TODAY)
    )
    store.append(
        _claim(
            "claim_b",
            source_url="https://x.example/doc#details",
            expires_at=_TODAY + timedelta(days=365),
        )
    )
    store.append(
        _claim(
            "claim_c",
            source_url="https://unregistered.example/page",
            expires_at=_TODAY + timedelta(days=365),
        )
    )
    return app_db


def test_cli_requires_at_least_one_database() -> None:
    assert main([]) == 1


def test_cli_rejects_a_missing_database_path(tmp_path: Path) -> None:
    assert main(["--corpus-db", str(tmp_path / "absent.db")]) == 1


def test_cli_reports_both_sides_with_the_track_join(tmp_path: Path, capsys: Any) -> None:
    corpus_db = _build_corpus(tmp_path)
    app_db = _build_app_db(tmp_path)
    exit_code = main(
        ["--corpus-db", str(corpus_db), "--app-db", str(app_db)],
        clock=FrozenClock(_NOW),
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "corpus: 2 documents, 2 snapshot(s)" in out
    assert "claims: 3 claims" in out
    assert "claims by track" in out
    assert "unmapped: 1 claim(s)" in out
    assert "heuristic prior" in out


def test_cli_claims_only_run_reports_everything_unmapped(tmp_path: Path, capsys: Any) -> None:
    app_db = _build_app_db(tmp_path)
    assert main(["--app-db", str(app_db)], clock=FrozenClock(_NOW)) == 0
    out = capsys.readouterr().out
    assert "corpus:" not in out
    assert "unmapped: 3 claim(s)" in out


def test_cli_json_output_is_machine_readable(tmp_path: Path, capsys: Any) -> None:
    corpus_db = _build_corpus(tmp_path)
    app_db = _build_app_db(tmp_path)
    exit_code = main(
        ["--corpus-db", str(corpus_db), "--app-db", str(app_db), "--json"],
        clock=FrozenClock(_NOW),
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["as_of"] == _TODAY.isoformat()
    assert payload["stale_window_days"] == _RAMP
    assert payload["decay_stale_share_threshold"] == DECAY_STALE_SHARE_THRESHOLD
    assert payload["corpus"]["documents"] == 2
    assert payload["claims"]["overall"]["total"] == 3
    # claim_a (x.example, expired) counts in both of the doc's tracks.
    swe = next(row for row in payload["claims"]["by_track"] if row["track"] == "swe")
    assert swe["counts"]["expired"] == 1
