"""Contract + store tests for prose attachments (UX pass B5).

Fixture-driven contract checks (the ``test_call_log.py`` pattern) plus one
shared behavior suite parametrized over the in-memory and SQLite twins, so
both stores prove the same invariants: append-only identity, per-run/per-user
reads in insertion order, latest-by-kind lookup, and user-scoped deletion
(prose is derived personal data — spec privacy rule).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.llm_nodes.prose_attachment import (
    InMemoryProseAttachmentStore,
    ProseAttachmentAlreadyExistsError,
    ProseAttachmentKind,
    ProseAttachmentRecord,
    ProseAttachmentStore,
)
from agentic_calendar.llm_nodes.sqlite_prose_store import SqliteProseAttachmentStore
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "prose_attachment"
_NOW = datetime(2026, 7, 4, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    record = ProseAttachmentRecord.model_validate(payload)
    assert record.prose_attachment_id == payload["prose_attachment_id"]


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        ProseAttachmentRecord.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg


def _record(
    attachment_id: str,
    *,
    run_id: str = "run_1",
    user_id: str = "user_1",
    kind: ProseAttachmentKind = ProseAttachmentKind.REFLECTION,
    summary: str = "Practice tasks are taking longer than planned.",
) -> ProseAttachmentRecord:
    return ProseAttachmentRecord(
        prose_attachment_id=attachment_id,
        user_id=user_id,
        run_id=run_id,
        plan_version="v1",
        kind=kind,
        summary=summary,
        detail=("One supporting line.",),
        reason_code=ReasonCode.DRIFT_DURATION_UNDERESTIMATE,
        created_at=_NOW,
    )


def _in_memory(_tmp: Path) -> ProseAttachmentStore:
    return InMemoryProseAttachmentStore()


def _sqlite(tmp: Path) -> ProseAttachmentStore:
    return SqliteProseAttachmentStore(SqliteDatabase(tmp / "prose.db"))


@pytest.fixture(params=[_in_memory, _sqlite], ids=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> ProseAttachmentStore:
    return request.param(tmp_path)  # type: ignore[no-any-return]


def test_append_only_rejects_duplicate_id(store: ProseAttachmentStore) -> None:
    store.append(_record("p1"))
    with pytest.raises(ProseAttachmentAlreadyExistsError):
        store.append(_record("p1"))


def test_reads_scope_and_preserve_insertion_order(store: ProseAttachmentStore) -> None:
    store.append(_record("p1", run_id="run_1"))
    store.append(_record("p2", run_id="run_2", kind=ProseAttachmentKind.EXPLANATION))
    store.append(_record("p3", run_id="run_1", user_id="user_2"))

    assert [r.prose_attachment_id for r in store.list_for_run("run_1")] == ["p1", "p3"]
    assert [r.prose_attachment_id for r in store.list_for_user("user_1")] == ["p1", "p2"]


def test_latest_for_run_picks_newest_of_kind(store: ProseAttachmentStore) -> None:
    store.append(_record("p1", kind=ProseAttachmentKind.REFLECTION, summary="First."))
    store.append(_record("p2", kind=ProseAttachmentKind.REFLECTION, summary="Second."))
    store.append(_record("p3", kind=ProseAttachmentKind.EXPLANATION, summary="Expl."))

    latest = store.latest_for_run("run_1", kind=ProseAttachmentKind.REFLECTION)
    assert latest is not None and latest.summary == "Second."
    assert store.latest_for_run("run_x", kind=ProseAttachmentKind.REFLECTION) is None


def test_delete_for_user_erases_only_that_user(store: ProseAttachmentStore) -> None:
    store.append(_record("p1"))
    store.append(_record("p2", user_id="user_2"))

    assert store.delete_for_user("user_1") == 1
    assert store.list_for_user("user_1") == []
    assert [r.prose_attachment_id for r in store.list_for_user("user_2")] == ["p2"]


def test_sqlite_round_trip_survives_reopen(tmp_path: Path) -> None:
    first = SqliteProseAttachmentStore(SqliteDatabase(tmp_path / "p.db"))
    first.append(_record("p1"))
    reopened = SqliteProseAttachmentStore(SqliteDatabase(tmp_path / "p.db"))
    records = reopened.list_for_run("run_1")
    assert len(records) == 1
    assert records[0].summary == "Practice tasks are taking longer than planned."
    assert records[0].kind is ProseAttachmentKind.REFLECTION
