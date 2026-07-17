"""Tests for the corpus ingestion CLI. No network: fetching is always faked."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import derive_doc_id
from agentic_calendar.contracts.corpus_snapshot import ChunkingParams
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.retrieval import (
    DEFAULT_CHUNKING_PARAMS,
    InMemoryCorpusRegistry,
    SqliteCorpusRegistry,
)
from agentic_calendar.tools.ingest_corpus import (
    CorpusManifest,
    FetchOutcome,
    FetchStatus,
    IngestStatus,
    UrllibFetcher,
    load_manifest,
    main,
    run_ingestion,
)

_TODAY = date(2026, 7, 6)

_REPO_MANIFEST = Path(__file__).parents[2] / "corpus" / "manifest_v1.json"


class FakeFetcher:
    """Canned fetch outcomes keyed by URL; records every call."""

    def __init__(self, pages: dict[str, FetchOutcome]) -> None:
        self._pages = pages
        self.calls: list[str] = []

    def fetch(self, url: str) -> FetchOutcome:
        self.calls.append(url)
        return self._pages[url]


def _ok(text: str) -> FetchOutcome:
    return FetchOutcome(status=FetchStatus.OK, text=text)


def _manifest(**overrides: object) -> CorpusManifest:
    payload: dict[str, object] = {
        "manifest_version": "corpus-manifest-v1",
        "engineering_blog_hosts": ["engineering.acme.com"],
        "sources": [
            {
                "url": "https://engineering.acme.com/interview-guide",
                "expected_type": "company_engineering_blog",
                "track_tags": ["swe"],
                "license_note": "Public blog post; excerpts bounded.",
                "title": "Interview guide",
            },
            {
                "url": "https://example.org/notes",
                "expected_type": "unclassified",
                "track_tags": ["mle"],
                "license_note": "Public page.",
                "title": "Notes",
            },
        ],
    }
    payload.update(overrides)
    return CorpusManifest.model_validate(payload)


#: Fixture pages are realistically sized: the thin-document gate (default
#: ``DEFAULT_MIN_DOC_CHARS``) must see them as real pages, and the double
#: spaces exercise normalization exactly as the old one-line bodies did.
_GUIDE_NORMALIZED = (
    "Guide\nAPI design questions reward structured preparation: estimate "
    "capacity first, partition the data, and name the load-balancer "
    "trade-offs before drawing boxes. Strong candidates rehearse clarifying "
    "questions out loud and close every design with its failure modes."
)
_NOTES_NORMALIZED = (
    "Plain notes about feature stores, offline training tables, and the "
    "online serving skew that appears when the two drift apart. Batch "
    "features arrive hourly, streaming features arrive in seconds, and a "
    "daily reconciliation job compares both paths for silent divergence."
)

_PAGES = {
    "https://engineering.acme.com/interview-guide": _ok(
        "<!DOCTYPE html><html><body><h1>Guide</h1><p>"
        + _GUIDE_NORMALIZED.split("\n", 1)[1].replace("API design", "API   design", 1)
        + "</p></body></html>"
    ),
    "https://example.org/notes": _ok(
        _NOTES_NORMALIZED.replace("about feature", "about   feature", 1)
    ),
}


def test_run_ingestion_registers_normalized_documents() -> None:
    registry = InMemoryCorpusRegistry()
    fetcher = FakeFetcher(dict(_PAGES))
    report = run_ingestion(
        _manifest(), registry=registry, fetcher=fetcher, today=_TODAY, max_fetches=10
    )

    assert [r.status for r in report.results] == [IngestStatus.REGISTERED] * 2
    assert not report.failed
    documents = registry.list_documents()
    assert len(documents) == 2
    guide_id = derive_doc_id("https://engineering.acme.com/interview-guide", _TODAY)
    assert registry.get_text(guide_id) == _GUIDE_NORMALIZED
    assert registry.get_text(
        derive_doc_id("https://example.org/notes", _TODAY)
    ) == _NOTES_NORMALIZED
    assert registry.list_documents(track=CareerTrack.SWE)[0].doc_id == guide_id


def test_reingest_unchanged_pages_is_a_noop() -> None:
    registry = InMemoryCorpusRegistry()
    run_ingestion(
        _manifest(),
        registry=registry,
        fetcher=FakeFetcher(dict(_PAGES)),
        today=_TODAY,
        max_fetches=10,
    )
    second = run_ingestion(
        _manifest(),
        registry=registry,
        fetcher=FakeFetcher(dict(_PAGES)),
        today=_TODAY,
        max_fetches=10,
    )
    assert [r.status for r in second.results] == [IngestStatus.UNCHANGED] * 2
    assert len(registry.list_documents()) == 2


def test_changed_page_same_day_is_a_typed_conflict() -> None:
    registry = InMemoryCorpusRegistry()
    run_ingestion(
        _manifest(),
        registry=registry,
        fetcher=FakeFetcher(dict(_PAGES)),
        today=_TODAY,
        max_fetches=10,
    )
    changed = dict(_PAGES)
    changed["https://example.org/notes"] = _ok(
        _NOTES_NORMALIZED + " Updated mid-day with a correction to the "
        "reconciliation cadence and a note on backfill windows."
    )
    report = run_ingestion(
        _manifest(),
        registry=registry,
        fetcher=FakeFetcher(changed),
        today=_TODAY,
        max_fetches=10,
    )
    by_url = {r.url: r for r in report.results}
    assert by_url["https://example.org/notes"].status is IngestStatus.CONFLICT
    assert report.failed
    # The stored document is unchanged.
    assert registry.get_text(
        derive_doc_id("https://example.org/notes", _TODAY)
    ) == _NOTES_NORMALIZED


def test_fetch_failures_are_typed_and_do_not_stop_the_run() -> None:
    pages = dict(_PAGES)
    pages["https://engineering.acme.com/interview-guide"] = FetchOutcome(
        status=FetchStatus.FETCH_FAILED, error="timed out"
    )
    registry = InMemoryCorpusRegistry()
    report = run_ingestion(
        _manifest(),
        registry=registry,
        fetcher=FakeFetcher(pages),
        today=_TODAY,
        max_fetches=10,
    )
    by_url = {r.url: r for r in report.results}
    assert by_url["https://engineering.acme.com/interview-guide"].status is (
        IngestStatus.FETCH_FAILED
    )
    assert by_url["https://example.org/notes"].status is IngestStatus.REGISTERED
    assert report.failed


def test_thin_fetch_is_a_typed_skip_and_fails_the_run() -> None:
    """A page that fetches but normalizes to (almost) nothing — the levels.fyi
    0-byte JS shell in the v1 corpus is the motivating case — must not enter
    the append-only registry."""
    pages = dict(_PAGES)
    pages["https://example.org/notes"] = _ok(
        "<!DOCTYPE html><html><body><script>renderApp()</script></body></html>"
    )
    registry = InMemoryCorpusRegistry()
    report = run_ingestion(
        _manifest(),
        registry=registry,
        fetcher=FakeFetcher(pages),
        today=_TODAY,
        max_fetches=10,
    )
    by_url = {r.url: r for r in report.results}
    thin = by_url["https://example.org/notes"]
    assert thin.status is IngestStatus.SKIPPED_THIN
    assert thin.error is not None and "0 chars" in thin.error
    assert report.failed
    # The good page still registered; the thin one left no trace.
    assert [d.source_url for d in registry.list_documents()] == [
        "https://engineering.acme.com/interview-guide"
    ]


def test_min_doc_chars_zero_disables_the_thin_gate() -> None:
    pages = dict(_PAGES)
    pages["https://example.org/notes"] = _ok(
        "<!DOCTYPE html><html><body><script>renderApp()</script></body></html>"
    )
    registry = InMemoryCorpusRegistry()
    report = run_ingestion(
        _manifest(),
        registry=registry,
        fetcher=FakeFetcher(pages),
        today=_TODAY,
        max_fetches=10,
        min_doc_chars=0,
    )
    assert [r.status for r in report.results] == [IngestStatus.REGISTERED] * 2
    assert registry.get_text(derive_doc_id("https://example.org/notes", _TODAY)) == ""


def test_per_run_fetch_cap_skips_remaining_sources() -> None:
    registry = InMemoryCorpusRegistry()
    fetcher = FakeFetcher(dict(_PAGES))
    report = run_ingestion(
        _manifest(), registry=registry, fetcher=fetcher, today=_TODAY, max_fetches=1
    )
    assert [r.status for r in report.results] == [
        IngestStatus.REGISTERED,
        IngestStatus.SKIPPED_OVER_CAP,
    ]
    assert fetcher.calls == ["https://engineering.acme.com/interview-guide"]
    assert len(registry.list_documents()) == 1


def test_company_domain_classifies_through_existing_classifier() -> None:
    """A manifest URL on a declared company domain becomes an official job
    posting — through ``source_claims.classification.classify_source``, no
    second rule set."""
    manifest = _manifest(
        known_company_domains=["acme.com"],
        engineering_blog_hosts=[],
        sources=[
            {
                "url": "https://acme.com/careers/12345",
                "expected_type": "official_job_posting",
                "track_tags": ["swe"],
                "license_note": "Public job posting; volatile.",
                "title": "Backend Engineer",
            }
        ],
    )
    registry = InMemoryCorpusRegistry()
    report = run_ingestion(
        manifest,
        registry=registry,
        fetcher=FakeFetcher(
            {
                "https://acme.com/careers/12345": _ok(
                    "Backend Engineer, Platform. Acme is hiring a backend "
                    "engineer to own the ingestion pipeline: Python services, "
                    "Postgres, and a queue that moves a few billion events a "
                    "day. You will design APIs, review capacity plans, and "
                    "carry the pager one week in six. Hybrid, Toronto."
                )
            }
        ),
        today=_TODAY,
        max_fetches=10,
    )
    (result,) = report.results
    assert result.status is IngestStatus.REGISTERED
    assert not result.type_mismatch
    (document,) = registry.list_documents()
    assert document.source_type is SourceType.OFFICIAL_JOB_POSTING


def test_expected_type_mismatch_is_flagged_and_classifier_wins() -> None:
    manifest = _manifest(
        engineering_blog_hosts=[],  # host no longer declared -> unclassified
    )
    registry = InMemoryCorpusRegistry()
    report = run_ingestion(
        manifest,
        registry=registry,
        fetcher=FakeFetcher(dict(_PAGES)),
        today=_TODAY,
        max_fetches=10,
    )
    by_url = {r.url: r for r in report.results}
    guide = by_url["https://engineering.acme.com/interview-guide"]
    assert guide.status is IngestStatus.REGISTERED
    assert guide.type_mismatch
    assert report.mismatches == [guide]
    stored = registry.get_document(
        derive_doc_id("https://engineering.acme.com/interview-guide", _TODAY)
    )
    assert stored is not None
    assert stored.source_type is SourceType.UNCLASSIFIED


# --------------------------------------------------------------------------- #
# CLI surface.
# --------------------------------------------------------------------------- #


def _write_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(_manifest().model_dump_json(), encoding="utf-8")
    return path


def test_cli_dry_run_touches_neither_network_nor_database(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = _write_manifest(tmp_path)
    db_path = tmp_path / "corpus.db"
    rc = main(
        ["--manifest", str(manifest_path), "--db", str(db_path), "--dry-run"],
        today=_TODAY,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "[would-fetch] https://engineering.acme.com/interview-guide" in out
    assert "nothing fetched, nothing registered" in out
    assert not db_path.exists()


def test_cli_live_run_registers_and_snapshots(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = _write_manifest(tmp_path)
    db_path = tmp_path / "corpus.db"
    now = datetime(2026, 7, 6, 18, 0, tzinfo=UTC)
    rc = main(
        ["--manifest", str(manifest_path), "--db", str(db_path), "--snapshot"],
        fetcher=FakeFetcher(dict(_PAGES)),
        today=_TODAY,
        now=now,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "summary: 2 sources — registered=2" in out
    assert "by source_type: company_engineering_blog=1, unclassified=1" in out
    assert "snapshot: snap_" in out

    registry = SqliteCorpusRegistry(SqliteDatabase(db_path))
    assert len(registry.list_documents()) == 2
    (snapshot,) = registry.list_snapshots()
    assert snapshot.created_at == now
    assert len(snapshot.doc_ids) == 2
    assert snapshot.chunking_params == DEFAULT_CHUNKING_PARAMS


def test_cli_snapshot_chunk_flags_pin_the_params(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = _write_manifest(tmp_path)
    db_path = tmp_path / "corpus.db"
    rc = main(
        [
            "--manifest",
            str(manifest_path),
            "--db",
            str(db_path),
            "--snapshot",
            "--chunk-target-chars",
            "800",
            "--chunk-overlap-chars",
            "100",
        ],
        fetcher=FakeFetcher(dict(_PAGES)),
        today=_TODAY,
        now=datetime(2026, 7, 6, 18, 0, tzinfo=UTC),
    )
    assert rc == 0
    assert "target=800 overlap=100" in capsys.readouterr().out
    registry = SqliteCorpusRegistry(SqliteDatabase(db_path))
    (snapshot,) = registry.list_snapshots()
    assert snapshot.chunking_params == ChunkingParams(
        algorithm="structure_v1", target_chars=800, overlap_chars=100
    )


def test_cli_rejects_invalid_chunk_flags(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = _write_manifest(tmp_path)
    rc = main(
        [
            "--manifest",
            str(manifest_path),
            "--db",
            str(tmp_path / "corpus.db"),
            "--snapshot",
            "--chunk-target-chars",
            "100",
            "--chunk-overlap-chars",
            "100",
        ],
        fetcher=FakeFetcher(dict(_PAGES)),
        today=_TODAY,
    )
    assert rc == 1
    assert "invalid chunking params" in capsys.readouterr().err


def test_cli_exits_nonzero_on_failures(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    pages = dict(_PAGES)
    pages["https://example.org/notes"] = FetchOutcome(
        status=FetchStatus.FETCH_FAILED, error="boom"
    )
    rc = main(
        ["--manifest", str(manifest_path), "--db", str(tmp_path / "c.db")],
        fetcher=FakeFetcher(pages),
        today=_TODAY,
    )
    assert rc == 1


def test_cli_requires_db_for_live_runs(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)
    rc = main(["--manifest", str(manifest_path)], today=_TODAY)
    assert rc == 1


def test_cli_rejects_invalid_manifest(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"manifest_version": "corpus-manifest-v1"}))
    rc = main(["--manifest", str(path), "--dry-run"], today=_TODAY)
    assert rc == 1


# --------------------------------------------------------------------------- #
# Robots handling (faked opener — no network).
# --------------------------------------------------------------------------- #


def test_urllib_fetcher_respects_robots_txt() -> None:
    opened: list[str] = []

    def opener(url: str, timeout: float, user_agent: str) -> tuple[bytes, str | None]:
        opened.append(url)
        if url == "https://example.org/robots.txt":
            return b"User-agent: *\nDisallow: /private/\n", "utf-8"
        return b"<html><body>ok</body></html>", "utf-8"

    fetcher = UrllibFetcher(opener=opener)
    blocked = fetcher.fetch("https://example.org/private/page")
    assert blocked.status is FetchStatus.ROBOTS_DISALLOWED
    # The disallowed page itself was never opened.
    assert opened == ["https://example.org/robots.txt"]

    allowed = fetcher.fetch("https://example.org/public")
    assert allowed.status is FetchStatus.OK
    assert allowed.text is not None and "ok" in allowed.text
    # robots.txt is cached per host: no second robots fetch.
    assert opened == ["https://example.org/robots.txt", "https://example.org/public"]


def test_urllib_fetcher_rejects_non_http_urls() -> None:
    def opener(url: str, timeout: float, user_agent: str) -> tuple[bytes, str | None]:
        raise AssertionError("must not be called")

    outcome = UrllibFetcher(opener=opener).fetch("file:///etc/passwd")
    assert outcome.status is FetchStatus.FETCH_FAILED
    assert outcome.error is not None and "http" in outcome.error


# --------------------------------------------------------------------------- #
# The checked-in starter manifest stays honest.
# --------------------------------------------------------------------------- #


def test_repo_manifest_is_valid_and_consistent_with_classifier() -> None:
    manifest = load_manifest(_REPO_MANIFEST)
    assert manifest.sources, "starter manifest must not be empty"
    for source in manifest.sources:
        assert manifest.classify(source.url) is source.expected_type, (
            f"{source.url}: manifest expects {source.expected_type.value!r} but "
            f"the classifier says {manifest.classify(source.url).value!r}"
        )


def test_repo_manifest_covers_every_track() -> None:
    # Three starter tracks (G-B) plus the G-I expansion — a new enum member
    # without manifest sources would ship a track with no corpus behind it.
    manifest = load_manifest(_REPO_MANIFEST)
    covered = {tag for source in manifest.sources for tag in source.track_tags}
    assert covered == set(CareerTrack)
