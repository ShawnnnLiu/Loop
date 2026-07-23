"""The /sources bibliography generator (``export_sources_page``).

The page is re-derived from the corpus registry, never hand-maintained: each
:class:`CorpusDocument` already carries the ``track_tags`` career labels, so the
tool deduplicates by URL, buckets by track, discovers which tracks are present,
and renders deterministic HTML. ``--check`` gates drift in CI.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.retrieval import SqliteCorpusRegistry
from agentic_calendar.tools.export_sources_page import main, render

_COLLECTED = date(2026, 7, 1)


def _register(
    registry: SqliteCorpusRegistry,
    url: str,
    *,
    title: str,
    tracks: list[CareerTrack],
    source_type: SourceType = SourceType.COMPANY_ENGINEERING_BLOG,
) -> None:
    text = f"Corpus text for {url} long enough to be a plausible page body."
    registry.register(
        CorpusDocument(
            doc_id=derive_doc_id(url, _COLLECTED),
            source_url=url,
            source_type=source_type,
            license_note="Public page; test fixture.",
            date_collected=_COLLECTED,
            source_published_date=None,
            track_tags=tracks,
            content_hash=content_hash_for(text),
            title=title,
        ),
        text=text,
    )


def _corpus(tmp_path: Path) -> Path:
    corpus_db = tmp_path / "corpus.db"
    registry = SqliteCorpusRegistry(SqliteDatabase(corpus_db))
    # A multi-track source, a single-track source, and a source on a track that
    # is NOT in the preferred order list (data_analyst starts empty in prod).
    _register(
        registry,
        "https://eng.example/scaling",
        title="Scaling systems",
        tracks=[CareerTrack.SWE, CareerTrack.MLE],
    )
    _register(
        registry,
        "https://ai.example/agents",
        title="Building agents",
        tracks=[CareerTrack.AI_ENGINEER],
        source_type=SourceType.PERSONAL_ANECDOTE,
    )
    _register(
        registry,
        "https://analytics.example/dashboards",
        title="Dashboards that matter",
        tracks=[CareerTrack.DATA_ANALYST],
    )
    return corpus_db


def _docs(tmp_path: Path) -> list[CorpusDocument]:
    return SqliteCorpusRegistry(SqliteDatabase(_corpus(tmp_path))).list_documents()


def test_render_groups_by_track_and_counts_unique_sources(tmp_path: Path) -> None:
    html = render(_docs(tmp_path))
    # Three unique URLs; the multi-track source appears under BOTH its tracks,
    # so the section anchors exist for swe, mle, ai_engineer, data_analyst.
    assert "3 unique sources" in html
    for track in ("swe", "mle", "ai_engineer", "data_analyst"):
        assert f'id="{track}"' in html
    # A track with no sources never renders.
    assert 'id="quant_dev"' not in html
    # The multi-track source is listed under both swe and mle.
    assert html.count("https://eng.example/scaling") == 2
    # Human-friendly source-type label is rendered, not the raw enum value.
    assert "Practitioner essay" in html
    assert "personal_anecdote" not in html


def test_render_discovers_newly_populated_tracks(tmp_path: Path) -> None:
    # data_analyst is absent from prod today; the page must surface it the
    # moment a source is scraped onto it - no code change required.
    html = render(_docs(tmp_path))
    assert "Data Analytics" in html
    assert 'href="#data_analyst"' in html


def test_render_is_deterministic(tmp_path: Path) -> None:
    docs = _docs(tmp_path)
    assert render(docs) == render(docs)


def test_write_then_check_roundtrip(tmp_path: Path) -> None:
    corpus_db = _corpus(tmp_path)
    out = tmp_path / "sources.html"
    argv = ["--corpus-db", str(corpus_db), "--out", str(out)]

    assert main(argv) == 0
    assert out.is_file()
    # A freshly written page passes --check.
    assert main([*argv, "--check"]) == 0

    # Any drift fails --check.
    out.write_text(out.read_text(encoding="utf-8") + "\n<!--drift-->", encoding="utf-8")
    assert main([*argv, "--check"]) == 1


def test_check_reports_missing_output(tmp_path: Path) -> None:
    corpus_db = _corpus(tmp_path)
    out = tmp_path / "never-written.html"
    assert main(["--corpus-db", str(corpus_db), "--out", str(out), "--check"]) == 1


def test_missing_corpus_db_is_a_clean_error(tmp_path: Path) -> None:
    out = tmp_path / "sources.html"
    assert main(["--corpus-db", str(tmp_path / "absent.db"), "--out", str(out)]) == 1
    assert not out.exists()
