"""Tests for the ``CorpusRegistry`` implementations.

The behavioral suite is parametrized over the in-memory and SQLite
implementations (house pattern from the Phase 9 stores): both must satisfy
the protocol identically. The restart-survival test at the bottom is
SQLite-only by nature.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from agentic_calendar.contracts.corpus_snapshot import (
    ChunkingParams,
    derive_snapshot_id,
)
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.retrieval import (
    CorpusContentHashMismatchError,
    CorpusDocumentConflictError,
    CorpusRegistry,
    EmptySnapshotError,
    InMemoryCorpusRegistry,
    SqliteCorpusRegistry,
    UnknownCorpusDocumentError,
)

_COLLECTED = date(2026, 7, 6)
_CREATED_AT = datetime(2026, 7, 6, 18, 0, tzinfo=UTC)
_PARAMS = ChunkingParams(algorithm="structure_v1", target_chars=1600, overlap_chars=200)


@pytest.fixture(params=["in_memory", "sqlite"])
def registry(request: pytest.FixtureRequest, tmp_path: Path) -> CorpusRegistry:
    if request.param == "sqlite":
        return SqliteCorpusRegistry(SqliteDatabase(tmp_path / "corpus.db"))
    return InMemoryCorpusRegistry()


def _doc(
    url: str,
    *,
    text: str,
    tracks: tuple[CareerTrack, ...] = (CareerTrack.SWE,),
    license_note: str = "Public page; test fixture.",
) -> tuple[CorpusDocument, str]:
    document = CorpusDocument(
        doc_id=derive_doc_id(url, _COLLECTED),
        source_url=url,
        source_type=SourceType.UNCLASSIFIED,
        license_note=license_note,
        date_collected=_COLLECTED,
        track_tags=list(tracks),
        content_hash=content_hash_for(text),
        title="Test document",
    )
    return document, text


def test_satisfies_protocol(registry: CorpusRegistry) -> None:
    assert isinstance(registry, CorpusRegistry)


def test_register_and_read_round_trip(registry: CorpusRegistry) -> None:
    document, text = _doc("https://example.com/a", text="Alpha body.")
    assert registry.register(document, text=text) is True
    assert registry.get_document(document.doc_id) == document
    assert registry.get_text(document.doc_id) == text


def test_identical_reregister_is_a_noop(registry: CorpusRegistry) -> None:
    document, text = _doc("https://example.com/a", text="Alpha body.")
    assert registry.register(document, text=text) is True
    assert registry.register(document, text=text) is False
    assert len(registry.list_documents()) == 1


def test_conflicting_reregister_is_typed_and_leaves_store_unchanged(
    registry: CorpusRegistry,
) -> None:
    document, text = _doc("https://example.com/a", text="Alpha body.")
    registry.register(document, text=text)
    changed, changed_text = _doc("https://example.com/a", text="Changed body.")
    with pytest.raises(CorpusDocumentConflictError):
        registry.register(changed, text=changed_text)
    assert registry.get_document(document.doc_id) == document
    assert registry.get_text(document.doc_id) == text


def test_register_rejects_text_that_does_not_hash_to_pin(
    registry: CorpusRegistry,
) -> None:
    document, _ = _doc("https://example.com/a", text="Alpha body.")
    with pytest.raises(CorpusContentHashMismatchError):
        registry.register(document, text="Different body.")
    assert registry.get_document(document.doc_id) is None


def test_missing_reads_return_none(registry: CorpusRegistry) -> None:
    assert registry.get_document("doc_0000000000000000") is None
    assert registry.get_text("doc_0000000000000000") is None
    assert registry.get_snapshot("snap_0000000000000000") is None


def test_list_documents_preserves_insertion_order_and_filters_by_track(
    registry: CorpusRegistry,
) -> None:
    swe, swe_text = _doc(
        "https://example.com/swe", text="SWE.", tracks=(CareerTrack.SWE,)
    )
    mle, mle_text = _doc(
        "https://example.com/mle", text="MLE.", tracks=(CareerTrack.MLE,)
    )
    both, both_text = _doc(
        "https://example.com/both",
        text="Both.",
        tracks=(CareerTrack.SWE, CareerTrack.MLE),
    )
    registry.register(swe, text=swe_text)
    registry.register(mle, text=mle_text)
    registry.register(both, text=both_text)
    assert registry.list_documents() == [swe, mle, both]
    assert registry.list_documents(track=CareerTrack.SWE) == [swe, both]
    assert registry.list_documents(track=CareerTrack.MLE) == [mle, both]
    assert registry.list_documents(track=CareerTrack.AI_ENGINEER) == []


def test_create_snapshot_pins_sorted_membership(registry: CorpusRegistry) -> None:
    a, a_text = _doc("https://example.com/a", text="Alpha body.")
    b, b_text = _doc("https://example.com/b", text="Beta body.")
    registry.register(a, text=a_text)
    registry.register(b, text=b_text)

    snapshot = registry.create_snapshot(
        [b.doc_id, a.doc_id], created_at=_CREATED_AT, chunking_params=_PARAMS
    )

    assert snapshot.doc_ids == sorted([a.doc_id, b.doc_id])
    assert snapshot.content_hashes == [
        registry.get_document(doc_id).content_hash  # type: ignore[union-attr]
        for doc_id in snapshot.doc_ids
    ]
    assert snapshot.snapshot_id == derive_snapshot_id(
        [a.content_hash, b.content_hash], _PARAMS
    )
    assert registry.get_snapshot(snapshot.snapshot_id) == snapshot
    assert registry.list_snapshots() == [snapshot]


def test_same_membership_any_order_returns_existing_snapshot(
    registry: CorpusRegistry,
) -> None:
    a, a_text = _doc("https://example.com/a", text="Alpha body.")
    b, b_text = _doc("https://example.com/b", text="Beta body.")
    registry.register(a, text=a_text)
    registry.register(b, text=b_text)

    first = registry.create_snapshot(
        [a.doc_id, b.doc_id], created_at=_CREATED_AT, chunking_params=_PARAMS
    )
    later = datetime(2026, 7, 7, 9, 0, tzinfo=UTC)
    second = registry.create_snapshot(
        [b.doc_id, a.doc_id], created_at=later, chunking_params=_PARAMS
    )

    # Identity is the membership; the original created_at is preserved.
    assert second == first
    assert len(registry.list_snapshots()) == 1


def test_different_chunking_params_pin_a_new_snapshot(
    registry: CorpusRegistry,
) -> None:
    a, a_text = _doc("https://example.com/a", text="Alpha body.")
    registry.register(a, text=a_text)
    other = ChunkingParams(algorithm="structure_v1", target_chars=800, overlap_chars=100)

    first = registry.create_snapshot(
        [a.doc_id], created_at=_CREATED_AT, chunking_params=_PARAMS
    )
    second = registry.create_snapshot(
        [a.doc_id], created_at=_CREATED_AT, chunking_params=other
    )

    # Re-chunking is a new snapshot, never an in-place change.
    assert first.snapshot_id != second.snapshot_id
    assert first.chunking_params == _PARAMS
    assert second.chunking_params == other
    assert registry.list_snapshots() == [first, second]


def test_create_snapshot_canonicalizes_duplicate_ids(
    registry: CorpusRegistry,
) -> None:
    a, a_text = _doc("https://example.com/a", text="Alpha body.")
    registry.register(a, text=a_text)
    snapshot = registry.create_snapshot(
        [a.doc_id, a.doc_id], created_at=_CREATED_AT, chunking_params=_PARAMS
    )
    assert snapshot.doc_ids == [a.doc_id]


def test_create_snapshot_rejects_unknown_documents(registry: CorpusRegistry) -> None:
    a, a_text = _doc("https://example.com/a", text="Alpha body.")
    registry.register(a, text=a_text)
    with pytest.raises(UnknownCorpusDocumentError) as exc_info:
        registry.create_snapshot(
            [a.doc_id, "doc_0000000000000000"],
            created_at=_CREATED_AT,
            chunking_params=_PARAMS,
        )
    assert exc_info.value.doc_ids == ["doc_0000000000000000"]
    assert registry.list_snapshots() == []


def test_create_snapshot_rejects_empty_membership(registry: CorpusRegistry) -> None:
    with pytest.raises(EmptySnapshotError):
        registry.create_snapshot([], created_at=_CREATED_AT, chunking_params=_PARAMS)


def test_stored_models_are_frozen(registry: CorpusRegistry) -> None:
    document, text = _doc("https://example.com/a", text="Alpha body.")
    registry.register(document, text=text)
    snapshot = registry.create_snapshot(
        [document.doc_id], created_at=_CREATED_AT, chunking_params=_PARAMS
    )
    with pytest.raises(ValidationError):
        snapshot.snapshot_id = "snap_ffffffffffffffff"  # type: ignore[misc]
    stored = registry.get_document(document.doc_id)
    assert stored is not None
    with pytest.raises(ValidationError):
        stored.title = "Mutated"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Restart survival (SQLite-only by nature): state written before a process
# exit must be fully recovered by a fresh registry instance on the same file.
# --------------------------------------------------------------------------- #


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "corpus.db"
    db = SqliteDatabase(db_path)
    first = SqliteCorpusRegistry(db)
    a, a_text = _doc("https://example.com/a", text="Alpha body.")
    b, b_text = _doc("https://example.com/b", text="Beta body.")
    first.register(a, text=a_text)
    first.register(b, text=b_text)
    snapshot = first.create_snapshot(
        [a.doc_id, b.doc_id], created_at=_CREATED_AT, chunking_params=_PARAMS
    )
    db.close()

    reopened = SqliteCorpusRegistry(SqliteDatabase(db_path))
    assert reopened.list_documents() == [a, b]
    assert reopened.get_text(a.doc_id) == a_text
    assert reopened.get_snapshot(snapshot.snapshot_id) == snapshot
    assert reopened.list_snapshots() == [snapshot]
